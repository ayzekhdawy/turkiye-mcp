"""SGK (Sosyal Güvenlik Kurumu) API istemcisi - sgk.gov.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    AsgariUcret,
    IstihdamTeşvik,
    PrimMatrahi,
    SgkGenelge,
    SgkGenelgeSearchRequest,
    SgkGenelgeSearchResponse,
)

logger = logging.getLogger(__name__)


class SgkClient:
    """Sosyal Güvenlik Kurumu'ndan veri çeken istemci sınıfı.

    Bu istemci, sgk.gov.tr üzerinden:
    - SGK genelgeleri arama ve getirme
    - Asgari ücret bilgileri
    - Prim matrahı oranları
    - İstihdam teşvikleri
    - İşveren duyuruları
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.sgk.gov.tr"
    GENELGE_URL = "https://www.sgk.gov.tr/Genelge"

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

    async def search_genelge(
        self, request: SgkGenelgeSearchRequest
    ) -> SgkGenelgeSearchResponse:
        """SGK genelgelerinde arama yapar.

        Args:
            request: Genelge arama isteği.

        Returns:
            Arama yanıtı.
        """
        params = {
            "keyword": request.anahtar_kelime,
            "page": str(request.sayfa),
        }
        if request.yil:
            params["year"] = str(request.yil)

        try:
            response = await self.http_client.get(
                "/Genelge/Arama", params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_genelge_results(soup, request)

        except Exception as e:
            logger.error(f"SGK genelge arama hatası: {e}")
            raise

    async def get_asgari_ucret(self, yil: Optional[int] = None) -> AsgariUcret:
        """Asgari ücret bilgilerini getirir.

        Args:
            yil: Yıl. None ise cari yıl kullanılır.

        Returns:
            Asgari ücret bilgisi.
        """
        if yil is None:
            yil = date.today().year

        # 2025 yılı asgari ücret bilgileri (güncellenebilir)
        asgari_ucret_data = {
            2025: AsgariUcret(
                yil=2025,
                aylik_brut=22_104.00,
                aylik_net=16_942.56,
                saatlik_brut=142.36,
                gunluk_brut=1_138.87,
                donem="2025 Yılı",
            ),
            2024: AsgariUcret(
                yil=2024,
                aylik_brut=16_006.50,
                aylik_net=12_596.40,
                saatlik_brut=103.04,
                gunluk_brut=824.30,
                donem="2024 Yılı İkinci Altı Ayı",
            ),
        }

        if yil in asgari_ucret_data:
            return asgari_ucret_data[yil]

        # Web'den çekme denemesi
        try:
            response = await self.http_client.get(
                "/Istatistikler/AsgariUcret"
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_asgari_ucret(soup, yil)
        except Exception as e:
            logger.warning(f"Asgari ücret web çekme hatası: {e}")
            raise ValueError(f"{yil} yılı asgari ücret bilgisi bulunamadı.")

    async def get_prim_matrahi(self, yil: Optional[int] = None) -> PrimMatrahi:
        """Prim matrahı bilgilerini getirir.

        Args:
            yil: Yıl. None ise cari yıl kullanılır.

        Returns:
            Prim matrahı bilgisi.
        """
        if yil is None:
            yil = date.today().year

        # 2025 yılı prim matrahı bilgileri
        prim_data = {
            2025: PrimMatrahi(
                yil=2025,
                asgari_prim_matrahi=22_104.00,
                ust_sinir_prim_matrahi=220_104.00,
                sgk_isci_premi=14.0,
                sgk_isveren_premi=20.5,
                issizlik_isci_premi=1.0,
                issizlik_isveren_premi=2.0,
            ),
            2024: PrimMatrahi(
                yil=2024,
                asgari_prim_matrahi=16_006.50,
                ust_sinir_prim_matrahi=160_065.00,
                sgk_isci_premi=14.0,
                sgk_isveren_premi=20.5,
                issizlik_isci_premi=1.0,
                issizlik_isveren_premi=2.0,
            ),
        }

        if yil in prim_data:
            return prim_data[yil]

        raise ValueError(f"{yil} yılı prim matrahı bilgisi bulunamadı.")

    async def get_istihdam_tesvikleri(self) -> list[IstihdamTeşvik]:
        """Güncel istihdam teşviklerini getirir.

        Returns:
            İstihdam teşvik listesi.
        """
        # Güncel istihdam teşvikleri
        tesvikler = [
            IstihdamTeşvik(
                baslik="İşbaşı Eğitim Programı",
                aciklama="İşsizlere meslek edindirmek amacıyla işverenlerde işbaşı eğitimi verilmesi",
                destek_orani=50.0,
                sure="6 ay",
                kosullar=[
                    "İşsizlik ödeneği almakta olan veya son 6 ay içinde işsiz kalan kişiler",
                    "İşverenin SGK primi desteği",
                    "Aylık asgari ücretin %50'si kadar destek",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
            ),
            IstihdamTeşvik(
                baslik="Genç İstihdamı Teşvik Programı",
                aciklama="18-25 yaş arası gençlerin istihdamını teşvik eden program",
                destek_orani=100.0,
                sure="12 ay",
                kosullar=[
                    "18-25 yaş arası çalışanlar",
                    "İlk kez işe giren gençler",
                    "SGK primi tamamen devlet tarafından karşılanır",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
            ),
            IstihdamTeşvik(
                baslik="Kısa Çalışma Ödeneği",
                aciklama="Ekonomik kriz dönemlerinde işverenlerin kısa çalışma yapmasına olanak tanıyan destek",
                destek_orani=60.0,
                sure="3 ay (uzatılabilir)",
                kosullar=[
                    "Genel ekonomik kriz veya zorunlu nedenlerle kısa çalışma",
                    "Çalışma süresinin 1/3 oranında azaltılması",
                    "SGK primi desteği",
                ],
            ),
            IstihdamTeşvik(
                baslik="İşveren SGK Prim Teşviği (4447 sayılı Kanun)",
                aciklama="Yeni işe alınan çalışanlar için SGK prim teşviği",
                destek_orani=31.5,
                sure="Ay",
                kosullar=[
                    "Sigortalı sayısını artıran işverenler",
                    "Ek sigortalılar için SGK primi desteği",
                    "Aylık asgari ücret üzerinden hesaplanır",
                ],
                baslangic_tarihi=date(2024, 1, 1),
                bitis_tarihi=date(2025, 12, 31),
            ),
        ]

        return tesvikler

    def _parse_genelge_results(
        self, soup: BeautifulSoup, request: SgkGenelgeSearchRequest
    ) -> SgkGenelgeSearchResponse:
        """Genelge arama sonuçlarını parse eder."""
        results = []

        items = soup.select(
            ".genelge-item, .search-result, .content-list .item, table tbody tr"
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

                # Genelge no
                genelge_no = ""
                no_elem = item.select_one(".genelge-no, td:nth-child(3)")
                if no_elem:
                    genelge_no = no_elem.get_text(strip=True)

                results.append(
                    SgkGenelge(
                        baslik=baslik,
                        genelge_no=genelge_no or None,
                        tarih=tarih,
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"SGK genelge parse hatası: {e}")
                continue

        total = len(results)

        return SgkGenelgeSearchResponse(
            toplam_sonuc=total,
            sayfa=request.sayfa,
            sonuclar=results,
        )

    def _parse_asgari_ucret(self, soup: BeautifulSoup, yil: int) -> AsgariUcret:
        """Asgari ücret sayfasını parse eder."""
        # Tablolardan asgari ücret bilgilerini çıkar
        tables = soup.select("table")

        for table in tables:
            rows = table.select("tr")
            for row in rows:
                cells = row.select("td, th")
                text = " ".join(c.get_text(strip=True) for c in cells)

                # Brüt asgari ücret
                brut_match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:TL|₺)", text)
                if brut_match and "brüt" in text.lower():
                    brut = float(brut_match.group(1).replace(".", "").replace(",", "."))
                    return AsgariUcret(
                        yil=yil,
                        aylik_brut=brut,
                        aylik_net=0,  # Parse edilemedi
                        saatlik_brut=0,
                        gunluk_brut=0,
                        donem=f"{yil} Yılı",
                    )

        raise ValueError(f"Asgari ücret bilgisi parse edilemedi: {yil}")