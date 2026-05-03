from datetime import date
from pydantic import BaseModel, Field
from typing import Optional


class ApartmentListing(BaseModel):
    id: str
    title: str
    price_chf: float
    neighborhood: str
    address: Optional[str] = None
    link: str
    available_from: Optional[date] = None
    size_m2: Optional[float] = None
    rooms: Optional[float] = None
    source: str
    furnished: bool = True
    description_snippet: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)  # for debugging
