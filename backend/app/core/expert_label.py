"""Model inceleme — mühendisin tanı kararı (uzman etiketi). (Faz 12.3)

NEDEN?
------
Faz 6.9'daki öğrenme eğrisi hâlâ yükseliyordu: bu modele en çok katkı
yapacak şey başka bir algoritma değil, **daha çok gerçek, etiketli veri**.
Faz 6.5'te model emin olmadığında vakayı "uzman incelemesi" diye
işaretliyordu, ama işaretin sonrası yoktu: uzmanın kararı hiçbir yere
yazılmıyordu. Bu modül o kararı kayda geçirir. Her karar hem bugünkü
bakım kararını düzeltir hem de yarının eğitim verisi olur.

DÖRT KARAR
----------
1. **Uzman kararı modelin önüne geçer.** Etiketlenmiş bir ölçümde filo
   kartındaki tanı, ciddi arıza işareti ve arıza ailesi uzman kararından
   gelir; modelin tahmini ``model_prediction`` alanında korunur. .NET
   planlayıcısı bu alanları okuduğu için doğru iş emri kendiliğinden çıkar.
2. **Emin olunan tanı da etiketlenebilir.** En tehlikeli hata, modelin
   emin olup yanıldığı durumdur; kuyruk düşük güvenli vakaları öne alır
   ama etiketlemeyi onlarla sınırlamaz.
3. **"Belirlenemedi" geçerli bir karardır.** Uzman emin değilse tahmin
   yürütmek yerine bunu söyler. Bu etiket veri setine GİRMEZ ve vaka
   inceleme işaretini korur — uydurulmuş bir etiket, hiç etiket olmamasından
   kötüdür, çünkü modele yanlışı öğretir.
4. **Dört göz:** ölçümü kaydeden kişi o ölçümün tanısını etiketleyemez
   (Faz 12.2 ile aynı ilke).

Bu modül saftır: veritabanı ve HTTP bilmez.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .gases import FAULT_CLASSES, FAULT_FAMILY, FAULT_GROUP, FAULT_LABELS_TR, SEVERE_FAULTS

UNDETERMINED = "undetermined"

LABELS: List[str] = [*FAULT_CLASSES, UNDETERMINED]

LABELS_TR: Dict[str, str] = {**FAULT_LABELS_TR, UNDETERMINED: "Belirlenemedi"}

# Modelle AYNI FİKİRDE olmayan karar gerekçe ister: "neden farklı
# düşünüyorum" bilgisi, etiketin kendisi kadar değerlidir. Aynı fikirdeyse
# gerekçe isteğe bağlı — zorunlu tutmak "katılıyorum" yazmaya iterdi.
NOTE_MIN_LENGTH = 10


def is_determined(label: Optional[str]) -> bool:
    """Etiket bir arıza sınıfı mı (veri setine girebilir mi)?"""
    return label in FAULT_CLASSES


def validate_label(measurement: Mapping[str, object], label: str,
                   note: Optional[str], reviewer_employee_no: str,
                   existing: Optional[Mapping[str, object]]
                   ) -> Optional[Tuple[int, str]]:
    """Etiket kaydedilebilir mi? Sorun varsa (HTTP kodu, mesaj)."""
    if label not in LABELS:
        return 400, ("Geçersiz tanı. Seçenekler: " + ", ".join(FAULT_CLASSES)
                     + " ya da 'Belirlenemedi'.")

    if existing:
        by = existing.get("labeled_by_name") or "bir mühendis"
        return 409, (f"Bu ölçüm zaten etiketlendi ({by}: "
                     f"{LABELS_TR.get(str(existing.get('expert_label')), '?')}). "
                     "Uzman kararı bir kez verilir.")

    recorded_by = measurement.get("recorded_by_id")
    if recorded_by and str(recorded_by) == str(reviewer_employee_no):
        return 403, ("Dört göz ilkesi: kendi kaydettiğiniz ölçümün tanısını "
                     "etiketleyemezsiniz. Kararı başka bir mühendis vermeli.")

    if label != measurement.get("prediction"):
        if not note or len(note.strip()) < NOTE_MIN_LENGTH:
            reason = ("Belirlenemedi kararında" if label == UNDETERMINED
                      else "Modelden farklı bir tanıda")
            return 400, (f"{reason} gerekçe zorunludur (en az "
                         f"{NOTE_MIN_LENGTH} karakter). Neden farklı "
                         "düşündüğünüz, etiketin kendisi kadar değerlidir.")

    return None


def apply_to_card(card: Dict[str, object],
                  label: Optional[Mapping[str, object]]) -> Dict[str, object]:
    """Filo kartına uzman kararını uygular (kartı yerinde günceller).

    Modelin tahmini ``model_prediction`` alanında HER ZAMAN korunur; böylece
    arayüz "uzman: T3 · model: D1" diyebilir ve bilgi kaybolmaz.
    """
    model_prediction = card.get("prediction")
    card["model_prediction"] = model_prediction
    card["prediction_source"] = "model"
    card["expert_label"] = None
    card["expert_label_tr"] = None
    card["expert_labeled_by"] = None

    if not label:
        return card

    expert = str(label.get("expert_label"))
    card["expert_label"] = expert
    card["expert_label_tr"] = LABELS_TR.get(expert, expert)
    card["expert_labeled_by"] = label.get("labeled_by_name")

    if is_determined(expert):
        # Uzman bir sınıf seçti: tanı artık onun kararı. İnceleme tamamlandı.
        card["prediction"] = expert
        card["prediction_label"] = FAULT_LABELS_TR.get(expert)
        card["prediction_group"] = FAULT_GROUP.get(expert)
        card["prediction_family"] = FAULT_FAMILY.get(expert)
        card["severe"] = expert in SEVERE_FAULTS
        card["prediction_source"] = "expert"
        card["needs_review"] = False
    # "Belirlenemedi": tanı değişmez ve inceleme işareti KORUNUR — uzman da
    # emin değilse vaka hâlâ çözülmemiştir (ör. yeni numune gerekir).
    return card


def agreement_stats(rows: Iterable[Mapping[str, object]]) -> Dict[str, object]:
    """Uzman kararları ile model tahminlerinin karşılaştırması.

    Faz 6.4'ün dersi burada da geçerli: tek bir "uyum oranı" yetmez.
    "T1 yerine T2" ile "D2 yerine Normal" aynı ağırlıkta hata değildir, bu
    yüzden AİLE uyumu (Normal / Termal / Deşarj) ayrıca raporlanır ve
    anlaşmazlıklar model → uzman çiftleri olarak listelenir.
    """
    rows = list(rows)
    determined = [r for r in rows if is_determined(r.get("expert_label"))]  # type: ignore[arg-type]
    agreed = [r for r in determined if r.get("expert_label") == r.get("model_prediction")]
    family_agreed = [
        r for r in determined
        if FAULT_FAMILY.get(str(r.get("expert_label")))
        == FAULT_FAMILY.get(str(r.get("model_prediction")))
    ]

    pairs: Dict[Tuple[str, str], int] = {}
    for r in determined:
        if r.get("expert_label") != r.get("model_prediction"):
            key = (str(r.get("model_prediction")), str(r.get("expert_label")))
            pairs[key] = pairs.get(key, 0) + 1

    # Güvenli sayılan tanıda (≥ eşik değil, burada yalnızca etiketlenen
    # vakalar içinde) modelin yanıldığı durumlar ayrıca sayılır: en
    # tehlikeli hata türü budur.
    severe_missed = [r for r in determined
                     if r.get("expert_label") in SEVERE_FAULTS
                     and r.get("model_prediction") not in SEVERE_FAULTS]

    def rate(part: List[object], whole: List[object]) -> Optional[float]:
        return round(len(part) / len(whole), 3) if whole else None

    return {
        "labeled": len(rows),
        "determined": len(determined),
        "undetermined": len(rows) - len(determined),
        "agreed": len(agreed),
        "agreement_rate": rate(agreed, determined),       # type: ignore[arg-type]
        "family_agreement_rate": rate(family_agreed, determined),  # type: ignore[arg-type]
        "severe_missed_by_model": len(severe_missed),
        "disagreements": [
            {"model": m, "expert": e, "count": n,
             "model_tr": FAULT_LABELS_TR.get(m, m),
             "expert_tr": FAULT_LABELS_TR.get(e, e)}
            for (m, e), n in sorted(pairs.items(), key=lambda kv: -kv[1])
        ],
    }
