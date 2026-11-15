import numpy as np
import pandas as pd
import pytest

from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor


def test_preprocessor_cleans_scales_and_excludes_labels_and_identifiers():
    data = pd.DataFrame(
        {
            "Time": [1.0, np.nan, 3.0],
            "Amount": [10.0, np.inf, 30.0],
            "V1": [2.0, np.nan, 6.0],
            "Class": [0, 1, 1],
            "id_transacao": [101, 102, 103],
            "empty": [np.nan, np.nan, np.nan],
        }
    )

    processor = Preprocessor()
    prepared = processor.fit_transform(data)

    assert processor.feature_names == ("Time", "Amount", "V1")
    assert prepared.shape == (3, 3)
    assert prepared.flags.c_contiguous
    assert np.isfinite(prepared).all()
    assert prepared[:, 0].mean() == pytest.approx(0.0)
    assert prepared[:, 1].mean() == pytest.approx(0.0)


def test_preprocessor_rejects_label_as_explicit_feature():
    data = pd.DataFrame({"Amount": [1.0, 2.0], "Class": [0, 1]})

    with pytest.raises(ValueError, match="não podem ser features"):
        Preprocessor(features=["Amount", "Class"]).fit(data)


def test_preprocessor_rejects_missing_features_at_transform_time():
    processor = Preprocessor().fit(
        pd.DataFrame({"Amount": [1.0, 2.0], "V1": [3.0, 4.0]})
    )

    with pytest.raises(ValueError, match="Colunas selecionadas ausentes"):
        processor.transform(pd.DataFrame({"Amount": [5.0]}))


def test_preprocessor_rejects_empty_input():
    with pytest.raises(ValueError, match="não contém transações"):
        Preprocessor().fit(pd.DataFrame())
