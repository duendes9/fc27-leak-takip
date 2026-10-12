#!/usr/bin/env python3
"""
r/fut Gündem Özeti
------------------
r/fut'ta son 24 saatte en çok konuşulan gönderileri toplar, gürültüyü
(pack luck, mizah, "takımımı puanla" vb.) eler, konularına göre gruplar ve
Telegram'a tek mesajlık bir özet gönderir.

Kullanım:
  python reddit_ozet.py            # özeti hazırla ve Telegram'a gönder
  python reddit_ozet.py --yazdir   # sadece ekrana yazdır (deneme için)

Ortam değişkenleri: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
(leak_takip.py ile aynı secret'ları kullanır)
"""

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

from leak_takip import (ISTANBUL, UA, log, rss_coz, telegram_gonder, temizle)

SUBREDDIT = "fut"
SAAT_PENCERESI = 24            # son kaç saatin gönderileri
GOSTERILECEK = 12              # özette en fazla kaç gönderi
KATEGORI_BASI_MAKS = 4         # bir kategoriden en fazla kaç gönderi

JSON_URL = f"https://www.reddit.com/r/{SUBREDDIT}/hot.json?limit=100&raw_json=1"
RSS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/top/.rss?t=day&limit=50"

# Kategoriler: (anahtar, başlık, flair kelimeleri, başlık kelimeleri)
# Sıra önemli: bir gönderi ilk eşleştiği kategoriye girer.
KATEGORILER = [
    ("leak", "🔴 Leak & Haber",
     ["leak", "news", "rumour", "rumor", "official", "announcement"],
     ["leak", "leaked", "leaks", "rumour", "rumor", "rumoured", "rumored",
      "insider", "datamine", "futsheriff", "fut sheriff", "confirmed",
      "announced", "coming soon", "next week", "upcoming", "teaser"]),
    ("piyasa", "💰 Piyasa & Trading",
     ["trading", "market", "investment"],
     ["market", "trade", "trading", "trader", "price", "prices", "crash",
      "crashing", "invest", "investment", "flip", "flipping", "snipe",
      "sniping", "coins", "fodder", "tax", "profit", "sell", "selling",
      "buy now", "inflated", "rising", "dropping", "extinct"]),
    ("sbc", "🧩 SBC & Evolution",
     ["sbc", "evolution", "evo", "objectives"],
     ["sbc", "sbcs", "evo", "evos", "evolution", "evolutions", "objective",
      "objectives", "worth it", "worth doing", "upgrade", "player pick",
      "season pass", "gallery"]),
    ("promo", "⭐ Promo & Kartlar",
     ["promo", "team of the week", "totw", "card"],
     ["promo", "totw", "team of the week", "future stars", "icon", "icons",
      "hero", "heroes", "card", "cards", "review", "in game", "ingame",
      "loading screen", "team 2", "team 1", "toty", "special"]),
    ("oyun", "⚙️ Oyun, Meta & Sorunlar",
     ["gameplay", "meta", "tactics", "bug", "glitch", "discussion", "question"],
     ["meta", "tactic", "tactics", "formation", "custom tactics", "gameplay",
      "patch", "update", "bug", "glitch", "server", "servers", "rivals",
      "champions", "weekend league", "squad battles", "playstyle",
      "playstyles", "ea", "rewards", "dc", "disconnect"]),
]

# Bunlar özete girmez
GURULTU_FLAIR = ["meme", "humour", "humor", "pack luck", "packs", "rate my team",
                 "squad", "fluff", "shitpost", "showcase"]
GURULTU_BASLIK = ["packed", "pack luck", "my pack", "walkout", "walked out",
                  "rate my", "rtg", "road to glory", "first time ever",
                  "lol", "lmao", "meme", "finally got", "look who", "pulled",
                  "buy fc", "cheap coins", "coins for sale"]

# Öne çıkan isimleri bulurken atlanacak büyük harfli kelimeler
STOP = set("""
A An The I Im I'm Is Are Was Were Be It Its It's This That These Those What Why
How When Where Who Which Do Does Did Don't Can Can't Should Would Could Will Just
So And Or But If Then Than For Of On In At To From By With Without About My Me
We Our You Your They Their He His She Her Not No Yes Any All Some Every New Best
Worst Anyone Someone Everyone PSA Help Question Discussion Thoughts Opinion
EA FC FUT UT SBC SBCs Evo Evos Evolution TOTW Promo Team Week Rivals Champions
Squad Battles Weekend League Icon Icons Hero Heroes Card Cards Pack Packs Coins
Market Gold Rare Silver Bronze Day Today Tomorrow Tonight Monday Tuesday Wednesday
Thursday Friday Saturday Sunday Future Stars Playstyle PlayStyles Plus Meta
Glory Destined Ones Watch Trailblazers Sheriff Leak Leaks Leaked Official Update
Patch Gameplay Game Games Player Players One Two Three First Last Next Still Got
Get Ever Even Why's Who's There Here Again Also Really Actually Finally Please
Upgrade Upgrades Objectives Objective Gallery Season Pass Rewards Reward Tactics
""".split())


