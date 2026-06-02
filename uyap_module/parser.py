"""UYAP EYP/UDF Belge Çözümleyici.

EYP (Elektronik Yazışma Paketi) ve UDF dosyalarını parse eder.
Dosyalar ZIP formatındadır ve içlerinde XML metadata + PDF belgeler bulunur.
"""

import zipfile
import xml.etree.ElementTree as ET
import logging
import re
import io
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# UYAP XML namespace'leri
NAMESPACES = {
    "ey": "urn:dpt:eyazisma:schema:xsd:Tipler-1",
    "bh": "urn:dpt:eyazisma:schema:xsd:BelgeHedef-1",
    "no": "urn:dpt:eyazisma:schema:xsd:NihaiOzet-1",
    "po": "urn:dpt:eyazisma:schema:xsd:PaketOzeti-1",
    "uv": "urn:dpt:eyazisma:schema:xsd:Ustveri-1",
    "bi": "urn:dpt:eyazisma:schema:xsd:BelgeImza-1",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


@dataclass
class Taraf:
    """Dava tarafı."""
    ad: str = ""
    tckn: str = ""
    rol: str = ""  # SANIK, MÜŞTEKİ, Müdafii, vs.
    kisi_mi_kurum_mu: str = ""  # "0" = kişi, "1" = kurum


@dataclass
class DosyaBilgisi:
    """Dosya bilgileri."""
    dosya_no: str = ""
    dosya_tur: str = ""
    birim_adi: str = ""
    birim_il: str = ""
    birim_ilce: str = ""
    detsis_no: str = ""


@dataclass
class Imza:
    """Dijital imza bilgisi."""
    imzalayan_ad: str = ""
    imzalayan_soyad: str = ""
    tckn: str = ""
    makam: str = ""
    tarih: str = ""


@dataclass
class EkBilgisi:
    """Ek dosya bilgisi."""
    dosya_adi: str = ""
    tur: str = ""  # DED, PDF, vs.
    mime_turu: str = ""
    sira_no: int = 0
    imzali_mi: bool = False


@dataclass
class UyapBelge:
    """Çözümlenmiş UYAP belgesi."""
    # Metadata
    belge_id: str = ""
    konu: str = ""
    tarih: str = ""
    belge_no: str = ""
    guvenlik_kodu: str = ""
    mime_turu: str = ""

    # Oluşturan
    olusturan_kkk: str = ""
    olusturan_adi: str = ""
    olusturan_il: str = ""

    # Taraflar
    taraflar: list[Taraf] = field(default_factory=list)

    # Dosya bilgileri
    dosya_bilgisi: Optional[DosyaBilgisi] = None

    # İmzalar
    imzalar: list[Imza] = field(default_factory=list)

    # Ekler
    ekler: list[EkBilgisi] = field(default_factory=list)

    # Dağıtım
    dagitim_taraflar: list[Taraf] = field(default_factory=list)

    # PDF içerikleri
    ust_yazi_pdf: bytes = b""
    ek_pdfs: list[tuple[str, bytes]] = field(default_factory=list)  # (dosya_adi, içerik)

    # Çıkarılan metin
    ust_yazi_metin: str = ""
    ek_metinler: list[tuple[str, str]] = field(default_factory=list)  # (dosya_adi, metin)

    # Ham XML'ler (debug için)
    raw_xmls: dict[str, str] = field(default_factory=dict)

    # Referans numaraları (otomatik tespit)
    referanslar: list[dict] = field(default_factory=list)


class UyapParser:
    """UYAP EYP/UDF belge çözümleyici."""

    # Hukuki referans regex kalıpları
    REFERENCE_PATTERNS = [
        # Esas numarası: 2023/1234, 2024/5-678
        (r"(?:esas\s*(?:say[ıi]s[ıi]?\s*)?(?:no[:\.]?\s*)?)?(\d{4}[/-]\d{1,6})", "esas_no"),
        # Karar numarası: K.2023/1234
        (r"[Kk][\.\s]*(\d{4}[/-]\d{1,6})", "karar_no"),
        # Resmi Gazete: RG 32222
        (r"(?:resmi\s*gazete\s*(?:say[ıi]s[ıi]?\s*)?(?:no[:\.]?\s*)?)?(\d{5,6})", "rg_sayi"),
        # VKN/TCKN: 10-11 haneli numara
        (r"\b(\d{10,11})\b", "vkn_tckn"),
        # Kanun numarası: 4721 sayılı kanun
        (r"(\d{1,5})\s*(?:say[ıi]l[ıi]\s*kanun|say[ıi]l[ıi]\s*KHK)", "kanun_no"),
        # İhale kayıt no: 2023/123456
        (r"(?:ihale\s*(?:kay[ıi]t\s*)?(?:no[:\.]?\s*)?)?(\d{4}[/-]\d{4,8})", "ihale_no"),
        # Dosya numarası: D:2023/123
        (r"[Dd][\.\s:](\d{4}[/-]\d{1,6})", "dosya_no"),
        # Belge numarası: 63878147/(2025/395)/15011
        (r"(\d+/\(\d{4}/\d+\)/\d+)", "belge_no"),
    ]

    def parse_eyp(self, file_path_or_bytes) -> UyapBelge:
        """EYP/UDF dosyasını çözümle.

        Args:
            file_path_or_bytes: Dosya yolu (str) veya bayt verisi (bytes)

        Returns:
            UyapBelge: Çözümlenmiş belge bilgileri
        """
        belge = UyapBelge()

        try:
            if isinstance(file_path_or_bytes, (str, os.PathLike)):
                with open(file_path_or_bytes, "rb") as f:
                    data = f.read()
            else:
                data = file_path_or_bytes

            with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
                # Her XML dosyasını parse et
                self._parse_ustveri(zf, belge)
                self._parse_core(zf, belge)
                self._parse_belge_hedef(zf, belge)
                self._parse_imzalar(zf, belge)
                self._parse_ekler(zf, belge)
                self._parse_dosya_bilgileri(zf, belge)
                self._extract_pdfs(zf, belge)
                self._extract_references(belge)

        except zipfile.BadZipFile:
            logger.error("Geçersiz EYP/UDF dosyası (ZIP formatında değil)")
            raise ValueError("Geçersiz EYP/UDF dosyası: ZIP formatında değil")
        except Exception as e:
            logger.error(f"EYP/UDF parse hatası: {e}")
            raise

        return belge

    def _get_xml(self, zf: zipfile.ZipFile, path: str) -> Optional[ET.Element]:
        """ZIP içinden XML dosyası oku."""
        try:
            content = zf.read(path)
            # Namespace'leri temizle (bazı EYP dosyalarında sorunlu olabilir)
            return ET.fromstring(content)
        except KeyError:
            # Dosya yoksa None dön
            return None
        except ET.ParseError as e:
            logger.warning(f"XML parse hatası ({path}): {e}")
            return None

    def _get_text(self, element: Optional[ET.Element], tag: str, ns: str = "") -> str:
        """XML elementten metin değeri al."""
        if element is None:
            return ""
        # Namespace ile veya without dene
        for prefix, uri in NAMESPACES.items():
            try:
                found = element.find(f"{{{uri}}}{tag}")
                if found is not None and found.text:
                    return found.text.strip()
            except Exception:
                continue
        # Namespace olmadan dene
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        # .-tag formatında dene (Ustveri'de ns2:Konu gibi)
        for child in element:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == tag and child.text:
                return child.text.strip()
        return ""

    def _parse_ustveri(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """Ustveri.xml dosyasını parse et."""
        root = self._get_xml(zf, "Ustveri/Ustveri.xml")
        if root is None:
            return

        # Ham XML'i sakla
        try:
            belge.raw_xmls["ustveri"] = zf.read("Ustveri/Ustveri.xml").decode("utf-8", errors="replace")
        except Exception:
            pass

        # Tüm alt elementleri gez (namespace sorunlarını aşmak için)
        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "BelgeId" and child.text:
                belge.belge_id = child.text.strip()
            elif local == "Konu" and child.text:
                belge.konu = child.text.strip()
            elif local == "Tarih" and child.text:
                belge.tarih = child.text.strip()
            elif local == "BelgeNo" and child.text:
                belge.belge_no = child.text.strip()
            elif local == "GuvenlikKodu" and child.text:
                belge.guvenlik_kodu = child.text.strip()
            elif local == "MimeTuru" and child.text:
                belge.mime_turu = child.text.strip()

        # Oluşturan bilgileri
        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "Olusturan":
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "KKK" and sub.text:
                        belge.olusturan_kkk = sub.text.strip()
                    elif sub_local == "Adi" and sub.text:
                        belge.olusturan_adi = sub.text.strip()
                    elif sub_local == "Il" and sub.text:
                        belge.olusturan_il = sub.text.strip()

        # Ekler
        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "Ek":
                ek = EkBilgisi()
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "DosyaAdi" and sub.text:
                        ek.dosya_adi = sub.text.strip()
                    elif sub_local == "Tur" and sub.text:
                        ek.tur = sub.text.strip()
                    elif sub_local == "MimeTuru" and sub.text:
                        ek.mime_turu = sub.text.strip()
                    elif sub_local == "SiraNo" and sub.text:
                        try:
                            ek.sira_no = int(sub.text.strip())
                        except ValueError:
                            pass
                    elif sub_local == "ImzaliMi" and sub.text:
                        ek.imzali_mi = sub.text.strip().lower() == "true"
                belge.ekler.append(ek)

        # Dağıtım listesi
        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "Dagitim":
                taraf = Taraf()
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "IlkAdi" and sub.text:
                        taraf.ad = sub.text.strip()
                    elif sub_local == "Soyadi" and sub.text:
                        taraf.ad += " " + sub.text.strip() if taraf.ad else sub.text.strip()
                    elif sub_local == "TCKN" and sub.text:
                        taraf.tckn = sub.text.strip()
                    elif sub_local == "Ivedilik" and sub.text:
                        taraf.rol = sub.text.strip()  # NRM, ACIL, vs.
                if taraf.ad or taraf.tckn:
                    belge.dagitim_taraflar.append(taraf)

    def _parse_core(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """docProps/core.xml dosyasını parse et."""
        root = self._get_xml(zf, "docProps/core.xml")
        if root is None:
            return

        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "title" and child.text:
                # dc:title veya title
                if not belge.konu:
                    belge.konu = child.text.strip()
            elif local == "subject" and child.text:
                if not belge.konu:
                    belge.konu = child.text.strip()
            elif local == "creator" and child.text:
                if not belge.olusturan_adi:
                    belge.olusturan_adi = child.text.strip()

    def _parse_belge_hedef(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """BelgeHedef.xml dosyasını parse et — alıcı bilgileri."""
        root = self._get_xml(zf, "BelgeHedef/BelgeHedef.xml")
        if root is None:
            return

        try:
            belge.raw_xmls["belge_hedef"] = zf.read("BelgeHedef/BelgeHedef.xml").decode("utf-8", errors="replace")
        except Exception:
            pass

        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "Hedef" or local == "GercekSahis":
                taraf = Taraf()
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "IlkAdi" and sub.text:
                        taraf.ad = sub.text.strip()
                    elif sub_local == "Soyadi" and sub.text:
                        taraf.ad += " " + sub.text.strip() if taraf.ad else sub.text.strip()
                    elif sub_local == "TCKN" and sub.text:
                        taraf.tckn = sub.text.strip()
                if taraf.ad or taraf.tckn:
                    belge.taraflar.append(taraf)

    def _parse_imzalar(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """Imzalar/BelgeImza.xml dosyasını parse et."""
        root = self._get_xml(zf, "Imzalar/BelgeImza.xml")
        if root is None:
            return

        try:
            belge.raw_xmls["belge_imza"] = zf.read("Imzalar/BelgeImza.xml").decode("utf-8", errors="replace")
        except Exception:
            pass

        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "Imza":
                imza = Imza()
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "IlkAdi" and sub.text:
                        imza.imzalayan_ad = sub.text.strip()
                    elif sub_local == "Soyadi" and sub.text:
                        imza.imzalayan_soyad = sub.text.strip()
                    elif sub_local == "TCKN" and sub.text:
                        imza.tckn = sub.text.strip()
                    elif sub_local == "Makam" and sub.text:
                        imza.makam = sub.text.strip()
                    elif sub_local == "Tarih" and sub.text:
                        imza.tarih = sub.text.strip()
                belge.imzalar.append(imza)

    def _parse_ekler(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """Ekler klasöründeki dosya bilgilerini parse et."""
        # Ekler zaten Ustveri'den alındı, burada ek bilgileri güncellenir
        pass

    def _parse_dosya_bilgileri(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """Ekler/(1)_dosyaBilgileriV1.xml dosyasını parse et."""
        # dosyaBilgileri dosyasını bul
        dosya_bilgi_path = None
        for name in zf.namelist():
            if "dosyaBilgileri" in name and name.endswith(".xml"):
                dosya_bilgi_path = name
                break

        if dosya_bilgi_path is None:
            return

        root = self._get_xml(zf, dosya_bilgi_path)
        if root is None:
            return

        try:
            belge.raw_xmls["dosya_bilgileri"] = zf.read(dosya_bilgi_path).decode("utf-8", errors="replace")
        except Exception:
            pass

        dosya_bilgisi = DosyaBilgisi()

        for child in root.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            # Dosya bilgileri
            if local == "dosyano" and child.text:
                dosya_bilgisi.dosya_no = child.text.strip()
            elif local == "dosyatur" and child.text:
                dosya_bilgisi.dosya_tur = child.text.strip()
            elif local == "adi" and child.text:
                if not dosya_bilgisi.birim_adi:
                    dosya_bilgisi.birim_adi = child.text.strip()
            elif local == "il" and child.text:
                dosya_bilgisi.birim_il = child.text.strip()
            elif local == "ilce" and child.text:
                dosya_bilgisi.birim_ilce = child.text.strip()
            elif local == "detsisNo" and child.text:
                dosya_bilgisi.detsis_no = child.text.strip()

            # Taraflar
            if local == "taraf":
                taraf = Taraf()
                for sub in child.iter():
                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_local == "tarafadi" and sub.text:
                        taraf.ad = sub.text.strip()
                    elif sub_local == "tekilAlan" and sub.text:
                        taraf.tckn = sub.text.strip()
                    elif sub_local == "tarafrolu" and sub.text:
                        taraf.rol = sub.text.strip()
                    elif sub_local == "kisiMiKurummu" and sub.text:
                        taraf.kisi_mi_kurum_mu = sub.text.strip()
                belge.taraflar.append(taraf)

        if dosya_bilgisi.dosya_no:
            belge.dosya_bilgisi = dosya_bilgisi

    def _extract_pdfs(self, zf: zipfile.ZipFile, belge: UyapBelge):
        """ZIP içindeki PDF dosyalarını çıkar ve metinlerini oku."""
        for name in zf.namelist():
            if name.lower().endswith(".pdf"):
                try:
                    pdf_content = zf.read(name)
                    if "UstYazi" in name:
                        belge.ust_yazi_pdf = pdf_content
                    elif "Ekler" in name:
                        belge.ek_pdfs.append((name, pdf_content))
                except Exception as e:
                    logger.warning(f"PDF okuma hatası ({name}): {e}")

        # PyMuPDF ile metin çıkar
        self._extract_text_from_pdfs(belge)

    def _extract_text_from_pdfs(self, belge: UyapBelge):
        """PDF dosyalarından metin çıkar."""
        try:
            import pymupdf
        except ImportError:
            logger.warning("pymupdf yüklü değil — PDF metin çıkarma devre dışı")
            return

        # Üst yazı PDF'ini çıkar
        if belge.ust_yazi_pdf:
            text = self._pdf_to_text(belge.ust_yazi_pdf, pymupdf)
            if text:
                belge.ust_yazi_metin = text

        # Ek PDF'lerini çıkar
        for dosya_adi, pdf_content in belge.ek_pdfs:
            text = self._pdf_to_text(pdf_content, pymupdf)
            if text:
                belge.ek_metinler.append((dosya_adi, text))

    def _pdf_to_text(self, pdf_content: bytes, pymupdf) -> str:
        """PDF bayt verisinden metin çıkar."""
        try:
            doc = pymupdf.open(stream=pdf_content, filetype="pdf")
            text_parts = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text.strip())
            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.warning(f"PDF metin çıkarma hatası: {e}")
            return ""

    def _extract_references(self, belge: UyapBelge):
        """Belge metinlerinden hukuki referansları otomatik tespit et."""
        all_text = belge.ust_yazi_metin
        for _, text in belge.ek_metinler:
            all_text += "\n" + text

        # Ayrıca konu ve belge_no'dan da referans çıkar
        if belge.konu:
            all_text += "\n" + belge.konu
        if belge.belge_no:
            all_text += "\n" + belge.belge_no
        if belge.dosya_bilgisi and belge.dosya_bilgisi.dosya_no:
            all_text += "\n" + belge.dosya_bilgisi.dosya_no

        seen = set()
        for pattern, ref_type in self.REFERENCE_PATTERNS:
            for match in re.finditer(pattern, all_text, re.IGNORECASE):
                value = match.group(1) if match.lastindex else match.group(0)
                key = f"{ref_type}:{value}"
                if key in seen:
                    continue
                seen.add(key)

                # Arama terimi oluştur
                search_term = value
                if ref_type == "rg_sayi":
                    search_term = f"resmi gazete {value}"
                elif ref_type == "kanun_no":
                    search_term = f"{value} sayılı kanun"
                elif ref_type == "ihale_no":
                    search_term = f"ihale {value}"

                label = {
                    "esas_no": "Esas No",
                    "karar_no": "Karar No",
                    "rg_sayi": "Resmi Gazete Sayısı",
                    "vkn_tckn": "VKN/TCKN",
                    "kanun_no": "Kanun No",
                    "ihale_no": "İhale Kayıt No",
                    "dosya_no": "Dosya No",
                    "belge_no": "Belge No",
                }.get(ref_type, ref_type)

                belge.referanslar.append({
                    "type": ref_type,
                    "value": value,
                    "search_term": search_term,
                    "label": label,
                })

    def to_markdown(self, belge: UyapBelge) -> str:
        """Çözümlenmiş belgeyi Markdown formatında döndür."""
        lines = []
        lines.append("# UYAP Belge Analizi\n")

        # Üstveri
        lines.append("## Belge Bilgileri\n")
        if belge.konu:
            lines.append(f"**Konu:** {belge.konu}\n")
        if belge.belge_no:
            lines.append(f"**Belge No:** {belge.belge_no}\n")
        if belge.tarih:
            lines.append(f"**Tarih:** {belge.tarih}\n")
        if belge.guvenlik_kodu:
            lines.append(f"**Güvenlik Kodu:** {belge.guvenlik_kodu}\n")
        if belge.belge_id:
            lines.append(f"**Belge ID:** {belge.belge_id}\n")

        # Oluşturan
        if belge.olusturan_adi:
            lines.append(f"\n## Oluşturan\n")
            lines.append(f"- **Birim:** {belge.olusturan_adi}")
            if belge.olusturan_kkk:
                lines.append(f"- **KKK:** {belge.olusturan_kkk}")
            if belge.olusturan_il:
                lines.append(f"- **İl:** {belge.olusturan_il}")

        # Dosya bilgileri
        if belge.dosya_bilgisi:
            db = belge.dosya_bilgisi
            lines.append(f"\n## Dosya Bilgileri\n")
            if db.dosya_no:
                lines.append(f"- **Dosya No:** {db.dosya_no}")
            if db.dosya_tur:
                lines.append(f"- **Dosya Türü:** {db.dosya_tur}")
            if db.birim_adi:
                lines.append(f"- **Birim:** {db.birim_adi}")
            if db.birim_il:
                lines.append(f"- **İl:** {db.birim_il}")

        # Taraflar
        if belge.taraflar:
            lines.append(f"\n## Taraflar\n")
            for taraf in belge.taraflar:
                rol = f" ({taraf.rol})" if taraf.rol else ""
                lines.append(f"- **{taraf.ad}**{rol} — TCKN: {taraf.tckn}")

        # Dağıtım
        if belge.dagitim_taraflar:
            lines.append(f"\n## Dağıtım Listesi\n")
            for taraf in belge.dagitim_taraflar:
                lines.append(f"- **{taraf.ad}** — TCKN: {taraf.tckn}")

        # İmzalar
        if belge.imzalar:
            lines.append(f"\n## İmzalar\n")
            for imza in belge.imzalar:
                lines.append(f"- **{imza.imzalayan_ad} {imza.imzalayan_soyad}** — {imza.makam} ({imza.tarih})")

        # Ekler
        if belge.ekler:
            lines.append(f"\n## Ekler\n")
            for ek in belge.ekler:
                imza_durum = "✅" if ek.imzali_mi else "❌"
                lines.append(f"- {imza_durum} **{ek.dosya_adi}** ({ek.tur}, {ek.mime_turu})")

        # Referanslar
        if belge.referanslar:
            lines.append(f"\n## Tespit Edilen Referanslar\n")
            for ref in belge.referanslar:
                lines.append(f"- **{ref['label']}:** {ref['value']}")

        # Üst yazı metni (kısaltılmış)
        if belge.ust_yazi_metin:
            lines.append(f"\n## Üst Yazı Metni\n")
            text = belge.ust_yazi_metin[:5000]
            if len(belge.ust_yazi_metin) > 5000:
                text += "\n\n... (kesildi)"
            lines.append(f"```\n{text}\n```")

        # Ek metinleri
        for dosya_adi, text in belge.ek_metinler:
            lines.append(f"\n## Ek: {dosya_adi}\n")
            truncated = text[:5000]
            if len(text) > 5000:
                truncated += "\n\n... (kesildi)"
            lines.append(f"```\n{truncated}\n```")

        return "\n".join(lines)


# os import for path handling
import os