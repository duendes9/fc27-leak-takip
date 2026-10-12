# FC 27 Leak Takip – Kurulum

Bu sistem 10 dakikada bir FC 27 Ultimate Team leak ve haberlerini tarar, yeni bir şey çıkınca Telegram'dan mesaj atar. Ücretsizdir ve bilgisayarının açık olması gerekmez: GitHub'ın sunucularında çalışır.

Sadece herkese açık haber sitelerini okur (Google News, Reddit, FUT.GG, Dexerto, FIFA UTeam, Football Gaming Zone). EA hesabına, web app'e veya companion app'e **hiç bağlanmaz**, bu yüzden ban riski yoktur.

Toplam kurulum süresi: ~15 dakika.

---

## 1. Telegram botunu oluştur (5 dk)

1. Telegram'da **@BotFather**'ı aç, `/newbot` yaz.
2. Bota bir isim ver (ör. `FC27 Leak`), sonra `bot` ile biten bir kullanıcı adı ver (ör. `murat_fc27_leak_bot`).
3. BotFather sana uzun bir **token** verecek (ör. `7412345678:AAH...`). Bunu bir yere kopyala. **Kimseyle paylaşma.**
4. Yeni botunun sohbetini aç ve **Start**'a bas, sonra bir mesaj yaz (ör. `merhaba`).

### Chat ID'ni bul

