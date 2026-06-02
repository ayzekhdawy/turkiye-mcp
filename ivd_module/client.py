"""İVD (İnteraktif Vergi Dairesi) API istemcisi - ivd.gib.gov.tr üzerinden veri çekme."""

import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    BorcSorgulamaSonucu,
    FaturaDogrulama,
    FaturaDogrulamaSonucu,
    MukellefSorgulama,
)

logger = logging.getLogger(__name__)


class IvdClient:
    """İnteraktif Vergi Dairesi'nden veri çeken istemci sınıfı.

    Bu istemci, ivd.gib.gov.tr üzerinden:
    - Mükellef sorgulama (şifresiz)
    - e-Fatura/e-İrsaliye mükellef listesi sorgulama
    - Fatura doğrulama
    işlemlerini gerçekleştirir.

    Not: Borç sorgulama gibi kimlik doğrulama gerektiren
    işlemler için kullanıcı credential'ları gereklidir.
    """

    BASE_URL = "https://ivd.gib.gov.tr"
    EFATURA_LIST_URL = "https://ebelge.gib.gov.tr/api/v1"

    def __init__(self, request_timeout: float = 30.0):
        self.http_client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "User-Agent": "MaliMusavirMCP/0.1.0 (Turkish Financial Advisory MCP)",
                "Content-Type": "application/json",
            },
            timeout=request_timeout,
            follow_redirects=True,
        )

    async def close(self):
        """HTTP istemcisini kapatır."""
        await self.http_client.aclose()

    async def check_efatura_taxpayer(
        self, vergi_kimlik_no: str
    ) -> MukellefSorgulama:
        """e-Fatura mükellefi olup olmadığını sorgular.

        Bu işlem şifresiz olarak yapılabilir.

        Args:
            vergi_kimlik_no: Vergi Kimlik Numarası (10 veya 11 haneli).

        Returns:
            Mükellef sorgulama sonucu.
        """
        # VKN formatını doğrula
        vkn = vergi_kimlik_no.replace(" ", "").replace("-", "")
        if not vkn.isdigit() or len(vkn) not in (10, 11):
            raise ValueError(
                f"Geçersiz VKN/TCKN: {vergi_kimlik_no}. "
                "10 haneli VKN veya 11 haneli TCKN giriniz."
            )

        try:
            # e-Fatura mükellef listesi API'si
            url = f"{self.EFATURA_LIST_URL}/mukellef/{vkn}"
            response = await self.http_client.get(url)

            if response.status_code == 200:
                data = response.json()
                return MukellefSorgulama(
                    vergi_kimlik_no=vkn,
                    unvan=data.get("unvan"),
                    adi=data.get("adi"),
                    soyadi=data.get("soyadi"),
                    vergi_dairesi=data.get("vergiDairesi"),
                    il=data.get("il"),
                    ilce=data.get("ilce"),
                    nace_kodu=data.get("naceKodu"),
                    faaliyet_konusu=data.get("faaliyetKonusu"),
                    efatura_mukellef=data.get("efaturaMukellef", False),
                    eirsaliye_mukellef=data.get("eirsaliyeMukellef", False),
                    edefter_mukellef=data.get("edefterMukellef", False),
                )

            # Fallback: Web scraping yöntemi
            return await self._check_efatura_web(vkn)

        except httpx.HTTPStatusError as e:
            logger.warning(f"e-Fatura sorgulama HTTP hatası: {e}")
            # Web scraping fallback
            return await self._check_efatura_web(vkn)
        except Exception as e:
            logger.error(f"e-Fatura sorgulama hatası: {e}")
            raise

    async def _check_efatura_web(self, vkn: str) -> MukellefSorgulama:
        """Web scraping ile e-Fatura mükellef sorgulama (fallback).

        Args:
            vkn: Vergi Kimlik Numarası.

        Returns:
            Mükellef sorgulama sonucu.
        """
        try:
            response = await self.http_client.post(
                "/tvd-server/controllers/inspections/api",
                json={
                    "vkn": vkn,
                    "operation": "mukellefSorgula",
                },
            )
            response.raise_for_status()

            data = response.json()
            return MukellefSorgulama(
                vergi_kimlik_no=vkn,
                unvan=data.get("unvan"),
                vergi_dairesi=data.get("vergiDairesi"),
                il=data.get("il"),
                efatura_mukellef=data.get("efaturaMukellef", False),
                eirsaliye_mukellef=data.get("eirsaliyeMukellef", False),
                edefter_mukellef=data.get("edefterMukellef", False),
            )

        except Exception as e:
            logger.error(f"e-Fatura web sorgulama hatası: {e}")
            return MukellefSorgulama(vergi_kimlik_no=vkn)

    async def verify_invoice(
        self, fatura: FaturaDogrulama
    ) -> FaturaDogrulamaSonucu:
        """Fatura doğrulama işlemi yapar.

        Args:
            fatura: Fatura doğrulama isteği.

        Returns:
            Fatura doğrulama sonucu.
        """
        try:
            url = f"{self.EFATURA_LIST_URL}/fatura/dogrula"
            payload = {
                "faturaNo": fatura.fatura_no,
                "vkn": fatura.vergi_kimlik_no,
            }

            if fatura.fatura_tarihi:
                payload["tarih"] = fatura.fatura_tarihi.isoformat()
            if fatura.tutar:
                payload["tutar"] = fatura.tutar

            response = await self.http_client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                return FaturaDogrulamaSonucu(
                    fatura_no=fatura.fatura_no,
                    dogrulama_durumu=data.get("durum", "Sorgulanamadı"),
                    vergi_kimlik_no=fatura.vergi_kimlik_no,
                    unvan=data.get("unvan"),
                    fatura_tarihi=fatura.fatura_tarihi,
                    tutar=fatura.tutar,
                    aciklama=data.get("aciklama"),
                )

            return FaturaDogrulamaSonucu(
                fatura_no=fatura.fatura_no,
                dogrulama_durumu="Doğrulanamadı",
                vergi_kimlik_no=fatura.vergi_kimlik_no,
                aciklama=f"HTTP {response.status_code}: Doğrulama yapılamadı",
            )

        except Exception as e:
            logger.error(f"Fatura doğrulama hatası: {e}")
            return FaturaDogrulamaSonucu(
                fatura_no=fatura.fatura_no,
                dogrulama_durumu="Hata",
                vergi_kimlik_no=fatura.vergi_kimlik_no,
                aciklama=str(e),
            )

    async def search_efatura_taxpayers(
        self, unvan: str, il: Optional[str] = None
    ) -> list[MukellefSorgulama]:
        """e-Fatura mükellefleri arasında arama yapar.

        Args:
            unvan: Mükellef unvanında aranacak ifade.
            il: İl filtresi (opsiyonel).

        Returns:
            Mükellef listesi.
        """
        try:
            url = f"{self.EFATURA_LIST_URL}/mukellef/ara"
            payload = {"unvan": unvan}
            if il:
                payload["il"] = il

            response = await self.http_client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                results = []

                for item in data.get("results", data if isinstance(data, list) else []):
                    results.append(
                        MukellefSorgulama(
                            vergi_kimlik_no=item.get("vkn", item.get("vergiKimlikNo", "")),
                            unvan=item.get("unvan"),
                            vergi_dairesi=item.get("vergiDairesi"),
                            il=item.get("il"),
                            efatura_mukellef=True,
                            eirsaliye_mukellef=item.get("eirsaliyeMukellef", False),
                            edefter_mukellef=item.get("edefterMukellef", False),
                        )
                    )

                return results[:20]  # Maksimum 20 sonuç

            return []

        except Exception as e:
            logger.error(f"e-Fatura mükellef arama hatası: {e}")
            return []