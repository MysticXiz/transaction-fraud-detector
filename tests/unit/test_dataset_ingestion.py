import hashlib
import io
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from src.fraud_detector.application.use_cases.manage_datasets import (
    GerenciarDatasetsUseCase,
    ImportarDatasetUseCase,
)
from src.fraud_detector.computational.ingestion.dataset_csv import (
    DatasetCsvError,
    DatasetCsvReader,
    DatasetTooLargeError,
    _format_copy_line,
    stream_upload_to_file,
)
from src.fraud_detector.infrastructure.models.dataset import DatasetModel
from src.fraud_detector.infrastructure.repositories.dataset_repository import (
    IngestionLoadStats,
    RepositorioDataset,
)


class DatasetCsvReaderTests(unittest.TestCase):
    def test_reads_credit_card_columns_and_optional_label(self):
        parser = DatasetCsvReader(b"Time,V1,Amount,Class\n1.5,0.25,12.34,1\n")
        rows = list(parser.iter_transactions())

        self.assertEqual(parser.colunas, ("Time", "V1", "Amount", "Class"))
        self.assertTrue(parser.possui_rotulo)
        self.assertEqual(rows[0].indice_origem, 0)
        self.assertEqual(str(rows[0].valor), "12.34")
        self.assertEqual(rows[0].atributos, {"V1": 0.25})
        self.assertTrue(rows[0].rotulo_real)

    def test_reads_semicolon_csv_without_label(self):
        parser = DatasetCsvReader(b"Time;Amount;Feature\n2;3.50;-0.75\n")
        row = next(parser.iter_transactions())

        self.assertFalse(parser.possui_rotulo)
        self.assertEqual(row.atributos, {"Feature": -0.75})
        self.assertIsNone(row.rotulo_real)

    def test_rejects_missing_required_column(self):
        with self.assertRaisesRegex(DatasetCsvError, "Time e Amount"):
            DatasetCsvReader(b"Amount,Class\n12.34,0\n")

    def test_rejects_non_numeric_feature(self):
        parser = DatasetCsvReader(b"Time,Amount,Merchant\n1,2,loja\n")
        with self.assertRaisesRegex(DatasetCsvError, "valor numérico inválido"):
            list(parser.iter_transactions())

    def test_rejects_non_binary_label(self):
        parser = DatasetCsvReader(b"Time,Amount,Class\n1,2,3\n")
        with self.assertRaisesRegex(DatasetCsvError, "rótulo deve ser 0 ou 1"):
            list(parser.iter_transactions())

    def test_rejects_duplicate_or_multiple_label_columns(self):
        with self.assertRaisesRegex(DatasetCsvError, "duplicados"):
            DatasetCsvReader(b"Time,Amount,time\n1,2,1\n")
        with self.assertRaisesRegex(DatasetCsvError, "no máximo uma coluna de rótulo"):
            DatasetCsvReader(b"Time,Amount,Class,Label\n1,2,0,0\n")

    def test_rejects_amount_precision_that_database_would_round(self):
        parser = DatasetCsvReader(b"Time,Amount\n1,2.345\n")
        with self.assertRaisesRegex(DatasetCsvError, "Amount aceita no máximo 2 casas"):
            list(parser.iter_transactions())

    def test_rejects_inconsistent_row_width(self):
        parser = DatasetCsvReader(b"Time,Amount\n1,2,3\n")
        with self.assertRaisesRegex(DatasetCsvError, "esperadas 2 colunas"):
            list(parser.iter_transactions())

    def test_rejects_empty_file(self):
        with self.assertRaisesRegex(DatasetCsvError, "vazio"):
            DatasetCsvReader(b"")

    def test_rejects_invalid_encoding(self):
        with self.assertRaisesRegex(DatasetCsvError, "UTF-8"):
            DatasetCsvReader(b"Time,Amount\n\xff\xfe,1\n")

    def test_streams_from_path_without_keeping_bytes(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as handle:
            handle.write(b"Time,Amount\n" + b"1,2.50\n" * 2000)
            path = Path(handle.name)
        try:
            parser = DatasetCsvReader(path)
            self.assertIsNone(parser._bytes)
            self.assertEqual(sum(1 for _ in parser.iter_transactions()), 2000)
        finally:
            path.unlink(missing_ok=True)

    def test_copy_text_keeps_json_and_null_label(self):
        parser = DatasetCsvReader(b"Time,V1,Amount\n1.5,0.25,12.34\n")
        line = next(parser.iter_copy_text(42))
        self.assertEqual(line, _format_copy_line(42, 0, "12.34", "1.5", '{"V1":0.25}', None))
        self.assertIn(b"\\N", line)


class StreamUploadTests(unittest.TestCase):
    def test_hashes_in_chunks_and_rejects_oversize(self):
        content = b"Time,Amount\n1,2\n"
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "out.csv"
            digest, size = stream_upload_to_file(io.BytesIO(content), destination, 100, 4)
            self.assertEqual(size, len(content))
            self.assertEqual(digest, hashlib.sha256(content).hexdigest())
            self.assertEqual(destination.read_bytes(), content)

            with self.assertRaises(DatasetTooLargeError):
                stream_upload_to_file(io.BytesIO(content), destination, 5, 4)


class FakeRepository:
    def __init__(self, existing_hash=None):
        self.dataset = None
        self.datasets: list = []
        self.transactions = None
        self.existing_hash = existing_hash
        self.deleted = None
        self.lock = threading.Lock()

    def get_by_hash(self, file_hash):
        if self.existing_hash == file_hash:
            return object()
        for dataset in self.datasets:
            if dataset.hash_arquivo == file_hash:
                return dataset
        if self.dataset is not None and self.dataset.hash_arquivo == file_hash:
            return self.dataset
        return None

    def create_with_copy(self, dataset, parser, **kwargs):
        with self.lock:
            if self.get_by_hash(dataset.hash_arquivo) is not None:
                raise FileExistsError("Este arquivo já foi importado")
            dataset.id_dataset = len(self.datasets) + 1
            self.dataset = dataset
            self.datasets.append(dataset)
            self.transactions = list(parser.iter_transactions())
            dataset.total_registros = len(self.transactions)
            return dataset, IngestionLoadStats(len(self.transactions), 0.0, 0.0, 0.0)

    def get_by_id(self, dataset_id, owner_id):
        for dataset in self.datasets:
            if dataset.id_dataset == dataset_id and dataset.id_usuario == owner_id:
                return dataset
        if self.dataset and self.dataset.id_dataset == dataset_id and self.dataset.id_usuario == owner_id:
            return self.dataset
        return None

    def delete_owned(self, dataset_id, owner_id):
        dataset = self.get_by_id(dataset_id, owner_id)
        if dataset is None:
            return None
        self.deleted = dataset
        self.datasets = [item for item in self.datasets if item is not dataset]
        self.dataset = None
        return dataset.caminho_arquivo


class ImportarDatasetUseCaseTests(unittest.TestCase):
    def test_saves_hash_metadata_and_csv_artifact(self):
        content = b"Time,Amount,Class\n1,2.50,0\n"
        repository = FakeRepository()
        with tempfile.TemporaryDirectory() as directory:
            dataset = ImportarDatasetUseCase(
                repository, Path(directory), max_upload_bytes=1024
            ).execute(io.BytesIO(content), "input.csv", 7, "Sample", None, "synthetic")
            artifact_path = Path(dataset.caminho_arquivo)

            self.assertEqual(dataset.hash_arquivo, hashlib.sha256(content).hexdigest())
            self.assertEqual(artifact_path.read_bytes(), content)
            self.assertEqual(dataset.id_usuario, 7)
            self.assertEqual(dataset.total_colunas, 3)
            self.assertEqual(repository.transactions[0].rotulo_real, False)

    def test_invalid_csv_does_not_leave_artifact(self):
        repository = FakeRepository()
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            with self.assertRaises(DatasetCsvError):
                ImportarDatasetUseCase(repository, storage, max_upload_bytes=1024).execute(
                    io.BytesIO(b"Amount,Class\n1,0\n"), "bad.csv", 1, "Bad", None, "x"
                )
            self.assertFalse(list(storage.glob("*")))

    def test_rejects_duplicate_hash(self):
        content = b"Time,Amount\n1,2.00\n"
        digest = hashlib.sha256(content).hexdigest()
        repository = FakeRepository(existing_hash=digest)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                ImportarDatasetUseCase(repository, Path(directory), max_upload_bytes=1024).execute(
                    io.BytesIO(content), "dup.csv", 1, "Dup", None, "x"
                )
            self.assertFalse(list(Path(directory).glob("*")))

    def test_copy_error_removes_artifact_and_does_not_keep_dataset(self):
        class FailingRepository(FakeRepository):
            def create_with_copy(self, dataset, parser, **kwargs):
                raise RuntimeError("erro durante COPY")

        with tempfile.TemporaryDirectory() as directory:
            repository = FailingRepository()
            with self.assertRaisesRegex(RuntimeError, "COPY"):
                ImportarDatasetUseCase(repository, Path(directory), max_upload_bytes=1024).execute(
                    io.BytesIO(b"Time,Amount\n1,2.00\n"), "x.csv", 1, "X", None, "x"
                )
            self.assertIsNone(repository.dataset)
            self.assertFalse(list(Path(directory).glob("*")))

    def test_concurrent_uploads_do_not_share_mutable_parser_state(self):
        content_a = b"Time,Amount\n1,2.00\n"
        content_b = b"Time,Amount,V1\n3,4.00,0.5\n"
        repository = FakeRepository()
        errors = []

        def run(payload, name):
            try:
                ImportarDatasetUseCase(repository, Path(directory), max_upload_bytes=1024).execute(
                    io.BytesIO(payload), name, 1, name, None, "x"
                )
            except Exception as error:
                errors.append(error)

        with tempfile.TemporaryDirectory() as directory:
            first = threading.Thread(target=run, args=(content_a, "a.csv"))
            second = threading.Thread(target=run, args=(content_b, "b.csv"))
            first.start()
            second.start()
            first.join()
            second.join()
            self.assertFalse(errors)
            self.assertEqual(len(list(Path(directory).glob("*.csv"))), 2)
            self.assertEqual(len(repository.datasets), 2)


class GerenciarDatasetsUseCaseTests(unittest.TestCase):
    def test_delete_empty_dataset_removes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            artifact = storage / "file.csv"
            artifact.write_text("Time,Amount\n", encoding="utf-8")
            repository = FakeRepository()
            repository.dataset = DatasetModel(
                id_usuario=3,
                nome="vazio",
                descricao=None,
                caminho_arquivo=str(artifact.resolve()),
                hash_arquivo="a" * 64,
                total_registros=0,
                total_colunas=2,
                origem="x",
                possui_rotulo=False,
            )
            repository.dataset.id_dataset = 11
            GerenciarDatasetsUseCase(repository, storage).delete(11, 3)
            self.assertFalse(artifact.exists())
            self.assertIsNone(repository.dataset)

    def test_delete_missing_or_foreign_dataset(self):
        repository = FakeRepository()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LookupError):
                GerenciarDatasetsUseCase(repository, Path(directory)).delete(99, 1)
            repository.dataset = DatasetModel(
                id_usuario=2,
                nome="outro",
                descricao=None,
                caminho_arquivo="x.csv",
                hash_arquivo="b" * 64,
                total_registros=1,
                total_colunas=2,
                origem="x",
                possui_rotulo=False,
            )
            repository.dataset.id_dataset = 5
            with self.assertRaises(LookupError):
                GerenciarDatasetsUseCase(repository, Path(directory)).delete(5, 1)


