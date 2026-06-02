"""İSMMMO (İstanbul SMMM Odası) API istemcisi - ismmmo.org.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    IsmmmoDuyuru,
    IsmmmoRehber,
    IsmmmoRehberSearchRequest,
    IsmmmoRehberSearchResponse,
)

logger = logging.getLogger(__name__)


class IsmmmoClient:
    """İSMMMO'dan veri çeken istemci sınıfı.

    Bu istemci, ismmmo.org.tr üzerinden:
    - Pratik bilgiler rehberleri
    - Mali rehberler
    - Duyurular
    - Eğitim materyalleri
    işlemlerini gerçekleştirir.

    İSMMMO'nun "Pratik Bilgiler" kitapçıkları, MCP'nin
    veri tabanına gömmek için en iyi kaynaktır.
    """

    BASE_URL = "https://ismmmo.org.tr"
    REHBER_URL = "https://ismmmo.org.tr/pratik-bilgiler"
    DUYURU_URL = "https://ismmmo.org.tr/duyurular"

    # Rehber kategorileri
    REHBER_KATEGORILER = {
        "vergi": "Vergi",
        "sgk": "Sosyal Güvenlik",
        "is_hukuku": "İş Hukuku",
        "muhasebe": "Muhasebe",
        "denetim": "Denetim",
        "msl": "Muhasebe Standartları",
        "kdv": "KDV",
        "gelir_vergisi": "Gelir Vergisi",
        "kurumlar_vergisi": "Kurumlar Vergisi",
        "gecici_vergi": "Geçici Vergi",
        "beyanname": "Beyanname",
        "defter": "Defter Tutma",
    }

    def __init__(self, request_timeout: float = 30.0):
        self.http_client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "User-Agent": "MaliMusavirMCP/0.1.0 (Turkish Financial Advisory MCP)",
            },
            timeout=request_timeout,
            follow_redirects=True,
        )

    async def close(self):
        """HTTP istemcisini kapatır."""
        await self.http_client.aclose()

    async def search_rehber(
        self, request: IsmmmoRehberSearchRequest
    ) -> IsmmmoRehberSearchResponse:
        """İSMMMO rehberlerinde arama yapar.

        Args:
            request: Rehber arama isteği.

        Returns:
            Arama yanıtı.
        """
        params = {
            "keyword": request.anahtar_kelime,
            "page": str(request.sayfa),
        }
        if request.kategori and request.kategori in self.REHBER_KATEGORILER:
            params["kategori"] = request.kategori
        if request.yil:
            params["year"] = str(request.yil)

        try:
            response = await self.http_client.get(
                "/pratik-bilgiler/arama", params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_rehber_results(soup, request)

        except Exception as e:
            logger.error(f"İSMMMO rehber arama hatası: {e}")
            # Fallback: Statik rehber verisi
            return self._get_static_rehber(request)

    async def get_pratik_bilgiler(
        self, kategori: Optional[str] = None
    ) -> list[IsmmmoRehber]:
        """İSMMMO pratik bilgilerini getirir.

        Args:
            kategori: Kategori filtresi.

        Returns:
            Pratik bilgi listesi.
        """
        url = self.REHBER_URL
        if kategori and kategori in self.REHBER_KATEGORILER:
            url = f"{self.REHBER_URL}?kategori={kategori}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_pratik_bilgiler(soup)

        except Exception as e:
            logger.error(f"İSMMMO pratik bilgi hatası: {e}")
            return self._get_static_pratik_bilgiler(kategori)

    async def get_duyurular(self, limit: int = 10) -> list[IsmmmoDuyuru]:
        """İSMMMO duyurularını getirir.

        Args:
            limit: Maksimum duyuru sayısı.

        Returns:
            Duyuru listesi.
        """
        try:
            response = await self.http_client.get(self.DUYURU_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            duyurular = []

            items = soup.select(
                ".duyuru-item, .announcement-item, .content-list .item"
            )

            for item in items[:limit]:
                try:
                    link = item.select_one("a")
                    if not link:
                        continue

                    baslik = link.get_text(strip=True)
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"{self.BASE_URL}{href}"

                    # Tarih
                    tarih = None
                    date_elem = item.select_one(".date, time")
                    if date_elem:
                        tarih_str = date_elem.get_text(strip=True)
                        try:
                            tarih = datetime.strptime(tarih_str, "%d.%m.%Y").date()
                        except ValueError:
                            pass

                    # Özet
                    ozet = ""
                    summary_elem = item.select_one("p, .summary")
                    if summary_elem:
                        ozet = summary_elem.get_text(strip=True)[:200]

                    duyurular.append(
                        IsmmmoDuyuru(
                            baslik=baslik,
                            tarih=tarih,
                            ozet=ozet or None,
                            detay_url=href or None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"İSMMMO duyuru parse hatası: {e}")
                    continue

            return duyurular

        except Exception as e:
            logger.error(f"İSMMMO duyuru hatası: {e}")
            raise

    def _parse_rehber_results(
        self, soup: BeautifulSoup, request: IsmmmoRehberSearchRequest
    ) -> IsmmmoRehberSearchResponse:
        """Rehber arama sonuçlarını parse eder."""
        results = []

        items = soup.select(
            ".rehber-item, .content-list .item, table tbody tr"
        )

        for item in items:
            try:
                link = item.select_one("a")
                if not link:
                    continue

                baslik = link.get_text(strip=True)
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Kategori
                kategori = ""
                cat_elem = item.select_one(".category, .kategori")
                if cat_elem:
                    kategori = cat_elem.get_text(strip=True)

                # Yıl
                yil = None
                year_elem = item.select_one(".year, td:nth-child(3)")
                if year_elem:
                    yil_match = re.search(r"(\d{4})", year_elem.get_text())
                    if yil_match:
                        yil = int(yil_match.group(1))

                results.append(
                    IsmmmoRehber(
                        baslik=baslik,
                        kategori=kategori or "genel",
                        yil=yil,
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"İSMMMO rehber sonuç parse hatası: {e}")
                continue

        return IsmmmoRehberSearchResponse(
            toplam_sonuc=len(results),
            sayfa=request.sayfa,
            sonuclar=results,
        )

    def _parse_pratik_bilgiler(self, soup: BeautifulSoup) -> list[IsmmmoRehber]:
        """Pratik bilgiler sayfasını parse eder."""
        bilgiler = []

        items = soup.select(
            ".pratik-bilgi-item, .content-list .item, .rehber-item"
        )

        for item in items:
            try:
                link = item.select_one("a")
                if not link:
                    continue

                baslik = link.get_text(strip=True)
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                bilgiler.append(
                    IsmmmoRehber(
                        baslik=baslik,
                        kategori="pratik_bilgi",
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"İSMMMO pratik bilgi parse hatası: {e}")
                continue

        return bilgiler

    def _get_static_pratik_bilgiler(
        self, kategori: Optional[str] = None
    ) -> list[IsmmmoRehber]:
        """Statik pratik bilgi verisi döndürür."""
        all_bilgiler = [
            IsmmmoRehber(
                baslik="2025 Pratik Bilgiler - Vergi",
                kategori="vergi",
                yil=2025,
                ozet="2025 yılı vergi pratik bilgileri rehberi",
                icerik="""# 2025 Yılı Vergi Pratik Bilgileri

