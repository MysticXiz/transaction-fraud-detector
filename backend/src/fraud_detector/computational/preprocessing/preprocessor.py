from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


class Preprocessor:
    """Prepara atributos numéricos sem incluir rótulos ou identificadores."""

    LABEL_COLUMNS = {
        "class",
        "label",
        "rotulo",
        "rotulo_real",
        "fraud",
        "is_fraud",
    }
    IDENTIFIER_COLUMNS = {
        "id",
        "id_dataset",
        "id_transacao",
        "indice_origem",
        "index",
        "transaction_id",
    }
    SCALED_COLUMNS = {"amount", "time", "valor", "tempo_relativo"}

    def __init__(self, features: Sequence[str] | None = None):
        self._requested_features = tuple(features) if features is not None else None
        self.feature_names: tuple[str, ...] = ()
        self._imputer: SimpleImputer | None = None
        self._scaler: StandardScaler | None = None
        self._scaled_positions: tuple[int, ...] = ()

    def fit(self, data: pd.DataFrame) -> Preprocessor:
        if data.empty:
            raise ValueError("O conjunto de dados não contém transações")
        if not data.columns.is_unique:
            raise ValueError("O conjunto de dados possui nomes de coluna duplicados")

        self.feature_names = self._select_features(data)
        values = self._numeric_values(data, self.feature_names)
        self._imputer = SimpleImputer(strategy="median")
        imputed = self._imputer.fit_transform(values)

        self._scaled_positions = tuple(
            position
            for position, name in enumerate(self.feature_names)
            if name.casefold() in self.SCALED_COLUMNS
        )
        if self._scaled_positions:
            self._scaler = StandardScaler()
            self._scaler.fit(imputed[:, self._scaled_positions])
        else:
            self._scaler = None
        return self

    def transform(self, data: pd.DataFrame) -> np.ndarray:
        if self._imputer is None:
            raise RuntimeError("O pré-processador precisa ser ajustado antes do uso")
        missing = set(self.feature_names).difference(data.columns)
        if missing:
            raise ValueError(
                "Colunas selecionadas ausentes: " + ", ".join(sorted(missing))
            )

        values = self._numeric_values(data, self.feature_names)
        prepared = self._imputer.transform(values)
        if self._scaler is not None:
            positions = list(self._scaled_positions)
            prepared[:, positions] = self._scaler.transform(prepared[:, positions])
        return np.ascontiguousarray(prepared, dtype=np.float64)

    def fit_transform(self, data: pd.DataFrame) -> np.ndarray:
        return self.fit(data).transform(data)

    def _select_features(self, data: pd.DataFrame) -> tuple[str, ...]:
        if self._requested_features is not None:
            if not self._requested_features:
                raise ValueError("Selecione ao menos uma feature")
            if len(set(self._requested_features)) != len(self._requested_features):
                raise ValueError("A seleção contém features duplicadas")
            missing = set(self._requested_features).difference(data.columns)
            if missing:
                raise ValueError(
                    "Features não encontradas: " + ", ".join(sorted(missing))
                )
            excluded = [
                name for name in self._requested_features if self._is_excluded(name)
            ]
            if excluded:
                raise ValueError(
                    "Rótulos e identificadores não podem ser features: "
                    + ", ".join(excluded)
                )
            candidates = self._requested_features
        else:
            candidates = tuple(
                name for name in data.columns if not self._is_excluded(name)
            )

        usable = tuple(
            name
            for name in candidates
            if self._numeric_values(data, (name,)).notna().any(axis=None)
        )
        if not usable:
            raise ValueError("Nenhuma feature numérica utilizável foi encontrada")
        return usable

    @classmethod
    def _is_excluded(cls, name: str) -> bool:
        normalized = name.strip().casefold()
        return (
            normalized in cls.LABEL_COLUMNS
            or normalized in cls.IDENTIFIER_COLUMNS
            or normalized.startswith("id_")
        )

    @staticmethod
    def _numeric_values(data: pd.DataFrame, features: Sequence[str]) -> pd.DataFrame:
        numeric = data.loc[:, list(features)].apply(pd.to_numeric, errors="coerce")
        return numeric.replace([np.inf, -np.inf], np.nan)
