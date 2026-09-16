# Marka varlıkları (GE Vernova)

Bu klasördeki logo dosyaları **git'e girmez** (`.gitignore`). Sebebi:
kurumsal logo projenin kaynak kodu değil, ayrı lisansa tabi bir varlıktır.

Arayüzün beklediği iki dosya:

| Dosya | Nerede görünür | Öneri |
|---|---|---|
| `ge-mark.png` | Başlık çubuğu, menü başlığı, giriş kartı | kare/yuvarlak amblem, en az 96×96 px, saydam zemin |
| `ge-vernova.png` | Giriş ekranı alt imzası | yatay "GE VERNOVA" kilidi, en az 480 px genişlik, saydam zemin |

Dosyalar yoksa arayüz **yazı işaretine** düşer (`BrandLogo.jsx`), yani
ekran bozulmaz — yalnızca görsel logo yerine "GE VERNOVA" yazısı çıkar.
