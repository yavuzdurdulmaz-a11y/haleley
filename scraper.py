import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

# Şarkıların bulunduğu ana dizin veya site URL'si
KAYNAK_URL = "https://radyonet.net/cdn/muzik/"

def clean_name(filename):
    """Dosya adından temiz bir şarkı ismi çıkarır."""
    name = urllib.parse.unquote(filename)
    name = name.replace(".mp3", "")
    # Sondaki id/tarih gibi rakamları siler (örn: -1647013272-23739)
    name = re.sub(r'-\d+-\d+$', '', name)
    name = re.sub(r'-\d+$', '', name)
    return name.replace("-", " ").title()

def create_m3u():
    print(f"{KAYNAK_URL} adresindeki tüm liste taranıyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(KAYNAK_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Hata: Siteye bağlanılamadı. {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    m3u_content = "#EXTM3U\n"
    mp3_count = 0
    
    # Sayfadaki tüm linkleri (a etiketlerini) bul
    for a_tag in soup.find_all('a'):
        link = a_tag.get('href')
        
        # Eğer linkin içinde .mp3 varsa listeye ekle
        if link and link.lower().endswith('.mp3'):
            full_link = urllib.parse.urljoin(KAYNAK_URL, link)
            
            # Linkten dosya adını alıp temizle
            filename = full_link.split('/')[-1]
            name = clean_name(filename)

            # FanatikPlay için varsayılan logo
            logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=FanatikPlay"

            m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {name}\n'
            m3u_content += f"{full_link}\n"
            mp3_count += 1

    # Dosyayı kaydet
    if mp3_count > 0:
        with open("müzikmp3.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"Harika! Toplam {mp3_count} adet şarkı bulundu ve 'müzikmp3.m3u' dosyasına eklendi.")
    else:
        print("Uyarı: Bu sayfada hiç MP3 dosyası bulunamadı.")

if __name__ == "__main__":
    create_m3u()
