"""GİB (Gelir İdaresi Başkanlığı) veri modelleri."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SirkulerTuru(str, Enum):
    """GİB sirküler türleri."""
    VERGI_SIRKULERI = "vergi_sirkuleri"
    ICGENELGE = "ic_genelge"
    DUYURU = "duyuru"
    TEBLIG = "teblig"


class GibSirkulerSearchRequest(BaseModel):
    """GİB sirküler arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
    )
    sirkuler_turu: Optional[SirkulerTuru] = Field(
        default=None,
        description="Sirküler türü filtresi",
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


class GibSirkuler(BaseModel):
    """GİB sirküler özeti."""
    baslik: str = Field(description="Sirküler başlığı")
    sirkuler_no: Optional[str] = Field(default=None, description="Sirküler numarası")
    tarih: Optional[date] = Field(default=None, description="Yayım tarihi")
    turu: str = Field(description="Sirküler türü")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")
    pdf_url: Optional[str] = Field(default=None, description="PDF URL'si")


class GibSirkulerSearchResponse(BaseModel):
    """GİB sirküler arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[GibSirkuler] = Field(description="Arama sonuçları")


class VergiTakvimiOge(BaseModel):
    """Vergi takvimi öğesi."""
    vergi_turu: str = Field(description="Vergi türü (Gelir, KDV, vb.)")
    donem: str = Field(description="Dönem (Ocak, Şubat, vb.)")
    beyanname_tarihi: date = Field(description="Beyanname verme son tarihi")
    odeme_tarihi: date = Field(description="Ödeme son tarihi")
    aciklama: Optional[str] = Field(default=None, description="Ek açıklama")
    mukellef_turu: str = Field(
        default="genel",
        description="Mükellef türü (genel, işveren, serbest, vb.)",
    )


class VergiTakvimiDonem(BaseModel):
    """Vergi takvimi dönem bilgisi."""
    yil: int = Field(description="Yıl")
    ay: str = Field(description="Ay adı")
    ogeler: list[VergiTakvimiOge] = Field(description="Dönem öğeleri")