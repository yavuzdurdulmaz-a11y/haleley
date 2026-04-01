import requests
from bs4 import BeautifulSoup
import re

# Hedef adres ve kimlik bilgisi
BASE_URL = "https://radyonet.net/mp3dinle"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def get_mp3_link(detail_url):
    """Detay sayfasından mp3 bağlantısını Regex ile çıkarır."""
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # JS içindeki mp3: "URL" yapısını yakalar
        match = re.search(r'mp3:\s*["\'](https://.*?\.mp3)["\']', response.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Hata ({detail_url}): {e}")
    return None

def main():
    print("Ana liste çekiliyor...")
    response = requests.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Şarkı satırlarını bul
    songs = soup.find_all('div', class_='mp3dinletabloSatir')
    
    playlist_content = "#EXTM3U\n"
    
    for song in songs:
        try:
            # Görseli çekme (Lazy load olduğu için data-src kullanıyoruz)
            img_tag = song.find('img', class_='lazy')
            img_url = img_tag.get('data-src') if img_tag else ""
            
            # Sanatçı ve şarkı adı etiketleri
            artist_tag = song.find('div', class_='mp3dinleSanatciAdi').find('a')
            title_tag = song.find('div', class_='mp3dinleSarkiAdi').find('a')
            
            artist = artist_tag.text.strip() if artist_tag else "Bilinmeyen Sanatçı"
            title = title_tag.text.strip() if title_tag else "Bilinmeyen Şarkı"
            
            # Detay sayfası URL'si
            detail_url = artist_tag['href'] if artist_tag else None
            
            if detail_url:
                print(f"İşleniyor: {artist} - {title}")
                mp3_url = get_mp3_link(detail_url)
                
                if mp3_url:
                    # M3U formatında satırı oluştur
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
