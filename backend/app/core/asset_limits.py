"""Varlığa özel eşik — kayıtlı mühendislik istisnası. (Faz 12.4)

NEDEN?
------
Yağ kalitesi eşikleri (``oil_quality.LIMITS``) gerilim sınıfına göre
filonun TAMAMINA uygulanır. Ama her trafo standart değildir: "TR-07 eski
tasarım, serbest solunumlu konservatör; nem sınırı 20 değil 25 ppm" gibi
istisnalar sahada gerçektir. İstisna tanımlanamazsa iki kötü sonuçtan
biri olur:

* Aynı trafo her testte "kötü" çıkar ve onay kuyruğuna düşer → mühendis
  bakmadan onaylamaya başlar ("damga yorgunluğu", Faz 12.2).
* Biri eşiği kodda ya da veritabanında SESSİZCE değiştirir → kimse neden,
  kimin kararıyla ve ne zamana kadar değiştiğini bilmez.

Bu modül üçüncü yolu tanımlar: istisna bir KAYITTIR. Gerekçesi, süresi,
öneren ve onaylayan kişisi vardır.

KURALLAR
--------
1. **Gerekçe zorunlu** (en az 20 karakter).
2. **Süre zorunlu**, en fazla 365 gün. Süresi dolan istisna kendiliğinden
   düşer, standart eşik geri gelir. Süresiz istisna, fark edilmeyen bir
   standart değişikliğidir.
3. **Dört göz:** öneren kendi önerisini onaylayamaz. Eşik gevşetmek, tek
   bir testi onaylamaktan DAHA tehlikelidir: o trafonun gelecekteki bütün
   testlerini etkiler.
4. **Yazım hatası koruması:** yeni sınır standarttan en fazla %50 sapabilir.
   25 yerine 250 yazmak, trafoyu fiilen izlemeden çıkarırdı. Daha büyük
   bir fark istisna değil, standart değişikliğidir.
5. **Geri çekme dört göz istemez:** istisnayı kaldırmak standarda dönmektir,
   yani korumacı yöndedir. Öneren de geri çekebilir (gerekçeyle).
6. **Geçmişe uzanmaz:** geçerlilik bugünden önce başlayamaz ve istisna
   yalnızca bu aralıktaki TEST TARİHLERİNE uygulanır.
7. **Sessiz değil:** değerlendirme hem uygulanan hem standart eşiği taşır.
   Hüküm değiştiyse "standart eşikle hüküm X olurdu" uyarısı üretilir.

NEDEN YALNIZCA YAĞ PARAMETRELERİ?
---------------------------------
Yağ eşikleri **tasarıma bağlıdır** (konservatör tipi, yalıtım sistemi,
yaş). Elektriksel ve buşing eşikleri ise **arıza imzasıdır**: kısa devre
bir spir, trafonun tasarımı ne olursa olsun TTR'de sapma üretir. Onları
gevşetmek istisna tanımak değil, arızayı görmezden gelmek olur. Kapsam
dışı bırakılmaları bilinçli.

Bu modül saftır: veritabanı ve HTTP bilmez, doğrudan test edilir.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, Mapping, Optional, Tuple

from . import oil_quality

# İstisna tanımlanabilen parametreler: yağ kalitesi eşiklerinin tamamı.
OVERRIDABLE: Tuple[str, ...] = tuple(oil_quality.LIMITS)

# Kapsam dışı olanlar ve nedenleri — arayüz "neden burada yok?" sorusunu
# buradan cevaplar.
NOT_OVERRIDABLE: Dict[str, str] = {
    "electrical": ("TTR, sargı direnci, PI ve tan δ eşikleri arıza "
                   "imzasıdır; trafonun tasarımına göre değişmez."),
    "components": ("Buşing kapasitans/güç faktörü ve kademe değiştirici "
                   "sınırları arıza ve aşınma imzasıdır."),
    "dga": ("IEEE C57.104 gaz sınırları hem risk motorunun hem ML "
            "modelinin ortak girdisidir; bu fazın kapsamı dışında."),
}

PENDING = "pending"
ACTIVE = "active"
REJECTED = "rejected"
REVOKED = "revoked"
EXPIRED = "expired"

STATUS_LABELS: Dict[str, str] = {
    PENDING: "Onay bekliyor",
    ACTIVE: "Yürürlükte",
    REJECTED: "Reddedildi",
    REVOKED: "Geri çekildi",
    EXPIRED: "Süresi doldu",
}

DECISIONS: Dict[str, str] = {"approve": ACTIVE, "reject": REJECTED}

DIRECTION_LABELS: Dict[str, str] = {
    "loosen": "Gevşetme",
    "tighten": "Sıkılaştırma",
    "mixed": "Karışık",
    "none": "Değişiklik yok",
}

REASON_MIN_LENGTH = 20     # öneri gerekçesi
NOTE_MIN_LENGTH = 10       # ret ve geri çekme gerekçesi (Faz 12.2 ile aynı)
MAX_DURATION_DAYS = 365
MAX_DEVIATION = 0.5        # standarttan en fazla %50


def parse_date(value: object) -> Optional[date]:
    """ISO tarih ya da zaman damgasından takvim günü; bozuksa None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def standard_limits(parameter: str, vclass: str) -> Tuple[float, float]:
    """Gerilim sınıfına göre standart (iyi, kabul) sınırları."""
    good, acceptable = oil_quality.LIMITS[parameter]["thresholds"][vclass]  # type: ignore[index]
    return float(good), float(acceptable)


