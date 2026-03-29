import asyncio
import yaml
import json
import os
import re
import httpx
from base64 import b64decode
from Crypto.Cipher import AES
from selectolax.parser import HTMLParser
from contextlib import suppress

# ==========================================
# 1. AYARLAR (GÖMÜLÜ YAML KODU)
# ==========================================
YML_CONFIG = """
settings:
  timeout: 15
  output_dir: "outputs"
  category_max_pages: 1  # Tüm arşivi çekmek için burayı 999 yapabilirsin

plugin:
  name: "Dizilla"
  main_url: "https://dizilla.to"

# Taranacak API uç noktaları (SAYFA kelimesi bot tarafından otomatik değiştirilecek)
categories:
  "Aile": "https://dizilla.to/api/bg/findSeries?releaseYearStart=1900&releaseYearEnd=2050&imdbPointMin=0&imdbPointMax=10&categoryIdsComma=15&countryIdsComma=&orderType=date_desc&languageId=-1&currentPage=SAYFA&currentPageCount=24&queryStr=&categorySlugsComma=&countryCodesComma="
  "Aksiyon": "https://dizilla.to/api/bg/findSeries?releaseYearStart=1900&releaseYearEnd=2050&imdbPointMin=0&imdbPointMax=10&categoryIdsComma=9&countryIdsComma=&orderType=date_desc&languageId=-1&currentPage=SAYFA&currentPageCount=24&queryStr=&categorySlugsComma=&countryCodesComma="
  "Bilim Kurgu": "https://dizilla.to/api/bg/findSeries?releaseYearStart=1900&releaseYearEnd=2050&imdbPointMin=0&imdbPointMax=10&categoryIdsComma=5&countryIdsComma=&orderType=date_desc&languageId=-1&currentPage=SAYFA&currentPageCount=24&queryStr=&categorySlugsComma=&countryCodesComma="
"""

