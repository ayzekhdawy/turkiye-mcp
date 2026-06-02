"""İVD (İnteraktif Vergi Dairesi) veri modelleri."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class MukellefSorgulama(BaseModel):
    """Mükellef sorgulama sonucu."""
    vergi_kimlik_no: str = Field(description="Vergi Kimlik Numarası")
    unvan: Optional[str] = Field(default=None, description="Mükellef unvanı")
    adi: Optional[str] = Field(default=None, description="Adı")
    soyadi: Optional[str] = Field(default=None, description="Soyadı")
    vergi_dairesi: Optional[str] = Field(default=None, description="Vergi Dairesi")
    il: Optional[str] = Field(default=None, description="İl")
    ilce: Optional[str] = Field(default=None, description="İlçe")
    nace_kodu: Optional[str] = Field(default=None, description="NACE kodu")
    faaliyet_konusu: Optional[str] = Field(default=None, description="Faaliyet konusu")
    efatura_mukellef: bool = Field(default=False, description="e-Fatura mükellefi mi?")
    eirsaliye_mukellef: bool = Field(default=False, description="e-İrsaliye mükellefi mi?")
    edefter_mukellef: bool = Field(default=False, description="e-Defter mükellefi mi?")
    kayit_tarihi: Optional[date] = Field(default=None, description="Kayıt tarihi")


class FaturaDogrulama(BaseModel):
    """Fatura doğrulama isteği."""
    fatura_no: str = Field(description="Fatura numarası")
    vergi_kimlik_no: str = Field(description="Vergi Kimlik Numarası")
    fatura_tarihi: Optional[date] = Field(default=None, description="Fatura tarihi")
    tutar: Optional[float] = Field(default=None, description="Fatura tutarı")


class FaturaDogrulamaSonucu(BaseModel):
    """Fatura doğrulama sonucu."""
    fatura_no: str = Field(description="Fatura numarası")
    dogrulama_durumu: str = Field(description="Doğrulama durumu")
    vergi_kimlik_no: str = Field(description="Vergi Kimlik Numarası")
    unvan: Optional[str] = Field(default=None, description="Mükellef unvanı")
    fatura_tarihi: Optional[date] = Field(default=None, description="Fatura tarihi")
    tutar: Optional[float] = Field(default=None, description="Fatura tutarı")
    aciklama: Optional[str] = Field(default=None, description="Ek açıklama")


class BorcSorgulamaSonucu(BaseModel):
    """Borç sorgulama sonucu."""
    vergi_kimlik_no: str = Field(description="Vergi Kimlik Numarası")
    vergi_turu: str = Field(description="Vergi türü")
    donem: str = Field(description="Dönem")
    borc_miktari: float = Field(description="Borç miktarı")
    borc_turu: str = Field(description="Borç türü (asli, gecikme zammı, vb.)")
    son_odeme_tarihi: Optional[date] = Field(default=None, description="Son ödeme tarihi")
    aciklama: Optional[str] = Field(default=None, description="Ek açıklama")