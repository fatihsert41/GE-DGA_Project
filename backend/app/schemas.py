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


class TransformerCreate(BaseModel):
    id: str
    name: str
    location: str = ""