# ==========================================
# 2. KAZIYICI MOTOR VE AES ÇÖZÜCÜ
# ==========================================
class DizillaScraper:
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
        # AES Şifreleme Anahtarı
        self.aes_key = "9bYMCNQiWsXIYFWYAu7EkdsSbmGBTyUI".encode("utf-8")
        self.aes_iv = bytes([0] * 16)

    def decrypt_response(self, response_str: str) -> dict:
        """Dizilla'nın şifreli JSON yanıtlarını AES/CBC yöntemiyle çözer."""
        try:
            encrypted_bytes = b64decode(response_str)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            decrypted = cipher.decrypt(encrypted_bytes)
            
            # PKCS5/PKCS7 padding temizleme
            pad_len = decrypted[-1]
            decrypted = decrypted[:-pad_len]
            
            return json.loads(decrypted.decode("utf-8"))
        except Exception as e:
            print(f"[!] AES Çözme Hatası: {e}")
            return {}

    def fix_url(self, url: str) -> str:
        if not url: return ""
        if url.startswith("http"): return url
        if url.startswith("//"): return f"https:{url}"
        if url.startswith("/"): return f"{self.main_url}{url}"
        return f"{self.main_url}/{url}"

    def fix_poster_url(self, url: str) -> str:
        """Google AMP önbellek URL'lerini asıl resim URL'lerine çevirir."""
        if not url: return ""
        if "cdn.ampproject.org" in url:
            match = re.search(r"cdn\.ampproject\.org/[^/]+/s/(.+)$", url)
            if match:
                return f"https://{match.group(1)}"
        return url

    async def crawl_category(self, endpoint: str, max_pages: int) -> list:
        items = []
        for page in range(1, max_pages + 1):
            url = endpoint.replace("SAYFA", str(page))
            try:
                response = await self.client.post(url)
                data = response.json()
                
                # Yanıtı AES ile çöz
                decrypted = self.decrypt_response(data.get("response", ""))
                veriler = decrypted.get("result", [])
                
                if not veriler:
                    break
                
                for veri in veriler:
                    title = veri.get("original_title") or veri.get("used_title") or "Bilinmeyen"
                    href = self.fix_url(veri.get("used_slug"))
                    poster = self.fix_poster_url(self.fix_url(veri.get("poster_url")))
                    items.append({"title": title, "url": href, "poster": poster})
            except Exception as e:
                print(f"[!] Sayfa çekilemedi (Sayfa {page}): {e}")
                break
        return items

    async def get_series_info(self, url: str) -> dict:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            # Next.js verilerini bul
            next_data_node = tree.css_first("script#__NEXT_DATA__")
            if not next_data_node:
                return {"source_url": url, "episodes": []}
                
            next_data = json.loads(next_data_node.text(strip=True))
            secure_data = next_data.get("props", {}).get("pageProps", {}).get("secureData")
            
            if not secure_data:
                return {"source_url": url, "episodes": []}
                
            decrypted = self.decrypt_response(secure_data)
            content = decrypted.get("contentItem", {})
            
            title = content.get("original_title") or content.get("used_title") or "Bilinmeyen Dizi"
            poster = self.fix_poster_url(self.fix_url(content.get("back_url") or content.get("poster_url")))
            
            episodes = []
            seasons = decrypted.get("RelatedResults", {}).get("getSerieSeasonAndEpisodes", {}).get("result", [])
            
            for season in seasons:
                s_no = season.get("season_no", 1)
                for ep in season.get("episodes", []):
                    e_no = ep.get("episode_no", 1)
                    slug = ep.get("used_slug", "")
                    ep_name = ep.get("episode_text", f"{s_no}. Sezon {e_no}. Bölüm")
                    
                    episodes.append({
                        "season": s_no,
                        "episode": e_no,
                        "title": ep_name,
                        "url": self.fix_url(slug),
                        "video_links": []
                    })

            return {"title": title, "poster": poster, "source_url": url, "episodes": episodes}

        except Exception as e:
            print(f"[!] Dizi detayı çekilemedi ({url}): {e}")
            return {"source_url": url, "episodes": []}

    async def get_video_links(self, url: str) -> list:
        results = []
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            next_data_node = tree.css_first("script#__NEXT_DATA__")
            if not next_data_node: return results
                
            next_data = json.loads(next_data_node.text(strip=True))
            secure_data = next_data.get("props", {}).get("pageProps", {}).get("secureData", "")
            decrypted = self.decrypt_response(secure_data)
            
            related = decrypted.get("RelatedResults", {})
            sources = related.get("getEpisodeSources", {}).get("result", [])
            if not sources:
                sources = related.get("getEpisodeSourcesById", {}).get("result", [])
                
            if not sources: return results
            
            # Dizilla iframe (player) linklerini gömülü HTML içinden veriyor
            for source in sources:
                source_content = str(source.get("source_content", ""))
                cleaned_source = source_content.replace('"', '').replace('\\', '')
                
                iframe_secici = HTMLParser(cleaned_source)
                iframe_node = iframe_secici.css_first("iframe")
                
                if iframe_node:
                    iframe_src = iframe_node.attributes.get("src")
                    if iframe_src:
                        results.append(self.fix_url(iframe_src))

        except Exception:
            pass
            
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
    print("[*] Dizilla AES Çözücü & Tarayıcı Başlatılıyor...\n")
    
    config = yaml.safe_load(YML_CONFIG)
    output_dir = config['settings'].get('output_dir', 'outputs')
    max_pages = config['settings'].get('category_max_pages', 1)
    os.makedirs(output_dir, exist_ok=True)

    scraper = DizillaScraper(config)
    categories = config.get('categories', {})

    for cat_name, cat_endpoint in categories.items():
        print(f"=======================================")
        print(f"[*] KATEGORİ TARANIYOR: {cat_name}")
        print(f"=======================================")
        
        items = await scraper.crawl_category(cat_endpoint, max_pages)
        print(f"[+] Toplam {len(items)} dizi bulundu.\n")
        
        category_data = []
        for idx, item in enumerate(items, 1):
            print(f"  [{idx}/{len(items)}] Şifreler Çözülüyor: {item['title']}")
            
            details = await scraper.get_series_info(item['url'])
            item["episodes"] = details.get("episodes", [])
            
            # Bölümlerin videolarını (iframe linklerini) çöz
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
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
