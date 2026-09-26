import csv
import hashlib
import io
import json
import re
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, Iterator, TextIO


class DatasetCsvError(ValueError):
    pass


class DatasetTooLargeError(ValueError):
    pass


class ParsedTransaction:
    __slots__ = ("indice_origem", "valor", "tempo_relativo", "atributos", "rotulo_real")

    def __init__(
        self,
        indice_origem: int,
        valor: Decimal,
        tempo_relativo: Decimal,
        atributos: dict[str, float],
        rotulo_real: bool | None,
    ):
        self.indice_origem = indice_origem
        self.valor = valor
        self.tempo_relativo = tempo_relativo
        self.atributos = atributos
        self.rotulo_real = rotulo_real


_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


class DatasetCsvReader:
    REQUIRED_COLUMNS = {"time", "amount"}
    LABEL_COLUMNS = ("class", "label", "rotulo", "rotulo_real")
    _AMOUNT_LIMIT = 1000000000000.0
    _TIME_LIMIT = 10000000000.0

    def __init__(self, source: bytes | Path):
        if isinstance(source, bytes):
            if not source:
                raise DatasetCsvError("O arquivo CSV está vazio")
            self._path: Path | None = None
            self._bytes: bytes | None = source
            sample = source[:8192]
        else:
            self._path = source
            self._bytes = None
            sample = self._read_sample(source)

        delimiter = self._sniff_delimiter(sample)
        with self._open_text() as stream:
            reader = csv.reader(stream, delimiter=delimiter, strict=True)
            try:
                headers = tuple(header.strip() for header in next(reader))
            except StopIteration as error:
                raise DatasetCsvError("O arquivo CSV não contém cabeçalho") from error
            except csv.Error as error:
                raise DatasetCsvError(f"Cabeçalho CSV inválido: {error}") from error
            except UnicodeDecodeError as error:
                raise DatasetCsvError("O arquivo deve usar codificação UTF-8") from error

        self._validate_headers(headers)
        normalized_headers = tuple(header.casefold() for header in headers)
        self.colunas = headers
        self._delimiter = delimiter
        self._positions = {name: index for index, name in enumerate(normalized_headers)}
        missing = self.REQUIRED_COLUMNS.difference(self._positions)
        if missing:
            raise DatasetCsvError("As colunas obrigatórias são Time e Amount")

        matching_labels = [name for name in self.LABEL_COLUMNS if name in self._positions]
        if len(matching_labels) > 1:
            raise DatasetCsvError("O arquivo deve conter no máximo uma coluna de rótulo")
        self._label_name = matching_labels[0] if matching_labels else None
        self.possui_rotulo = self._label_name is not None
        self._time_position = self._positions["time"]
        self._amount_position = self._positions["amount"]
        self._label_position = self._positions[self._label_name] if self._label_name else None
        reserved = {self._time_position, self._amount_position}
        if self._label_position is not None:
            reserved.add(self._label_position)
        self._feature_indexes = tuple(index for index in range(len(headers)) if index not in reserved)
        self._feature_names = tuple(headers[index] for index in self._feature_indexes)

    @staticmethod
    def _read_sample(path: Path) -> bytes:
        with path.open("rb") as handle:
            sample = handle.read(8192)
        if not sample:
            raise DatasetCsvError("O arquivo CSV está vazio")
        return sample

    @staticmethod
    def _sniff_delimiter(sample: bytes) -> str:
        try:
            text = sample.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DatasetCsvError("O arquivo deve usar codificação UTF-8") from error
        try:
            return csv.Sniffer().sniff(text, delimiters=",;\t").delimiter
        except csv.Error:
            return ","

    def _open_text(self) -> TextIO:
        if self._path is not None:
            return self._path.open("r", encoding="utf-8-sig", newline="")
        assert self._bytes is not None
        try:
            return io.StringIO(self._bytes.decode("utf-8-sig"), newline="")
        except UnicodeDecodeError as error:
            raise DatasetCsvError("O arquivo deve usar codificação UTF-8") from error

    @staticmethod
    def _validate_headers(headers: tuple[str, ...]) -> None:
        if not headers or any(not header for header in headers):
            raise DatasetCsvError("Todas as colunas precisam ter um nome")
        if len(headers) > 32767:
            raise DatasetCsvError("O arquivo excede o limite de colunas aceito")
        normalized = tuple(header.casefold() for header in headers)
        if len(set(normalized)) != len(normalized):
            raise DatasetCsvError("O arquivo possui nomes de coluna duplicados")

    def iter_transactions(self) -> Iterator[ParsedTransaction]:
        for indice, valor, tempo, atributos_json, rotulo in self._iter_validated_rows():
            yield ParsedTransaction(
                indice_origem=indice,
                valor=Decimal(valor),
                tempo_relativo=Decimal(tempo),
                atributos=json.loads(atributos_json) if atributos_json != "{}" else {},
                rotulo_real=rotulo,
            )

    def iter_copy_text(self, dataset_id: int) -> Iterator[bytes]:
        prefix = f"{dataset_id}\t".encode("utf-8")
        for indice, valor, tempo, atributos_json, rotulo in self._iter_validated_rows():
            if rotulo is None:
                label_str = "\\N"
            else:
                label_str = "t" if rotulo else "f"
            line = f"{indice}\t{valor}\t{tempo}\t{atributos_json}\t{label_str}\n".encode("utf-8")
            yield prefix + line

    def _iter_validated_rows(self) -> Iterator[tuple[int, str, str, str, bool | None]]:
        time_position = self._time_position
        amount_position = self._amount_position
        label_position = self._label_position
        feature_indexes = self._feature_indexes
        feature_names = self._feature_names
        column_count = len(self.colunas)
        transaction_index = 0

        try:
            with self._open_text() as stream:
                reader = csv.reader(stream, delimiter=self._delimiter, strict=True)
                next(reader, None)
                for row in reader:
                    row_number = reader.line_num
                    if not row:
                        continue
                    if len(row) != column_count:
                        raise DatasetCsvError(
                            f"Linha {row_number}: esperadas {column_count} colunas, recebidas {len(row)}"
                        )

                    amount_text = self._validate_numeric(
                        row[amount_position].strip(), row_number, self.colunas[amount_position], 2, self._AMOUNT_LIMIT
                    )
                    time_text = self._validate_numeric(
                        row[time_position].strip(), row_number, self.colunas[time_position], 4, self._TIME_LIMIT
                    )

                    label: bool | None = None
                    if label_position is not None:
                        label_text = row[label_position].strip()
                        if not label_text:
                            raise DatasetCsvError(f"Linha {row_number}, coluna '{self.colunas[label_position]}': valor vazio")
                        if label_text not in ("0", "1", "0.0", "1.0"):
                            try:
                                label_float = float(label_text)
                                if label_float not in (0.0, 1.0):
                                    raise ValueError()
                                label = bool(label_float)
                            except ValueError:
                                raise DatasetCsvError(
                                    f"Linha {row_number}, coluna '{self.colunas[label_position]}': rótulo deve ser 0 ou 1"
                                )
                        else:
                            label = label_text in ("1", "1.0")

                    if not feature_indexes:
                        atributos_json = "{}"
                    else:
                        features = {}
                        for key, idx in zip(feature_names, feature_indexes):
                            val_str = row[idx].strip()
                            if not val_str:
                                raise DatasetCsvError(f"Linha {row_number}, coluna '{key}': valor vazio")
                            try:
                                features[key] = float(val_str)
                            except ValueError:
                                raise DatasetCsvError(f"Linha {row_number}, coluna '{key}': valor numérico inválido")
                        try:
                            # allow_nan=False ensures no NaN/Inf is passed to JSON
                            atributos_json = json.dumps(features, allow_nan=False, separators=(',', ':'))
                        except ValueError:
                            raise DatasetCsvError(f"Linha {row_number}: valor numérico fora do limite (NaN ou Inf)")

                    yield transaction_index, amount_text, time_text, atributos_json, label
                    transaction_index += 1
        except UnicodeDecodeError as error:
            raise DatasetCsvError("O arquivo deve usar codificação UTF-8") from error
        except csv.Error as error:
            raise DatasetCsvError(f"Conteúdo CSV inválido: {error}") from error

    def _validate_numeric(
        self,
        value_text: str,
        row_number: int,
        column_name: str,
        max_decimals: int,
        limit: float,
    ) -> str:
        if not value_text:
            raise DatasetCsvError(f"Linha {row_number}, coluna '{column_name}': valor vazio")
        try:
            val_float = float(value_text)
        except ValueError:
            raise DatasetCsvError(f"Linha {row_number}, coluna '{column_name}': valor numérico inválido")
            
        if not math.isfinite(val_float):
            raise DatasetCsvError(f"Linha {row_number}, coluna '{column_name}': valor precisa ser finito")
            
        if abs(val_float) >= limit:
            raise DatasetCsvError(f"Linha {row_number}: {column_name} excede o limite aceito")
            
        parts = value_text.split('.')
        if len(parts) == 2:
            frac = parts[1]
            if 'e' in frac or 'E' in frac:
                try:
                    d = Decimal(value_text)
                    if d.quantize(Decimal(f"1e-{max_decimals}")) != d:
                        raise DatasetCsvError(f"Linha {row_number}: {column_name} aceita no máximo {max_decimals} casas decimais")
                except InvalidOperation:
                    raise DatasetCsvError(f"Linha {row_number}, coluna '{column_name}': valor numérico inválido")
            elif len(frac) > max_decimals:
                raise DatasetCsvError(f"Linha {row_number}: {column_name} aceita no máximo {max_decimals} casas decimais")
                
        return value_text


def stream_upload_to_file(
    source: BinaryIO,
    destination: Path,
    max_bytes: int,
    chunk_bytes: int,
) -> tuple[str, int]:
    hasher = hashlib.sha256()
    written = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = source.read(chunk_bytes)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise DatasetTooLargeError("Arquivo excede o limite de upload")
            hasher.update(chunk)
            handle.write(chunk)
    if written == 0:
        raise DatasetCsvError("O arquivo CSV está vazio")
    return hasher.hexdigest(), written
