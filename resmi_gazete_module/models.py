"""Resmi Gazete veri modelleri."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BelgeTuru(str, Enum):
    """Resmi Gazete belge türleri."""
    KANUN = "kanun"
    KANUN_HUKMUNDE_KARARNAME = "khk"
    CUMHURBASKANLIKI_KARAR = "cbk"
    YONETMELIK = "yonetmelik"
    TEBLIG = "teblig"
    SIRKULER = "sirkuler"
    GENELGE = "genelge"
    DUYURU = "duyuru"
    TEBLIGAT = "tebligat"


class ResmiGazeteSearchRequest(BaseModel):
    """Resmi Gazete arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
    )
    belge_turu: Optional[BelgeTuru] = Field(
        default=None,
        description="Belge türü filtresi",
    )
    baslangic_tarihi: Optional[date] = Field(
        default=None,
        description="Arama başlangıç tarihi (YYYY-MM-DD)",
    )
    bitis_tarihi: Optional[date] = Field(
        default=None,
        description="Arama bitiş tarihi (YYYY-MM-DD)",
    )
    sayfa: int = Field(
        default=1,
        description="Sayfa numarası",
        ge=1,
    )
    sayfa_buyuklugu: int = Field(
        default=20,
        description="Sayfa başına sonuç sayısı",
        ge=1,
        le=100,
    )


class ResmiGazeteBulten(BaseModel):
    """Resmi Gazete bülten özeti."""
    baslik: str = Field(description="Bülten başlığı")
    sayi: str = Field(description="Resmi Gazete sayısı")
    tarihi: date = Field(description="Yayım tarihi")
    belge_turu: str = Field(description="Belge türü")
    kurum: Optional[str] = Field(default=None, description="İlgili kurum")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")
    md5: Optional[str] = Field(default=None, description="Belge MD5 hash değeri")


class ResmiGazeteDetay(BaseModel):
    """Resmi Gazete belge detayı."""
    baslik: str = Field(description="Belge başlığı")
    sayi: str = Field(description="Resmi Gazete sayısı")
    tarihi: date = Field(description="Yayım tarihi")
    belge_turu: str = Field(description="Belge türü")
    kurum: Optional[str] = Field(default=None, description="İlgili kurum")
    icerik: str = Field(description="Belge içeriği (Markdown formatında)")
    kaynak_url: str = Field(description="Orijinal kaynak URL'si")
    maddeler: Optional[list[str]] = Field(
        default=None,
        description="Belgedeki madde listesi",
    )


class ResmiGazeteSearchResponse(BaseModel):
    """Resmi Gazete arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    toplam_sayfa: int = Field(description="Toplam sayfa sayısı")
    sonuclar: list[ResmiGazeteBulten] = Field(description="Arama sonuçları")