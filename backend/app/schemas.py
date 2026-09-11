"""Pydantic request/response models (drives FastAPI's auto-docs)."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GasReading(BaseModel):
    """The seven dissolved gases, in ppm."""
    H2: float = Field(0, ge=0, description="Hidrojen (ppm)")
    CH4: float = Field(0, ge=0, description="Metan (ppm)")
    C2H6: float = Field(0, ge=0, description="Etan (ppm)")
    C2H4: float = Field(0, ge=0, description="Etilen (ppm)")
    C2H2: float = Field(0, ge=0, description="Asetilen (ppm)")
    CO: float = Field(0, ge=0, description="Karbonmonoksit (ppm)")
    CO2: float = Field(0, ge=0, description="Karbondioksit (ppm)")

    def as_dict(self) -> Dict[str, float]:
        return self.model_dump()


class PredictRequest(BaseModel):
    gases: GasReading
    transformer_id: Optional[str] = None
    transformer_name: Optional[str] = None
    persist: bool = False


class SampleInput(BaseModel):
    """One historical sample for trend analysis."""
    month: float
    gases: GasReading


class TrendRequest(BaseModel):
    samples: List[SampleInput]
    horizon: int = Field(6, ge=1, le=36)


class NameplateIn(BaseModel):
    """Trafo künyesi — hepsi opsiyonel, kısmi güncelleme yapılabilir.

    Alanların hiçbiri zorunlu değil: künye çoğu zaman parça parça girilir
    (saha ekibi seri numarasını sonra bulur). Gönderilmeyen alan
    değiştirilmez, silinmez.
    """
    manufacturer: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=50)
    year_made: Optional[int] = Field(None, ge=1900, le=2100)
    commissioned_at: Optional[str] = Field(
        None, description="YYYY-AA-GG biçiminde devreye alma tarihi")
    hv_kv: Optional[float] = Field(None, gt=0, description="YG gerilimi (kV)")
    lv_kv: Optional[float] = Field(None, gt=0, description="AG gerilimi (kV)")
    vector_group: Optional[str] = Field(None, description="Ör. YNd11")
    cooling: Optional[str] = Field(None, description="ONAN/ONAF/OFAF/ODAF")
    oil_volume_l: Optional[float] = Field(None, gt=0)
    winding_material: Optional[str] = Field(None, description="Cu veya Al")
    insulation_type: Optional[str] = Field(None, description="kraft veya tuk")
    tap_changer_type: Optional[str] = Field(None, description="OLTC/DETC/none")
    tap_min: Optional[int] = None
    tap_max: Optional[int] = None
    tap_step_percent: Optional[float] = Field(None, gt=0)
    rated_hotspot_c: Optional[float] = Field(None, gt=0)
    rated_top_oil_c: Optional[float] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=500)


class TransformerCreate(BaseModel):
    id: str
    name: str
    location: str = ""
    asset_class: str = "MPT"
    mva: Optional[float] = Field(None, gt=0)
    nameplate: Optional[NameplateIn] = None


class OilTestIn(BaseModel):
    """Yağ kalitesi testi girişi — tüm ölçümler opsiyonel.

    Laboratuvarlar her zaman tüm parametreleri ölçmez; furan analizi
    ayrıca istenir ve pahalıdır. Zorunlu tutmak, elindeki kısmi sonucu
    girmek isteyen kullanıcıyı engellerdi. En az bir değer olması yeterli
    (uç nokta kontrol ediyor).
    """
    water_ppm: Optional[float] = Field(None, ge=0, description="Nem (ppm)")
    bdv_kv: Optional[float] = Field(None, ge=0,
                                    description="Delinme gerilimi (kV)")
    acidity_mgkoh_g: Optional[float] = Field(None, ge=0,
                                             description="Asitlik (mg KOH/g)")
    ift_mn_m: Optional[float] = Field(None, ge=0,
                                      description="Arayüzey gerilimi (mN/m)")
    furan_2fal_mgl: Optional[float] = Field(
        None, ge=0, description="2-FAL furan (mg/L) — kağıt yaşlanması")
    color_astm: Optional[float] = Field(None, ge=0, le=8,
                                        description="Renk (ASTM D1500)")
    sampled_at: Optional[str] = Field(None, description="ISO tarih")
    lab: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class ElectricalTestIn(BaseModel):
    """Elektriksel test girişi — tüm ölçümler opsiyonel. (Faz 8.6)

    Sahada dört testin dördü birden nadiren yapılır: TTR ve sargı direnci
    aynı cihazla hızlıca alınır, yalıtım direnci 10 dakika bekler, tan δ
    ayrı bir köprü cihazı ister. Hepsini zorunlu tutmak, elindeki kısmi
    raporu girmek isteyen kullanıcıyı engellerdi.

    ``tap_position`` ölçüm değil BAĞLAMDIR: beklenen sarım oranı kademeye
    göre kayar, bu yüzden TTR girilirken birlikte verilmelidir.
    """
    tap_position: Optional[int] = Field(
        None, ge=-20, le=20, description="Kademe pozisyonu (TTR için bağlam)")

    ttr_a: Optional[float] = Field(None, gt=0, description="A fazı sarım oranı")
    ttr_b: Optional[float] = Field(None, gt=0, description="B fazı sarım oranı")
    ttr_c: Optional[float] = Field(None, gt=0, description="C fazı sarım oranı")

    rw_a_ohm: Optional[float] = Field(None, gt=0, description="A fazı sargı direnci (Ω)")
    rw_b_ohm: Optional[float] = Field(None, gt=0, description="B fazı sargı direnci (Ω)")
    rw_c_ohm: Optional[float] = Field(None, gt=0, description="C fazı sargı direnci (Ω)")
    winding_temp_c: Optional[float] = Field(
        None, ge=-40, le=150, description="Sargı sıcaklığı (°C) — düzeltme için")

    ir_1min_mohm: Optional[float] = Field(
        None, gt=0, description="Yalıtım direnci, 1 dakika (MΩ)")
    ir_10min_mohm: Optional[float] = Field(
        None, gt=0, description="Yalıtım direnci, 10 dakika (MΩ) — PI için")
    insulation_temp_c: Optional[float] = Field(None, ge=-40, le=150)

    tan_delta_pct: Optional[float] = Field(
        None, ge=0, le=100, description="Kayıp faktörü tan δ (%)")
    tan_delta_temp_c: Optional[float] = Field(None, ge=-40, le=150)

    tested_at: Optional[str] = Field(None, description="ISO tarih")
    tested_by: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class VoidTestIn(BaseModel):
    """Bir test kaydını geçersiz işaretleme isteği. (Faz 8.6)

    Gerekçe ZORUNLUDUR. Gerekçesiz bir "geçersiz" damgası, silmekten pek
    farklı olmazdı: kayıt durur ama neden güvenilmediği bilinmez. Asıl
    değer gerekçede — aynı hata tekrarlanıyorsa bunu ancak o gösterir.
    """
    reason: str = Field(..., min_length=5, max_length=300,
                        description="Neden geçersiz? (ör. basamak hatası)")


class UnvoidTestIn(BaseModel):
    """Geçersiz işaretini kaldırma (yanlışlıkla işaretlendiyse)."""
    reason: None = None