def _istek(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _istek_tekrarli(url):
    try:
        return _istek(url)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(8)
        return _istek(url)


def json_ile_getir():
    """Skor ve yorum sayısıyla birlikte gönderileri döner."""
    veri = json.loads(_istek_tekrarli(JSON_URL))
    simdi = time.time()
    gonderiler = []
    for c in veri.get("data", {}).get("children", []):
        p = c.get("data", {})
        if p.get("stickied") or p.get("over_18"):
            continue
        yas_saat = (simdi - p.get("created_utc", simdi)) / 3600
        if yas_saat > SAAT_PENCERESI:
            continue
        gonderiler.append({
            "baslik": temizle(p.get("title", "")),
            "flair": (p.get("link_flair_text") or "").strip(),
            "skor": int(p.get("score", 0)),
            "yorum": int(p.get("num_comments", 0)),
            "link": "https://www.reddit.com" + p.get("permalink", ""),
            "yas": yas_saat,
        })
    return gonderiler


def rss_ile_getir():
    """Yedek yol: skor yok, Reddit'in 'günün en iyileri' sırasını kullanır."""
    ogeler = rss_coz(_istek_tekrarli(RSS_URL))
    n = len(ogeler)
    gonderiler = []
    for i, (baslik, link, tarih) in enumerate(ogeler):
        gonderiler.append({
            "baslik": baslik, "flair": "", "skor": None, "yorum": None,
            "link": link, "yas": None,
            "sira_puani": n - i,  # üstteki daha önemli
        })
    return gonderiler


def _iceriyor(metin, kelimeler):
    metin = metin.lower()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", metin)
               for k in kelimeler)


def gurultu_mu(g):
    if g["flair"] and _iceriyor(g["flair"], GURULTU_FLAIR):
        return True
    return _iceriyor(g["baslik"], GURULTU_BASLIK)


def kategori_bul(g):
    for anahtar, _, flair_k, baslik_k in KATEGORILER:
        if g["flair"] and _iceriyor(g["flair"], flair_k):
            return anahtar
    for anahtar, _, _, baslik_k in KATEGORILER:
        if _iceriyor(g["baslik"], baslik_k):
            return anahtar
    return "diger"


def etkilesim(g):
    if g.get("skor") is None:
        return g.get("sira_puani", 0)
    # Yorumlar "konuşulma"yı daha iyi gösterir; yeni gönderilere hafif bonus
    taban = g["skor"] + 3 * g["yorum"]
    tazelik = 1.0 + max(0.0, (12 - (g["yas"] or 12)) / 24)  # 0-12 saat arası +%0-50
    return taban * tazelik


def one_cikan_isimler(gonderiler, adet=6):
    """Başlıklarda birden fazla kez geçen özel isimleri (oyuncu vb.) bulur."""
    sayac = Counter()
    for g in gonderiler:
        gorulen = set()
        for kelime in re.findall(r"\b[A-ZÀ-Ý][a-zà-ÿ'’\-]{2,}(?:\s[A-ZÀ-Ý][a-zà-ÿ'’\-]{2,})?\b",
                                 g["baslik"]):
            parcalar = kelime.split()
            if all(p.strip("'’") in STOP for p in parcalar):
                continue
            # İkili ifadede baştaki stop kelimeyi at ("Is Mbappe" -> "Mbappe")
            parcalar = [p for p in parcalar if p.strip("'’") not in STOP]
            ad = " ".join(parcalar)
            if ad and ad not in gorulen:
                gorulen.add(ad)
                sayac[ad] += 1
    return [(ad, n) for ad, n in sayac.most_common(adet) if n >= 2]


def kisa_sayi(n):
    if n is None:
        return ""
    return f"{n / 1000:.1f}K".replace(".0K", "K") if n >= 1000 else str(n)


