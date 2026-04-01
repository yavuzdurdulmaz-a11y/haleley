import cloudscraper
from bs4 import BeautifulSoup
import re
import sys
import time

# Cloudflare engelini aşmak için scraper nesnesi oluşturuyoruz
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def get_mp3_link(detail_url):
    """Detay sayfasından mp3 bağlantısını Regex ile çıkarır."""
    try:
        response = scraper.get(detail_url, timeout=15)
        if response.status_code != 200:
            return None
        
        # JS içindeki mp3: "URL" yapısını yakalar
        match = re.search(r'mp3:\s*["\'](https://.*?\.mp3)["\']', response.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Hata ({detail_url}): {e}")
    return None

def main():
    playlist_content = "#EXTM3U\n"
    sayfa = 1
    
    # Github Actions'ın zaman aşımına uğramaması için maksimum sayfa sınırı koyabilirsin (İsteğe bağlı)
    # Şimdilik 300'e kadar tarayacak şekilde ayarladık, zaten site bittiğinde otomatik duracak.
    MAX_SAYFA = 300 

    while sayfa <= MAX_SAYFA:
        print(f"\n--- Sayfa {sayfa} İşleniyor ---")
        
        # Sayfa 1 ise ana link, diğerleri için parametreli link
        if sayfa == 1:
            url = "https://radyonet.net/mp3dinle"
        else:
            url = f"https://radyonet.net/mp3dinle?en-cok-dinlenenler-sayfa={sayfa}"

        response = scraper.get(url)
        
        if response.status_code != 200:
            print(f"Hata: Sayfa {sayfa} erişilemedi (HTTP {response.status_code}). Döngü durduruluyor.")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Sayfadaki diğer listelerle karışmaması için sadece "En Çok Dinlenenler" tablosunu bul
        hedef_tablo = soup.find('table', class_='enCokDinlenenlerTablo')
        
        if not hedef_tablo:
            print(f"Sayfa {sayfa}'de hedef tablo bulunamadı. Son sayfaya ulaşılmış olabilir.")
            break
            
        # Hedef tablonun içindeki şarkı satırlarını bul
        songs = hedef_tablo.find_all('div', class_='mp3dinletabloSatir')
        
        if not songs:
            print(f"Sayfa {sayfa} boş. Tarama tamamlandı.")
            break
            
        for song in songs:
            try:
                # Görseli çekme
                img_tag = song.find('img', class_='lazy')
                img_url = img_tag.get('data-src') if img_tag else ""
                
                # Sanatçı ve şarkı adı
                artist_tag = song.find('div', class_='mp3dinleSanatciAdi')
                artist_a = artist_tag.find('a') if artist_tag else None
                
                title_tag = song.find('div', class_='mp3dinleSarkiAdi')
                title_a = title_tag.find('a') if title_tag else None
                
                artist = artist_a.text.strip() if artist_a else "Bilinmeyen Sanatçı"
                title = title_a.text.strip() if title_a else "Bilinmeyen Şarkı"
                
                # Detay sayfası URL'si
                detail_url = artist_a['href'] if artist_a else None
                
                if detail_url:
                    if not detail_url.startswith('http'):
                        detail_url = "https://radyonet.net" + detail_url
                        
                    print(f"-> {artist} - {title}")
                    mp3_url = get_mp3_link(detail_url)
                    
                    if mp3_url:
                        # M3U formatında satırı ekle
                        playlist_content += f'#EXTINF:-1 tvg-logo="{img_url}", {artist} - {title}\n'
                        playlist_content += f'{mp3_url}\n'
                    
                    # ÖNEMLİ: Cloudflare banı yememek için her detay sayfasından sonra 1 saniye bekle
                    time.sleep(1)
                        
            except Exception as e:
                print(f"Şarkı işlenirken hata: {e}")
        
        # Bir sonraki sayfaya geç
        sayfa += 1

    # Tüm döngü bittikten sonra dosyayı kaydet
    with open("radyonet.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
        
    print("\n✅ İşlem Başarılı! Tüm sayfalar tarandı ve radyonet.m3u dosyası oluşturuldu.")

if __name__ == "__main__":
    main()
