import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

# MP3 linklerinin ve görsellerinin bulunduğu kaynak sayfanın URL'si
# LÜTFEN BURAYA MP3'LERİN LİSTELENDİĞİ SAYFANIN ADRESİNİ YAZIN
KAYNAK_URL = "https://radyonet.net/mp3-listesi-sayfasi" 

def clean_name(filename):
    """
    Dosya adından temiz bir şarkı ismi çıkarır.
    Örn: sena-sener-cok-gec-kaldin-1647013272-23739.mp3 -> Sena Sener Cok Gec Kaldin
    """
    # .mp3 uzantısını kaldır
    name = filename.replace(".mp3", "")
    # Sondaki tire ile ayrılmış tarih/ID rakamlarını temizle (örn: -1647013272-23739)
    name = re.sub(r'-\d+-\d+$', '', name)
    name = re.sub(r'-\d+$', '', name)
    # Tireleri boşluk yap ve her kelimenin baş harfini büyüt
    return name.replace("-", " ").title()

def create_m3u():
    print(f"{KAYNAK_URL} adresinden veriler çekiliyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    response = requests.get(KAYNAK_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"Hata: Sayfaya ulaşılamadı. Durum Kodu: {response.status_code}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # M3U başlığı
    m3u_content = "#EXTM3U\n"
    
    # Sayfadaki tüm <a> (link) etiketlerini bul
    for a_tag in soup.find_all('a', href=True):
        link = a_tag['href']
        
        # Eğer link bir mp3 dosyasıysa
        if link.endswith('.mp3'):
            full_link = urllib.parse.urljoin(KAYNAK_URL, link)
            
            # Şarkı ismini bul (Önce etiket metnine bak, yoksa URL'den temizle)
            raw_name = a_tag.text.strip()
            if not raw_name:
                filename = link.split('/')[-1]
                name = clean_name(filename)
            else:
                name = raw_name

            # Görseli bul (Eğer linkin içinde veya yanında bir img varsa)
            img_tag = a_tag.find('img')
            if img_tag and img_tag.get('src'):
                logo_url = urllib.parse.urljoin(KAYNAK_URL, img_tag['src'])
            else:
                # Görsel yoksa varsayılan bir radyo/müzik logosu koyabilirsiniz
                logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=Muzik"

            # M3U formatında ekle
            m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {name}\n'
            m3u_content += f"{full_link}\n"

    # Dosyayı kaydet
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print("Harika! playlist.m3u dosyası başarıyla oluşturuldu.")

if __name__ == "__main__":
    create_m3u()
