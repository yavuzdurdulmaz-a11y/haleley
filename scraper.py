import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import os

# Buraya doğrudan bir MP3 linki VEYA mp3'lerin bulunduğu bir web sayfası linki yazabilirsin.
KAYNAK_URL = "https://radyonet.net/cdn/muzik/sena-sener-cok-gec-kaldin-1647013272-23739.mp3"

def clean_name(filename):
    """Dosya adından temiz bir şarkı ismi çıkarır."""
    name = urllib.parse.unquote(filename)
    name = name.replace(".mp3", "")
    name = re.sub(r'-\d+-\d+$', '', name)
    name = re.sub(r'-\d+$', '', name)
    return name.replace("-", " ").title()

def create_m3u():
    print(f"{KAYNAK_URL} adresinden veriler isleniyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    m3u_content = "#EXTM3U\n"
    mp3_count = 0

    # DURUM 1: Eğer verilen link doğrudan bir MP3 dosyası ise
    if KAYNAK_URL.lower().endswith('.mp3'):
        filename = KAYNAK_URL.split('/')[-1]
        name = clean_name(filename)
        # FanatikPlay için varsayılan bir logo
        logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=FanatikPlay"
        
        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {name}\n'
        m3u_content += f"{KAYNAK_URL}\n"
        mp3_count += 1

    # DURUM 2: Eğer verilen link bir web sayfası ise (İçindeki mp3'leri tara)
    else:
        try:
            response = requests.get(KAYNAK_URL, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for tag in soup.find_all(['a', 'audio', 'source']):
                link = tag.get('href') or tag.get('src')
                if link and '.mp3' in link.lower():
                    full_link = urllib.parse.urljoin(KAYNAK_URL, link)
                    
                    raw_name = tag.text.strip() if tag.name == 'a' else ""
                    if not raw_name:
                        filename = full_link.split('/')[-1]
                        name = clean_name(filename)
                    else:
                        name = raw_name

                    img_tag = tag.find('img') if tag.name == 'a' else None
                    if img_tag and img_tag.get('src'):
                        logo_url = urllib.parse.urljoin(KAYNAK_URL, img_tag['src'])
                    else:
                        logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=FanatikPlay"

                    m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {name}\n'
                    m3u_content += f"{full_link}\n"
                    mp3_count += 1
        except Exception as e:
            print(f"Bağlantı hatası veya sayfa okunamadı: {e}")
            return

    # Dosyayı oluştur ve kaydet
    if mp3_count > 0:
        with open("müzikmp3.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"Başarılı! {mp3_count} adet şarkı 'müzikmp3.m3u' dosyasına kaydedildi.")
    else:
        print("Uyarı: Geçerli bir MP3 bulunamadı, dosya oluşturulmadı.")

if __name__ == "__main__":
    create_m3u()
