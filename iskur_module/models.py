"""İŞKUR (İş ve İşçi Bulma Kurumu) veri modelleri."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class IskurDuyuruSearchRequest(BaseModel):
    """İŞKUR duyuru arama isteği."""
    anahtar_kelime: str = Field(
        ...,
        description="Aranacak anahtar kelime veya ifade",
        min_length=2,
        max_length=500,
    )
    kategori: Optional[str] = Field(
        default=None,
        description="Duyuru kategorisi (teşvik, istihdam, eğitim, vb.)",
    )
    sayfa: int = Field(
        default=1,
        description="Sayfa numarası",
        ge=1,
    )


class IskurDuyuru(BaseModel):
    """İŞKUR duyuru özeti."""
    baslik: str = Field(description="Duyuru başlığı")
    tarih: Optional[date] = Field(default=None, description="Duyuru tarihi")
    kategori: Optional[str] = Field(default=None, description="Duyuru kategorisi")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")


class IskurDuyuruSearchResponse(BaseModel):
    """İŞKUR duyuru arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[IskurDuyuru] = Field(description="Arama sonuçları")


class IskurIstihdamTesviki(BaseModel):
    """İŞKUR istihdam teşvik bilgisi."""
    baslik: str = Field(description="Teşvik başlığı")
    aciklama: str = Field(description="Teşvik açıklaması")
    destek_orani: Optional[float] = Field(default=None, description="Destek oranı (%)")
    sure: Optional[str] = Field(default=None, description="Teşvik süresi")
    hedef_grup: Optional[str] = Field(default=None, description="Hedef grup")
    basvuru_kosullari: list[str] = Field(
        default_factory=list, description="Başvuru koşulları"
    )
    baslangic_tarihi: Optional[date] = Field(
        default=None, description="Başlangıç tarihi"
    )
    bitis_tarihi: Optional[date] = Field(
        default=None, description="Bitiş tarihi"
    )
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")