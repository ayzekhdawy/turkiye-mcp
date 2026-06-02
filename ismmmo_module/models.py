"""İSMMMO (İstanbul SMMM Odası) veri modelleri."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class IsmmmoRehberSearchRequest(BaseModel):
    """İSMMMO rehber arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
    )
    kategori: Optional[str] = Field(
        default=None,
        description="Rehber kategorisi (vergi, sgk, iş hukuku, muhasebe, vb.)",
    )
    yil: Optional[int] = Field(
        default=None,
        description="Yıl filtresi",
        ge=2000,
        le=2030,
    )
    sayfa: int = Field(
        default=1,
        description="Sayfa numarası",
        ge=1,
    )


class IsmmmoRehber(BaseModel):
    """İSMMMO rehber özeti."""
    baslik: str = Field(description="Rehber başlığı")
    kategori: str = Field(description="Rehber kategorisi")
    yil: Optional[int] = Field(default=None, description="Rehber yılı")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    icerik: Optional[str] = Field(default=None, description="Rehber içeriği (Markdown)")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")
    pdf_url: Optional[str] = Field(default=None, description="PDF URL'si")


class IsmmmoRehberSearchResponse(BaseModel):
    """İSMMMO rehber arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[IsmmmoRehber] = Field(description="Arama sonuçları")


class IsmmmoDuyuru(BaseModel):
    """İSMMMO duyuru özeti."""
    baslik: str = Field(description="Duyuru başlığı")
    tarih: Optional[date] = Field(default=None, description="Duyuru tarihi")
    kategori: Optional[str] = Field(default=None, description="Duyuru kategorisi")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")