"""Kimlik doğrulama — imzalı belirteci .NET'e SORMADAN doğrular. (Faz 9.0c)

MİMARİ GEREKÇE
--------------
Faz 7'de bir kural konmuştu: **Python servisi .NET'i bilmez.** Bu sayede
.NET kapalıyken Python çalışmaya devam ediyor (Faz 7.4'te ölçülerek
doğrulanmıştı).

Kimlik doğrulama bu kuralı tehdit ediyordu: Python'un da "bu belirteç
geçerli mi?" sorusunu cevaplaması gerek. Naif çözüm her yazma isteğinde
.NET'e HTTP atmaktı — ama o zaman **bağımlılık yönü tersine döner** ve
.NET çöktüğünde Python'a ölçüm girilemez hâle gelir. Bir bakım ekibinin
sahadayken ölçüm girememesi, kabul edilemez bir bağımlılık.

Çözüm: belirteç **imzalı**. .NET onu paylaşılan gizli anahtarla imzalar
(HMAC-SHA256); Python aynı anahtarla imzayı kendi başına doğrular. Ağ
isteği yok, bağımlılık yok.

    <yük(base64url)>.<imza(base64url)>

BEDELİ — ve neden kabul ediyoruz
--------------------------------
İmzalı belirteç **iptal edilemez**: Python, .NET'te oturumun kapatıldığını
bilemez. Yani çıkış yapılmış bir belirteç, süresi dolana kadar (9 saat)
Python tarafında geçerli kalır.

Bu bilinçli bir ödünleşim: *Python'un ayakta kalması, Python tarafındaki
anlık iptalden daha değerli.* Üstelik izlenebilirlik bozulmuyor — o
belirteçle girilen kayıt yine kendi sahibinin adına yazılır.

⚠ GİZLİ ANAHTAR: Geliştirme anahtarı kaynak kodda ve **gizli değildir**.
Gerçek kurulumda ``TRANSFORMERAI_AUTH_SECRET`` ortam değişkeninden
okunmalı — .NET tarafında da aynı değer olmalı.

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
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

# .NET'teki TokenIssuer.DevelopmentSecret ile AYNI olmalı.
DEVELOPMENT_SECRET = "transformerai-dev-secret-degistirin"


def _secret() -> str:
    return os.environ.get("TRANSFORMERAI_AUTH_SECRET") or DEVELOPMENT_SECRET


def using_development_secret() -> bool:
    return not os.environ.get("TRANSFORMERAI_AUTH_SECRET")


@dataclass(frozen=True)
class Identity:
    """Belirteçten çözülen kimlik."""
    employee_no: str
    name: str
    role: str
    expires_at: int

    @property
    def is_supervisor(self) -> bool:
        return self.role == "Supervisor"

    @property
    def can_approve(self) -> bool:
        """Mühendis ve süpervizör onay verebilir, teknisyen veremez."""
        return self.role in ("Engineer", "Supervisor")


def _b64url_decode(text: str) -> bytes:
    """Base64Url çözer (dolgu karakterleri eksik olabilir)."""
    padded = text.replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    return base64.b64decode(padded)


def verify_token(token: Optional[str]) -> Optional[Identity]:
    """Belirtecin imzasını ve süresini doğrular; geçersizse None.

    Ağ isteği YOK: doğrulama tamamen yereldir.
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

    # compare_digest: SABİT SÜREDE karşılaştırır. Sıradan `==` ilk farklı
    # baytta durur; saldırgan yanıt süresini ölçerek imzayı bayt bayt
    # tahmin edebilir (zamanlama saldırısı). .NET tarafında da aynı
    # önlem var (CryptographicOperations.FixedTimeEquals).
    if not hmac.compare_digest(given, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None

    expires = int(payload.get("expires_at_unix", 0))
    if expires <= int(time.time()):
        return None

    return Identity(
        employee_no=str(payload.get("employee_no", "")),
        name=str(payload.get("name", "")),
        role=str(payload.get("role", "")),
        expires_at=expires,
    )


# --- FastAPI bağımlılıkları ------------------------------------------------
#
# FastAPI'de "bağımlılık" (dependency), uç nokta çalışmadan ÖNCE çalışan
# bir fonksiyondur. Uç nokta imzasına parametre olarak yazılır ve FastAPI
# onu kendisi çağırır. Böylece kimlik kontrolü her uç noktada tekrar
# tekrar yazılmaz.


def current_identity(
    authorization: Optional[str] = Header(default=None),
) -> Optional[Identity]:
    """Belirteci başlıktan okur; yoksa None (zorunlu DEĞİL).

    Okuma uç noktalarında kullanılır: kimlik varsa bilinsin, yoksa da
    çalışsın. Filo ekranını görmek için giriş şartı koymuyoruz.
    """
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return verify_token(token)


def require_identity(
    authorization: Optional[str] = Header(default=None),
) -> Identity:
    """Kimlik ZORUNLU — yoksa 401.

    Yazma uç noktalarında kullanılır: bir kaydın sorumlusu bilinmeden
    o kayıt oluşturulmamalı. Bu, "kayıt silinmez, geçersiz işaretlenir"
    kararının tamamlayıcısı — sorumlusu olmayan bir kayıt için denetim
    izi tutmanın anlamı yok.
    """
    identity = current_identity(authorization)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Bu işlem için giriş yapmalısınız. Sicil numaranız ve "
                   "PIN'inizle oturum açın.")
    return identity
