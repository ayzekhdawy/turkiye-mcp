"""UYAP EYP/UDF Belge Çözümleyici.

EYP (Elektronik Yazışma Paketi) ve UDF dosyalarını analiz eder.
Bu dosyalar UYAP (Ulusal Yargı Ağı Projesi) sistemi tarafından kullanılır.

EYP yapısı:
- ZIP arşivi (PK başlığı)
- _rels/.rels — İlişkiler
- [Content_Types].xml — İçerik türleri
- Ustveri/Ustveri.xml — Üstveri (belge metadata)
- UstYazi/ustyazi.pdf — Üstyazı (asıl belge)
- BelgeHedef/BelgeHedef.xml — Belge hedefi (alıcı bilgileri)
- Ekler/ — Ek dosyalar (PDF, XML)
- Imzalar/ — Dijital imzalar
- docProps/core.xml — Belge özellikleri
- PaketOzeti/ — Paket özeti (bütünlük doğrulama)
- NihaiOzet/ — Nihai özet (imza özeti)

UDF yapısı:
- Benzer ZIP arşivi, farklı XML şemaları
"""

from .parser import UyapParser, UyapBelge

__all__ = ["UyapParser", "UyapBelge"]