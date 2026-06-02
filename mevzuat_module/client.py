"""Mevzuat Bilgi Sistemi API istemcisi - mevzuat.gov.tr üzerinden veri çekme."""

import logging
import re
from datetime import date
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .models import (
    MevzuatDetay,
    MevzuatMadde,
    MevzuatSearchRequest,
    MevzuatSearchResponse,
    MevzuatTuru,
)

logger = logging.getLogger(__name__)


class MevzuatClient:
    """Mevzuat Bilgi Sistemi'nden veri çeken istemci sınıfı.

    Bu istemci, mevzuat.gov.tr üzerinden:
    - Kanun, KHK, yönetmelik arama
    - Mevzuat metni getirme
    - Birleştirilmiş metin erişimi
    - Madde bazlı sorgulama
    işlemlerini gerçekleştirir.
    """

    BASE_URL = "https://www.mevzuat.gov.tr"
    SEARCH_URL = "https://www.mevzuat.gov.tr/MevzuatMetin/Arama"
    DETAIL_URL = "https://www.mevzuat.gov.tr/MevzuatMetin"

    MEVZUAT_TURU_MAP = {
        MevzuatTuru.KANUN: "1",
        MevzuatTuru.KHK: "2",
        MevzuatTuru.CUMHURBASKANLIKI_KARARNAME: "3",
        MevzuatTuru.YONETMELIK: "4",
        MevzuatTuru.TEBLIG: "5",
        MevzuatTuru.YONERGE: "6",
        MevzuatTuru.GENELGE: "7",
        MevzuatTuru.BUTCE_KANUNU: "8",
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

    async def search(
        self, request: MevzuatSearchRequest
    ) -> MevzuatSearchResponse:
        """Mevzuat Bilgi Sistemi'nde arama yapar.

        Args:
            request: Arama isteği parametreleri.

        Returns:
            Arama yanıtı.
        """
        params = {
            "ArananKelime": request.anahtar_kelime,
            "Sayfa": str(request.sayfa),
        }

        if request.mevzuat_turu:
            params["MevzuatTuru"] = self.MEVZUAT_TURU_MAP.get(
                request.mevzuat_turu, ""
            )

        if request.yil:
            params["Yil"] = str(request.yil)

        try:
            response = await self.http_client.get(
                "/MevzuatMetin/Arama", params=params
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_search_results(soup, request)

        except Exception as e:
            logger.error(f"Mevzuat arama hatası: {e}")
            raise

    async def get_mevzuat_detail(
        self, mevzuat_url: str
    ) -> MevzuatDetay:
        """Mevzuat detayını getirir.

        Args:
            mevzuat_url: Mevzuat detay URL'si.

        Returns:
            Mevzuat detayı.
        """
        try:
            response = await self.http_client.get(mevzuat_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_mevzuat_detail(soup, mevzuat_url)

        except Exception as e:
            logger.error(f"Mevzuat detay hatası: {e}")
            raise

    async def get_mevzuat_by_number(
        self,
        mevzuat_turu: MevzuatTuru,
        mevzuat_no: str,
        yil: Optional[int] = None,
    ) -> MevzuatDetay:
        """Mevzuat numarasına göre detay getirir.

        Args:
            mevzuat_turu: Mevzuat türü.
            mevzuat_no: Mevzuat numarası.
            yil: Yıl (opsiyonel).

        Returns:
            Mevzuat detayı.
        """
        # Mevzuat URL formatı: /MevzuatMetin/{tur}/{no}
        tur_path = self.MEVZUAT_TURU_MAP.get(mevzuat_turu, "1")
        url = f"{self.DETAIL_URL}/{tur_path}/{mevzuat_no}"

        if yil:
            url += f"?yil={yil}"

        return await self.get_mevzuat_detail(url)

    async def search_tax_laws(
        self, keyword: str, sayfa: int = 1
    ) -> MevzuatSearchResponse:
        """Vergi ve mali mevzuat araması yapar.

        Mali müşavirlik ile ilgili kanunları bulmak için
        özelleştirilmiş arama.

        Args:
            keyword: Arama anahtar kelimesi.
            sayfa: Sayfa numarası.

        Returns:
            Arama yanıtı.
        """
        mali_keywords = [
            "vergi", "muhasebe", "gelir", "kurumlar", "katma değer",
            "damga", "vergi usul", "mükellef", "beyanname",
        ]

        # Anahtar kelimeye mali bağlam ekleme
        expanded_keyword = keyword
        if not any(kw in keyword.lower() for kw in mali_keywords):
            # Eğer arama kelimesi zaten mali bir terim içermiyorsa
            # genişletme yapmıyoruz, direkt arıyoruz
            pass

        request = MevzuatSearchRequest(
            anahtar_kelime=expanded_keyword,
            sayfa=sayfa,
        )

        return await self.search(request)

    def _parse_search_results(
        self, soup: BeautifulSoup, request: MevzuatSearchRequest
    ) -> MevzuatSearchResponse:
        """Arama sonuç sayfasını parse eder."""
        results = []

        # Mevzuat arama sonuçlarını bul
        result_items = soup.select(
            ".search-result, .mevzuat-item, .list-item, table tbody tr"
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

                # Meta bilgileri çıkarma
                meta_text = item.get_text(strip=True)

                result = {
                    "baslik": baslik,
                    "url": href,
                    "tur": "",
                    "tarih": None,
                    "no": "",
                }

                # Tür bilgisi
                type_elem = item.select_one(
                    ".mevzuat-type, .type, td:nth-child(2)"
                )
                if type_elem:
                    result["tur"] = type_elem.get_text(strip=True)

                # Tarih bilgisi
                date_elem = item.select_one(
                    ".mevzuat-date, .date, td:nth-child(3)"
                )
                if date_elem:
                    result["tarih"] = date_elem.get_text(strip=True)

                results.append(result)

            except Exception as e:
                logger.warning(f"Mevzuat sonuç parse hatası: {e}")
                continue

        # Toplam sayı
        total_elem = soup.select_one(".total-count, .result-count")
        total = 0
        if total_elem:
            total_text = total_elem.get_text(strip=True)
            total_match = re.search(r"(\d+)", total_text)
            if total_match:
                total = int(total_match.group(1))
        else:
            total = len(results)

        return MevzuatSearchResponse(
            toplam_sonuc=total,
            sayfa=request.sayfa,
            sonuclar=results,
            anahtar_kelime=request.anahtar_kelime,
        )

    def _parse_mevzuat_detail(
        self, soup: BeautifulSoup, source_url: str
    ) -> MevzuatDetay:
        """Mevzuat detay sayfasını parse eder."""
        # Başlık
        title_elem = soup.select_one(
            "h1, h2, .mevzuat-title, .page-title"
        )
        baslik = title_elem.get_text(strip=True) if title_elem else "Mevzuat"

        # İçerik
        content_elem = soup.select_one(
            ".mevzuat-content, .content, #metin, .article-content"
        )

        if content_elem:
            icerik = self._html_to_markdown(content_elem)
        else:
            icerik = soup.get_text(strip=True)

        # Maddeleri çıkarma
        maddeler = self._extract_articles(icerik)

        # Meta bilgiler
        resmi_gazete_sayisi = ""
        resmi_gazete_tarihi = None
        yururluk_tarihi = None
        mevzuat_no = ""
        mevzuat_turu = ""

        meta_section = soup.select_one(
            ".mevzuat-meta, .meta-info, .doc-info"
        )
        if meta_section:
            meta_text = meta_section.get_text()
            # Resmi Gazete sayısı
            rg_match = re.search(r"Resmi Gazete Sayısı[:\s]+(\S+)", meta_text)
            if rg_match:
                resmi_gazete_sayisi = rg_match.group(1)
            # Resmi Gazete tarihi
            rg_date = re.search(
                r"Resmi Gazete Tarihi[:\s]+(\d{2}\.\d{2}\.\d{4})", meta_text
            )
            if rg_date:
                from datetime import datetime
                resmi_gazete_tarihi = datetime.strptime(
                    rg_date.group(1), "%d.%m.%Y"
                ).date()
            # Yürürlük tarihi
            yurur_date = re.search(
                r"Yürürlük Tarihi[:\s]+(\d{2}\.\d{2}\.\d{4})", meta_text
            )
            if yurur_date:
                from datetime import datetime
                yururluk_tarihi = datetime.strptime(
                    yurur_date.group(1), "%d.%m.%Y"
                ).date()
            # Mevzuat no
            no_match = re.search(r"Mevzuat No[:\s]+(\S+)", meta_text)
            if no_match:
                mevzuat_no = no_match.group(1)

        return MevzuatDetay(
            baslik=baslik,
            mevzuat_turu=mevzuat_turu,
            resmi_gazete_sayisi=resmi_gazete_sayisi or None,
            resmi_gazete_tarihi=resmi_gazete_tarihi,
            yururluk_tarihi=yururluk_tarihi,
            mevzuat_no=mevzuat_no or None,
            icerik=icerik,
            maddeler=maddeler,
            kaynak_url=source_url,
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
        md_lines.append(
            "| " + " | ".join(c.get_text(strip=True) for c in header_cells) + " |"
        )
        md_lines.append(
            "| " + " | ".join("---" for _ in header_cells) + " |"
        )

        for row in rows[1:]:
            cells = row.select("th, td")
            md_lines.append(
                "| " + " | ".join(c.get_text(strip=True) for c in cells) + " |"
            )

        return "\n".join(md_lines)

    def _extract_articles(self, content: str) -> list[MevzuatMadde]:
        """Mevzuat içeriğinden maddeleri çıkarır."""
        maddeler = []
        pattern = r"(?:MADDE|Madde)\s+(\d+)\s*[-–—]\s*(.+?)(?=(?:MADDE|Madde)\s+\d+|$)"
        matches = re.findall(pattern, content, re.DOTALL)

        for num, text in matches:
            maddeler.append(
                MevzuatMadde(
                    madde_no=num,
                    madde_adi=None,
                    icerik=text.strip(),
                    degisiklik_var=False,
                    yururlukten_kalkma=False,
                )
            )

        return maddeler