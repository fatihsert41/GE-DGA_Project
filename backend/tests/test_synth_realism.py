"""Sentetik üretecin gerçekçilik katmanı (Faz 6.7)."""
from __future__ import annotations

from app.core.gases import FAULT_CLASSES, GASES
from app.ml.synth import (PRESET_FIELD_LIKE, make_dataset,
                          make_field_like_dataset)

_G5 = ["H2", "CH4", "C2H6", "C2H4", "C2H2"]


def _cv(df, label):
    """Sınıf içi değişim katsayısı: std / ortalama."""
    tot = df[df["label"] == label][_G5].sum(axis=1)
    return float(tot.std() / tot.mean())


def test_realism_zero_is_backward_compatible():
    """Varsayılan davranış değişmemeli: eski model ve testler buna bağlı."""
    a = make_dataset(n=300, seed=5)
    b = make_dataset(n=300, seed=5, realism=0.0)
    assert a.equals(b)


def test_realism_widens_within_class_spread():
    """Gerçek veride sınıf içi CV 1.7-4.9; temel üreteçte 0.24-0.46 idi."""
    base = make_dataset(n=2000, seed=3, realism=0.0)
    rich = make_dataset(n=2000, seed=3, realism=1.0)
    assert _cv(rich, "D2") > 2 * _cv(base, "D2")


def test_components_are_independently_controllable():
    """Her bileşen ayrı ayarlanabilmeli — ablasyon bunun üstüne kurulu."""
    only_noise = make_dataset(n=400, seed=4, realism=0.0, noise=1.0)
    plain = make_dataset(n=400, seed=4, realism=0.0)
    # Gürültü değerleri değiştirir ama etiket dağılımını bozmaz.
    assert not only_noise[_G5].equals(plain[_G5])
    assert only_noise["label"].tolist() == plain["label"].tolist()


def test_severity_does_not_touch_normal_class():
    """Sağlıklı trafonun 'şiddeti' olmaz; ölçekleme etiketi bozardı."""
    a = make_dataset(n=800, seed=6, realism=0.0)
    b = make_dataset(n=800, seed=6, realism=0.0, severity=1.0)
    an = a[a["label"] == "Normal"][_G5].sum(axis=1)
    bn = b[b["label"] == "Normal"][_G5].sum(axis=1)
    # Normal sınıfın yayılımı şiddetten etkilenmemeli.
    assert abs(an.std() / an.mean() - bn.std() / bn.mean()) < 0.15


def test_field_like_preset_is_valid_and_complete():
    df = make_field_like_dataset(n=500, seed=8)
    assert list(df.columns) == [*GASES, "label"]
    assert set(df["label"]) <= set(FAULT_CLASSES)
    assert not df.isnull().any().any()
    assert (df[GASES] >= 0).all().all()
    # Ön ayar ölçülerek seçildi: zarar veren bileşenler kapalı olmalı.
    assert PRESET_FIELD_LIKE["severity"] == 0.0
    assert PRESET_FIELD_LIKE["mixed"] == 0.0
    assert PRESET_FIELD_LIKE["incipient"] > 0
