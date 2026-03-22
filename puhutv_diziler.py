import requests
import json
from bs4 import BeautifulSoup
import time

BASE_URL = "https://puhutv.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_next_data(url):
    """Verilen PuhuTV linkinden __NEXT_DATA__ içindeki JSON'u çıkarır."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if script_tag:
            return json.loads(script_tag.string)
    except Exception as e:
        print(f"Hata ({url}): {e}")
    return None

def main():
    print("PuhuTV Dizi Listesi Çekiliyor...")
    m3u_lines = ["#EXTM3U\n"]
    
    # 1. Tüm dizilerin listesini al
    dizi_sayfasi_url = f"{BASE_URL}/dizi"
    dizi_data = get_next_data(dizi_sayfasi_url)
    
    if not dizi_data:
        print("Dizi sayfası verisi alınamadı!")
        return

    scraped_series = set()
    containers = dizi_data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {}).get('container_items', [])
    
    for container in containers:
        for item in container.get('items', []):
            series_name = item.get('name')
            slug = item.get('meta', {}).get('slug')
            
            # Aynı diziyi tekrar taramamak için kontrol
            if not slug or slug in scraped_series:
                continue
                
            scraped_series.add(slug)
            print(f"Taraniyor: {series_name} ({slug})")
            
            # 2. Dizinin detay sayfasına gidip bölümleri çek
            detail_url = f"{BASE_URL}/{slug}"
            detail_data = get_next_data(detail_url)
            
            if not detail_data:
                continue
                
            # JSON içinden bölümleri (episodes) bul
            try:
                details = detail_data.get('props', {}).get('pageProps', {}).get('details', {})
                # Bazı sayfalarda 'details' bazen 'watchDetails' altında olabiliyor
                if not details:
                    details = detail_data.get('props', {}).get('pageProps', {}).get('watchDetails', {})
                
                episodes_data = details.get('episodes', {}).get('data', {}).get('episodes', [])
                
                for ep in episodes_data:
                    ep_name = ep.get('name', 'Bilinmeyen Bölüm')
                    ep_image = ep.get('image', '')
                    ep_slug = ep.get('slug', '')
                    
                    # Başlık formatı: Dizi Adı - Bölüm Adı
                    full_title = f"{series_name} - {ep_name}"
                    
                    # İzleme Linki (PuhuTV oynatıcısı için)
                    stream_url = f"{BASE_URL}/{ep_slug}"
                    
                    # M3U formatında satırları oluştur. (group-title dizinin kendi adıdır)
                    m3u_lines.append(f'#EXTINF:-1 tvg-logo="{ep_image}" group-title="{series_name}", {full_title}\n')
                    m3u_lines.append(f'{stream_url}\n')
            except Exception as e:
                print(f"Bölümler çekilirken hata: {e}")
            
            # Sunucuyu yormamak ve engellenmemek için ufak bir bekleme
            time.sleep(0.5)

    # 3. Dosyayı Kaydet
    output_filename = "puhutv_diziler.m3u"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    
    print(f"\nİşlem Başarılı! Toplam {len(scraped_series)} dizi tarandı.")
    print(f"Liste '{output_filename}' adıyla kaydedildi.")

if __name__ == "__main__":
    main()