Tarayıcıda şu adresi aç (TOKEN yerine kendi token'ını yaz):

```
https://api.telegram.org/botTOKEN/getUpdates
```

Çıkan yazıda `"chat":{"id":123456789` gibi bir kısım göreceksin. Bu sayı senin **chat ID**'n. Boş geliyorsa bota tekrar mesaj atıp sayfayı yenile.

---

## 2. GitHub'a yükle (7 dk)

1. https://github.com adresinde ücretsiz hesap aç (yoksa).
2. Sağ üstten **+ → New repository**. İsim: `fc27-leak-takip`. **Public** seç (aşağıdaki nota bak), **Create repository**.
3. Açılan sayfada **uploading an existing file** linkine tıkla ve zip'ten çıkan dosyaları sürükle:
   - `leak_takip.py`
   - `KURULUM.md`
   - `.github` klasörü (içinde `workflows/leak-takip.yml`)

   > Not: `.github` gizli klasör olduğu için bilgisayarında görünmeyebilir. Görünmüyorsa: repoda **Add file → Create new file** de, dosya adına `.github/workflows/leak-takip.yml` yaz ve `leak-takip.yml` dosyasının içeriğini yapıştır.
4. **Commit changes**'a bas.

### Token ve Chat ID'yi gizli olarak ekle

1. Repoda **Settings → Secrets and variables → Actions → New repository secret**.
2. İki tane ekle:
   - Ad: `TELEGRAM_BOT_TOKEN` → Değer: BotFather'dan aldığın token
   - Ad: `TELEGRAM_CHAT_ID` → Değer: chat ID'n

Bunlar şifrelenir, repo public olsa bile kimse göremez.

---

## 3. Çalıştır ve dene (2 dk)

1. Repoda **Actions** sekmesine git. İş akışlarını etkinleştirmeni isterse onayla.
2. Soldan **FC 27 Leak Takip**'i seç → **Run workflow** → **Run workflow**.
3. Bir dakika içinde Telegram'a şu mesaj gelmeli: **✅ FC 27 Leak Takip çalışıyor**.

Bundan sonra kendiliğinden her 10 dakikada bir çalışır. İlk çalışmada mevcut haberleri sadece öğrenir, sana yığın halinde mesaj atmaz; sonrasında sadece **yeni** çıkanları bildirir.

---

## Mesajlar nasıl görünecek?

- 🔴 **LEAK / SÖYLENTİ**: başlıkta leak, rumour, insider vb. geçen haberler. En önemli olanlar bunlar.
- 🟡 **FC 27 UT haberi**: SBC, promo, TOTW, evolution gibi Ultimate Team haberleri.
- 💡 Konuya göre kısa bir ipucu (ör. SBC haberi → fodder fiyatları artabilir).

Bir leak düştüğünde bana (Claude'a) linki yapıştırırsan, PS fiyatlarına bakıp somut bir al-sat planı çıkarabilirim.

---

## Türkçe çeviri

Haber ve Reddit başlıkları ücretsiz MyMemory çeviri servisiyle Türkçeye çevrilir. Leak bildirimlerinde Türkçe başlığın altında orijinal İngilizce başlık da durur (oyuncu adları ve terimler karışmasın diye). SBC, evo, fodder, TOTW gibi oyun terimleri çeviride korunur.

- Ücretsiz sınır günde ~5.000 karakter; normal kullanımda yeter. Sınır dolarsa başlıklar o gün İngilizce gelir, bildirimler kesilmez.
- Sınırı ~50.000'e çıkarmak istersen `MYMEMORY_EMAIL` adında bir secret ekleyip e-posta adresini yazabilir, iki `.yml` dosyasındaki `env:` kısmına `MYMEMORY_EMAIL: ${{ secrets.MYMEMORY_EMAIL }}` satırını ekleyebilirsin.
- Çeviriyi kapatmak için aynı yere `CEVIRI: "0"` ekle.

---

## r/fut gündem özeti

`reddit_ozet.py` ve `.github/workflows/reddit-ozet.yml` her gün **12:00 ve 19:30**'da (İstanbul) r/fut'ta son 24 saatte en çok konuşulan gönderileri tek mesajda gönderir:

- Pack luck, mizah, "takımımı puanla" gibi gürültüyü eler.
- Gönderileri beğeni + yorum sayısına göre sıralar (yorumlar daha ağır basar, yeni gönderilere küçük bonus).
- Konularına göre gruplar: 🔴 Leak & Haber, 💰 Piyasa & Trading, 🧩 SBC & Evolution, ⭐ Promo & Kartlar, ⚙️ Oyun, Meta & Sorunlar.
- Başlıklarda en çok geçen oyuncu isimlerini ve piyasa sohbetlerinin yönünü (düşüş/yükseliş) gösterir.

Elle denemek için: **Actions → r/fut Gündem Özeti → Run workflow**. Saatleri değiştirmek için `reddit-ozet.yml` içindeki cron satırlarını düzenle (saatler UTC, İstanbul = UTC+3).

---

## Bilmen gerekenler

- **Neden public repo?** GitHub, public repolarda bu çalıştırmaları ücretsiz ve sınırsız veriyor. Private repoda aylık 2.000 dakika sınırı var ve 10 dakikada bir çalışma bunu aşar. Kodun içinde gizli bir şey yok; token ve chat ID "secret" olarak saklandığı için görünmez.
- **Gecikme:** GitHub yoğun saatlerde zamanlanmış çalışmaları birkaç dakika (bazen 10-15 dk) geciktirebilir. Yani bildirimler "en geç ~10-20 dakika içinde" gelir.
- **60 gün kuralı:** Repoda 60 gün hiç değişiklik olmazsa GitHub zamanlanmış çalışmayı durdurur ve sana e-posta atar. Actions sekmesinden tek tıkla tekrar açabilirsin.
- **Kaynak bazen okunamaz:** Bazı siteler (özellikle Reddit, FUTBIN) GitHub sunucularını zaman zaman engelleyebilir. Sistem o kaynağı atlar, diğerlerinden devam eder. Actions sekmesindeki çalışma kayıtlarında hangi kaynağın okunduğu yazar.
- **X (Twitter):** X'teki paylaşımlar doğrudan okunmuyor (X'in API'si ücretli). FUTSheriff gibi hesapların leak'leri genelde dakikalar içinde Reddit'e ve haber sitelerine düştüğü için onlar üzerinden yakalanır.
- **Leak'ler yanılabilir.** Tek bir söylentiye bakiyenin büyük kısmını yatırma.

---

## Ayar değiştirmek istersen

`leak_takip.py` dosyasının başındaki listeler:

- `KAYNAKLAR`: okunan siteler
- `LEAK_KELIMELERI` / `UT_KELIMELERI`: hangi başlıkların bildirileceği
- `ENGEL_KELIMELERI`: atlanacak başlıklar (coin satış spamı vb.)

Kontrol sıklığını değiştirmek için `.github/workflows/leak-takip.yml` içindeki `*/10` değerini değiştir (ör. `*/15` = 15 dakikada bir).

---

## Alternatif: Kendi bilgisayarında çalıştırmak

Sürekli açık bir bilgisayarın varsa (Python 3.9+ yüklü):

```bash
# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="token"; $env:TELEGRAM_CHAT_ID="chatid"
python leak_takip.py --test-mesaji   # deneme mesajı
python leak_takip.py --dongu         # 10 dakikada bir sürekli kontrol

# macOS / Linux
export TELEGRAM_BOT_TOKEN="token" TELEGRAM_CHAT_ID="chatid"
python3 leak_takip.py --dongu
```
