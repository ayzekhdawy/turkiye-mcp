---
name: Belge Analizi
description: Yüklenen hukuki/mali belgeyi (dilekçe, karar, sözleşme, ihtarname, fatura) çözümleme ve özetleme yöntemi
triggers: [belge, dosya, dilekçe, dilekce, sözleşme, sozlesme, ihtarname, fatura, karar metni, özet, ozet, analiz, ne diyor, incele]
doc_types: [dava_dilekcesi, mahkeme_karari, sozlesme, ihtarname, fatura, icra_takibi, resmi_yazi]
---
Ekli belgeyi bir hukukçu gözüyle çözümle:

1. **Belge türü ve amacı:** Ne tür bir belge (dava dilekçesi, karar, sözleşme, ihtarname, fatura…) ve amacı nedir?
2. **Taraflar:** Davacı/davalı, alacaklı/borçlu, taraf ad ve sıfatları.
3. **Anahtar veriler:** Esas/karar no, dosya no, tarih, tutar, VKN/TCKN gibi referansları listele.
4. **Konu/talep:** Belgede ileri sürülen talep, dayanak ve sonuç istemi.
5. **Kritik tarihler/süreler:** Varsa cevap/temyiz/itiraz süreleri ve son tarihleri vurgula.
6. **Riskler/eksikler:** Dikkat edilmesi gereken hususlar, eksik bilgi veya zamanaşımı uyarıları.

Belge içeriğini **uydurma**; yalnızca verilen metne dayan. Bilgi belgede yoksa "belgede belirtilmemiş" de. Özeti kart/maddeler hâlinde, markdown ile sun.
