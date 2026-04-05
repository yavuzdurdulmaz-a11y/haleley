import requests
from bs4 import BeautifulSoup

BASE_URL = "https://mp3indirdur.life"
CATEGORY_URL = f"{BASE_URL}/kategori/turkce-sarkilar"
OUTPUT_FILE = "sarkilar.m3u"

def scrape_songs():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        print(f"[{CATEGORY_URL}] adresine baglaniliyor...")
        response = requests.get(CATEGORY_URL, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # İlk sayfadaki şarkı linklerini bulalım (OrtaListe class'ı altındaki linkler)
        song_links = []
        for a_tag in soup.select("ul.OrtaListe li a"):
            href = a_tag.get("href")
            if href and href not in song_links:
                song_links.append(href)

        print(f"Toplam {len(song_links)} sarki bulundu. Detaylar cekiliyor...")

        m3u_lines = ["#EXTM3U"]

        for link in song_links:
            full_url = link if link.startswith("http") else BASE_URL + link
            
            detail_res = requests.get(full_url, headers=headers)
            detail_soup = BeautifulSoup(detail_res.text, "html.parser")

            # 1. Şarkı İsmini Çekme
            title_tag = detail_soup.select_one(".mks h1")
            if title_tag:
                title = title_tag.text.replace(" Mp3 İndir", "").strip()
            else:
                title = "Bilinmeyen Sarki"

            # 2. Görseli Çekme
            img_tag = detail_soup.select_one(".Mp3-images img")
            img_url = ""
            if img_tag and img_tag.get("src"):
                img_url = img_tag.get("src")
                img_url = img_url if img_url.startswith("http") else BASE_URL + img_url

            # 3. Ses Dosyası Linkini Çekme (Audio src'sini çekiyoruz)
            audio_tag = detail_soup.select_one("audio#mp3player")
            audio_url = ""
            if audio_tag and audio_tag.get("src"):
                audio_url = audio_tag.get("src")
                audio_url = audio_url if audio_url.startswith("http") else BASE_URL + audio_url

            # Eğer ses linki bulabildiysek M3U listesine ekleyelim
            if audio_url:
                print(f"Eklendi: {title}")
                m3u_lines.append(f'#EXTINF:-1 tvg-logo="{img_url}", {title}')
                m3u_lines.append(audio_url)

        # M3U dosyasını oluştur ve kaydet
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        
        print(f"M3U dosyasi basariyla olusturuldu: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Hata olustu: {e}")

if __name__ == "__main__":
    scrape_songs()