def ozet_olustur(gonderiler, kaynak_turu):
    simdi = datetime.now(ISTANBUL).strftime("%d.%m %H:%M")
    temiz = [g for g in gonderiler if g["baslik"] and not gurultu_mu(g)]
    elenen = len(gonderiler) - len(temiz)
    for g in temiz:
        g["kategori"] = kategori_bul(g)
        g["puan"] = etkilesim(g)
    temiz.sort(key=lambda g: g["puan"], reverse=True)

    secilen, kat_sayac = [], Counter()
    for g in temiz:
        if kat_sayac[g["kategori"]] >= KATEGORI_BASI_MAKS:
            continue
        secilen.append(g)
        kat_sayac[g["kategori"]] += 1
        if len(secilen) >= GOSTERILECEK:
            break

    satirlar = [f"📊 <b>r/{SUBREDDIT} gündemi</b> · {simdi}",
                f"<i>Son {SAAT_PENCERESI} saat · {len(gonderiler)} gönderi tarandı, "
                f"{elenen} gürültü elendi</i>"]

    if not secilen:
        satirlar.append("\nKayda değer bir tartışma bulunamadı.")
        return "\n".join(satirlar)

    basliklar = {k: b for k, b, _, _ in KATEGORILER}
    basliklar["diger"] = "💬 Diğer gündem"
    sira = [k for k, _, _, _ in KATEGORILER] + ["diger"]
    for kat in sira:
        grup = [g for g in secilen if g["kategori"] == kat]
        if not grup:
            continue
        satirlar.append(f"\n<b>{basliklar[kat]}</b>")
        for g in grup:
            baslik = g["baslik"]
            if len(baslik) > 110:
                baslik = baslik[:107].rstrip() + "…"
            istatistik = ""
            if g["skor"] is not None:
                istatistik = f" <i>(⬆️{kisa_sayi(g['skor'])} 💬{kisa_sayi(g['yorum'])})</i>"
            satirlar.append(
                f'• <a href="{html.escape(g["link"], quote=True)}">{html.escape(baslik)}</a>{istatistik}')

    isimler = one_cikan_isimler(temiz)
    if isimler:
        satirlar.append("\n<b>🔥 En çok geçen isimler:</b> " +
                        ", ".join(f"{html.escape(ad)} ({n})" for ad, n in isimler))

    # Piyasa havası: piyasa gönderilerinde düşüş/yükseliş kelimeleri
    piyasa_basliklari = " ".join(g["baslik"].lower() for g in temiz if g["kategori"] == "piyasa")
    dusus = len(re.findall(r"\b(crash\w*|drop\w*|dump\w*|falling|tank\w*)\b", piyasa_basliklari))
    yukselis = len(re.findall(r"\b(ris\w*|spik\w*|inflat\w*|skyrocket\w*|pump\w*|extinct)\b",
                              piyasa_basliklari))
    if dusus + yukselis >= 2:
        if dusus > yukselis:
            hava = "📉 Piyasa sohbetleri daha çok <b>düşüş</b> üzerine; satış için acele, alım için sabır."
        elif yukselis > dusus:
            hava = "📈 Piyasa sohbetleri daha çok <b>yükseliş</b> üzerine; elindeki fodder'ı satmak için iyi zaman olabilir."
        else:
            hava = "↔️ Piyasa sohbetleri karışık; net bir yön yok."
        satirlar.append("\n" + hava)

    if kaynak_turu == "rss":
        satirlar.append("\n<i>Not: Reddit skor verisi alınamadı, sıralama Reddit'in günlük 'top' sırasına göre.</i>")
    return "\n".join(satirlar)


def main():
    p = argparse.ArgumentParser(description="r/fut gündem özeti")
    p.add_argument("--yazdir", action="store_true", help="Telegram'a göndermeden ekrana yaz")
    a = p.parse_args()

    kaynak_turu = "json"
    try:
        gonderiler = json_ile_getir()
        log(f"Reddit JSON: {len(gonderiler)} gönderi")
    except Exception as e:
        log(f"Reddit JSON okunamadı ({e}); RSS yedeği deneniyor")
        kaynak_turu = "rss"
        try:
            gonderiler = rss_ile_getir()
            log(f"Reddit RSS: {len(gonderiler)} gönderi")
        except Exception as e2:
            log(f"Reddit RSS de okunamadı ({e2}). Özet gönderilmedi.")
            return

    mesaj = ozet_olustur(gonderiler, kaynak_turu)
    if a.yazdir:
        print(mesaj)
    else:
        telegram_gonder(mesaj)
        log("Özet gönderildi.")


if __name__ == "__main__":
    main()
