"""Kimlik doğrulama — imzalı belirteci .NET'e SORMADAN doğrular. (Faz 9.0c)

MİMARİ GEREKÇE
--------------
Faz 7'de bir kural konmuştu: **Python servisi .NET'i bilmez.** Bu sayede
.NET kapalıyken Python çalışmaya devam ediyor (Faz 7.4'te ölçülerek
doğrulanmıştı).

Kimlik doğrulama bu kuralı tehdit ediyordu: Python'un da "bu belirteç
geçerli mi?" sorusunu cevaplaması gerek. Naif çözüm her yazma isteğinde
.NET'e HTTP atmaktı — ama o zaman **bağımlılık yönü tersine döner** ve
.NET çöktüğünde Python'a ölçüm girilemez hâle gelir.

Çözüm: belirteç **imzalı**. .NET onu paylaşılan gizli anahtarla imzalar
(HMAC-SHA256); Python aynı anahtarla imzayı kendi başına doğrular. Ağ
isteği yok, bağımlılık yok.

    <yük(base64url)>.<imza(base64url)>

YETKİLER (Faz 10)
-----------------
Belirteç kişinin **departmanını ve yetki listesini** de taşıyor. Yetki
haritası YALNIZCA .NET'te tanımlı (``Models/Department.cs``); Python
belirtece yazılmış listeye bakar.

İPTAL PENCERESİ — ve nasıl daraltıldı (güvenlik sertleştirme)
--------------------------------------------------------------
İmzalı belirteç tek başına **iptal edilemez**: Python, .NET'te oturumun
kapatıldığını bilemez. İlk sürümde çıkış yapılmış ya da parolası
sıfırlanmış birinin belirteci Python'da **9 saat** geçerli kalabiliyordu.

Artık belirteç **üretim zamanını** (``issued_at_unix``) taşıyor ve Python
en fazla ``MAX_TOKEN_AGE_SECONDS`` (20 dk) yaşındaki belirteci kabul ediyor.
Arayüz 10 dakikada bir .NET'ten yeni belirteç alıyor (``/auth/refresh``);
.NET yenilerken oturum satırına baktığı için kapatılmış oturum YENİLENEMEZ.
Sonuç: iptal penceresi 9 saatten **en fazla 20 dakikaya** indi ve Python
hâlâ .NET'e hiç sormuyor.

GİZLİ ANAHTAR — hızlı başarısızlık
----------------------------------
Geliştirme anahtarı kaynak kodda ve **gizli değildir**. Onunla çalışan bir
üretim sunucusunda HERKES geçerli belirteç üretebilir. Bu yüzden
``TRANSFORMERAI_ENV`` geliştirme DEĞİLSE ve anahtar yoksa / geliştirme
anahtarıysa / kısaysa servis **açılmayı reddeder** (``validate_configuration``
``main.py`` içinde import anında çağrılır). .NET'teki ``TokenIssuer`` aynı
kuralları uyguluyor.

⚠ BU KATMAN HTTPS DEĞİLDİR. Belirteç, TLS olmadan ağda açık gider.
Demo localhost'ta çalıştığı için sorun değil; gerçek kurulumda şart.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, FrozenSet, Optional

from fastapi import Header, HTTPException

# .NET'teki TokenIssuer.DevelopmentSecret ile AYNI olmalı. GİZLİ DEĞİLDİR.
DEVELOPMENT_SECRET = "transformerai-dev-secret-degistirin"

# .NET'teki TokenIssuer.MinSecretLength ile aynı.
MIN_SECRET_LENGTH = 32

# Python'un kabul ettiği en yaşlı belirteç. Arayüz 10 dk'da bir yeniliyor;
# 20 dk, bir yenilemenin kaçması (ağ kesintisi, uyku modu) için pay bırakır.
MAX_TOKEN_AGE_SECONDS = 20 * 60

# Sunucu saatleri arasındaki küçük farka tolerans: .NET'in saati Python'dan
# biraz ileride olabilir; "gelecekten gelen" belirteç yalnızca bu payın
# ötesindeyse reddedilir.
CLOCK_SKEW_SECONDS = 60

SECRET_VARIABLE = "TRANSFORMERAI_AUTH_SECRET"
ENV_VARIABLE = "TRANSFORMERAI_ENV"


def environment() -> str:
    """Çalışma ortamı. Tanımlı değilse 'development' (yerel çalışma)."""
    return (os.environ.get(ENV_VARIABLE) or "development").strip().lower()


def is_development() -> bool:
    return environment() == "development"


def resolve_secret(configured: Optional[str], development: bool) -> str:
    """Kullanılacak anahtarı seçer; güvensiz yapılandırmada RuntimeError.

    Saf fonksiyon: ortam okumaz, test edilebilir. .NET'teki
    ``TokenIssuer.ResolveSecret`` ile aynı kurallar.
    """
    if configured is None or not configured.strip():
        if development:
            return DEVELOPMENT_SECRET
        raise RuntimeError(
            f"Belirteç imza anahtarı tanımlı değil. Geliştirme ortamı dışında "
            f"{SECRET_VARIABLE} ortam değişkeni ZORUNLU (en az "
            f"{MIN_SECRET_LENGTH} karakter). Geliştirme anahtarı kaynak kodda "
            "ve gizli değildir; onunla çalışmak herkesin geçerli belirteç "
            "üretebilmesi demektir.")

    if configured == DEVELOPMENT_SECRET:
        if development:
            return DEVELOPMENT_SECRET
        raise RuntimeError(
            "Geliştirme anahtarı geliştirme ortamı dışında kullanılamaz: "
            "kaynak kodda yazılı.")

    if len(configured) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"Belirteç imza anahtarı çok kısa ({len(configured)} karakter); "
            f"en az {MIN_SECRET_LENGTH} karakter olmalı.")

    return configured


def _secret() -> str:
    return resolve_secret(os.environ.get(SECRET_VARIABLE), is_development())


def using_development_secret() -> bool:
    return _secret() == DEVELOPMENT_SECRET


def validate_configuration() -> None:
    """Açılışta çağrılır: yanlış yapılandırmayla servis AÇILMAZ."""
    _secret()


@dataclass(frozen=True)
class Identity:
    """Belirteçten çözülen kimlik."""
    employee_no: str
    name: str
    role: str
    expires_at: int
    # Faz 10. Varsayılanlar BOŞ: yetki listesi taşımayan eski bir
    # belirteç hiçbir yazma yetkisi vermez.
    department: str = ""
    department_name: str = ""
    permissions: FrozenSet[str] = field(default_factory=frozenset)
    issued_at: int = 0

    @property
    def is_supervisor(self) -> bool:
        return self.role == "Supervisor"

    @property
    def can_approve(self) -> bool:
        """Mühendis ve süpervizör onay verebilir, teknisyen veremez."""
        return self.role in ("Engineer", "Supervisor")

    def has(self, permission: str) -> bool:
        """Bu kişi bu işlemi yapabilir mi?"""
        return permission in self.permissions


def _b64url_decode(text: str) -> bytes:
    """Base64Url çözer (dolgu karakterleri eksik olabilir)."""
    padded = text.replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    return base64.b64decode(padded)


def verify_token(token: Optional[str], now: Optional[int] = None) -> Optional[Identity]:
    """Belirtecin imzasını, süresini ve YAŞINI doğrular; geçersizse None.

    Ağ isteği YOK: doğrulama tamamen yereldir.
    ``now`` testler içindir; verilmezse sistem saati.
    """
    if not token:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None

    body, signature = parts
    expected = hmac.new(_secret().encode("utf-8"),
                        body.encode("utf-8"), hashlib.sha256).digest()

    try:
        given = _b64url_decode(signature)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None

    # compare_digest: SABİT SÜREDE karşılaştırır (zamanlama saldırısı).
    if not hmac.compare_digest(given, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None

    current = int(time.time()) if now is None else int(now)

    expires = int(payload.get("expires_at_unix", 0))
    if expires <= current:
        return None

    # Yaş sınırı (güvenlik sertleştirme). Üretim zamanı olmayan belirteç
    # REDDEDİLİR: yaşı bilinmeyen bir belirtecin iptal edilip edilmediği de
    # bilinemez.
    issued = int(payload.get("issued_at_unix", 0) or 0)
    if issued <= 0:
        return None
    if current - issued > MAX_TOKEN_AGE_SECONDS:
        return None
    if issued - current > CLOCK_SKEW_SECONDS:
        return None      # "gelecekten gelen" belirteç: saat oynaması ya da sahtecilik

    permissions = payload.get("permissions") or []
    if not isinstance(permissions, list):
        permissions = []

    return Identity(
        employee_no=str(payload.get("employee_no", "")),
        name=str(payload.get("name", "")),
        role=str(payload.get("role", "")),
        expires_at=expires,
        department=str(payload.get("department", "") or ""),
        department_name=str(payload.get("department_name", "") or ""),
        permissions=frozenset(str(p) for p in permissions),
        issued_at=issued,
    )


# --- FastAPI bağımlılıkları ------------------------------------------------
#
# FastAPI'de "bağımlılık" (dependency), uç nokta çalışmadan ÖNCE çalışan
# bir fonksiyondur. Uç nokta imzasına parametre olarak yazılır ve FastAPI
# onu kendisi çağırır.


def current_identity(
    authorization: Optional[str] = Header(default=None),
) -> Optional[Identity]:
    """Belirteci başlıktan okur; yoksa None (zorunlu DEĞİL)."""
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return verify_token(token)


def require_identity(
    authorization: Optional[str] = Header(default=None),
) -> Identity:
    """Kimlik ZORUNLU — yoksa 401."""
    identity = current_identity(authorization)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Bu işlem için giriş yapmalısınız ya da oturumunuzun "
                   "yenilenmesi gerekiyor. Sicil numaranız ve parolanızla "
                   "oturum açın.")
    return identity


def check_permission(identity: Identity, permission: str) -> None:
    """Yetki yoksa 403 fırlatır.

    401 ile 403 farklı şeyler söyler: 401 "kim olduğunu bilmiyorum",
    403 "kim olduğunu biliyorum ama bu işe yetkin yok".
    """
    if identity.has(permission):
        return
    department = identity.department_name or identity.department or "tanımsız"
    detail = {
        "message": "Bu işlem için yetkiniz yok. Departmanınız "
                   f"({department}) bu işlemi yapamıyor.",
        "required_permission": permission,
        "department": identity.department,
    }
    if not identity.permissions:
        # Geçici parolalı oturum ya da Faz 10 öncesi belirteç.
        detail["message"] = ("Oturumunuzun yetkisi yok. Geçici parolanızı "
                             "değiştirin ya da yeniden giriş yapın.")
    raise HTTPException(status_code=403, detail=detail)


def require_permission(permission: str) -> Callable[..., Identity]:
    """Belirli bir yetki ZORUNLU — yoksa 401 veya 403.

    Kullanım: ``identity: Identity = Depends(require_permission("tests.oil"))``
    """
    def dependency(
        authorization: Optional[str] = Header(default=None),
    ) -> Identity:
        identity = require_identity(authorization)
        check_permission(identity, permission)
        return identity

    return dependency
