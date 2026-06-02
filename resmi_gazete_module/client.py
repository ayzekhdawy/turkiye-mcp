"""Resmi Gazete API istemcisi - resmigazete.gov.tr üzerinden veri çekme."""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .models import (
    BelgeTuru,
    ResmiGazeteBulten,
    ResmiGazeteDetay,
    ResmiGazeteSearchRequest,
    ResmiGazeteSearchResponse,
)

logger = logging.getLogger(__name__)


class ResmiGazeteClient:
    """Resmi Gazete web sitesinden veri çeken istemci sınıfı.

    Bu istemci, resmigazete.gov.tr üzerinden:
    - Günlük bültenleri çekme
    - Belge arama
    - Belge detayı getirme
    - RSS feed parse etme
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.resmigazete.gov.tr"
    SEARCH_URL = "https://www.resmigazete.gov.tr/eskiler"
    RSS_URL = "https://www.resmigazete.gov.tr/rss/rss.xml"

    # Belge türü URL parametre eşleştirmesi
    BELGE_TURU_MAP = {
        BelgeTuru.KANUN: "1",
        BelgeTuru.KANUN_HUKMUNDE_KARARNAME: "2",
        BelgeTuru.CUMHURBASKANLIKI_KARAR: "3",
        BelgeTuru.YONETMELIK: "4",
        BelgeTuru.TEBLIG: "5",
        BelgeTuru.SIRKULER: "6",
        BelgeTuru.GENELGE: "7",
        BelgeTuru.DUYURU: "8",
        BelgeTuru.TEBLIGAT: "9",
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

    async def get_daily_bulletin(
        self, target_date: Optional[date] = None
    ) -> list[ResmiGazeteBulten]:
        """Belirli bir tarihte yayımlanan Resmi Gazete bültenlerini getirir.

        Args:
            target_date: Hedef tarih. None ise bugünün tarihi kullanılır.

        Returns:
            Bülten listesi.
        """
        if target_date is None:
            target_date = date.today()

        # Resmi Gazete URL formatı: /DD.MM.YYYY (ör: /02.06.2026)
        date_path = target_date.strftime("%d.%m.%Y")
        url = f"/{date_path}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            bultens = self._parse_daily_page(soup, target_date)

            logger.info(
                f"Resmi Gazete bültenleri alındı: {target_date} - {len(bultens)} belge"
            )
            return bultens

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                logger.warning(f"Resmi Gazete bulunamadı: {target_date}")
                return []
            raise
        except Exception as e:
            logger.error(f"Resmi Gazete bülten hatası: {e}")
            raise

    async def search(
        self, request: ResmiGazeteSearchRequest
    ) -> ResmiGazeteSearchResponse:
        """Resmi Gazete'de arama yapar.

        Args:
            request: Arama isteği parametreleri.

        Returns:
            Arama yanıtı.
        """
        params = {
            "Arama": "Ara",
            "Kelime": request.anahtar_kelime,
            "Sayfa": str(request.sayfa),
            "SayfaAdet": str(request.sayfa_buyuklugu),
        }

        if request.belge_turu:
            params["BelgeTuru"] = self.BELGE_TURU_MAP.get(
                request.belge_turu, ""
            )

        if request.baslangic_tarihi:
            params["TarihBaslangic"] = request.baslangic_tarihi.strftime(
                "%d.%m.%Y"
            )

        if request.bitis_tarihi:
            params["TarihBitis"] = request.bitis_tarihi.strftime("%d.%m.%Y")

        try:
            response = await self.http_client.post(
                "/arama", data=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_search_results(soup, request)

        except Exception as e:
            logger.error(f"Resmi Gazete arama hatası: {e}")
            raise

    async def get_document_detail(self, detail_url: str) -> ResmiGazeteDetay:
        """Belge detayını getirir.

        Args:
            detail_url: Belge detay URL'si.

        Returns:
            Belge detayı.
        """
        try:
            response = await self.http_client.get(detail_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_document_detail(soup, detail_url)

        except Exception as e:
            logger.error(f"Resmi Gazete belge detay hatası: {e}")
            raise

    async def get_recent_changes(
        self, days: int = 7
    ) -> list[ResmiGazeteBulten]:
        """Son N gün içinde yayımlanan mali belgeleri getirir.

        Vergi, SGK, iş hukuku ve muhasebe ile ilgili
        belgeleri filtreleyerek döndürür.

        Args:
            days: Geriye dönük gün sayısı.

        Returns:
            İlgili bülten listesi.
        """
        all_bultens = []
        today = date.today()

        # Mali müşavirlik ile ilgili anahtar kelimeler
        mali_keywords = [
            "vergi", "muhasebe", "sgk", "sosyal güvenlik",
            "gelir", "kurumlar", "katma değer", "kdv", "stopaj",
            "beyanname", "teblig", "sirküler", "asgari ücret",
            "işveren", "bordro", "damga", "işverenin",
            "finans", "mali", "muafiyet", "istisna",
        ]

        for i in range(days):
            target_date = today - timedelta(days=i)
            try:
                bultens = await self.get_daily_bulletin(target_date)
                for b in bultens:
                    baslik_lower = b.baslik.lower()
                    if any(kw in baslik_lower for kw in mali_keywords):
                        all_bultens.append(b)
            except Exception as e:
                logger.warning(f"Günlük bülten hatası ({target_date}): {e}")
                continue

        return all_bultens

    def _parse_daily_page(
        self, soup: BeautifulSoup, gazete_date: date
    ) -> list[ResmiGazeteBulten]:
        """Günlük Resmi Gazete sayfasını parse eder.

        Resmi Gazete sayfası URL formatı: /DD.MM.YYYY
        Belge linkleri formatı: /eskiler/YYYY/MM/YYYYMMDD-N.htm
        """
        bultens = []

        # Resmi Gazete sayfasındaki tüm belge linklerini bul
        # Format: /eskiler/YYYY/MM/YYYYMMDD-N.htm veya .pdf
        date_str = gazete_date.strftime("%Y%m%d")
        all_links = soup.select("a[href]")

        for link in all_links:
            try:
                href = link.get("href", "")
                if not href:
                    continue

                # Sadece /eskiler/ ile başlayan belge linklerini filtrele
                if "/eskiler/" not in href:
                    continue

                # Tarih formatını kontrol et (YYYYMMDD)
                if date_str not in href:
                    continue

                baslik = link.get_text(strip=True)
                if not baslik or len(baslik) < 5:
                    continue

                # Tam URL oluştur
                if href.startswith("/"):
                    full_url = f"{self.BASE_URL}{href}"
                elif not href.startswith("http"):
                    full_url = f"{self.BASE_URL}/{href}"
                else:
                    full_url = href

                # Belge türünü sayfa yapısından çıkarma
                # Resmi Gazete sayfasında bölümler: YÖNETMELİK, KANUN, TEBLİĞ, vb.
                belge_turu = ""
                parent = link.parent
                if parent:
                    # Üst bölüm başlığından türü bul
                    section_headers = [
                        "KANUN", "KARARNAME", "YÖNETMELİK", "TEBLİĞ",
                        "SİRKÜLER", "GENELGE", "DUYURU", "KURUL KARARI",
                    ]
                    parent_text = parent.get_text(strip=True).upper()
                    for h in section_headers:
                        if h in parent_text:
                            belge_turu = h.title()
                            break

                bultens.append(
                    ResmiGazeteBulten(
                        baslik=baslik,
                        sayi=str(gazete_date.strftime("%Y%m%d")),
                        tarihi=gazete_date,
                        belge_turu=belge_turu,
                        kurum="",
                        detay_url=full_url,
                    )
                )
            except Exception as e:
                logger.warning(f"Bülten parse hatası: {e}")
                continue

        # Link bulunamazsa, sayfanın genel yapısını parse et
        if not bultens:
            # Alternatif: Sayfanın bölümlerini bul
            sections = soup.select(".section-title, h2, h3")
            current_turu = ""

            for section in sections:
                section_text = section.get_text(strip=True).upper()
                section_headers = {
                    "YÖNETMELİK": "Yönetmelik",
                    "KANUN": "Kanun",
                    "KARARNAME": "Kararname",
                    "TEBLİĞ": "Tebliğ",
                    "SİRKÜLER": "Sirküler",
                    "GENELGE": "Genelge",
                    "KURUL KARARI": "Kurul Kararı",
                }
                for key, val in section_headers.items():
                    if key in section_text:
                        current_turu = val
                        break

                # Bölüm altındaki linkleri bul
                next_sibling = section.find_next_sibling()
                while next_sibling and next_sibling.name not in ("h2", "h3", "h4"):
                    if next_sibling.name == "a":
                        baslik = next_sibling.get_text(strip=True)
                        href = next_sibling.get("href", "")
                        if baslik and href:
                            if href.startswith("/"):
                                full_url = f"{self.BASE_URL}{href}"
                            else:
                                full_url = href

                            bultens.append(
                                ResmiGazeteBulten(
                                    baslik=baslik,
                                    sayi=str(gazete_date.strftime("%Y%m%d")),
                                    tarihi=gazete_date,
                                    belge_turu=current_turu,
                                    kurum="",
                                    detay_url=full_url,
                                )
                            )
                    next_sibling = next_sibling.find_next_sibling()

        return bultens

    def _parse_search_results(
        self, soup: BeautifulSoup, request: ResmiGazeteSearchRequest
    ) -> ResmiGazeteSearchResponse:
        """Arama sonuç sayfasını parse eder."""
        results = []

        # Arama sonuçlarını bul
        result_items = soup.select(
            ".search-result-item, .result-item, .belge-item, table tbody tr"
        )

        for item in result_items:
            try:
                link = item.select_one("a")
                if not link:
                    continue

                baslik = link.get_text(strip=True)
                href = link.get("href", "")

                if href and not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Tarih ve tür bilgilerini çıkarma
                belge_turu = ""
                kurum = ""
                tarih = None

                date_elem = item.select_one(
                    ".date, .tarih, td:nth-child(2)"
                )
                if date_elem:
                    try:
                        tarih_str = date_elem.get_text(strip=True)
                        tarih = datetime.strptime(
                            tarih_str, "%d.%m.%Y"
                        ).date()
                    except ValueError:
                        pass

                results.append(
                    ResmiGazeteBulten(
                        baslik=baslik,
                        sayi="",
                        tarihi=tarih or date.today(),
                        belge_turu=belge_turu,
                        kurum=kurum,
                        detay_url=href or None,
                    )
                )
            except Exception as e:
                logger.warning(f"Arama sonuç parse hatası: {e}")
                continue

        # Toplam sayı
        total_text = soup.select_one(".total-results, .result-count")
        total = int(total_text.get_text(strip=True)) if total_text else len(results)

        total_pages = (total + request.sayfa_buyuklugu - 1) // request.sayfa_buyuklugu

        return ResmiGazeteSearchResponse(
            toplam_sonuc=total,
            sayfa=request.sayfa,
            toplam_sayfa=total_pages,
            sonuclar=results,
        )

    def _parse_document_detail(
        self, soup: BeautifulSoup, source_url: str
    ) -> ResmiGazeteDetay:
        """Belge detay sayfasını parse eder."""
        # Başlık
        title_elem = soup.select_one("h1, .belge-baslik, .page-title")
        baslik = title_elem.get_text(strip=True) if title_elem else "Belge"

        # İçerik - HTML'den Markdown'a dönüşüm
        content_elem = soup.select_one(
            ".belge-icerik, .content, .article-content, #metin"
        )

        if content_elem:
            icerik = self._html_to_markdown(content_elem)
        else:
            icerik = soup.get_text(strip=True)

        # Madde listesini çıkarma
        maddeler = self._extract_articles(icerik)

        # Meta bilgileri çıkarma
        belge_turu = ""
        kurum = ""
        gazete_sayi = ""
        tarih = date.today()

        meta_elems = soup.select(".belge-meta, .meta-info, .doc-info")
        for meta in meta_elems:
            text = meta.get_text(strip=True)
            if "Sayı" in text:
                gazete_sayi = re.search(r"Sayı[:\s]+(\d+)", text)
                if gazete_sayi:
                    gazete_sayi = gazete_sayi.group(1)
            if "Tarih" in text:
                tarih_match = re.search(
                    r"Tarih[:\s]+(\d{2}\.\d{2}\.\d{4})", text
                )
                if tarih_match:
                    tarih = datetime.strptime(
                        tarih_match.group(1), "%d.%m.%Y"
                    ).date()

        return ResmiGazeteDetay(
            baslik=baslik,
            sayi=gazete_sayi or "",
            tarihi=tarih,
            belge_turu=belge_turu,
            kurum=kurum,
            icerik=icerik,
            kaynak_url=source_url,
            maddeler=maddeler if maddeler else None,
        )

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
            elif child.name is None:  # Text node
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

        # Header
        header_cells = rows[0].select("th, td")
        md_lines.append(
            "| " + " | ".join(c.get_text(strip=True) for c in header_cells) + " |"
        )
        md_lines.append(
            "| " + " | ".join("---" for _ in header_cells) + " |"
        )

        # Data rows
        for row in rows[1:]:
            cells = row.select("th, td")
            md_lines.append(
                "| " + " | ".join(c.get_text(strip=True) for c in cells) + " |"
            )

        return "\n".join(md_lines)

    def _extract_articles(self, content: str) -> list[str]:
        """Belge içeriğinden madde listesini çıkarır."""
        maddeler = []
        # Madde formatı: "Madde 1 - ..." veya "MADDE 1 – ..."
        pattern = r"(?:MADDE|Madde)\s+(\d+)\s*[-–—]\s*(.+?)(?=(?:MADDE|Madde)\s+\d+|$)"
        matches = re.findall(pattern, content, re.DOTALL)
        for num, text in matches:
            maddeler.append(f"Madde {num} – {text.strip()}")
        return maddeler