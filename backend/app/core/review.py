"""Test onay akışı — mühendislik dört göz kontrolü. (Faz 12.2)

NEDEN?
------
Faz 12'ye kadar bir test girildiği anda hükme, sağlık endeksine ve iş
emri önerilerine etki ediyordu. Gerçek işletmelerde kritik bir sonuç
**ikinci bir göz** olmadan karar üretmez: yanlış bağlanmış bir TTR
kablosu ya da nemli alınmış bir yağ numunesi, sağlam bir trafoyu devre
dışı bıraktırabilir.

KURAL: yalnızca SINIR DIŞI sonuç onaya düşer
-------------------------------------------
Her testi onaya sokmak kuyruğu şişirir ve onayı anlamsızlaştırır ("damga
yorgunluğu": mühendis bakmadan onaylamaya başlar). Genel hükmü "kötü"
olan test onay bekler; "iyi" ve "kabul" edilebilir sonuçlar beklemez.

ÜÇ KARAR
--------
* **Onayla**          → ölçüm doğru, sonuç geçerli.
* **Tekrar ölçülsün** → sonuç şüpheli. Hesapta KALIR ama "doğrulanmamış"
  işaretli kalır. Onay beklerken kritik bir bulguyu yok saymak, onu
  hatalı kabul etmekten daha tehlikelidir.
* **Reddet**          → ölçüm hatalı. Hükme ve sağlık endeksine GİRMEZ;
  kayıt SİLİNMEZ (Faz 8.6'daki "geçersiz işaretleme" ilkesiyle aynı).

DÖRT GÖZ
--------
Testi giren kişi kendi testine karar veremez. Yetki sistemi mühendise
test girme yetkisi vermiyor (Faz 12.1), ama Yönetim hem test girebilir
hem onaylayabilir — kural bu yüzden yetkiye değil KİŞİYE bakıyor.

Bu modül saftır: veritabanı ve HTTP bilmez, doğrudan test edilir.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

# Onay akışına giren test türleri. Fiziksel gözlem DIŞARIDA: o bir cihaz
# ölçümü değil göz kontrolüdür; "ölçüm hatalı mı?" sorusu orada anlamsız.
KINDS: Dict[str, Dict[str, object]] = {
    "oil": {
        "kind": "oil",
        "table": "oil_tests",
        "label": "Yağ kalitesi testi",
        "date_field": "sampled_at",
        # Aynı yağ numunesi iki boyutu besliyor: yağ kalitesi ve kağıt DP.
        "dimensions": ["oil", "paper"],
    },
    "electrical": {
        "kind": "electrical",
        "table": "electrical_tests",
        "label": "Elektriksel test",
        "date_field": "tested_at",
        "dimensions": ["electrical"],
    },
    "components": {
        "kind": "components",
        "table": "component_tests",
        "label": "Buşing / kademe testi",
        "date_field": "tested_at",
        "dimensions": ["components"],
    },
}

NOT_REQUIRED = "not_required"
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
RETEST = "retest"

STATUS_LABELS: Dict[str, str] = {
    NOT_REQUIRED: "Onay gerekmiyor",
    PENDING: "Onay bekliyor",
    APPROVED: "Onaylandı",
    REJECTED: "Reddedildi",
    RETEST: "Tekrar ölçüm istendi",
}

DECISIONS: Dict[str, str] = {
    "approve": APPROVED,
    "reject": REJECTED,
    "retest": RETEST,
}

# Reddetme ve tekrar ölçüm için gerekçe zorunlu. 10 karakter: "hatalı"
# gibi tek kelimelik bir gerekçe bir sonraki kişiye hiçbir şey anlatmaz.
NOTE_MIN_LENGTH = 10

# Onaya düşüren hüküm.
REVIEW_TRIGGER = "kötü"


def initial_status(overall: Optional[str]) -> str:
    """Yeni kaydedilen testin onay durumu."""
    return PENDING if overall == REVIEW_TRIGGER else NOT_REQUIRED


def is_usable(row: Mapping[str, object]) -> bool:
    """Kayıt hükme ve sağlık endeksine girebilir mi?

    Geçersiz işaretlenmiş (Faz 8.6) ya da mühendisin REDDETTİĞİ kayıt
    girmez. İkisi de silinmez; geçmişte görünür kalır.
    """
    return not row.get("voided_at") and row.get("review_status") != REJECTED


def is_unverified(status: Optional[str]) -> bool:
    """Sonuç hesapta ama henüz doğrulanmamış mı?"""
    return status in (PENDING, RETEST)


def unverified_dimensions(statuses: Mapping[str, Optional[str]]) -> List[str]:
    """Test türü → onay durumu eşlemesinden doğrulanmamış sağlık boyutları.

    Örnek: yağ testi onay bekliyorsa hem "oil" hem "paper" boyutu
    doğrulanmamıştır — ikisi de aynı numuneden okunuyor.
    """
    dims: List[str] = []
    for kind, status in statuses.items():
        if kind in KINDS and is_unverified(status):
            dims.extend(KINDS[kind]["dimensions"])  # type: ignore[arg-type]
    return dims


def validate_decision(row: Mapping[str, object], decision: str,
                      note: Optional[str],
                      reviewer_employee_no: str) -> Optional[Tuple[int, str]]:
    """Karar verilebilir mi? Sorun varsa (HTTP kodu, mesaj), yoksa None.

    Kontrol sırası bilinçli: önce kararın kendisi, sonra kaydın durumu,
    sonra kişi, en son gerekçe. Böylece kullanıcı önce DÜZELTEMEYECEĞİ
    sorunu (ör. dört göz) görür, gerekçe yazmakla vakit kaybetmez.
    """
    if decision not in DECISIONS:
        return 400, ("Geçersiz karar. Seçenekler: onayla (approve), "
                     "reddet (reject), tekrar ölçülsün (retest).")

    if row.get("voided_at"):
        return 409, "Bu test geçersiz işaretlenmiş; onay kararı verilemez."

    status = row.get("review_status")
    if status != PENDING:
        label = STATUS_LABELS.get(str(status), "sınıflandırılmamış")
        return 409, f"Bu test onay beklemiyor (durum: {label})."

    recorded_by = row.get("recorded_by_id")
    if recorded_by and str(recorded_by) == str(reviewer_employee_no):
        return 403, ("Dört göz ilkesi: kendi girdiğiniz teste karar "
                     "veremezsiniz. Kararı başka bir mühendis vermeli.")

    if decision in ("reject", "retest"):
        if not note or len(note.strip()) < NOTE_MIN_LENGTH:
            return 400, (f"Reddetme ve tekrar ölçüm isteğinde gerekçe "
                         f"zorunludur (en az {NOTE_MIN_LENGTH} karakter). "
                         "Bir sonraki kişi neden güvenilmediğini bilmeli.")

    return None
