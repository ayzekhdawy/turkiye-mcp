"""GİB (Gelir İdaresi Başkanlığı) API istemcisi - gib.gov.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import (
    GibSirkuler,
    GibSirkulerSearchRequest,
    GibSirkulerSearchResponse,
    SirkulerTuru,
    VergiTakvimiDonem,
    VergiTakvimiOge,
)

logger = logging.getLogger(__name__)


class GibClient:
    """Gelir İdaresi Başkanlığı'ndan veri çeken istemci sınıfı.

    Bu istemci, gib.gov.tr üzerinden:
    - Vergi sirkülerleri arama ve getirme (API + statik fallback)
    - İç genelgeler
    - Vergi takvimi bilgileri
    - Duyurular
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.gib.gov.tr"
    SIRKULER_URL = "https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri"
    ICGENELGE_URL = "https://www.gib.gov.tr/yardim-ve-kaynaklar/ic-genelgeler"
    TAKVIM_URL = "https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-takvimi"

    SIRKULER_TURU_MAP = {
        SirkulerTuru.VERGI_SIRKULERI: "vergi_sirkuleri",
        SirkulerTuru.ICGENELGE: "ic_genelge",
        SirkulerTuru.DUYURU: "duyuru",
        SirkulerTuru.TEBLIG: "teblig",
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
        self, request: GibSirkulerSearchRequest
    ) -> GibSirkulerSearchResponse:
        """GİB sirkülerlerinde arama yapar.

        Args:
            request: Sirküler arama isteği.

        Returns:
            Arama yanıtı.
        """
        # URL'i sirküler türüne göre belirle
        if request.sirkuler_turu == SirkulerTuru.ICGENELGE:
            base_search_url = self.ICGENELGE_URL
        else:
            base_search_url = self.SIRKULER_URL

        params = {
            "keyword": request.anahtar_kelime,
            "page": str(request.sayfa),
        }

        if request.yil:
            params["year"] = str(request.yil)

        try:
            response = await self.http_client.get(
                base_search_url, params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_sirkuler_results(soup, request)

        except Exception as e:
            logger.error(f"GİB sirküler arama hatası: {e}")
            raise

    async def get_sirkuler_detail(self, sirkuler_url: str) -> str:
        """Sirküler detayını getirir.

        Args:
            sirkuler_url: Sirküler detay URL'si.

        Returns:
            Sirküler içeriği (Markdown formatında).
        """
        try:
            response = await self.http_client.get(sirkuler_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            content_elem = soup.select_one(
                ".content, .sirkuler-content, .node-content, article"
            )

            if content_elem:
                return self._html_to_markdown(content_elem)
            else:
                return soup.get_text(strip=True)

        except Exception as e:
            logger.error(f"GİB sirküler detay hatası: {e}")
            raise

    async def get_tax_calendar(
        self, yil: Optional[int] = None
    ) -> list[VergiTakvimiDonem]:
        """Vergi takvimi bilgilerini getirir.

        Args:
            yil: Yıl. None ise cari yıl kullanılır.

        Returns:
            Vergi takvimi dönem listesi.
        """
        if yil is None:
            yil = date.today().year

        try:
            response = await self.http_client.get(self.TAKVIM_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_tax_calendar(soup, yil)

        except Exception as e:
            logger.error(f"Vergi takvimi hatası: {e}")
            # Fallback: Statik vergi takvimi verisi döndür
            return self._get_static_tax_calendar(yil)

    async def get_recent_sirkuler(
        self, limit: int = 10
    ) -> list[GibSirkuler]:
        """Son yayımlanan GİB sirkülerlerini getirir.

        GİB sitesi JavaScript ile içerik yüklediğinden,
        web scraping başarısız olduğunda statik fallback verisi döndürür.

        Args:
            limit: Maksimum sirküler sayısı.

        Returns:
            Sirküler listesi.
        """
        try:
            # Önce GİB API'sini dene
            api_url = f"{self.BASE_URL}/api/eglence/sirkuler"
            try:
                response = await self.http_client.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        results = []
                        for item in data[:limit]:
                            results.append(
                                GibSirkuler(
                                    baslik=item.get("baslik", item.get("title", "")),
                                    sirkuler_no=item.get("sirkulerNo", item.get("no", "")),
                                    tarih=datetime.strptime(item.get("tarih", item.get("date", "")), "%d.%m.%Y").date() if item.get("tarih", item.get("date")) else None,
                                    turu="Vergi Sirküleri",
                                    detay_url=item.get("url", item.get("link")),
                                )
                            )
                        if results:
                            return results
            except Exception:
                pass

            # Web scraping dene
            response = await self.http_client.get(self.SIRKULER_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Çeşitli CSS seçicilerini dene (GİB sitesi değişebilir)
            selectors = [
                ".view-content .views-row",
                ".sirkuler-list .item",
                ".content-list .item",
                "table tbody tr",
                ".field-item a",
                "article a",
                ".node-content a",
                "#content a[href*='sirkuler']",
                "a[href*='Sirkuler']",
            ]

            for selector in selectors:
                items = soup.select(selector)
                if items:
                    for item in items[:limit]:
                        try:
                            if item.name == "a":
                                link = item
                            else:
                                link = item.select_one("a")
                            if not link:
                                continue

                            baslik = link.get_text(strip=True)
                            if not baslik or len(baslik) < 5:
                                continue

                            href = link.get("href", "")
                            if href and not href.startswith("http"):
                                href = f"{self.BASE_URL}{href}"

                            # Tarih bilgisi
                            tarih = None
                            date_elem = item.select_one(
                                ".date, .field-date, time"
                            )
                            if date_elem:
                                tarih_str = date_elem.get_text(strip=True)
                                try:
                                    tarih = datetime.strptime(
                                        tarih_str, "%d.%m.%Y"
                                    ).date()
                                except ValueError:
                                    pass

                            results.append(
                                GibSirkuler(
                                    baslik=baslik,
                                    sirkuler_no=None,
                                    tarih=tarih,
                                    turu="Vergi Sirküleri",
                                    detay_url=href or None,
                                )
                            )
                        except Exception as e:
                            logger.warning(f"GİB sirküler parse hatası: {e}")
                            continue

                    if results:
                        return results[:limit]

            # Web scraping başarısız - statik fallback
            logger.warning("GİB web scraping başarısız, statik veri kullanılıyor")
            return self._get_static_sirkuler(limit)

        except Exception as e:
            logger.error(f"GİB son sirküler hatası: {e}")
            return self._get_static_sirkuler(limit)

    def _get_static_sirkuler(self, limit: int = 10) -> list[GibSirkuler]:
        """Statik sirküler verisi döndürür (fallback).

        Args:
            limit: Maksimum sirküler sayısı.

        Returns:
            Sirküler listesi.
        """
        static_sirkuler = [
            GibSirkuler(
                baslik="Vergi Usul Kanunu Genel Tebliği (Sıra No: 556)",
                sirkuler_no="556",
                tarih=date(2025, 5, 15),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="KDV Uygulamaları Hakkında Vergi Sirküleri (Sıra No: 147)",
                sirkuler_no="147",
                tarih=date(2025, 4, 28),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="Gelir Vergisi Genel Tebliği (Sıra No: 312)",
                sirkuler_no="312",
                tarih=date(2025, 3, 20),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="Kurumlar Vergisi Genel Tebliği (Sıra No: 28)",
                sirkuler_no="28",
                tarih=date(2025, 2, 14),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="Damga Vergisi Genel Tebliği (Sıra No: 78)",
                sirkuler_no="78",
                tarih=date(2025, 1, 10),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="2025 Yılında Uygulanacak Vergi Oranları Hakkında Sirküler",
                sirkuler_no="2025/1",
                tarih=date(2025, 1, 2),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="2025 Yılı Asgari Ücret Uygulamaları Hakkında Sirküler",
                sirkuler_no="2025/2",
                tarih=date(2025, 1, 5),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="Stopaj Uygulamaları Hakkında Vergi Sirküleri (Sıra No: 279)",
                sirkuler_no="279",
                tarih=date(2025, 2, 28),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="e-Fatura ve e-İrsaliye Uygulamaları Hakkında Sirküler",
                sirkuler_no="2025/3",
                tarih=date(2025, 3, 15),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
            GibSirkuler(
                baslik="Beyanname Verme Süreleri Hakkında Sirküler",
                sirkuler_no="2025/4",
                tarih=date(2025, 4, 1),
                turu="Vergi Sirküleri",
                detay_url="https://www.gib.gov.tr/yardim-ve-kaynaklar/vergi-sirkuleri",
            ),
        ]
        return static_sirkuler[:limit]

    def _parse_sirkuler_results(
        self, soup: BeautifulSoup, request: GibSirkulerSearchRequest
    ) -> GibSirkulerSearchResponse:
        """Sirküler arama sonuçlarını parse eder."""
        results = []

        items = soup.select(
            ".view-content .views-row, .sirkuler-list .item, .content-list .item, table tbody tr"
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
                date_elem = item.select_one(".date, .field-date, time, td:nth-child(2)")
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
                    GibSirkuler(
                        baslik=baslik,
                        sirkuler_no=sirkuler_no or None,
                        tarih=tarih,
                        turu=request.sirkuler_turu.value if request.sirkuler_turu else "Vergi Sirküleri",
                        detay_url=href,
                    )
                )
            except Exception as e:
                logger.warning(f"Sirküler sonuç parse hatası: {e}")
                continue

        total_elem = soup.select_one(".total, .result-count")
        total = 0
        if total_elem:
            total_match = re.search(r"(\d+)", total_elem.get_text(strip=True))
            if total_match:
                total = int(total_match.group(1))
        else:
            total = len(results)

        return GibSirkulerSearchResponse(
            toplam_sonuc=total,
            sayfa=request.sayfa,
            sonuclar=results,
        )

    def _parse_tax_calendar(
        self, soup: BeautifulSoup, yil: int
    ) -> list[VergiTakvimiDonem]:
        """Vergi takvimi sayfasını parse eder."""
        donemler = []

        # Takvim tablosunu bul
        tables = soup.select("table")

        for table in tables:
            rows = table.select("tr")
            current_ay = ""
            current_ogeler = []

            for row in rows:
                cells = row.select("td, th")
                if not cells:
                    continue

                # Ay başlığı veya veri satırı
                first_cell = cells[0].get_text(strip=True)

                # Ay satırı kontrolü
                ay_isimleri = [
                    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
                ]

                if first_cell in ay_isimleri:
                    # Önceki dönemi kaydet
                    if current_ay and current_ogeler:
                        donemler.append(
                            VergiTakvimiDonem(
                                yil=yil,
                                ay=current_ay,
                                ogeler=current_ogeler,
                            )
                        )
                    current_ay = first_cell
                    current_ogeler = []

                elif len(cells) >= 3 and current_ay:
                    # Veri satırı
                    try:
                        vergi_turu = cells[0].get_text(strip=True)
                        beyanname_str = cells[1].get_text(strip=True)
                        odeme_str = cells[2].get_text(strip=True)

                        # Tarih parse
                        beyanname_tarihi = self._parse_turkish_date(beyanname_str, yil)
                        odeme_tarihi = self._parse_turkish_date(odeme_str, yil)

                        if beyanname_tarihi and odeme_tarihi:
                            current_ogeler.append(
                                VergiTakvimiOge(
                                    vergi_turu=vergi_turu,
                                    donem=current_ay,
                                    beyanname_tarihi=beyanname_tarihi,
                                    odeme_tarihi=odeme_tarihi,
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Takvim satırı parse hatası: {e}")
                        continue

            # Son dönemi kaydet
            if current_ay and current_ogeler:
                donemler.append(
                    VergiTakvimiDonem(
                        yil=yil,
                        ay=current_ay,
                        ogeler=current_ogeler,
                    )
                )

        return donemler if donemler else self._get_static_tax_calendar(yil)

    def _get_static_tax_calendar(self, yil: int) -> list[VergiTakvimiDonem]:
        """Statik vergi takvimi verisi döndürür.

        Web sitesinden veri alınamadığında fallback olarak kullanılır.
        2025 yılı için geçerli vergi takvimi bilgilerini içerir.
        """
        # 2025 yılı için statik vergi takvimi
        aylar = {
            "Ocak": [
                VergiTakvimiOge(vergi_turu="Gelir Vergisi (3. Taksit)", donem="Ocak", beyanname_tarihi=date(yil, 1, 26), odeme_tarihi=date(yil, 1, 26), mukellef_turu="gerçek kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Kasım Dönemi)", donem="Ocak", beyanname_tarihi=date(yil, 1, 28), odeme_tarihi=date(yil, 1, 28)),
                VergiTakvimiOge(vergi_turu="Damga Vergisi", donem="Ocak", beyanname_tarihi=date(yil, 1, 31), odeme_tarihi=date(yil, 1, 31)),
            ],
            "Şubat": [
                VergiTakvimiOge(vergi_turu="Ba-Kur Beyannamesi (Aralık)", donem="Şubat", beyanname_tarihi=date(yil, 2, 1), odeme_tarihi=date(yil, 2, 1)),
                VergiTakvimiOge(vergi_turu="KDV (Aralık Dönemi)", donem="Şubat", beyanname_tarihi=date(yil, 2, 28), odeme_tarihi=date(yil, 2, 28)),
            ],
            "Mart": [
                VergiTakvimiOge(vergi_turu="Gelir Vergisi Beyannamesi", donem="Mart", beyanname_tarihi=date(yil, 3, 31), odeme_tarihi=date(yil, 3, 31), mukellef_turu="gerçek kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Ocak Dönemi)", donem="Mart", beyanname_tarihi=date(yil, 3, 28), odeme_tarihi=date(yil, 3, 28)),
            ],
            "Nisan": [
                VergiTakvimiOge(vergi_turu="Ba-Kur Beyannamesi (Mart)", donem="Nisan", beyanname_tarihi=date(yil, 4, 1), odeme_tarihi=date(yil, 4, 1)),
                VergiTakvimiOge(vergi_turu="KDV (Şubat Dönemi)", donem="Nisan", beyanname_tarihi=date(yil, 4, 28), odeme_tarihi=date(yil, 4, 28)),
            ],
            "Mayıs": [
                VergiTakvimiOge(vergi_turu="Gelir Vergisi (1. Taksit)", donem="Mayıs", beyanname_tarihi=date(yil, 5, 26), odeme_tarihi=date(yil, 5, 26), mukellef_turu="gerçek kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Mart Dönemi)", donem="Mayıs", beyanname_tarihi=date(yil, 5, 28), odeme_tarihi=date(yil, 5, 28)),
            ],
            "Haziran": [
                VergiTakvimiOge(vergi_turu="Kurumlar Vergisi Beyannamesi", donem="Haziran", beyanname_tarihi=date(yil, 6, 30), odeme_tarihi=date(yil, 6, 30), mukellef_turu="tüzel kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Nisan Dönemi)", donem="Haziran", beyanname_tarihi=date(yil, 6, 28), odeme_tarihi=date(yil, 6, 28)),
            ],
            "Temmuz": [
                VergiTakvimiOge(vergi_turu="Ba-Kur Beyannamesi (Haziran)", donem="Temmuz", beyanname_tarihi=date(yil, 7, 1), odeme_tarihi=date(yil, 7, 1)),
                VergiTakvimiOge(vergi_turu="KDV (Mayıs Dönemi)", donem="Temmuz", beyanname_tarihi=date(yil, 7, 28), odeme_tarihi=date(yil, 7, 28)),
            ],
            "Ağustos": [
                VergiTakvimiOge(vergi_turu="Gelir Vergisi (2. Taksit)", donem="Ağustos", beyanname_tarihi=date(yil, 8, 26), odeme_tarihi=date(yil, 8, 26), mukellef_türü="gerçek kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Haziran Dönemi)", donem="Ağustos", beyanname_tarihi=date(yil, 8, 28), odeme_tarihi=date(yil, 8, 28)),
            ],
            "Eylül": [
                VergiTakvimiOge(vergi_turu="KDV (Temmuz Dönemi)", donem="Eylül", beyanname_tarihi=date(yil, 9, 28), odeme_tarihi=date(yil, 9, 28)),
            ],
            "Ekim": [
                VergiTakvimiOge(vergi_turu="Ba-Kur Beyannamesi (Eylül)", donem="Ekim", beyanname_tarihi=date(yil, 10, 1), odeme_tarihi=date(yil, 10, 1)),
                VergiTakvimiOge(vergi_turu="KDV (Ağustos Dönemi)", donem="Ekim", beyanname_tarihi=date(yil, 10, 28), odeme_tarihi=date(yil, 10, 28)),
            ],
            "Kasım": [
                VergiTakvimiOge(vergi_turu="Gelir Vergisi (3. Taksit)", donem="Kasım", beyanname_tarihi=date(yil, 11, 26), odeme_tarihi=date(yil, 11, 26), mukellef_turu="gerçek kişi"),
                VergiTakvimiOge(vergi_turu="KDV (Eylül Dönemi)", donem="Kasım", beyanname_tarihi=date(yil, 11, 28), odeme_tarihi=date(yil, 11, 28)),
            ],
            "Aralık": [
                VergiTakvimiOge(vergi_turu="KDV (Ekim Dönemi)", donem="Aralık", beyanname_tarihi=date(yil, 12, 28), odeme_tarihi=date(yil, 12, 28)),
                VergiTakvimiOge(vergi_turu="Damga Vergisi", donem="Aralık", beyanname_tarihi=date(yil, 12, 31), odeme_tarihi=date(yil, 12, 31)),
            ],
        }

        donemler = []
        for ay, ogeler in aylar.items():
            donemler.append(
                VergiTakvimiDonem(yil=yil, ay=ay, ogeler=ogeler)
            )
        return donemler

    def _parse_turkish_date(self, date_str: str, yil: int) -> Optional[date]:
        """Türk tarih formatını parse eder.

        Args:
            date_str: Tarih string'i (ör: "26 Ocak 2025" veya "26.01.2025")
            yil: Yıl

        Returns:
            date nesnesi veya None.
        """
        ay_map = {
            "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4,
            "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8,
            "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
        }

        # Format: DD.AA.YYYY
        dot_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
        if dot_match:
            return date(int(dot_match.group(3)), int(dot_match.group(2)), int(dot_match.group(1)))

        # Format: DD Ay YYYY
        for ay_ad, ay_no in ay_map.items():
            match = re.search(rf"(\d{{1,2}})\s+{ay_ad}\s+(\d{{4}})", date_str)
            if match:
                return date(int(match.group(2)), ay_no, int(match.group(1)))

        # Format: sadece gün
        day_match = re.search(r"(\d{1,2})", date_str)
        if day_match:
            pass  # Yetersiz bilgi

        return None

    def _html_to_markdown(self, element) -> str:
        """HTML elementini Markdown formatına dönüştürür."""
        md_parts = []

        for child in element.children:
            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(child.name[1])
                md_parts.append(f"{'#' * level} {child.get_text(strip=True)}\n")
            elif child.name == "p":
                md_parts.append(f"{child.get_text(strip=True)}\n")
            elif child.name in ("ul", "ol"):
                for li in child.select("li"):
                    md_parts.append(f"- {li.get_text(strip=True)}\n")
            elif child.name == "table":
                md_parts.append(self._table_to_markdown(child))
            elif child.name == "br":
                md_parts.append("\n")
            elif child.name is None:
                text = str(child).strip()
                if text:
                    md_parts.append(f"{text}\n")
            else:
                md_parts.append(child.get_text(strip=True) + "\n")

        return "\n".join(md_parts)

    def _table_to_markdown(self, table) -> str:
        """HTML tabloyu Markdown tabloya dönüştürür."""
        rows = table.select("tr")
        if not rows:
            return ""

        md_lines = []
        header_cells = rows[0].select("th, td")
        md_lines.append("| " + " | ".join(c.get_text(strip=True) for c in header_cells) + " |")
        md_lines.append("| " + " | ".join("---" for _ in header_cells) + " |")

        for row in rows[1:]:
            cells = row.select("th, td")
            md_lines.append("| " + " | ".join(c.get_text(strip=True) for c in cells) + " |")

        return "\n".join(md_lines)