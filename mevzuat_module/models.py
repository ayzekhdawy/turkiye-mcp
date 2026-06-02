"""Mevzuat veri modelleri."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MevzuatTuru(str, Enum):
    """Mevzuat türleri."""
    KANUN = "kanun"
    KHK = "khk"
    CUMHURBASKANLIKI_KARARNAME = "cbk"
    YONETMELIK = "yonetmelik"
    TEBLIG = "teblig"
    YONERGE = "yonerge"
    GENELGE = "genelge"
    BUTCE_KANUNU = "butce_kanunu"


class MevzuatSearchRequest(BaseModel):
    """Mevzuat arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
    )
    mevzuat_turu: Optional[MevzuatTuru] = Field(
        default=None,
        description="Mevzuat türü filtresi",
    )
    yil: Optional[int] = Field(
        default=None,
        description="Yıl filtresi",
        ge=1920,
        le=2030,
    )
    sayfa: int = Field(
        default=1,
        description="Sayfa numarası",
        ge=1,
    )


class MevzuatMadde(BaseModel):
    """Mevzuat maddesi."""
    madde_no: str = Field(description="Madde numarası")
    madde_adi: Optional[str] = Field(default=None, description="Madde başlığı")
    icerik: str = Field(description="Madde içeriği")
    degisiklik_var: bool = Field(
        default=False,
        description="Maddede değişiklik yapılıp yapılmadığı",
    )
    yururlukten_kalkma: bool = Field(
        default=False,
        description="Yürürlükten kaldırılıp kaldırılmadığı",
    )


class MevzuatDetay(BaseModel):
    """Mevzuat detay bilgisi."""
    baslik: str = Field(description="Mevzuat başlığı")
    mevzuat_turu: str = Field(description="Mevzuat türü")
    resmi_gazete_sayisi: Optional[str] = Field(
        default=None, description="Resmi Gazete sayısı"
    )
    resmi_gazete_tarihi: Optional[date] = Field(
        default=None, description="Resmi Gazete tarihi"
    )
    yururluk_tarihi: Optional[date] = Field(
        default=None, description="Yürürlük tarihi"
    )
    mevzuat_no: Optional[str] = Field(default=None, description="Mevzuat numarası")
    icerik: str = Field(description="Mevzuat tam metni (Markdown formatında)")
    maddeler: list[MevzuatMadde] = Field(
        default_factory=list, description="Mevzuat maddeleri"
    )
    kaynak_url: str = Field(description="Kaynak URL")
    birlestirilmis_metin: bool = Field(
        default=True,
        description="Birleştirilmiş metin mi?",
    )


class MevzuatSearchResponse(BaseModel):
    """Mevzuat arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[dict] = Field(description="Arama sonuçları")
    anahtar_kelime: str = Field(description="Aranan anahtar kelime")