class RepositorioDatasetCopyTests(unittest.TestCase):
    def test_copy_rollback_when_driver_write_fails(self):
        writes = []

        class CopyCM:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def write(self, data):
                raise RuntimeError("erro durante COPY")

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def copy(self, statement):
                self.statement = statement
                return CopyCM()

        class Driver:
            def cursor(self):
                return Cursor()

        class ConnectionFairy:
            driver_connection = Driver()

        class SAConnection:
            connection = ConnectionFairy()

        session = MagicMock()
        session.connection.return_value = SAConnection()
        dataset = DatasetModel(
            id_usuario=1,
            nome="x",
            descricao=None,
            caminho_arquivo="x.csv",
            hash_arquivo="c" * 64,
            total_registros=0,
            total_colunas=2,
            origem="x",
            possui_rotulo=False,
        )

        def add(model):
            model.id_dataset = 8

        session.add.side_effect = add
        parser = DatasetCsvReader(b"Time,Amount\n1,2.00\n")
        with self.assertRaisesRegex(RuntimeError, "COPY"):
            RepositorioDataset(session).create_with_copy(dataset, parser)
        session.rollback.assert_called()
        session.commit.assert_not_called()
        self.assertEqual(writes, [])

    def test_delete_owned_uses_sql_returning(self):
        session = MagicMock()
        result = MagicMock()
        result.first.return_value = ("/tmp/file.csv",)
        session.execute.return_value = result
        path = RepositorioDataset(session).delete_owned(3, 9)
        self.assertEqual(path, "/tmp/file.csv")
        session.commit.assert_called_once()
        sql = str(session.execute.call_args.args[0])
        self.assertIn("DELETE FROM dataset", sql)
        self.assertIn("RETURNING caminho_arquivo", sql)


class ConcurrentHashCheckTests(unittest.TestCase):
    def test_second_upload_of_same_bytes_is_rejected(self):
        content = b"Time,Amount\n9,8.00\n"
        repository = FakeRepository()
        with tempfile.TemporaryDirectory() as directory:
            first = ImportarDatasetUseCase(repository, Path(directory), max_upload_bytes=1024)
            first.execute(io.BytesIO(content), "one.csv", 1, "One", None, "x")
            with self.assertRaises(FileExistsError):
                ImportarDatasetUseCase(repository, Path(directory), max_upload_bytes=1024).execute(
                    io.BytesIO(content), "two.csv", 1, "Two", None, "x"
                )


if __name__ == "__main__":
    unittest.main()
