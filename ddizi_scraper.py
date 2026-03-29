import asyncio
import yaml
import json
import os
import re
from ddizi_scraper import DDiziScraper

def sanitize_filename(name: str) -> str:
    """Dosya adında sorun yaratacak karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def save_as_json(data: dict, filepath: str):
    """Veriyi JSON formatında kaydeder."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_as_m3u(data: dict, filepath: str):
    """Veriyi IPTV'lerde izlenebilir standart M3U formatında kaydeder."""
    lines = ["#EXTM3U\n"]
    series_title = data.get("title", "Bilinmeyen Dizi")
    poster = data.get("poster", "")
    
    for ep in data.get("episodes", []):
        for video_link in ep.get("video_links", []):
            ep_title = ep.get("title", f"S{ep.get('season', 1):02d}E{ep.get('episode', 1):02d}")
            
            # tvg-logo ile posteri, group-title ile dizi adını (klasörleme için) ekliyoruz.
            extinf = f'#EXTINF:-1 tvg-logo="{poster}" group-title="{series_title}", {series_title} - {ep_title}\n'
            lines.append(extinf)
            lines.append(f"{video_link}\n")
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

async def main():
    print("[*] DDizi Kazıyıcı Başlatılıyor...")
    
    # 1. Config dosyasını yükle
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("[!] config.yml dosyası bulunamadı!")
        return

    output_dir = config['settings'].get('output_dir', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    scraper = DDiziScraper(config)

    # 2. Hedef dizileri tara
    targets = config.get('targets', [])
    if not targets:
        print("[!] config.yml içinde taranacak 'targets' linkleri bulunamadı.")
        return

    for target_url in targets:
        print(f"\n[+] Dizi taranıyor: {target_url}")
        
        # Dizi detaylarını ve bölüm listesini çek
        series_data = await scraper.get_series_info(target_url)
        print(f"  -> Dizi Bulundu: {series_data['title']} ({len(series_data['episodes'])} Bölüm)")
        
        # Her bölümün sayfasına girip video linklerini çek
        for idx, ep in enumerate(series_data["episodes"], 1):
            print(f"  -> [{idx}/{len(series_data['episodes'])}] Linkler çözülüyor: {ep['title']}")
            ep["video_links"] = await scraper.get_video_links(ep["url"])

        # 3. Çıktıları kaydet
        safe_title = sanitize_filename(series_data['title'])
        json_path = os.path.join(output_dir, f"{safe_title}.json")
        m3u_path = os.path.join(output_dir, f"{safe_title}.m3u")

        save_as_json(series_data, json_path)
        save_as_m3u(series_data, m3u_path)
        
        print(f"\n[✓] İşlem Tamamlandı! Dosyalar kaydedildi:")
        print(f"    - JSON: {json_path}")
        print(f"    - M3U : {m3u_path}")

    await scraper.close()

if __name__ == "__main__":
    # Windows'ta asyncio hatalarını önlemek için policy ayarı
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
