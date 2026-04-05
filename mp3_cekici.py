import cloudscraper
from bs4 import BeautifulSoup
import time

BASE_URL = "https://mp3indirdur.life"
CATEGORY_URL = f"{BASE_URL}/kategori/turkce-sarkilar"
OUTPUT_FILE = "sarkilar.m3u"

# Cloudflare engelini aşmak için scraper nesnesi oluşturuyoruz
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def scrape_songs():
    try:
        print(f"[{CATEGORY_URL}] adresine baglaniliyor...")
        response = scraper.get(CATEGORY_URL, timeout=15)
        
        if response.status_code != 200:
            print(f"Hata: Sayfaya erişilemedi. Durum kodu: {response.status_code}")
            return

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
            
            try:
                detail_res = scraper.get(full_url, timeout=15)
                if detail_res.status_code != 200:
                    continue

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

                # 3. Ses Dosyası Linkini Çekme ve Asıl Linki Çözme
                audio_tag = detail_soup.select_one("audio#mp3player")
                audio_url = ""
                if audio_tag and audio_tag.get("src"):
                    temp_url = audio_tag.get("src")
                    temp_url = temp_url if temp_url.startswith("http") else BASE_URL + temp_url
                    
                    # Burada yönlendirmeyi takip edip mp3kulisi.mobi gibi asıl adresi buluyoruz
                    try:
                        # stream=True ile dosyayı indirmeden sadece asıl yönlenen adresi alıyoruz
                        res_redirect = scraper.get(temp_url, stream=True, timeout=15)
                        audio_url = res_redirect.url
                        res_redirect.close() # Bağlantıyı hemen kapat
                    except Exception as e:
                        print(f"Asil link cozulemedi, varsayilan kullaniliyor: {e}")
                        audio_url = temp_url

                # Eğer ses linki bulabildiysek M3U listesine ekleyelim
                if audio_url:
                    print(f"-> Eklendi: {title}")
                    m3u_lines.append(f'#EXTINF:-1 tvg-logo="{img_url}", {title}')
                    m3u_lines.append(audio_url)
                
                # Sunucuyu yormamak ve ban yememek için 1 saniye bekleme
                time.sleep(1)

            except Exception as e:
                print(f"Sarki islenirken hata ({full_url}): {e}")

        # M3U dosyasını oluştur ve kaydet
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        
        print(f"\n✅ islem Basarili! M3U dosyasi olusturuldu: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Genel Hata olustu: {e}")

if __name__ == "__main__":
    scrape_songs()
