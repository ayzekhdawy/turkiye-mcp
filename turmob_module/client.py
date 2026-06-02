"""TÜRMOB API istemcisi - turmob.org.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    TurmobPratikBilgi,
    TurmobSirkuler,
    TurmobSirkulerSearchRequest,
    TurmobSirkulerSearchResponse,
)

logger = logging.getLogger(__name__)


class TurmobClient:
    """TÜRMOB'dan veri çeken istemci sınıfı.

    Bu istemci, turmob.org.tr üzerinden:
    - Sirküler arama ve getirme
    - Pratik bilgiler
    - Mevzuat açıklamaları
    - Mesleki duyurular
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.turmob.org.tr"
    SIRKULER_URL = "https://www.turmob.org.tr/Sirkuler"
    PRATIK_BILGI_URL = "https://www.turmob.org.tr/PratikBilgiler"

    # Pratik bilgi kategorileri
    PRATIK_BILGI_KATEGORILER = {
        "vergi": "Vergi",
        "sgk": "Sosyal Güvenlik",
        "is_hukuku": "İş Hukuku",
        "muhasebe": "Muhasebe",
        "denetim": "Denetim",
        "kdv": "KDV",
        "gelir_vergisi": "Gelir Vergisi",
        "kurumlar_vergisi": "Kurumlar Vergisi",
        "damga_vergisi": "Damga Vergisi",
        "stopaj": "Stopaj",
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

    async def search_sirkuler(
        self, request: TurmobSirkulerSearchRequest
    ) -> TurmobSirkulerSearchResponse:
        """TÜRMOB sirkülerlerinde arama yapar.

        Args:
            request: Sirküler arama isteği.

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
                "/Sirkuler/Arama", params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_sirkuler_results(soup, request)

        except Exception as e:
            logger.error(f"TÜRMOB sirküler arama hatası: {e}")
            raise

    async def get_pratik_bilgiler(
        self, kategori: Optional[str] = None
    ) -> list[TurmobPratikBilgi]:
        """TÜRMOB pratik bilgilerini getirir.

        Mali müşavirler için en değerli veri kaynaklarından biri:
        KDV oranları, stopaj oranları, damga vergisi, asgari geçim
        indirimi gibi pratik hesaplama bilgileri.

        Args:
            kategori: Kategori filtresi (vergi, sgk, muhasebe, vb.).

        Returns:
            Pratik bilgi listesi.
        """
        url = self.PRATIK_BILGI_URL
        if kategori and kategori in self.PRATIK_BILGI_KATEGORILER:
            url = f"{self.PRATIK_BILGI_URL}?kategori={kategori}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_pratik_bilgiler(soup)

        except Exception as e:
            logger.error(f"TÜRMOB pratik bilgi hatası: {e}")
            # Fallback: Statik pratik bilgiler
            return self._get_static_pratik_bilgiler(kategori)

    async def get_recent_sirkuler(self, limit: int = 10) -> list[TurmobSirkuler]:
        """Son yayımlanan TÜRMOB sirkülerlerini getirir.

        Args:
            limit: Maksimum sirküler sayısı.

        Returns:
            Sirküler listesi.
        """
        try:
            response = await self.http_client.get(self.SIRKULER_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            items = soup.select(
                ".sirkuler-item, .content-list .item, table tbody tr"
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
                    date_elem = item.select_one(".date, time, td:nth-child(2)")
                    if date_elem:
                        tarih_str = date_elem.get_text(strip=True)
                        try:
                            tarih = datetime.strptime(tarih_str, "%d.%m.%Y").date()
                        except ValueError:
                            pass

                    # Sirküler no
                    sirkuler_no = ""
                    no_elem = item.select_one(".sirkuler-no, td:nth-child(3)")
                    if no_elem:
                        sirkuler_no = no_elem.get_text(strip=True)

                    results.append(
                        TurmobSirkuler(
                            baslik=baslik,
                            sirkuler_no=sirkuler_no or None,
                            tarih=tarih,
                            detay_url=href or None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"TÜRMOB sirküler parse hatası: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"TÜRMOB son sirküler hatası: {e}")
            raise

    def _parse_sirkuler_results(
        self, soup: BeautifulSoup, request: TurmobSirkulerSearchRequest
    ) -> TurmobSirkulerSearchResponse:
        """Sirküler arama sonuçlarını parse eder."""
        results = []

        items = soup.select(
            ".sirkuler-item, .content-list .item, table tbody tr"
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

                # Sirküler no
                sirkuler_no = ""
                no_elem = item.select_one(".sirkuler-no, td:nth-child(3)")
                if no_elem:
                    sirkuler_no = no_elem.get_text(strip=True)

                # Konu
                konu = ""
                konu_elem = item.select_one(".konu, td:nth-child(4)")
                if konu_elem:
                    konu = konu_elem.get_text(strip=True)

                results.append(
                    TurmobSirkuler(
                        baslik=baslik,
                        sirkuler_no=sirkuler_no or None,
                        tarih=tarih,
                        konu=konu or None,
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"TÜRMOB sirküler sonuç parse hatası: {e}")
                continue

        return TurmobSirkulerSearchResponse(
            toplam_sonuc=len(results),
            sayfa=request.sayfa,
            sonuclar=results,
        )

    def _parse_pratik_bilgiler(self, soup: BeautifulSoup) -> list[TurmobPratikBilgi]:
        """Pratik bilgiler sayfasını parse eder."""
        bilgiler = []

        items = soup.select(
            ".pratik-bilgi-item, .content-list .item, table tbody tr"
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
                    TurmobPratikBilgi(
                        baslik=baslik,
                        kategori="genel",
                        icerik="",
                        detay_url=href,
                    )
                )
            except Exception as e:
                logger.warning(f"TÜRMOB pratik bilgi parse hatası: {e}")
                continue

        return bilgiler

    def _get_static_pratik_bilgiler(
        self, kategori: Optional[str] = None
    ) -> list[TurmobPratikBilgi]:
        """Statik pratik bilgi verisi döndürür.

        Web sitesinden veri alınamadığında fallback olarak kullanılır.
        """
        all_bilgiler = [
            TurmobPratikBilgi(
                baslik="2025 Yılı KDV Oranları",
                kategori="kdv",
                icerik="""# 2025 Yılı KDV Oranları

## Genel KDV Oranları
- **%20**: Genel oran (teslim ve hizmetler)
- **%10**: Oranı düşürülen işlemler (gıda, ilaç, temel ihtiyaç maddeleri)
- **%1**: Çok düşük oran (konut kira, bazı gıda maddeleri)

## Önemli KDV İstisnaları
- İhracat teslimleri (%0)
- Yolcu taşımacılığı (uluslararası)
- Altın, gümüş teslimleri (Borsa'da)
- Konut teslimleri (150 m²'ye kadar %1, sonrası %20)

## KDV Tevkifatı Oranları
- %20 oranında KDV'ye tabi işlemlerde %10/20
- %10 oranında KDV'ye tabi işlemlerde %5/10""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı Stopaj Oranları",
                kategori="stopaj",
                icerik="""# 2025 Yılı Stopaj Oranları

## Gelir Vergisi Stopaj Oranları
- **%25**: Serbest meslek kazançları (genel)
- **%20**: Kâr payı, menkul kıymet gelirleri
- **%18**: Serbest bölge çalışanları
- **%15**: Ticari reklâm gelirleri
- **%10**: Basit usulde vergiye tabi mükelleflerden yapılan alışlar
- **%5**: Kira stopajı (konut)
- **%2**: Yeminli mali müşavirlik bedelleri

## KDV Stopaj Oranları
- **2/10**: Genel KDV tevkifat oranı
- **4/10**: Yüksek tevkifat oranı

## Önemli Notlar
- 2025 yılı için gelir vergisi tarifesinde değişiklik yapılmıştır
- Asgari geçim indirimi oranları güncellenmiştir""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı Damga Vergisi Oranları",
                kategori="vergi",
                icerik="""# 2025 Yılı Damga Vergisi Oranları

## Binde Bir (‰1) Oranında Damga Vergisi
- Mukavelenameler
- İhale dokümanları
- Teminat mektupları

## Binde Beş (‰5) Oranında Damga Vergisi
- Kredi mektupları
- Teminat mektupları (belirli tutar üstü)

## Maktu Damga Vergisi
- Binek araç ruhsatnamesi: 4.420,00 TL
- Ticari araç ruhsatnamesi: 8.840,00 TL

## İstisnalar
- Yurt dışından getirilen belgeler (belirli şartlar altında)
- Kıymetli evrakın devri (belirli şartlar altında)""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı SGK Prim Oranları",
                kategori="sgk",
                icerik="""# 2025 Yılı SGK Prim Oranları

## Sigorta Prim Oranları
- **SGK İşçi Payı**: %14
- **SGK İşveren Payı**: %20.5
- **İşsizlik İşçi Payı**: %1
- **İşsizlik İşveren Payı**: %2

## Toplam Prim Oranları
- **Genel Toplam**: %37.5 (İşçi %15 + İşveren %22.5)

## Prim Matrahı Sınırları (2025)
- **Asgari Prim Matrahı**: 22.104,00 TL (Asgari ücret)
- **Üst Sınır Prim Matrahı**: 220.104,00 TL (Asgari ücretin 10 katı)

## Asgari Ücret Üzerinden Prim Tutarları
- **SGK İşçi Primi**: 3.094,56 TL
- **SGK İşveren Primi**: 4.531,32 TL
- **İşsizlik İşçi Primi**: 221,04 TL
- **İşsizlik İşveren Primi**: 442,08 TL""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı Gelir Vergisi Tarifesi",
                kategori="vergi",
                icerik="""# 2025 Yılı Gelir Vergisi Tarifesi

## Ücret Gelirleri Tarifesi
| Dilim | Tutar | Oran |
|-------|-------|------|
| 1. Dilim | 0 - 110.000 TL | %15 |
| 2. Dilim | 110.000 - 230.000 TL | %20 |
| 3. Dilim | 230.000 - 580.000 TL | %27 |
| 4. Dilim | 580.000 - 3.000.000 TL | %35 |
| 5. Dilim | 3.000.000 TL üzeri | %40 |

## Serbest Bölge Çalışanları
- Sadece %18 oranında gelir vergisi stopajı

## Önemli Notlar
- Asgari geçim indirimi tutarları güncellenmiştir
- Damga vergisi istisna tutarı güncellenmiştir""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı Kurumlar Vergisi Tarifesi",
                kategori="vergi",
                icerik="""# 2025 Yılı Kurumlar Vergisi Tarifesi

## Genel Oran
- **Kurumlar Vergisi Oranı**: %20

## İndirim İstisnaları
- İştirak kazancı istisnası
- Araştırma ve geliştirme indirimi
- Yatırım indirimi (belirli bölgelerde)

## Kurumlar Vergisi Beyannamesi
- **Süresi**: Hesap döneminin bitiminden itibaren 4 ay içinde
- **2025 yılı için son beyanname tarihi**: 30 Haziran 2025

## Geçici Vergi
- **Dönemler**: 3, 6, 9, 12 aylık dönemler
- **Oran**: %20""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
            TurmobPratikBilgi(
                baslik="2025 Yılı İşveren Maliyetleri",
                kategori="muhasebe",
                icerik="""# 2025 Yılı İşveren Maliyetleri

## Asgari Ücret Üzerinden İşveren Maliyetleri
- **Brüt Asgari Ücret**: 22.104,00 TL
- **SGK İşveren Primi**: 4.531,32 TL (%20.5)
- **İşsizlik İşveren Primi**: 442,08 TL (%2)
- **Toplam İşveren Maliyeti**: 27.077,40 TL

## Bordro Hesaplama (Asgari Ücret)
- **Brüt Ücret**: 22.104,00 TL
- **SGK İşçi Primi**: -3.094,56 TL (%14)
- **İşsizlik İşçi Primi**: -221,04 TL (%1)
- **Gelir Vergisi**: -1.527,84 TL
- **Damga Vergisi**: -166,08 TL
- **Net Ücret**: 17.094,48 TL

## Not
- Asgari ücretten gelir vergisi alınmamaktadır (2025 yılı için)
- Damga vergisi maktu olarak uygulanmaktadır""",
                guncelleme_tarihi=date(2025, 1, 1),
            ),
        ]

        if kategori:
            return [b for b in all_bilgiler if b.kategori == kategori]

        return all_bilgiler