import asyncio
import yaml
import json
import os
import re
import httpx
from selectolax.parser import HTMLParser
from contextlib import suppress

# ==========================================
# 1. AYARLAR (GÖMÜLÜ YAML KODU)
# ==========================================
YML_CONFIG = """
settings:
  timeout: 15
  output_dir: "outputs"
  category_max_pages: 2  # Her kategoride kaç sayfa derine inilecek? (Test için 2, hepsini çekmek için 999 yap)

plugin:
  name: "DDizi"
  main_url: "https://www.ddizi.im"

# Taranacak sayfa kategorileri (İstediğini silip ekleyebilirsin)
categories:
  "Son Eklenen Bolumler": "/yeni-eklenenler7"
  "Yabanci Diziler": "/yabanci-dizi-izle"
  "Eski Diziler": "/eski.diziler"
  "Guncel Diziler": "/dizi-izle"
  "Programlar": "/programlar"
"""

# ==========================================
# 2. KAZIYICI MOTOR (SCRAPER Sınıfı)
# ==========================================
class DDiziScraper:
    def __init__(self, config: dict):
        self.main_url = config['plugin']['main_url']
        self.timeout = config['settings'].get('timeout', 15)
        
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"{self.main_url}/",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

    def fix_url(self, url: str) -> str:
        if not url: return ""
        if url.startswith("http"): return url
        if url.startswith("//"): return f"https:{url}"
        return f"{self.main_url}{url}"

    def extract_season_episode(self, text: str):
        s = re.search(r'(\d+)\.\s*Sezon', text, re.IGNORECASE)
        e = re.search(r'(\d+)\.\s*Bölüm', text, re.IGNORECASE)
        return int(s.group(1)) if s else 1, int(e.group(1)) if e else 1

    async def crawl_category(self, endpoint: str, max_pages: int) -> list:
        items = []
        base_cat_url = f"{self.main_url}{endpoint}"
        
        for page in range(1, max_pages + 1):
            url = f"{base_cat_url}/sayfa-{page - 1}" if page > 1 else base_cat_url
            try:
                response = await self.client.get(url)
                tree = HTMLParser(response.text)
            except Exception as e:
                print(f"[!] Sayfa yüklenemedi: {url} | Hata: {e}")
                continue
            
            nodes = tree.css("div.dizi-boxpost-cat, div.dizi-boxpost")
            if not nodes:
                break
                
            for node in nodes:
                a_tag = node.css_first("a")
                if not a_tag: continue
                
                title = a_tag.text(strip=True)
                href = self.fix_url(a_tag.attributes.get("href"))
                
                img_tag = node.css_first("img.img-back, img.img-back-cat")
                poster = img_tag.attributes.get("data-src") or img_tag.attributes.get("src") if img_tag else ""
                
                items.append({"title": title, "url": href, "poster": self.fix_url(poster)})
                
            has_next = any("Sonraki" in a.text(strip=True) for a in tree.css(".pagination a"))
            if not has_next:
                break
                
        return items

    async def get_series_info(self, url: str) -> dict:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
        except Exception:
            return {"source_url": url, "episodes": []}

        episodes = []
        page_eps = tree.css("div.bolumler a, div.sezonlar a, div.dizi-arsiv a, div.dizi-boxpost-cat a")
        
        for ep in page_eps:
            ep_name = ep.text(strip=True)
            ep_href = ep.attributes.get("href")
            if ep_name and ep_href:
                s, e = self.extract_season_episode(ep_name.replace("Final", "").strip())
                episodes.append({
                    "season": s, "episode": e, "title": ep_name, 
                    "url": self.fix_url(ep_href), "video_links": []
                })

        if not episodes:
            title_node = tree.css_first("h1, h2")
            title = title_node.text(strip=True) if title_node else "Bölüm"
            s, e = self.extract_season_episode(title)
            episodes.append({
                "season": s, "episode": e, "title": title, 
                "url": url, "video_links": []
            })

        return {"source_url": url, "episodes": episodes}

    async def get_video_links(self, url: str) -> list:
        results = []
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
        except Exception:
            return results
        
        target_url = None
        og_video = tree.css_first("meta[property='og:video']")
        if og_video: target_url = self.fix_url(og_video.attributes.get("content", ""))

        if not target_url:
            iframe = tree.css_first("iframe[src^='/player/oynat/']")
            if iframe: target_url = self.fix_url(iframe.attributes.get("src", ""))

        if target_url:
            with suppress(Exception):
                player_resp = await self.client.get(target_url, headers={"Referer": url})
                sources = re.findall(r'file:\s*["\']([^"\']+)["\']', player_resp.text)
                
                for src in sources:
                    src = self.fix_url(src)
                    if any(x in src.lower() for x in [".m3u8", ".mp4"]) and src not in results:
                        results.append(src)
                
                if not results and any(x in target_url.lower() for x in [".m3u8", ".mp4"]):
                    results.append(target_url)

        return results

    async def close(self):
        await self.client.aclose()


# ==========================================
# 3. M3U ve JSON ÇIKARTICILAR
# ==========================================
def save_as_json(data: list, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_as_m3u(data: list, filepath: str):
    lines = ["#EXTM3U\n"]
    for item in data:
        series_title = item.get("title", "Bilinmeyen")
        poster = item.get("poster", "")
        
        for ep in item.get("episodes", []):
            for video_link in ep.get("video_links", []):
                ep_title = ep.get("title", f"Bölüm {ep.get('episode', 1)}")
                extinf = f'#EXTINF:-1 tvg-logo="{poster}" group-title="{series_title}", {series_title} - {ep_title}\n'
                lines.append(extinf)
                lines.append(f"{video_link}\n")
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ==========================================
# 4. ANA ÇALIŞTIRICI (MAIN)
# ==========================================
async def main():
    print("[*] DDizi Tek Dosya Tarayıcı Başlatılıyor...\n")
    
    # Gömülü YML'yi oku
    config = yaml.safe_load(YML_CONFIG)

    output_dir = config['settings'].get('output_dir', 'outputs')
    max_pages = config['settings'].get('category_max_pages', 2)
    os.makedirs(output_dir, exist_ok=True)

    scraper = DDiziScraper(config)
    categories = config.get('categories', {})

    for cat_name, cat_endpoint in categories.items():
        print(f"=======================================")
        print(f"[*] KATEGORİ TARANIYOR: {cat_name}")
        print(f"=======================================")
        
        items = await scraper.crawl_category(cat_endpoint, max_pages)
        print(f"[+] Toplam {len(items)} dizi/bölüm bulundu.\n")
        
        category_data = []
        for idx, item in enumerate(items, 1):
            print(f"  [{idx}/{len(items)}] Çözülüyor: {item['title']}")
            
            details = await scraper.get_series_info(item['url'])
            item["episodes"] = details["episodes"]
            
            for ep in item["episodes"]:
                ep["video_links"] = await scraper.get_video_links(ep["url"])
                
            category_data.append(item)

        json_path = os.path.join(output_dir, f"{cat_name}.json")
        m3u_path = os.path.join(output_dir, f"{cat_name}.m3u")

        save_as_json(category_data, json_path)
        save_as_m3u(category_data, m3u_path)
        
        print(f"\n[✓] {cat_name} başarıyla kaydedildi!")
        print(f"    - {m3u_path}\n")

    await scraper.close()
    print("[*] Taramalar Tamamlandı!")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
