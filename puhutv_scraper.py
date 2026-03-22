import requests
import json
from bs4 import BeautifulSoup
import time
from tqdm import tqdm

BASE_URL = "https://puhutv.com"

# PuhuTV'yi kandırmak için Türkiye IP'si taklidi yapan başlıklar eklendi
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Forwarded-For": "85.110.15.111",
    "CF-Connecting-IP": "85.110.15.111",
    "Accept-Language": "tr-TR,tr;q=0.9"
}

def get_soup_and_next_data(url):
    """Sayfanın hem HTML'ini hem de JSON verisini çeker."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            script = soup.find('script', id='__NEXT_DATA__')
            if script:
                return soup, json.loads(script.string)
            return soup, None
    except Exception:
        pass
    return None, None

def main():
    m3u_lines = ["#EXTM3U\n"]

    # 1. CANLI TV'LERİ ÇEK
    print("1. Canlı Yayınlar Çekiliyor...")
    soup, home_data = get_soup_and_next_data(BASE_URL)
    if home_data:
        containers = home_data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {}).get('container_items', [])
        for c in containers:
            if c.get('type') == 'tv_channel':
                for item in c.get('items', []):
                    name = item.get('name', 'Canlı TV')
                    logo = item.get('image', '')
                    m3u8_url = item.get('meta', {}).get('and_hls_url', '') or item.get('meta', {}).get('ios_hls_url', '')
                    if m3u8_url:
                        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Canlı TV", {name}\n{m3u8_url}\n')

    # 2. DİZİLERİ ÇEK VE BÖLGE KISITLAMASINI (GEO-BLOCK) AŞ
    print("2. Diziler Taranıyor...")
    soup, dizi_data = get_soup_and_next_data(f"{BASE_URL}/dizi")
    
    series_dict = {}
    
    # Yöntem A: Normal Konteynerleri Tara
    if dizi_data:
        containers = dizi_data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {}).get('container_items', [])
        for c in containers:
            for item in c.get('items', []):
                slug = item.get('meta', {}).get('slug')
                name = item.get('name')
                if slug and slug not in series_dict:
                    series_dict[slug] = name
    
    # Yöntem B: Eğer GitHub sunucusu engellenmişse SEO verilerinden dizileri zorla çek
    if not series_dict and soup:
        ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in ld_scripts:
            if 'ItemList' in script.string:
                try:
                    ld_data = json.loads(script.string)
                    items = ld_data.get('itemListElement', [])
                    for group in items:
                        for item in group:
                            url = item.get('url', '')
                            name = item.get('name', '').strip()
                            if 'detay' in url:
                                slug = url.split('/')[-1]
                                if slug not in series_dict:
                                    series_dict[slug] = name
                except Exception:
                    pass

    print(f"Toplam {len(series_dict)} dizi bulundu. Bölümler çekiliyor...\n")

    # 3. HER DİZİNİN SEZON VE BÖLÜMLERİNİ AL
    for slug, series_name in tqdm(series_dict.items(), desc="İşleniyor"):
        _, detail_data = get_soup_and_next_data(f"{BASE_URL}/{slug}")
        if not detail_data:
            continue

        page_props = detail_data.get('props', {}).get('pageProps', {})
        details = page_props.get('details', {}).get('data', {})
        if not details:
            details = page_props.get('watchDetails', {}).get('data', {})

        # Sezon linklerini bul
        seasons = details.get('seasons', [])
        season_slugs = [s.get('slug') for s in seasons if s.get('slug')]
        if not season_slugs:
            season_slugs = [slug]

        # Sezon sayfalarına girip bölümleri çıkar
        for s_slug in season_slugs:
            _, season_data = get_soup_and_next_data(f"{BASE_URL}/{s_slug}")
            if not season_data:
                continue
            
            s_page_props = season_data.get('props', {}).get('pageProps', {})
            episodes_block = s_page_props.get('episodes', {}).get('data', {})
            
            episodes = episodes_block.get('episodes', [])
            season_name = episodes_block.get('name', '')
            
            for ep in episodes:
                ep_name = ep.get('name', '')
                video_id = ep.get('video_id', '')
                logo = ep.get('image', '')
                
                # İsim Formatı: Sahipsizler - 2. Sezon 51. Bölüm
                full_name = f"{series_name} - {season_name} {ep_name}".strip()
                
                if video_id:
                    # Senin eski kodundan aldığımız harika gizli API yönlendirmesi
                    stream_url = f"https://dygvideo.dygdigital.com/api/redirect?PublisherId=29&ReferenceId={video_id}&SecretKey=NtvApiSecret2014*&.m3u8"
                    m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{series_name}", {full_name}\n{stream_url}\n')

        # GitHub sunucusunun ban yememesi için çok ufak bir bekleme
        time.sleep(0.2)

    # 4. M3U DOSYASINI KAYDET
    output_file = "puhutv_diziler.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    
    print(f"\nİşlem Başarılı! Liste {output_file} olarak kaydedildi.")

if __name__ == "__main__":
    main()