def _lower_is_better(parameter: str) -> bool:
    return oil_quality.LIMITS[parameter]["direction"] == "lower_better"


def change_direction(parameter: str, good: float, acceptable: float,
                     std_good: float, std_acceptable: float) -> str:
    """İstisna eşiği gevşetiyor mu, sıkılaştırıyor mu?

    "Gevşetme", daha kötü bir değerin kabul edilmesi demektir. Nem gibi
    düşük olanın iyi olduğu parametrede sınırı YÜKSELTMEK, delinme gerilimi
    gibi yüksek olanın iyi olduğu parametrede sınırı DÜŞÜRMEK gevşetmedir.
    """
    lower_better = _lower_is_better(parameter)
    moves = []
    for new, std in ((good, std_good), (acceptable, std_acceptable)):
        if new == std:
            continue
        looser = new > std if lower_better else new < std
        moves.append("loosen" if looser else "tighten")
    if not moves:
        return "none"
    if all(m == "loosen" for m in moves):
        return "loosen"
    if all(m == "tighten" for m in moves):
        return "tighten"
    return "mixed"


def validate_proposal(parameter: str, good: Optional[float],
                      acceptable: Optional[float], vclass: str,
                      valid_from: object, valid_until: object,
                      reason: Optional[str],
                      today: date) -> Optional[Tuple[int, str]]:
    """Öneri kaydedilebilir mi? Sorun varsa (HTTP kodu, mesaj), yoksa None."""
    if parameter not in OVERRIDABLE:
        return 400, ("Bu parametre için istisna tanımlanamaz. Yalnızca yağ "
                     "kalitesi eşikleri: " + ", ".join(OVERRIDABLE) + ". "
                     "Elektriksel ve buşing eşikleri arıza imzasıdır.")

    if good is None or acceptable is None or good <= 0 or acceptable <= 0:
        return 400, "'İyi' ve 'kabul' sınırlarının ikisi de pozitif olmalı."

    spec = oil_quality.LIMITS[parameter]
    std_good, std_acc = standard_limits(parameter, vclass)

    if _lower_is_better(parameter) and not good < acceptable:
        return 400, (f"{spec['label']} için düşük değer iyidir: 'iyi' sınırı "
                     "'kabul' sınırından küçük olmalı.")
    if not _lower_is_better(parameter) and not good > acceptable:
        return 400, (f"{spec['label']} için yüksek değer iyidir: 'iyi' "
                     "sınırı 'kabul' sınırından büyük olmalı.")

    if change_direction(parameter, good, acceptable, std_good, std_acc) == "none":
        return 400, "Önerilen sınırlar standartla aynı; istisnaya gerek yok."

    for new, std, label in ((good, std_good, "iyi"),
                            (acceptable, std_acc, "kabul")):
        deviation = abs(new - std) / std
        if deviation > MAX_DEVIATION:
            return 400, (f"'{label}' sınırı standarttan %{deviation * 100:.0f} "
                         f"sapıyor (standart {std:g}, önerilen {new:g}); en "
                         f"fazla %{MAX_DEVIATION * 100:.0f}. Yazım hatası "
                         "olabilir. Daha büyük bir fark istisna değil, "
                         "standart değişikliğidir.")

    start = parse_date(valid_from)
    end = parse_date(valid_until)
    if start is None or end is None:
        return 400, "Geçerlilik başlangıç ve bitiş tarihi zorunlu (YYYY-AA-GG)."
    if start < today:
        return 400, ("Geçerlilik bugünden önce başlayamaz: istisna geçmiş "
                     "testlerin hükmünü sonradan değiştirmemeli.")
    if end < start:
        return 400, "Bitiş tarihi başlangıçtan önce olamaz."
    if (end - start).days > MAX_DURATION_DAYS:
        return 400, (f"İstisna en fazla {MAX_DURATION_DAYS} gün sürebilir. "
                     "Süresi dolunca yeniden değerlendirilmeli — süresiz "
                     "istisna fark edilmeyen bir standart değişikliğidir.")

    if not reason or len(reason.strip()) < REASON_MIN_LENGTH:
        return 400, (f"Gerekçe zorunludur (en az {REASON_MIN_LENGTH} "
                     "karakter). Bir sonraki mühendis bu trafonun neden "
                     "farklı değerlendirildiğini bilmeli.")

    return None


