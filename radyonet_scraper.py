import cloudscraper
from bs4 import BeautifulSoup
import re
import sys

# Hedef adres
BASE_URL = "https://radyonet.net/mp3dinle"

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
    print("Ana liste çekiliyor...")
    response = scraper.get(BASE_URL)
    
    # Sayfaya ulaşılamadıysa işlemi durdur
    if response.status_code != 200:
        print(f"Kritik Hata: Siteye erişilemedi (HTTP {response.status_code})")
        sys.exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    songs = soup.find_all('div', class_='mp3dinletabloSatir')
    
    # Eğer şarkı div'leri bulunamazsa loga uyarı bas ve dur
    if not songs:
        print("Uyarı: Sayfa çekildi ancak şarkılar bulunamadı! Cloudflare engellemiş olabilir.")
        sys.exit(1)
        
    playlist_content = "#EXTM3U\n"
    
    for song in songs:
        try:
            # Görseli çekme
            img_tag = song.find('img', class_='lazy')
            img_url = img_tag.get('data-src') if img_tag else ""
            
            # Sanatçı ve şarkı adı etiketleri
            artist_tag = song.find('div', class_='mp3dinleSanatciAdi')
            artist_a = artist_tag.find('a') if artist_tag else None
            
            title_tag = song.find('div', class_='mp3dinleSarkiAdi')
            title_a = title_tag.find('a') if title_tag else None
            
            artist = artist_a.text.strip() if artist_a else "Bilinmeyen Sanatçı"
            title = title_a.text.strip() if title_a else "Bilinmeyen Şarkı"
            
            # Detay sayfası URL'si
            detail_url = artist_a['href'] if artist_a else None
            
            if detail_url:
                # URL eksikse (göreceli adres ise) tamamla
                if not detail_url.startswith('http'):
                    detail_url = "https://radyonet.net" + detail_url
                    
                print(f"İşleniyor: {artist} - {title}")
                mp3_url = get_mp3_link(detail_url)
                
                if mp3_url:
                    # M3U formatı
                    playlist_content += f'#EXTINF:-1 tvg-logo="{img_url}", {artist} - {title}\n'
                    playlist_content += f'{mp3_url}\n'
                    
        except Exception as e:
            print(f"Şarkı işlenirken hata oluştu: {e}")
            
    # Dosyayı kaydet
    with open("radyonet.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
        
    print("M3U dosyası başarıyla güncellendi: radyonet.m3u")

if __name__ == "__main__":
    main()
