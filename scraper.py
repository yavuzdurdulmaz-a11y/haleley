import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

# Şarkıların liste halinde bulunduğu ana adres
KAYNAK_URL = "https://radyonet.net/mp3dinle"
BASE_URL = "https://radyonet.net"

def get_mp3_from_detail_page(detail_url, headers):
    """Şarkının alt sayfasına girip gizli olan .mp3 linkini bulur."""
    try:
        resp = requests.get(detail_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Önce audio, source veya a etiketleri içinde mp3 arayalım
            for tag in soup.find_all(['audio', 'source', 'a']):
                link = tag.get('src') or tag.get('href')
                if link and '.mp3' in link.lower():
                    return urllib.parse.urljoin(BASE_URL, link)
            
            # Eğer HTML içine gömülü değilse, arkaplandaki kodların (script) içindeki linki bulalım
            match = re.search(r'(https?://[^\s"\'<>]+?\.mp3)', resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        pass
    return None

def create_m3u():
    print(f"{KAYNAK_URL} adresindeki liste taranıyor...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(KAYNAK_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Hata: Sayfaya bağlanılamadı. {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    m3u_content = "#EXTM3U\n"
    mp3_count = 0
    
    # HTML içindeki şarkı satırlarını bul (Senin gönderdiğin HTML'deki class)
    sarki_satirlari = soup.find_all('div', class_='mp3dinletabloSatir')
    print(f"Sayfada {len(sarki_satirlari)} adet şarkı bulundu. MP3 dosyaları toplanıyor, lütfen bekleyin...")

    for satir in sarki_satirlari:
        try:
            # 1. Şarkı Alt Sayfası Linkini Al
            link_tag = satir.find('a', href=True)
            if not link_tag:
                continue
            detail_url = urllib.parse.urljoin(BASE_URL, link_tag['href'])
            
            # 2. Sanatçı ve Şarkı Adını Al (Gönderdiğin HTML'den çekildi)
            sanatci_tag = satir.find('div', class_='mp3dinleSanatciAdi')
            sarki_tag = satir.find('div', class_='mp3dinleSarkiAdi')
            
            sanatci_adi = sanatci_tag.text.strip() if sanatci_tag else ""
            sarki_adi = sarki_tag.text.strip() if sarki_tag else ""
            
            tam_isim = f"{sanatci_adi} - {sarki_adi}".strip(" -")
            if not tam_isim:
                tam_isim = "Bilinmeyen Şarkı"
                
            # 3. Görsel Linkini Al (Siten resimleri "data-src" içinde tembel yüklemeyle tutuyor)
            img_tag = satir.find('img')
            logo_url = "https://via.placeholder.com/150/000000/FFFFFF/?text=FanatikPlay" # Varsayılan
            if img_tag:
                resim = img_tag.get('data-src') or img_tag.get('src')
                if resim:
                    logo_url = urllib.parse.urljoin(BASE_URL, resim)
            
            # 4. Asıl sayfaya arka planda istek atıp MP3 linkini bul!
            mp3_link = get_mp3_from_detail_page(detail_url, headers)
            
            # Eğer MP3 linkini başarıyla bulduysa M3U dosyasına yaz
            if mp3_link:
                m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}", {tam_isim}\n'
                m3u_content += f"{mp3_link}\n"
                mp3_count += 1
                print(f"[EKLENDİ] {tam_isim}")
                
        except Exception as e:
            pass

    # Dosyayı kaydet
    if mp3_count > 0:
        with open("müzikmp3.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"\nHarika! Toplam {mp3_count} adet gerçek şarkı bulundu ve 'müzikmp3.m3u' dosyasına eklendi.")
    else:
        print("\nUyarı: Sayfa tarandı ancak geçerli hiçbir MP3 bağlantısı bulunamadı.")

if __name__ == "__main__":
    create_m3u()
