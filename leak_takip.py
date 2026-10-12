#!/usr/bin/env python3
"""
FC 27 Leak Takip
----------------
FC 27 Ultimate Team leak ve haberlerini haber sitelerinden okur,
yeni bir şey çıktığında Telegram'dan bildirim gönderir.

Sadece herkese açık haber sitelerini okur. EA hesabına, web app'e veya
companion app'e hiçbir şekilde bağlanmaz.

Kullanım:
  python leak_takip.py              # bir kez kontrol et (GitHub Actions bunu kullanır)
  python leak_takip.py --dongu      # sürekli çalış, 10 dakikada bir kontrol et
  python leak_takip.py --chat-id-bul  # Telegram chat ID'ni bulmana yardım eder
  python leak_takip.py --test-mesaji  # Telegram'a deneme mesajı gönderir

Gerekli ortam değişkenleri:
  TELEGRAM_BOT_TOKEN   BotFather'dan aldığın token
  TELEGRAM_CHAT_ID     Mesajların gideceği chat ID
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------

KONTROL_ARALIGI_SN = 600          # --dongu modunda 10 dakika
DURUM_DOSYASI = os.environ.get("DURUM_DOSYASI", "goruldu.json")
MAKS_KAYIT = 3000                 # durum dosyasında tutulacak en fazla kayıt
MAKS_MESAJ_TEK_SEFERDE = 10       # bir kontrolde en fazla kaç bildirim
ESKI_HABER_SAAT = 48              # bundan eski haberleri bildirme
ISTANBUL = timezone(timedelta(hours=3))

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 FC27LeakTakip/1.0")

# tur: "rss" (RSS/Atom akışı) veya "sayfa" (haber listesi HTML sayfası)
# genel: True ise kaynak her türlü oyun haberi yayınlar, FC 27 geçmesi şartı aranır
KAYNAKLAR = [
    {"ad": "Google News", "tur": "rss", "genel": True,
     "url": "https://news.google.com/rss/search?q=%22FC+27%22+(leak+OR+leaked+OR+SBC+OR+promo)+when:2d&hl=en-US&gl=US&ceid=US:en"},
    {"ad": "Google News", "tur": "rss", "genel": True,
     "url": "https://news.google.com/rss/search?q=%22EA+FC+27%22+Ultimate+Team+when:2d&hl=en-US&gl=US&ceid=US:en"},
    {"ad": "Reddit r/EASportsFC", "tur": "rss", "genel": True,
     "url": "https://www.reddit.com/r/EASportsFC/new/.rss"},
    {"ad": "Reddit r/fut", "tur": "rss", "genel": True,
     "url": "https://www.reddit.com/r/fut/new/.rss"},
    {"ad": "FIFA UTeam", "tur": "rss", "genel": False,
     "url": "https://fifauteam.com/feed/"},
    {"ad": "Dexerto", "tur": "rss", "genel": True,
     "url": "https://www.dexerto.com/ea-sports-fc/feed/"},
    {"ad": "Football Gaming Zone", "tur": "rss", "genel": True,
     "url": "https://footballgamingzone.com/feed/"},
    {"ad": "FUTBIN", "tur": "sayfa", "genel": False,
     "url": "https://www.futbin.com/news",
     "link_regex": r'href="(/news/articles/\d+/[^"#?]+)"',
     "taban": "https://www.futbin.com"},
    {"ad": "FUT.GG", "tur": "sayfa", "genel": False,
     "url": "https://www.fut.gg/news/",
     "link_regex": r'href="((?:https://www\.fut\.gg)?/news/[a-z0-9][a-z0-9-]+/)"',
     "taban": "https://www.fut.gg"},
]

# Başlıkta geçerse "LEAK" olarak işaretlenir (en yüksek öncelik)
LEAK_KELIMELERI = [
    "leak", "leaked", "leaks", "rumor", "rumour", "rumours", "rumors",
    "rumoured", "rumored", "reportedly",
    "insider", "datamine", "datamined", "spotted", "teased", "teaser",
    "futsheriff", "fut sheriff", "asyfut", "detectivefut",
]

# Başlıkta geçerse "Ultimate Team ile ilgili haber" sayılır
UT_KELIMELERI = [
    "sbc", "promo", "totw", "team of the week", "icon", "hero", "evo",
    "evolution", "objective", "upgrade", "future stars", "trailblazers",
    "centurions", "ones to watch", "otw", "rttk", "road to the knockouts",
    "toty", "team of the year", "winter wildcards", "fut birthday",
    "black friday", "thunderstruck", "rulebreakers", "pack", "token",
    "player pick", "release date", "coming", "upcoming", "next", "revealed",
    "prediction", "predictions", "market", "fodder", "ultimate team", "fut",
    "content", "squad", "card", "cards", "draft", "champions", "rivals",
]

# Başlıkta FC 27'yi işaret eden ifadeler (genel kaynaklar için şart)
FC27_DESENI = re.compile(
    r"\b(ea\s*(sports\s*)?fc\s*27|fc\s*27|fut\s*27|fifa\s*27|eafc\s*27|fc27)\b",
    re.IGNORECASE,
)

# Bu ifadeleri içeren başlıklar atlanır (satış spamı vb.)
ENGEL_KELIMELERI = [
    "buy fc", "cheap coins", "coins for sale", "buy coins", "coin seller",
    "mmoexp", "u4gm", "iggm", "ezbuff", "eznpc", "fifa points for",
    "career mode", "pro clubs", "the grounds", "trophy", "achievement",
]

# Başlıkta geçen konuya göre kısa yatırım ipucu (Türkçe)
IPUCLARI = [
    (("sbc",), "SBC haberi: yüksek reytingli fodder (83-86) talebi artabilir."),
    (("icon",), "İkon haberi: 84-86 fodder ve ikon fiyatları hareketlenebilir."),
    (("toty", "team of the year"), "TOTY yaklaşırken piyasa genelde önce düşer; nakit tutmayı düşün."),
    (("black friday",), "Black Friday döneminde paket arzı artar, fiyatlar düşer: satış için erken davran."),
    (("totw", "team of the week"), "TOTW: inform kartlar ve SBC fodder fiyatlarına bak."),
    (("evo", "evolution"), "Evolution: şartlara uyan ucuz oyuncular kısa sürede pahalanabilir."),
    (("promo", "future stars", "trailblazers", "centurions", "ones to watch"),
     "Promo haberi: promo çıkış saatinden önce fodder fiyatlarını kontrol et."),
]

# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def log(msg):
    zaman = datetime.now(ISTANBUL).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{zaman}] {msg}", flush=True)


def indir(url, zaman_asimi=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
        veri = r.read()
        kodlama = r.headers.get_content_charset() or "utf-8"
    return veri.decode(kodlama, errors="replace")


def temizle(metin):
    if not metin:
        return ""
    metin = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", metin, flags=re.S)
    metin = re.sub(r"<[^>]+>", " ", metin)
    metin = html.unescape(metin)
    return re.sub(r"\s+", " ", metin).strip()


def tarih_coz(metin):
    """RSS (RFC 822) veya Atom (ISO 8601) tarihini datetime'a çevirir."""
    if not metin:
        return None
    metin = metin.strip()
    from email.utils import parsedate_to_datetime
    try:
        d = parsedate_to_datetime(metin)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(metin.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def yerel_ad(etiket):
    return etiket.rsplit("}", 1)[-1].lower()


# ---------------------------------------------------------------------------
# Akış okuma
# ---------------------------------------------------------------------------


def rss_coz(metin):
    """RSS veya Atom akışından (baslik, link, tarih) listesi döner.
    Önce düzgün XML olarak dener, olmazsa regex ile esnek okur
    (bazı siteler hatalı XML yayınlıyor)."""
    ogeler = []
    try:
        kok = ET.fromstring(metin.encode("utf-8"))
        for el in kok.iter():
            ad = yerel_ad(el.tag)
            if ad not in ("item", "entry"):
                continue
            baslik, link, tarih = "", "", None
            for c in el:
                cad = yerel_ad(c.tag)
                if cad == "title":
                    baslik = temizle(c.text or "")
                elif cad == "link":
                    href = c.attrib.get("href")
                    if href and (not link or c.attrib.get("rel", "alternate") == "alternate"):
                        link = href
                    elif not href and c.text:
                        link = c.text.strip()
                elif cad in ("pubdate", "published", "updated", "date") and tarih is None:
                    tarih = tarih_coz(c.text)
            if baslik and link:
                ogeler.append((baslik, link, tarih))
        return ogeler
    except ET.ParseError:
        pass

    # Esnek (regex) okuma
    for m in re.finditer(r"<(item|entry)\b(.*?)</\1>", metin, flags=re.S | re.I):
        govde = m.group(2)
        b = re.search(r"<title[^>]*>(.*?)</title>", govde, flags=re.S | re.I)
        l = (re.search(r'<link[^>]*href="([^"]+)"', govde, flags=re.I)
             or re.search(r"<link[^>]*>(.*?)</link>", govde, flags=re.S | re.I))
        t = re.search(r"<(pubDate|published|updated)[^>]*>(.*?)</\1>", govde, flags=re.S | re.I)
        if b and l:
            ogeler.append((temizle(b.group(1)), temizle(l.group(1)),
                           tarih_coz(t.group(2)) if t else None))
    return ogeler


def sayfa_coz(metin, kaynak):
    """Haber listesi sayfasından makale linklerini çıkarır.
    Başlığı URL'deki slug'dan üretir (sayfa yapısı değişse bile çalışsın diye)."""
    ogeler, gorulen = [], set()
    for yol in re.findall(kaynak["link_regex"], metin):
        url = urllib.parse.urljoin(kaynak["taban"], yol)
        if url in gorulen:
            continue
        gorulen.add(url)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        baslik = slug.replace("-", " ").strip()
        baslik = re.sub(r"\bfc (\d\d)\b", r"FC \1", baslik, flags=re.I)
        baslik = baslik[:1].upper() + baslik[1:]
        ogeler.append((baslik, url, None))
    return ogeler


# ---------------------------------------------------------------------------
# Filtreleme ve sınıflandırma
# ---------------------------------------------------------------------------


def kelime_var(metin, kelimeler):
    metin = metin.lower()
    for k in kelimeler:
        if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", metin):
            return k
    return None


def siniflandir(baslik, kaynak):
    """('leak' | 'haber' | None) döner. None: bildirilmeyecek."""
    if kelime_var(baslik, ENGEL_KELIMELERI):
        return None
    fc27 = bool(FC27_DESENI.search(baslik))
    # Eski oyunların haberlerini ele (ör. "FC 26 ...", "FC 28 Pre-Order")
    eski_oyun = re.search(r"\b(fc|fut|fifa)\s*(2[0-68]|1\d)\b", baslik, re.I)
    if eski_oyun and not fc27:
        return None
    if kaynak["genel"] and not fc27:
        # Reddit gibi genel kaynaklarda "FC 27" yazmayabilir; bu durumda sadece
        # açıkça leak olan ve UT kelimesi içeren başlıkları al
        if not (kelime_var(baslik, LEAK_KELIMELERI) and kelime_var(baslik, UT_KELIMELERI)):
            return None
    if kelime_var(baslik, LEAK_KELIMELERI):
        return "leak"
    if kelime_var(baslik, UT_KELIMELERI):
        return "haber"
    return None


def ipucu_bul(baslik):
    for kelimeler, ipucu in IPUCLARI:
        if kelime_var(baslik, kelimeler):
            return ipucu
    return None


def anahtar(baslik):
    # Google News aynı haberi farklı linklerle ve " - Site Adı" ekiyle verebiliyor
    normal = re.sub(r"\s+[-–|]\s+[^-–|]{2,40}$", "", baslik)
    normal = re.sub(r"[^a-z0-9]+", " ", normal.lower()).strip()
    return hashlib.sha1(normal.encode()).hexdigest()[:16]


def link_anahtari(link):
    return "u:" + hashlib.sha1(link.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Durum (görülen haberler)
# ---------------------------------------------------------------------------


def durum_yukle():
    try:
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            d = json.load(f)
            return d.get("goruldu", []), d.get("ilk_calisma_bitti", False)
    except (FileNotFoundError, json.JSONDecodeError):
        return [], False


def durum_kaydet(goruldu, ilk_bitti):
    goruldu = goruldu[-MAKS_KAYIT:]
    gecici = DURUM_DOSYASI + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump({"goruldu": goruldu, "ilk_calisma_bitti": ilk_bitti}, f)
    os.replace(gecici, DURUM_DOSYASI)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def telegram_gonder(metin):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log("UYARI: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanımlı değil. Mesaj ekrana yazılıyor:")
        print(metin)
        return False
    veri = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": metin,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for deneme in range(3):
        try:
            req = urllib.request.Request(url, data=veri, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                if json.load(r).get("ok"):
                    return True
        except urllib.error.HTTPError as e:
            govde = e.read().decode(errors="replace")
            log(f"Telegram hatası ({e.code}): {govde[:200]}")
            if e.code == 429:
                time.sleep(5)
                continue
            return False
        except Exception as e:  # ağ hatası
            log(f"Telegram bağlantı hatası: {e}")
        time.sleep(2)
    return False


def mesaj_olustur(tur, baslik, link, kaynak_adi, tarih):
    simge = "🔴 <b>LEAK / SÖYLENTİ</b>" if tur == "leak" else "🟡 <b>FC 27 UT haberi</b>"
    satirlar = [simge, "", f"<b>{html.escape(baslik)}</b>", f"Kaynak: {html.escape(kaynak_adi)}"]
    if tarih:
        satirlar.append("Yayın: " + tarih.astimezone(ISTANBUL).strftime("%d.%m %H:%M") + " (İstanbul)")
    ipucu = ipucu_bul(baslik)
    if ipucu:
        satirlar.append(f"💡 {ipucu}")
    if tur == "leak":
        satirlar.append("⚠️ Leak'ler yanlış çıkabilir; tek söylentiye bakiyenin büyük kısmını yatırma.")
    satirlar.append(f'<a href="{html.escape(link, quote=True)}">Habere git</a>')
    return "\n".join(satirlar)


# ---------------------------------------------------------------------------
# Ana kontrol
# ---------------------------------------------------------------------------


def kontrol_et():
    goruldu_liste, ilk_bitti = durum_yukle()
    goruldu = set(goruldu_liste)
    simdi = datetime.now(timezone.utc)
    yeniler = []
    basarili_kaynak = 0

    for kaynak in KAYNAKLAR:
        try:
            metin = indir(kaynak["url"])
            ogeler = rss_coz(metin) if kaynak["tur"] == "rss" else sayfa_coz(metin, kaynak)
            basarili_kaynak += 1
            log(f"{kaynak['ad']}: {len(ogeler)} öğe")
        except Exception as e:
            log(f"{kaynak['ad']}: okunamadı ({e.__class__.__name__}: {e})")
            continue

        for baslik, link, tarih in ogeler:
            k1, k2 = anahtar(baslik), link_anahtari(link)
            if k1 in goruldu or k2 in goruldu:
                continue
            goruldu.add(k1)
            goruldu.add(k2)
            goruldu_liste.extend([k1, k2])
            if tarih and simdi - tarih > timedelta(hours=ESKI_HABER_SAAT):
                continue
            tur = siniflandir(baslik, kaynak)
            if tur:
                yeniler.append((tur, baslik, link, kaynak["ad"], tarih))

    if not ilk_bitti:
        # İlk çalışmada mevcut haberleri bildirme, sadece kaydet (spam olmasın)
        durum_kaydet(goruldu_liste, True)
        log(f"İlk çalışma: {len(goruldu_liste)} kayıt öğrenildi, bildirim gönderilmedi.")
        telegram_gonder(
            "✅ <b>FC 27 Leak Takip çalışıyor</b>\n\n"
            f"{basarili_kaynak}/{len(KAYNAKLAR)} kaynak okundu. "
            "Bundan sonra yeni leak ve UT haberleri buraya düşecek."
        )
        return

    # Önce leak'ler, sonra haberler
    yeniler.sort(key=lambda x: (x[0] != "leak",))
    gonderilen = 0
    for tur, baslik, link, kaynak_adi, tarih in yeniler[:MAKS_MESAJ_TEK_SEFERDE]:
        if telegram_gonder(mesaj_olustur(tur, baslik, link, kaynak_adi, tarih)):
            gonderilen += 1
        time.sleep(1)
    if len(yeniler) > MAKS_MESAJ_TEK_SEFERDE:
        telegram_gonder(f"…ve {len(yeniler) - MAKS_MESAJ_TEK_SEFERDE} haber daha var (sınır aşıldı).")

    durum_kaydet(goruldu_liste, True)
    log(f"Bitti: {len(yeniler)} yeni ilgili haber, {gonderilen} bildirim gönderildi. "
        f"({basarili_kaynak}/{len(KAYNAKLAR)} kaynak okundu)")


def chat_id_bul():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Önce TELEGRAM_BOT_TOKEN ortam değişkenini tanımla.")
        sys.exit(1)
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
        veri = json.load(r)
    bulunan = {}
    for u in veri.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            bulunan[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not bulunan:
        print("Hiç mesaj bulunamadı. Telegram'da botuna bir mesaj (ör. 'merhaba') gönder ve tekrar dene.")
    for cid, ad in bulunan.items():
        print(f"Chat ID: {cid}   ({ad})")


def main():
    p = argparse.ArgumentParser(description="FC 27 leak takip ve Telegram bildirimi")
    p.add_argument("--dongu", action="store_true", help="10 dakikada bir sürekli kontrol et")
    p.add_argument("--chat-id-bul", action="store_true", help="Telegram chat ID'ni göster")
    p.add_argument("--test-mesaji", action="store_true", help="Telegram'a deneme mesajı gönder")
    a = p.parse_args()

    if a.chat_id_bul:
        chat_id_bul()
        return
    if a.test_mesaji:
        ok = telegram_gonder("👋 FC 27 Leak Takip deneme mesajı. Bunu görüyorsan kurulum tamam!")
        print("Gönderildi." if ok else "Gönderilemedi, token ve chat ID'yi kontrol et.")
        return
    if a.dongu:
        while True:
            try:
                kontrol_et()
            except Exception as e:
                log(f"Beklenmeyen hata: {e}")
            time.sleep(KONTROL_ARALIGI_SN)
    else:
        kontrol_et()


if __name__ == "__main__":
    main()