def validate_decision(row: Mapping[str, object], decision: str,
                      note: Optional[str], reviewer_employee_no: str,
                      today: date) -> Optional[Tuple[int, str]]:
    """Onay/ret verilebilir mi? Kontrol sırası ``core/review.py`` ile aynı."""
    if decision not in DECISIONS:
        return 400, "Geçersiz karar. Seçenekler: onayla (approve), reddet (reject)."

    status = row.get("status")
    if status != PENDING:
        label = STATUS_LABELS.get(str(status), str(status))
        return 409, f"Bu istisna onay beklemiyor (durum: {label})."

    proposer = row.get("proposed_by_id")
    if proposer and str(proposer) == str(reviewer_employee_no):
        return 403, ("Dört göz ilkesi: kendi önerdiğiniz istisnayı "
                     "onaylayamaz ya da reddedemezsiniz. Kararı başka bir "
                     "mühendis vermeli.")

    if decision == "approve":
        end = parse_date(row.get("valid_until"))
        if end is not None and end < today:
            return 409, ("Önerinin geçerlilik süresi onay beklerken doldu; "
                         "yeniden önerilmeli.")

    if decision == "reject" and (not note or len(note.strip()) < NOTE_MIN_LENGTH):
        return 400, (f"Reddetme gerekçesi zorunludur (en az "
                     f"{NOTE_MIN_LENGTH} karakter).")

    return None


def validate_revoke(row: Mapping[str, object],
                    note: Optional[str]) -> Optional[Tuple[int, str]]:
    """Geri çekilebilir mi? Dört göz YOK: standarda dönmek korumacıdır."""
    if row.get("status") != ACTIVE:
        label = STATUS_LABELS.get(str(row.get("status")), str(row.get("status")))
        return 409, f"Yalnızca yürürlükteki istisna geri çekilebilir (durum: {label})."
    if not note or len(note.strip()) < NOTE_MIN_LENGTH:
        return 400, (f"Geri çekme gerekçesi zorunludur (en az "
                     f"{NOTE_MIN_LENGTH} karakter).")
    return None


def is_in_effect(row: Mapping[str, object], on_date: object) -> bool:
    """İstisna bu tarihteki bir teste uygulanır mı?"""
    if row.get("status") != ACTIVE:
        return False
    d = parse_date(on_date)
    start = parse_date(row.get("valid_from"))
    end = parse_date(row.get("valid_until"))
    if d is None or start is None or end is None:
        # Tarihi okunamayan teste istisna UYGULANMAZ: şüphede standart eşik.
        return False
    return start <= d <= end


def select_for_test(overrides: Iterable[Mapping[str, object]],
                    test_date: object) -> Dict[str, Mapping[str, object]]:
    """Bir teste uygulanacak istisnalar: parametre → istisna kaydı."""
    return {str(o["parameter"]): o for o in overrides
            if is_in_effect(o, test_date)}


def describe(row: Mapping[str, object], today: date) -> Dict[str, object]:
    """Kaydın arayüze giden hâli: etiketler ve türetilmiş alanlarla."""
    parameter = str(row["parameter"])
    spec = oil_quality.LIMITS.get(parameter, {})
    good = float(row["good_limit"])            # type: ignore[arg-type]
    acceptable = float(row["acceptable_limit"])  # type: ignore[arg-type]
    std_good = float(row["standard_good_limit"])            # type: ignore[arg-type]
    std_acc = float(row["standard_acceptable_limit"])       # type: ignore[arg-type]
    direction = change_direction(parameter, good, acceptable, std_good, std_acc)
    end = parse_date(row.get("valid_until"))

    return {
        **dict(row),
        "parameter_label": spec.get("label", parameter),
        "unit": spec.get("unit"),
        "standard": spec.get("standard"),
        "status_label": STATUS_LABELS.get(str(row.get("status")), "—"),
        "change_direction": direction,
        "change_direction_label": DIRECTION_LABELS[direction],
        "in_effect_today": is_in_effect(row, today),
        "days_left": ((end - today).days
                      if end is not None and row.get("status") == ACTIVE else None),
    }
