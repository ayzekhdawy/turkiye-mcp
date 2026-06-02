"""SGK (Sosyal Güvenlik Kurumu) veri modelleri."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class SgkGenelgeSearchRequest(BaseModel):
    """SGK genelge arama isteği."""
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


class SgkGenelge(BaseModel):
    """SGK genelge özeti."""
    baslik: str = Field(description="Genelge başlığı")
    genelge_no: Optional[str] = Field(default=None, description="Genelge numarası")
    tarih: Optional[date] = Field(default=None, description="Yayım tarihi")
    konu: Optional[str] = Field(default=None, description="Genelge konusu")
    ozet: Optional[str] = Field(default=None, description="Kısa özet")
    detay_url: Optional[str] = Field(default=None, description="Detay URL'si")
    pdf_url: Optional[str] = Field(default=None, description="PDF URL'si")


class SgkGenelgeSearchResponse(BaseModel):
    """SGK genelge arama yanıtı."""
    toplam_sonuc: int = Field(description="Toplam sonuç sayısı")
    sayfa: int = Field(description="Mevcut sayfa numarası")
    sonuclar: list[SgkGenelge] = Field(description="Arama sonuçları")


class AsgariUcret(BaseModel):
    """Asgari ücret bilgisi."""
    yil: int = Field(description="Yıl")
    aylik_brut: float = Field(description="Aylık brüt asgari ücret")
    aylik_net: float = Field(description="Aylık net asgari ücret")
    saatlik_brut: float = Field(description="Saatlik brüt asgari ücret")
    gunluk_brut: float = Field(description="Günlük brüt asgari ücret")
    donem: str = Field(description="Dönem (ör: '2025 Yılının İlk 6 Ayı')")


class PrimMatrahi(BaseModel):
    """Prim matrahı bilgisi."""
    yil: int = Field(description="Yıl")
    asgari_prim_matrahi: float = Field(description="Asgari prim matrahı")
    ust_sinir_prim_matrahi: float = Field(description="Üst sınır prim matrahı")
    sgk_isci_premi: float = Field(description="SGK işçi primi oranı (%)")
    sgk_isveren_premi: float = Field(description="SGK işveren primi oranı (%)")
    issizlik_isci_premi: float = Field(description="İşsizlik işçi primi oranı (%)")
    issizlik_isveren_premi: float = Field(description="İşsizlik işveren primi oranı (%)")


class IstihdamTeşvik(BaseModel):
    """İstihdam teşvik bilgisi."""
    baslik: str = Field(description="Teşvik başlığı")
    aciklama: str = Field(description="Teşvik açıklaması")
    destek_orani: Optional[float] = Field(default=None, description="Destek oranı (%)")
    sure: Optional[str] = Field(default=None, description="Teşvik süresi")
    kosullar: list[str] = Field(default_factory=list, description="Teşvik koşulları")
    baslangic_tarihi: Optional[date] = Field(default=None, description="Başlangıç tarihi")
    bitis_tarihi: Optional[date] = Field(default=None, description="Bitiş tarihi")