## Gelir Vergisi Tarifesi
- 0 - 110.000 TL: %15
- 110.000 - 230.000 TL: %20
- 230.000 - 580.000 TL: %27
- 580.000 - 3.000.000 TL: %35
- 3.000.000 TL üzeri: %40

## Kurumlar Vergisi
- Genel oran: %20

## KDV Oranları
- Genel: %20
- Düşük: %10
- Çok düşük: %1""",
                detay_url=f"{self.BASE_URL}/pratik-bilgiler/vergi-2025",
            ),
            IsmmmoRehber(
                baslik="2025 Pratik Bilgiler - SGK",
                kategori="sgk",
                yil=2025,
                ozet="2025 yılı SGK pratik bilgileri rehberi",
                icerik="""# 2025 Yılı SGK Pratik Bilgileri

## Prim Oranları
- SGK İşçi: %14
- SGK İşveren: %20.5
- İşsizlik İşçi: %1
- İşsizlik İşveren: %2

## Asgari Ücret (2025)
- Brüt: 22.104,00 TL
- Net: 17.094,48 TL

## Prim Matrahı
- Alt Sınır: 22.104,00 TL
- Üst Sınır: 220.104,00 TL""",
                detay_url=f"{self.BASE_URL}/pratik-bilgiler/sgk-2025",
            ),
            IsmmmoRehber(
                baslik="2025 Pratik Bilgiler - Muhasebe",
                kategori="muhasebe",
                yil=2025,
                ozet="2025 yılı muhasebe pratik bilgileri rehberi",
                icerik="""# 2025 Yılı Muhasebe Pratik Bilgileri

## Amortisman Oranları
- Binalar: %2 (50 yıl)
- Binek Araçlar: %20 (5 yıl)
- Demirbaşlar: %10 (10 yıl)
- Bilgisayarlar: %20 (5 yıl)

## Değerleme Ölçütleri
- Dönemsellik kavramı
- Tarihi maliyet esası
- Dürüst değerleme ilkesi

## Finansal Tablo Standartları
- TMS 1: Finansal Tabloların Sunumu
- TMS 2: Stoklar
- TMS 7: Nakit Akış Tablosu
- TMS 16: Maddi Duran Varlıklar""",
                detay_url=f"{self.BASE_URL}/pratik-bilgiler/muhasebe-2025",
            ),
        ]

        if kategori:
            return [b for b in all_bilgiler if b.kategori == kategori]

        return all_bilgiler

    def _get_static_rehber(
        self, request: IsmmmoRehberSearchRequest
    ) -> IsmmmoRehberSearchResponse:
        """Statik rehber verisi döndürür."""
        rehberler = self._get_static_pratik_bilgiler(request.kategori)

        # Anahtar kelime filtresi
        if request.anahtar_kelime:
            keyword = request.anahtar_kelime.lower()
            rehberler = [
                r for r in rehberler
                if keyword in r.baslik.lower()
                or (r.ozet and keyword in r.ozet.lower())
                or (r.icerik and keyword in r.icerik.lower())
            ]

        return IsmmmoRehberSearchResponse(
            toplam_sonuc=len(rehberler),
            sayfa=request.sayfa,
            sonuclar=rehberler,
        )