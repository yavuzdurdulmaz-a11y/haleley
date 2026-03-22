import requests
import json
from bs4 import BeautifulSoup
import time
from tqdm import tqdm

BASE_URL = "https://puhutv.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_next_data(url):
    """PuhuTV sayfalarındaki __NEXT_DATA__ JSON verisini ayıklar."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if script_tag:
            return json.loads(script_tag.string)
    except Exception:
        pass
    return None

def main():
    print("PuhuTV Dizi Arşivi Taranıyor...\n")
    m3u_lines = ["#EXTM3U\n"]
    
    # 1. Tüm dizilerin listesini çek
    diziler_url = f"{BASE_URL}/dizi"
    dizi_data = get_next_data(diziler_url)
    
    if not dizi_data:
        print("Dizi ana sayfası okunamadı!")
        return

    scraped_series = set()
    containers = dizi_data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {}).get('container_items', [])
    
    # Sadece benzersiz dizi slug'larını topla
    series_list = []
    for container in containers:
        for item in container.get('items', []):
            series_name = item.get('name')
            slug = item.get('meta', {}).get('slug')
            
            if slug and slug not in scraped_series:
                scraped_series.add(slug)
                series_list.append({"name": series_name, "slug": slug})

    # 2. Her dizi için detaylara ve sezonlara gir
    for series in tqdm(series_list, desc="Diziler İşleniyor"):
        series_name = series['name']
        series_slug = series['slug']
        
        detail_data = get_next_data(f"{BASE_URL}/{series_slug}")
        if not detail_data: continue

        # Sayfa yapısına göre details objesini bul
        page_props = detail_data.get('props', {}).get('pageProps', {})
        details = page_props.get('details', {}).get('data', {})
        if not details:
            details = page_props.get('watchDetails', {}).get('data', {})
        
        seasons = details.get('seasons', [])
        
        # Eğer sezon bilgisi dizi sayfasındaysa onları al, yoksa dizinin kendi slug'ını kullan
        season_slugs = [s.get('slug') for s in seasons if s.get('slug')]
        if not season_slugs:
            season_slugs = [series_slug]

        # 3. Sezon sayfalarındaki bölümleri çek
        for s_slug in season_slugs:
            season_data = get_next_data(f"{BASE_URL}/{s_slug}")
            if not season_data: continue
            
            s_page_props = season_data.get('props', {}).get('pageProps', {})
            episodes = s_page_props.get('episodeData', {}).get('data', {}).get('episodes', [])
            season_name = s_page_props.get('episodeData', {}).get('data', {}).get('name', '')
            
            # Ana dizinde bölüm listesi varsa onu al
            if not episodes and 'episodes' in s_page_props.get('details', {}):
                episodes = s_page_props['details']['episodes'].get('data', {}).get('episodes', [])

            for ep in episodes:
                ep_name = ep.get('name', '')
                video_id = ep.get('video_id', '')
                logo = ep.get('image', '')
                
                # Format: Dizi Adı - Sezon x - Bölüm y
                full_name = f"{series_name} - {season_name} {ep_name}".strip()
                
                if video_id:
                    # Çözümlenen Yayın URL'i
                    stream_url = f"https://dygvideo.dygdigital.com/api/redirect?PublisherId=29&ReferenceId={video_id}&SecretKey=NtvApiSecret2014*&.m3u8"
                    
                    m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{series_name}", {full_name}\n')
                    m3u_lines.append(f'{stream_url}\n')

        # Sunucuyu yormamak için kısa bekleme
        time.sleep(0.3)

    # 4. M3U Listesini Kaydet
    output_file = "puhutv_diziler.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    
    print(f"\nİşlem Başarılı! Liste {output_file} olarak kaydedildi.")

if __name__ == "__main__":
    main()
