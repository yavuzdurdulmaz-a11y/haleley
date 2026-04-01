import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import os

# LÜTFEN BURAYA MP3'LERİN LİSTELENDİĞİ ANA SAYFANIN ADRESİNİ YAZIN
# Örnek: "https://radyonet.net/kategori/pop"
KAYNAK_URL = "BURAYA_LINK_GELECEK"

def clean_name(filename):
    """Dosya adından temiz bir şarkı ismi çıkarır."""
    name = filename.replace(".mp3", "")
    name = re.sub(r'-\d+-\d+$', '', name)
    name = re.sub(r'-\d+$', '', name)
    return name.replace("-", " ").title()

def create_m3u():
    if KAYNAK_URL == "BURAYA_LINK_GELECEK":
        print("Hata: Lütfen scraper.py içindeki KAYNAK_URL değişkenine geçerli bir adres girin!")
        return

    print(f"{KAYNAK_URL} adresinden veriler çekiliyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Zaman aşımı ekleyerek sonsuz beklemeyi önlüyoruz
        response = requests.get(KAYNAK_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Bağlantı hatası: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    m3u_content = "#EXTM3U\n"
    mp3_count = 0
    
    # Sayfadaki a, audio ve source etiketlerini tara
    for tag in soup.find_all(['a', 'audio', 'source']):
        link = tag.get('href') or tag.get('src')
        
        if link and '.mp3' in link:
            full_link = urllib.parse.urljoin(KAYNAK_URL, link)
            
            # İsim çıkarma
            raw_name = tag.text.strip() if tag.name == 'a' else ""
            if not raw_name:
                filename = full_link.split('/')[-1]
                name = clean_name(filename)
            else:
                name = raw_name

            # Görsel bulma (linkin içinde img varsa al, yoksa varsayılan logo koy)
            img_tag = tag.find('img') if tag.name == 'a' else None
            if img_tag and img_tag.get('src'):
                logo_url = urllib.parse.urljoin(KAYNAK_URL, img_tag['src'])
            else:
                logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=FanatikPlay"

            m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {name}\n'
            m3u_content += f"{full_link}\n"
            mp3_count += 1

    # Eğer en az 1 tane mp3 bulunduysa dosyayı oluştur
    if mp3_count > 0:
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"Başarılı! {mp3_count} adet şarkı playlist.m3u dosyasına kaydedildi.")
    else:
        print("Uyarı: Sayfada hiç .mp3 uzantılı link bulunamadı. M3U dosyası oluşturulmadı.")

if __name__ == "__main__":
    create_m3u()
