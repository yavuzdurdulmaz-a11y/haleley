import asyncio
import json
import os
import re
import httpx
from selectolax.parser import HTMLParser
from contextlib import suppress

# ==========================================
# 1. AYARLAR
# ==========================================
MAIN_URL = "https://dizigom104.com"
ARCHIVE_URL = f"{MAIN_URL}/dizi-arsivi-hd2/"
OUTPUT_DIR = "outputs"
MAX_PAGES = 1  # Deneme amaçlı sadece ilk sayfayı çekiyoruz. Tümünü çekmek için burayı artırabilirsin.

# ==========================================
# 2. KAZIYICI SINIFI
# ==========================================
class DiziGomArchiveScraper:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": f"{MAIN_URL}/",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

    def fix_url(self, url: str) -> str:
        if not url: return ""
        if url.startswith("http"): return url
        if url.startswith("//"): return f"https:{url}"
        if url.startswith("/"): return f"{MAIN_URL}{url}"
        return f"{MAIN_URL}/{url}"

    async def get_archive_list(self, max_pages: int) -> list:
        items = []
        for page in range(1, max_pages + 1):
            # Arşiv sayfası linki
            url = f"{ARCHIVE_URL}page/{page}/" if page > 1 else ARCHIVE_URL
            
            try:
                response = await self.client.get(url)
                tree = HTMLParser(response.text)
            except Exception as e:
                print(f"[!] Sayfa yüklenemedi: {url} | Hata: {e}")
                continue
            
            # Arşiv sayfasındaki dizi kutucukları
            nodes = tree.css("div.single-item")
            if not nodes:
                break
                
            for node in nodes:
                # Dizi Adı ve Linki
                title_node = node.css_first("div.categorytitle a")
                title = title_node.text(strip=True) if title_node else "Bilinmeyen"
                href = self.fix_url(title_node.attributes.get("href")) if title_node else ""
                
                # Kapak Fotoğrafı
                img_tag = node.css_first("div.cat-img img")
                poster = self.fix_url(img_tag.attributes.get("src")) if img_tag else ""
                
                if href:
                    items.append({"title": title, "url": href, "poster": poster})
                    
        return items

    async def get_series_info(self, url: str) -> dict:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
        except Exception:
            return {"source_url": url, "episodes": []}

        # Dizi Başlığı
        title_node = tree.css_first("div.serieTitle h1")
        title = title_node.text(strip=True) if title_node else "Bilinmeyen Dizi"
        
        # Dizi Posteri
        poster_style = tree.css_first("div.seriePoster")
        poster = ""
        if poster_style and poster_style.attributes.get("style"):
            p_match = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", poster_style.attributes.get("style"))
            if p_match: poster = self.fix_url(p_match.group(1))

        # Bölümleri Topla
        episodes = []
        for ep_node in tree.css("div.bolumust"):
            ep_a = ep_node.css_first("a")
            if not ep_a: continue
            
            ep_href = ep_a.attributes.get("href")
            
            # "1. Sezon 1. Bölüm" metnini bul
            ep_title_node = ep_node.css_first("div.baslik")
            ep_title_text = ep_title_node.text(strip=False) if ep_title_node else ""
            
            # Bölüm özel ismini bul (Örn: Pilot)
            ep_name_node = ep_node.css_first("div.bolum-ismi")
            ep_name = ep_name_node.text(strip=True) if ep_name_node else ""
            
            season, episode = 1, 1
            # "1. Sezon 1. Bölüm" yazısından sayıları çek
            match = re.search(r'(\d+)\.\s*Sezon\s*(\d+)\.\s*Bölüm', ep_title_text)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))

            full_ep_title = f"{season}. Sezon {episode}. Bölüm {ep_name}".strip()

            if ep_href:
                episodes.append({
                    "season": season, 
                    "episode": episode, 
                    "title": full_ep_title,
                    "url": self.fix_url(ep_href), 
                    "video_links": []
                })

        # Bölümleri Sezon 1 Bölüm 1'den başlayacak şekilde ters çevir (Eskiden yeniye)
        return {"title": title, "poster": poster, "source_url": url, "episodes": episodes[::-1]}

    async def get_video_links(self, url: str) -> list:
        results = []
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            # Yeni HTML yapısındaki VideoObject içinden embed linkini çek
            for script_node in tree.css("script[type='application/ld+json']"):
                if "VideoObject" in script_node.text():
                    json_data = json.loads(script_node.text(strip=True))
                    content_url = json_data.get("contentUrl", "")
                    
                    if content_url:
                        # Dizigom taktiği: embed adresinin başına play. ekle
                        play_url = content_url.replace("https://dizigom", "https://play.dizigom")
                        results.append(play_url)
                        
                        # (Gelecekte play_url içine girip JS şifresi kırılarak saf m3u8 de çekilebilir)
                        break

        except Exception: pass
        return list(set(results))

    async def close(self):
        await self.client.aclose()

# ==========================================
# 3. ÇIKTI OLUŞTURUCULAR
# ==========================================
def save_as_json(data: list, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_as_m3u(data: list, filepath: str):
    lines = ["#EXTM3U\n"]
    for item in data:
        series_title = item.get("title", "Bilinmeyen Dizi")
        poster = item.get("poster", "")
        for ep in item.get("episodes", []):
            ep_title = ep.get("title")
            for video_link in ep.get("video_links", []):
                extinf = f'#EXTINF:-1 tvg-logo="{poster}" group-title="{series_title}", {series_title} - {ep_title}\n'
                lines.append(extinf)
                lines.append(f"{video_link}\n")
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

# ==========================================
# 4. ANA ÇALIŞTIRICI
# ==========================================
async def main():
    print("[*] DiziGom ARŞİV Tarayıcı Başlatılıyor...\n")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    scraper = DiziGomArchiveScraper()
    
    print(f"[*] Arşiv Taranıyor: {ARCHIVE_URL}")
    # Sadece ilk sayfayı (deneme amaçlı) çekiyoruz
    items = await scraper.get_archive_list(max_pages=MAX_PAGES)
    print(f"[+] Toplam {len(items)} dizi bulundu (Sadece Sayfa 1).\n")
    
    archive_data = []
    
    for idx, item in enumerate(items, 1):
        print(f"  [{idx}/{len(items)}] İşleniyor: {item['title']}")
        
        # Dizinin bölümlerini çek
        details = await scraper.get_series_info(item['url'])
        item["episodes"] = details.get("episodes", [])
        
        # Bölümlerin video (embed) linklerini çöz
        for ep in item["episodes"]:
            ep["video_links"] = await scraper.get_video_links(ep["url"])
            
        archive_data.append(item)

    json_path = os.path.join(OUTPUT_DIR, "Dizi_Arsivi_Sayfa1.json")
    m3u_path = os.path.join(OUTPUT_DIR, "Dizi_Arsivi_Sayfa1.m3u")
    
    save_as_json(archive_data, json_path)
    save_as_m3u(archive_data, m3u_path)
    
    await scraper.close()
    
    print(f"\n[✓] Deneme İşlemi Tamamlandı!")
    print(f"    - Kaydedilen JSON: {json_path}")
    print(f"    - Kaydedilen M3U : {m3u_path}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
