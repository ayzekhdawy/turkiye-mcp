"""TÜRMOB veri modelleri."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TurmobSirkulerSearchRequest(BaseModel):
    """TÜRMOB sirküler arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
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


class TurmobSirkuler(BaseModel):
    """TÜRMOB sirküler özeti."""
    baslik: str = Field(description="Sirküler başlığı")
    sirkuler_no: Optional[str] = Field(default=None, description="Sirküler numarası")
    tarih: Optional[date] = Field(default=None, description="Yayım tarihi")
    konu: Optional[str] = Field(default=None, description="Sirküler konusu")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")
    pdf_url: Optional[str] = Field(default=None, description="PDF URL'si")


class TurmobSirkulerSearchResponse(BaseModel):
    """TÜRMOB sirküler arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[TurmobSirkuler] = Field(description="Arama sonuçları")


class TurmobPratikBilgi(BaseModel):
    """TÜRMOB pratik bilgi."""
    baslik: str = Field(description="Bilgi başlığı")
    kategori: str = Field(description="Bilgi kategorisi (vergi, sgk, iş hukuku, vb.)")
    icerik: str = Field(description="Bilgi içeriği (Markdown formatında)")
    guncelleme_tarihi: Optional[date] = Field(default=None, description="Güncelleme tarihi")
    kaynak_url: Optional[str] = Field(default=None, description="Kaynak URL'si")