import requests
import json
from bs4 import BeautifulSoup
import os

BASE_URL = "https://puhutv.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_next_data(url):
    """Verilen URL'den __NEXT_DATA__ JSON objesini çeker."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if script_tag:
            return json.loads(script_tag.string)
    except Exception as e:
        print(f"Veri çekilemedi ({url}): {e}")
    return None

def main():
    m3u_lines = ["#EXTM3U\n"]
    
    print("PuhuTV Anasayfa verileri çekiliyor...")
    home_data = get_next_data(BASE_URL)
    
    if not home_data:
        print("Anasayfa verisi alınamadı, işlem sonlandırılıyor.")
        return

    # 1. Canlı Yayınları Çek (Doğrudan m3u8 içerir)
    print("Canlı yayınlar listeye ekleniyor...")
    lists = home_data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {}).get('container_items', [])
    
    for container in lists:
        if container.get('type') == 'tv_channel':
            for channel in container.get('items', []):
                name = channel.get('name', 'Bilinmeyen Kanal')
                logo = channel.get('image', '')
                m3u8_url = channel.get('meta', {}).get('and_hls_url', '')
                
                if m3u8_url:
                    m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="CANLI TV", {name}\n')
                    m3u_lines.append(f'{m3u8_url}\n')

    # 2. Dizileri ve Bölümleri Çek
    print("Dizi ve bölümler taranıyor...")
    scraped_slugs = set()
    
    for container in lists:
        if container.get('type') in ['poster', 'spotlight']:
            for item in container.get('items', []):
                slug = item.get('meta', {}).get('slug')
                
                if not slug or slug in scraped_slugs:
                    continue
                
                scraped_slugs.add(slug)
                series_name = item.get('name', 'Bilinmeyen Dizi')
                print(f"Taranıyor: {series_name}")
                
                detail_url = f"{BASE_URL}/{slug}"
                detail_data = get_next_data(detail_url)
                
                if not detail_data:
                    continue
                
                episodes_data = detail_data.get('props', {}).get('pageProps', {}).get('details', {}).get('episodes', {}).get('data', [])
                
                # Sezonları ve bölümleri döngüye al
                if isinstance(episodes_data, list):
                    for season in episodes_data:
                        for ep in season.get('episodes', []):
                            ep_name = ep.get('name', '')
                            full_name = f"{series_name} - {ep_name}"
                            logo = ep.get('image', item.get('image', ''))
                            # VOD içerikler için token gerektiğinden, şimdilik izleme linki veya video_id ekleniyor.
                            # API çözümlenirse buraya f"https://dygvideo.../{video_id}.m3u8" formatı gelebilir.
                            video_id = ep.get('video_id', '')
                            video_slug = ep.get('slug', '')
                            stream_url = f"{BASE_URL}/{video_slug}"
                            
                            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{series_name}", {full_name}\n')
                            m3u_lines.append(f'{stream_url}\n')

    # M3U Dosyasını Kaydet
    output_file = "puhutv_playlist.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    
    print(f"İşlem tamamlandı! Playlist kaydedildi: {output_file}")

if __name__ == "__main__":
    main()
