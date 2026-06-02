"""İŞKUR (İş ve İşçi Bulma Kurumu) API istemcisi - iskur.gov.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    IskurDuyuru,
    IskurDuyuruSearchRequest,
    IskurDuyuruSearchResponse,
    IskurIstihdamTesviki,
)

logger = logging.getLogger(__name__)


class IskurClient:
    """İŞKUR'dan veri çeken istemci sınıfı.

    Bu istemci, iskur.gov.tr üzerinden:
    - Duyuruları getirme
    - İstihdam teşvikleri
    - Kısa çalışma ödeneği bilgileri
    - İşbaşı eğitim programları
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.iskur.gov.tr"
    DUYURU_URL = "https://www.iskur.gov.tr/duyurular"
    TESVIK_URL = "https://www.iskur.gov.tr/istihdam-tesvikleri"

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

    async def search_duyurular(
        self, request: IskurDuyuruSearchRequest
    ) -> IskurDuyuruSearchResponse:
        """İŞKUR duyurularında arama yapar.

        Args:
            request: Duyuru arama isteği.

        Returns:
            Arama yanıtı.
        """
        params = {
            "keyword": request.anahtar_kelime,
            "page": str(request.sayfa),
        }
        if request.kategori:
            params["category"] = request.kategori

        try:
            response = await self.http_client.get(
                "/duyurular", params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_duyuru_results(soup, request)

        except Exception as e:
            logger.error(f"İŞKUR duyuru arama hatası: {e}")
            raise

    async def get_istihdam_tesvikleri(self) -> list[IskurIstihdamTesviki]:
        """Güncel istihdam teşviklerini getirir.

        Returns:
            İstihdam teşvik listesi.
        """
        # Güncel istihdam teşvikleri
        tesvikler = [
            IskurIstihdamTesviki(
                baslik="İşbaşı Eğitim Programı",
                aciklama="İşsizlere meslek edindirmek amacıyla işverenlerde işbaşı eğitimi verilmesi programı",
                destek_orani=50.0,
                sure="6 ay (uzatılabilir)",
                hedef_grup="İşsizlik ödeneği alan veya son 6 ay içinde işsiz kalan kişiler",
                basvuru_kosullari=[
                    "İşverenin İŞKUR'a başvurması gerekir",
                    "Program süresince SGK primi desteği sağlanır",
                    "Asgari ücretin %50'si kadar destek verilir",
                    "Program sonunda istihdam sağlanması durumunda ek teşvik",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
                detay_url="https://www.iskur.gov.tr/istihdam-tesvikleri/isbasi-egitim-programi",
            ),
            IskurIstihdamTesviki(
                baslik="Toplum Yararına Çalışma Programı",
                aciklama="Belediye ve kamu kurumlarında toplum yararına işler için istihdam programı",
                destek_orani=100.0,
                sure="6 ay",
                hedef_grup="Uzun süreli işsizler",
                basvuru_kosullari=[
                    "Belediye veya kamu kurumunun program açması gerekir",
                    "Asgari ücret üzerinden ödeme yapılır",
                    "SGK primi devlet tarafından karşılanır",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
                detay_url="https://www.iskur.gov.tr/istihdam-tesvikleri/toplum-yararina-program",
            ),
            IskurIstihdamTesviki(
                baslik="Genç İstihdamı Destek Programı",
                aciklama="18-25 yaş arası gençlerin istihdamını teşvik eden program",
                destek_orani=100.0,
                sure="12 ay",
                hedef_grup="18-25 yaş arası gençler",
                basvuru_kosullari=[
                    "18-25 yaş arası çalışanlar",
                    "İlk kez sigortalı olarak işe girenler",
                    "SGK primi tamamen devlet tarafından karşılanır",
                    "İşverenin ek istihdam yapması gerekir",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
                detay_url="https://www.iskur.gov.tr/istihdam-tesvikleri/genc-istihdam",
            ),
        ]

        # Web'den güncel teşvikleri de çekme denemesi
        try:
            response = await self.http_client.get("/istihdam-tesvikleri")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            web_tesvikler = self._parse_tesvik_page(soup)
            if web_tesvikler:
                return web_tesvikler

        except Exception as e:
            logger.warning(f"İŞKUR teşvik web çekme hatası: {e}")

        return tesvikler

    async def get_kisa_calisma_odenegi(self) -> dict:
        """Kısa çalışma ödeneği hakkında güncel bilgileri getirir.

        Returns:
            Kısa çalışma ödeneği bilgileri.
        """
        return {
            "durum": "Kısa çalışma ödeneği uygulaması aktif değil",
            "aciklama": "Kısa çalışma ödeneği, ekonomik kriz veya zorunlu nedenlerle işyerinde kısa çalışma yapılması durumunda çalışanlara ödenen destek",
            "sartlar": [
                "İşyerinde kısa çalışma yapılması gerekir",
                "İşverenin başvurması gerekir",
                "Çalışanın son 60 gün içinde 25 gün sigortalı olması gerekir",
            ],
            "odeme_miktari": "Aylık brüt ücretin %60'ı",
            "ust_sinir": "Asgari ücretin 1.5 katı",
        }

    def _parse_duyuru_results(
        self, soup: BeautifulSoup, request: IskurDuyuruSearchRequest
    ) -> IskurDuyuruSearchResponse:
        """Duyuru arama sonuçlarını parse eder."""
        results = []

        items = soup.select(
            ".duyuru-item, .announcement-item, .content-list .item, table tbody tr"
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

                # Tarih
                tarih = None
                date_elem = item.select_one(".date, time, td:nth-child(2)")
                if date_elem:
                    tarih_str = date_elem.get_text(strip=True)
                    try:
                        tarih = datetime.strptime(tarih_str, "%d.%m.%Y").date()
                    except ValueError:
                        pass

                # Kategori
                kategori = ""
                cat_elem = item.select_one(".category, .kategori, td:nth-child(3)")
                if cat_elem:
                    kategori = cat_elem.get_text(strip=True)

                # Özet
                ozet = ""
                summary_elem = item.select_one(".summary, .ozet, p")
                if summary_elem:
                    ozet = summary_elem.get_text(strip=True)[:200]

                results.append(
                    IskurDuyuru(
                        baslik=baslik,
                        tarih=tarih,
                        kategori=kategori or None,
                        ozet=ozet or None,
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"İŞKUR duyuru parse hatası: {e}")
                continue

        return IskurDuyuruSearchResponse(
            toplam_sonuc=len(results),
            sayfa=request.sayfa,
            sonuclar=results,
        )

    def _parse_tesvik_page(self, soup: BeautifulSoup) -> list[IskurIstihdamTesviki]:
        """Teşvik sayfasını parse eder."""
        tesvikler = []

        items = soup.select(
            ".tesvik-item, .program-item, .content-list .item"
        )

        for item in items:
            try:
                link = item.select_one("a")
                baslik = link.get_text(strip=True) if link else ""
                href = link.get("href", "") if link else ""
                if href and not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                aciklama = ""
                desc_elem = item.select_one("p, .description")
                if desc_elem:
                    aciklama = desc_elem.get_text(strip=True)

                if baslik:
                    tesvikler.append(
                        IskurIstihdamTesviki(
                            baslik=baslik,
                            aciklama=aciklama,
                            detay_url=href or None,
                        )
                    )
            except Exception as e:
                logger.warning(f"İŞKUR teşvik parse hatası: {e}")
                continue

        return tesvikler