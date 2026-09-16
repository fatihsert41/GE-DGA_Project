"""Güvenlik sertleştirme — imza anahtarı, belirteç yaşı, CORS.

.NET tarafındaki TokenIssuerTests ile AYNI kurallar. İki servis bir gün
farklı karar verirse (ör. biri kısa anahtarı kabul eder), belirteçler bir
serviste geçerli diğerinde geçersiz olur ve hatanın kaynağı aylarca
bulunamaz; bu yüzden kural iki tarafta da ayrı ayrı test ediliyor.
"""
from __future__ import annotations

import time

import pytest

from app import auth
from tests.test_electrical_api import _token

STRONG = "x" * auth.MIN_SECRET_LENGTH


# --- İmza anahtarı ---------------------------------------------------------

def test_gelistirmede_anahtar_yoksa_gelistirme_anahtari():
    assert auth.resolve_secret(None, development=True) == auth.DEVELOPMENT_SECRET


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_uretimde_anahtar_zorunlu(configured):
    with pytest.raises(RuntimeError, match="ZORUNLU"):
        auth.resolve_secret(configured, development=False)


def test_uretimde_gelistirme_anahtari_reddedilir():
    with pytest.raises(RuntimeError):
        auth.resolve_secret(auth.DEVELOPMENT_SECRET, development=False)


@pytest.mark.parametrize("development", [True, False])
def test_kisa_anahtar_her_ortamda_reddedilir(development):
    with pytest.raises(RuntimeError, match="kısa"):
        auth.resolve_secret("parola123", development=development)


def test_yeterli_anahtar_kabul_edilir():
    assert auth.resolve_secret(STRONG, development=False) == STRONG


def test_uretim_ortaminda_anahtarsiz_servis_acilmaz(monkeypatch):
    """Sessizce güvensiz çalışmaktansa gürültüyle çalışmamak."""
    monkeypatch.setenv(auth.ENV_VARIABLE, "production")
    monkeypatch.delenv(auth.SECRET_VARIABLE, raising=False)
    with pytest.raises(RuntimeError):
        auth.validate_configuration()


def test_ortam_tanimsizsa_gelistirme_sayilir(monkeypatch):
    monkeypatch.delenv(auth.ENV_VARIABLE, raising=False)
    assert auth.is_development()


# --- Belirteç yaşı (iptal penceresi) ----------------------------------------

def test_taze_belirtec_kabul_edilir():
    identity = auth.verify_token(_token())
    assert identity is not None
    assert identity.issued_at > 0


def test_yasli_belirtec_reddedilir():
    """Kapatılan oturumun belirteci en fazla MAX_TOKEN_AGE geçerli kalır."""
    old = int(time.time()) - auth.MAX_TOKEN_AGE_SECONDS - 5
    assert auth.verify_token(_token(issued_at=old)) is None


def test_yas_siniri_icindeki_belirtec_kabul_edilir():
    recent = int(time.time()) - auth.MAX_TOKEN_AGE_SECONDS + 60
    assert auth.verify_token(_token(issued_at=recent)) is not None


def test_uretim_zamani_olmayan_belirtec_reddedilir():
    """Yaşı bilinmeyen belirtecin iptal edilip edilmediği de bilinemez."""
    assert auth.verify_token(_token(issued_at=0)) is None


def test_gelecekten_gelen_belirtec_reddedilir():
    future = int(time.time()) + auth.CLOCK_SKEW_SECONDS + 600
    assert auth.verify_token(_token(issued_at=future)) is None


def test_kucuk_saat_farki_tolere_edilir():
    slightly_ahead = int(time.time()) + auth.CLOCK_SKEW_SECONDS - 10
    assert auth.verify_token(_token(issued_at=slightly_ahead)) is not None


# --- CORS -----------------------------------------------------------------

def test_cors_varsayilani_yalnizca_arayuz(monkeypatch):
    from app import main
    monkeypatch.delenv("TRANSFORMERAI_CORS_ORIGINS", raising=False)
    # Yalnızca arayüzün kendi adresi — TLS'li ve TLS'siz hâli.
    assert main._cors_origins() == [
        "https://localhost:5173",
        "http://localhost:5173",
    ]


def test_cors_ortam_degiskeniyle_genisletilir(monkeypatch):
    from app import main
    monkeypatch.setenv("TRANSFORMERAI_CORS_ORIGINS", "http://a.local, http://b.local ,")
    assert main._cors_origins() == ["http://a.local", "http://b.local"]
