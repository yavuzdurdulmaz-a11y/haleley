import cloudscraper
from bs4 import BeautifulSoup
import time
import json
import os

BASE_URL = "https://mp3indirdur.life"
OUTPUT_M3U = "sarkilar.m3u"
OUTPUT_JSON = "sarkilar.json"
STATE_FILE = "state.json"

# ================= AYARLAR =================
# 5 saat çalışıp kapanması için (5 * 60 * 60 = 18000 saniye)
MAX_DURATION_SECONDS = 5 * 60 * 60 
# ===========================================

KATEGORILER = [
    "https://mp3indirdur.life/kategori/turkce-sarkilar",
    "https://mp3indirdur.life/kategori/yabanci-sarkilar",
    "https://mp3indirdur.life/kategori/kurtce-sarkilar",
    "https://mp3indirdur.life/kategori/yeni-eklenen-muzikler"
]

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cat_idx": 0, "page": 1, "islenmis_linkler": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def load_db():
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_outputs(db):
    db_sorted = sorted(db, key=lambda x: (x['artist'].lower(), x['title'].lower()))

    # JSON Kaydı
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(db_sorted, f, ensure_ascii=False, indent=4)

    # M3U Kaydı
    lines = ["#EXTM3U"]
    for song in db_sorted:
        lines.append(f'#EXTINF:-1 group-title="{song["artist"]}" tvg-logo="{song["image"]}", {song["title"]}')
        lines.append(song["audio"])

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"\n✅ Dosyalar güncellendi: {OUTPUT_JSON} ve {OUTPUT_M3U} (Toplam: {len(db_sorted)} şarkı)")

def parse_artist_title(raw_title):
    title_text = raw_title.replace(" Mp3 İndir", "").strip()
    if " - " in title_text:
        parts = title_text.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    elif "-" in title_text:
        parts = title_text.split("-", 1)
        return parts[0].strip(), parts[1].strip()
    else:
        return "Karışık", title_text

def scrape_session():
    start_time = time.time()
    state = load_state()
    db = load_db()
    
    islenmis_linkler = set(state["islenmis_linkler"])
    cat_idx = state["cat_idx"]
    page = state["page"]
    time_up = False

    while cat_idx < len(KATEGORILER):
        kategori_url = KATEGORILER[cat_idx]
        print(f"\n{'='*50}\nKATEGORİ: {kategori_url}\n{'='*50}")

        while True:
            if time.time() - start_time > MAX_DURATION_SECONDS:
                print("\n⏱️ 5 Saatlik sınır doldu. GitHub Actions oturumu durduruyor...")
                time_up = True
                break

            guncel_url = kategori_url if page == 1 else f"{kategori_url}?page={page}"
            print(f"---> Sayfa {page} taranıyor...")

            try:
                response = scraper.get(guncel_url, timeout=15)
                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                sarki_link_etiketleri = soup.select("ul.OrtaListe li a")

                if not sarki_link_etiketleri:
                    break

                for a_tag in sarki_link_etiketleri:
                    if time.time() - start_time > MAX_DURATION_SECONDS:
                        time_up = True
                        break

                    link = a_tag.get("href")
                    if not link: continue
                    full_url = link if link.startswith("http") else BASE_URL + link

                    if full_url in islenmis_linkler:
                        continue

                    islenmis_linkler.add(full_url)

                    try:
                        detail_res = scraper.get(full_url, timeout=15)
                        if detail_res.status_code != 200: continue
                        detail_soup = BeautifulSoup(detail_res.text, "html.parser")

                        title_tag = detail_soup.select_one(".mks h1")
                        raw_title = title_tag.text if title_tag else "Bilinmeyen Sarki"
                        artist, song_title = parse_artist_title(raw_title)

                        img_tag = detail_soup.select_one(".Mp3-images img")
                        img_url = img_tag.get("src") if img_tag and img_tag.get("src") else ""
                        if img_url and not img_url.startswith("http"): img_url = BASE_URL + img_url

                        audio_tag = detail_soup.select_one("audio#mp3player")
                        audio_url = ""
                        if audio_tag and audio_tag.get("src"):
                            temp_url = audio_tag.get("src")
                            temp_url = temp_url if temp_url.startswith("http") else BASE_URL + temp_url
                            try:
                                res_redirect = scraper.get(temp_url, stream=True, timeout=15)
                                audio_url = res_redirect.url
                                res_redirect.close()
                            except:
                                audio_url = temp_url

                        if audio_url:
                            print(f"  + Eklendi: [{artist}] - {song_title}")
                            db.append({
                                "artist": artist,
                                "title": song_title,
                                "image": img_url,
                                "audio": audio_url,
                                "source_url": full_url
                            })

                        time.sleep(1)

                    except Exception:
                        pass 

                if time_up: break
                page += 1

            except Exception as e:
                print(f"Sayfa islenirken hata: {e}")
                break 

        if time_up: break
        cat_idx += 1
        page = 1

    state["cat_idx"] = cat_idx
    state["page"] = page
    state["islenmis_linkler"] = list(islenmis_linkler)
    
    save_state(state)
    save_outputs(db)

    return not time_up 

if __name__ == "__main__":
    is_finished = scrape_session()
    if is_finished:
        print("\n🎉 TÜM ŞARKILAR VE SAYFALAR BAŞARIYLA ÇEKİLDİ!")
        # İşlem tamamen bitince state.json'ı siliyoruz ki bir daha baştan başlamasın
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    else:
        print("\n⚙️ 5 saatlik görev tamamlandı. Veriler GitHub'a kaydedilecek ve 1 saat sonra cron ile devam edilecek.")
