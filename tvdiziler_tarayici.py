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
  category_max_pages: 1  # Her kategoride kaç sayfa taranacak? (Tüm arşivi çekmek için 999 yapabilirsin)

plugin:
  name: "TvDiziler"
  main_url: "https://tvdiziler.tv"

# Taranacak sayfa kategorileri
categories:
  "Son Bolumler": "https://tvdiziler.tv"
  "Aile": "https://tvdiziler.tv/dizi/tur/aile"
  "Aksiyon": "https://tvdiziler.tv/dizi/tur/aksiyon"
  "Bilim Kurgu": "https://tvdiziler.tv/dizi/tur/bilim-kurgu-fantazi"
  "Komedi": "https://tvdiziler.tv/dizi/tur/komedi"
"""

# ==========================================
# 2. KAZIYICI MOTOR (SCRAPER Sınıfı)
# ==========================================
class TvDizilerScraper:
    def __init__(self, config: dict):
        self.main_url = config['plugin']['main_url'].rstrip('/')
        self.timeout = config['settings'].get('timeout', 15)
        
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": f"{self.main_url}/",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

    def fix_url(self, url: str) -> str:
        if not url: return ""
        if url.startswith("http"): return url
        if url.startswith("//"): return f"https:{url}"
        if url.startswith("/"): return f"{self.main_url}{url}"
        return f"{self.main_url}/{url}"

    async def crawl_category(self, cat_name: str, endpoint: str, max_pages: int) -> list:
        items = []
        
        for page in range(1, max_pages + 1):
            # "Son Bolumler" ana sayfadadır ve sayfalama yapısı farklıdır
            if cat_name == "Son Bolumler":
                if page > 1: break  # Son bölümler için sadece ana sayfayı alıyoruz
                url = endpoint
            else:
                url = f"{endpoint}/{page}" if page > 1 else endpoint

            try:
                response = await self.client.get(url)
                tree = HTMLParser(response.text)
            except Exception as e:
                print(f"[!] Sayfa yüklenemedi: {url} | Hata: {e}")
                continue
            
            # Kategoriye göre CSS seçici
            nodes = tree.css("div.poster-xs") if cat_name == "Son Bolumler" else tree.css("div.poster-long")
            if not nodes:
                break
                
            for node in nodes:
                title_node = node.css_first("h2")
                title = title_node.text(strip=True).replace(" izle", "") if title_node else "Bilinmeyen"
                
                a_tag = node.css_first("a") if cat_name == "Son Bolumler" else node.css_first("div.poster-long-subject a")
                href = self.fix_url(a_tag.attributes.get("href")) if a_tag else ""
                
                img_tag = node.css_first("img")
                poster = img_tag.attributes.get("data-src") or img_tag.attributes.get("src") if img_tag else ""
                
                if href:
                    items.append({"title": title, "url": href, "poster": self.fix_url(poster)})
                
            # Sayfalama bitiş kontrolü (Sonraki sayfa var mı?)
            if cat_name != "Son Bolumler":
                has_next = any("Sonraki" in a.text(strip=True) for a in tree.css("ul.pagination a"))
                if not has_next:
                    break
                
        return items

    async def get_series_info(self, url: str) -> dict:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
        except Exception:
            return {"source_url": url, "episodes": []}

        # Eğer bir bölüm URL'siyse, breadcrumb üzerinden dizi ana sayfasına dönmeyi dener
        if "/dizi/" not in url:
            for link in tree.css("div.breadcrumb a"):
                href = link.attributes.get("href", "")
                if "dizi/" in href and "/tur/" not in href:
                    return await self.get_series_info(self.fix_url(href))

        # Detaylar
        title_node = tree.css_first("div.page-title p, div.page-title h1")
        title = title_node.text(strip=True).replace(" izle", "") if title_node else "Bilinmeyen_Dizi"
        
        poster_node = tree.css_first("div.series-profile-image img")
        poster = self.fix_url(poster_node.attributes.get("data-src", "")) if poster_node else ""

        episodes = []
        szn = 1
        
        # Sezonları ve bölümleri topla
        for sezon_node in tree.css("div.series-profile-episode-list"):
            blm = 1
            for bolum_node in sezon_node.css("li"):
                ep_name_node = bolum_node.css_first("h6.truncate a")
                if not ep_name_node: continue
                
                ep_name = ep_name_node.text(strip=True)
                ep_href = ep_name_node.attributes.get("href")
                
                if ep_href:
                    episodes.append({
                        "season": szn,
                        "episode": blm,
                        "title": ep_name,
                        "url": self.fix_url(ep_href),
                        "video_links": []
                    })
                blm += 1
            szn += 1

        # Eğer dizi sayfasında hiç bölüm yoksa, kendi linkini tek bir bölüm gibi ekle
        if not episodes:
            episodes.append({
                "season": 1, "episode": 1, "title": title, 
                "url": url, "video_links": []
            })

        return {"title": title, "poster": poster, "source_url": url, "episodes": episodes}

    async def extract_internal_player(self, url: str) -> list:
        """tvdiziler.tv/vid/ply/ şeklindeki kendi iç oynatıcılarından m3u8 çıkarır."""
        results = []
        try:
            resp = await self.client.get(url, headers={"Referer": f"{self.main_url}/"})
            match = re.search(r'sources:\s*(\[.*?\])', resp.text, re.DOTALL)
            if not match: return results

            for block_match in re.finditer(r'\{(.*?)\}', match.group(1)):
                block = block_match.group(1)
                file_m = re.search(r'file\s*:\s*[\'\"]([^\'\"]+)[\'\"]', block)
                if file_m:
                    results.append(self.fix_url(file_m.group(1)))
        except Exception:
            pass
        return results

    async def get_video_links(self, url: str) -> list:
        results = []
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
        except Exception:
            return results
        
        seen_srcs = set()

        # data-hhs butonlarındaki kaynakları çıkar
        for btn in tree.css("button[data-hhs]"):
            data_hhs = btn.attributes.get("data-hhs")
            if not data_hhs: continue
            
            for src in data_hhs.split(","):
                if not src or "404.html" in src or src in seen_srcs: continue
                seen_srcs.add(src)
                
                player_url = self.fix_url(src)
                if "/vid/kapat/?git=" in player_url:
                    player_url = player_url.split("git=")[-1]
                
                if "/vid/ply/" in player_url:
                    # Kendi internal oynatıcılarını çöz
                    internal_links = await self.extract_internal_player(player_url)
                    results.extend(internal_links)
                else:
                    # Harici oynatıcıları (iframe URL olarak) ekle
                    results.append(player_url)

        # Iframe src taglarını topla
        for iframe in tree.css("iframe"):
            iframe_src = iframe.attributes.get("src")
            if iframe_src and "404.html" not in iframe_src:
                iframe_url = self.fix_url(iframe_src)
                if iframe_url not in seen_srcs and "youtube.com" not in iframe_url:
                    seen_srcs.add(iframe_url)
                    
                    if "/vid/ply/" in iframe_url:
                        internal_links = await self.extract_internal_player(iframe_url)
                        results.extend(internal_links)
                    else:
                        results.append(iframe_url)

        # Çift URL'leri temizle
        return list(set(results))

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
        series_title = item.get("title", "Bilinmeyen Dizi")
        poster = item.get("poster", "")
        
        for ep in item.get("episodes", []):
            ep_title = ep.get("title", f"S{ep.get('season', 1):02d}E{ep.get('episode', 1):02d}")
            for video_link in ep.get("video_links", []):
                extinf = f'#EXTINF:-1 tvg-logo="{poster}" group-title="{series_title}", {series_title} - {ep_title}\n'
                lines.append(extinf)
                lines.append(f"{video_link}\n")
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


# ==========================================
# 4. ANA ÇALIŞTIRICI (MAIN)
# ==========================================
async def main():
    print("[*] TvDiziler Tarayıcı Başlatılıyor...\n")
    
    config = yaml.safe_load(YML_CONFIG)

    output_dir = config['settings'].get('output_dir', 'outputs')
    max_pages = config['settings'].get('category_max_pages', 1)
    os.makedirs(output_dir, exist_ok=True)

    scraper = TvDizilerScraper(config)
    categories = config.get('categories', {})

    for cat_name, cat_endpoint in categories.items():
        print(f"=======================================")
        print(f"[*] KATEGORİ TARANIYOR: {cat_name}")
        print(f"=======================================")
        
        items = await scraper.crawl_category(cat_name, cat_endpoint, max_pages)
        print(f"[+] Toplam {len(items)} dizi/bölüm bulundu.\n")
        
        category_data = []
        for idx, item in enumerate(items, 1):
            print(f"  [{idx}/{len(items)}] Dizi İşleniyor: {item['title']}")
            
            # Dizinin bölümlerini çıkar (Eğer URL bölümse otomatik diziye geçer)
            details = await scraper.get_series_info(item['url'])
            
            # Başlığı, posteri güncelle (diziye yönlenmişse daha detaylıdır)
            item["title"] = details.get("title", item["title"])
            item["poster"] = details.get("poster", item["poster"])
            item["episodes"] = details["episodes"]
            
            # Bölümlerin videolarını çöz
            for ep in item["episodes"]:
                ep["video_links"] = await scraper.get_video_links(ep["url"])
                
            category_data.append(item)

        safe_cat_name = sanitize_filename(cat_name)
        json_path = os.path.join(output_dir, f"{safe_cat_name}.json")
        m3u_path = os.path.join(output_dir, f"{safe_cat_name}.m3u")

        save_as_json(category_data, json_path)
        save_as_m3u(category_data, m3u_path)
        
        print(f"\n[✓] {cat_name} başarıyla kaydedildi!")
        print(f"    - {m3u_path}\n")

    await scraper.close()
    print("[*] Taramalar Tamamlandı!")

if __name__ == "__main__":
    # Windows'ta çalışanlar için asenkron policy ayarı
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
