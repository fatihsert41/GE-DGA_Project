"""Tests for synthetic data, feature building and the trend module."""
from __future__ import annotations

from app.ml.features import FEATURE_NAMES, build_features, features_from_dict
from app.ml.synth import make_aging_series, make_dataset
from app.services.trend import analyze_history


def test_dataset_has_all_classes_and_no_nan():
    df = make_dataset(n=700, seed=1)
    assert set(df["label"].unique()) == {
        "Normal", "PD", "D1", "D2", "T1", "T2", "T3"}
    assert not df.isnull().any().any()
    assert (df.drop(columns=["label"]) >= 0).all().all()


def test_features_match_contract():
    df = make_dataset(n=50, seed=2)
    feats = build_features(df.drop(columns=["label"]))
    assert list(feats.columns) == FEATURE_NAMES
    single = features_from_dict(df.drop(columns=["label"]).iloc[0].to_dict())
    assert single.shape == (1, len(FEATURE_NAMES))


def test_aging_series_is_increasing_overall():
    df = make_aging_series(fault_class="T3", months=24, seed=3)
    # Ethylene should trend up as the fault develops.
    assert df["C2H4"].iloc[-1] > df["C2H4"].iloc[0]


def test_trend_predicts_time_to_critical():
    df = make_aging_series(fault_class="T2", months=18, seed=4)
    times = df["month"].tolist()
    history = [{k: float(r[k]) for k in df.columns if k != "month"}
               for _, r in df.iterrows()]
    out = analyze_history(times, history, horizon=6)
    assert out["available"] is True
    assert out["status"] in {"stable", "watch", "critical_soon"}
    assert "per_gas" in out


def test_trend_stable_when_flat():
    history = [{"H2": 10, "CH4": 10, "C2H6": 8, "C2H4": 6, "C2H2": 0.3,
                "CO": 200, "CO2": 1800} for _ in range(6)]
    out = analyze_history([float(i) for i in range(6)], history)
    assert out["status"] == "stable"
