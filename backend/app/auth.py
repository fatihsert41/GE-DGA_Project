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

YETKİLER (Faz 10)
-----------------
Belirteç artık kişinin **departmanını ve yetki listesini** de taşıyor.
Yetki haritası YALNIZCA .NET'te tanımlı (``Models/Department.cs``); Python
haritayı bilmez, belirtece yazılmış listeye bakar. Haritayı burada tekrar
yazmak, bir gün iki tarafın ayrışmasına ve "ekranda düğme var ama sunucu
reddediyor" türü hatalara yol açardı.

İmza yükü kurcalanamaz kıldığı için listeye güvenmek güvenlidir: yetki
eklemek için imzayı yeniden üretmek, bunun için de gizli anahtarı bilmek
gerekir.

BEDELİ — ve neden kabul ediyoruz
--------------------------------
İmzalı belirteç **iptal edilemez**: Python, .NET'te oturumun kapatıldığını
bilemez. Yani çıkış yapılmış bir belirteç, süresi dolana kadar (9 saat)
Python tarafında geçerli kalır. Aynı şekilde departmanı değiştirilen
kişinin Python tarafındaki yetkileri de yeniden giriş yapana kadar eski
kalır (.NET tarafında değişiklik anında geçerli).

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
from dataclasses import dataclass, field
from typing import Callable, FrozenSet, Optional

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
    # Faz 10. Varsayılanlar BOŞ: yetki listesi taşımayan eski bir
    # belirteç hiçbir yazma yetkisi vermez. Tersi (eksikse tam yetki),
    # güncelleme öncesi açılmış her oturumu açık bir kapıya çevirirdi.
    department: str = ""
    department_name: str = ""
    permissions: FrozenSet[str] = field(default_factory=frozenset)

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


def check_permission(identity: Identity, permission: str) -> None:
    """Yetki yoksa 403 fırlatır.

    401 ile 403 farklı şeyler söyler: 401 "kim olduğunu bilmiyorum",
    403 "kim olduğunu biliyorum ama bu işe yetkin yok". Arayüz birinde
    giriş ekranına, diğerinde "yetkiniz yok" mesajına gider.
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
        # Faz 10 öncesi açılmış oturumun belirtecinde yetki listesi yok.
        detail["message"] = ("Oturumunuz yetki sisteminden önce açılmış. "
                             "Çıkış yapıp yeniden giriş yapın.")
    raise HTTPException(status_code=403, detail=detail)


def require_permission(permission: str) -> Callable[..., Identity]:
    """Belirli bir yetki ZORUNLU — yoksa 401 veya 403.

    Kullanım: ``identity: Identity = Depends(require_permission("tests.oil"))``

    Bu bir "fabrika": yetki adını alıp FastAPI'nin çağıracağı asıl
    bağımlılık fonksiyonunu üretir. Böylece her uç nokta hangi yetkiyi
    istediğini imzasında açıkça yazar.
    """
    def dependency(
        authorization: Optional[str] = Header(default=None),
    ) -> Identity:
        identity = require_identity(authorization)
        check_permission(identity, permission)
        return identity

    return dependency
