import cloudscraper
from bs4 import BeautifulSoup
import time

BASE_URL = "https://mp3indirdur.life"
OUTPUT_FILE = "sarkilar.m3u"

# Taranacak tüm kategorilerin listesi
KATEGORILER = [
    "https://mp3indirdur.life/kategori/turkce-sarkilar",
    "https://mp3indirdur.life/kategori/yabanci-sarkilar",
    "https://mp3indirdur.life/kategori/kurtce-sarkilar",
    "https://mp3indirdur.life/kategori/yeni-eklenen-muzikler"
]

# Cloudflare engelini aşmak için scraper nesnesi
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def scrape_songs():
    m3u_lines = ["#EXTM3U"]
    
    # Aynı şarkıyı birden fazla kez eklememek için URL'leri tutacağımız küme (set)
    islenmis_linkler = set()

    for kategori_url in KATEGORILER:
        print(f"\n=========================================")
        print(f"KATEGORİ TARANIYOR: {kategori_url}")
        print(f"=========================================")
        
        sayfa = 1
        # Sınır kaldırıldı, sayfalar bitene kadar devam edecek
        while True:
            # 1. sayfa için direk URL, diğerleri için ?page=N eklemesi
            if sayfa == 1:
                guncel_url = kategori_url
            else:
                guncel_url = f"{kategori_url}?page={sayfa}"
                
            print(f"\n---> Sayfa {sayfa} işleniyor: {guncel_url}")
            
            try:
                response = scraper.get(guncel_url, timeout=15)
                if response.status_code != 200:
                    print(f"Sayfaya ulaşılamadı. Kategori sonu gelmiş olabilir. (Kod: {response.status_code})")
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # Sayfadaki şarkı linklerini bul
                sarki_link_etiketleri = soup.select("ul.OrtaListe li a")
                
                # Eğer sayfada şarkı linki yoksa (son sayfaya gelinmişse) sonsuz döngüyü kır
                if not sarki_link_etiketleri:
                    print("Bu sayfada şarkı bulunamadı. Kategori tamamlandı.")
                    break

                for a_tag in sarki_link_etiketleri:
                    link = a_tag.get("href")
                    if not link:
                        continue
                        
                    full_url = link if link.startswith("http") else BASE_URL + link
                    
                    # ÇİFT KAYIT KONTROLÜ: Şarkı daha önce eklendiyse (veya başka sayfada varsa) atla
                    if full_url in islenmis_linkler:
                        print(f"Zaten eklendi, atlanıyor: {full_url}")
                        continue
                        
                    islenmis_linkler.add(full_url)

                    # Şarkı detay sayfasına gir
                    try:
                        detail_res = scraper.get(full_url, timeout=15)
                        if detail_res.status_code != 200:
                            continue

                        detail_soup = BeautifulSoup(detail_res.text, "html.parser")

                        # 1. Şarkı İsmini Çekme
                        title_tag = detail_soup.select_one(".mks h1")
                        title = title_tag.text.replace(" Mp3 İndir", "").strip() if title_tag else "Bilinmeyen Sarki"

                        # 2. Görseli Çekme
                        img_tag = detail_soup.select_one(".Mp3-images img")
                        img_url = ""
                        if img_tag and img_tag.get("src"):
                            img_url = img_tag.get("src")
                            img_url = img_url if img_url.startswith("http") else BASE_URL + img_url

                        # 3. Ses Dosyası Linkini Çekme ve Asıl Linki Çözme
                        audio_tag = detail_soup.select_one("audio#mp3player")
                        audio_url = ""
                        if audio_tag and audio_tag.get("src"):
                            temp_url = audio_tag.get("src")
                            temp_url = temp_url if temp_url.startswith("http") else BASE_URL + temp_url
                            
                            try:
                                # stream=True ile indirmeden asıl yönlenen (mp3kulisi vb.) linki yakala
                                res_redirect = scraper.get(temp_url, stream=True, timeout=15)
                                audio_url = res_redirect.url
                                res_redirect.close()
                            except Exception as e:
                                print(f"Asıl link çözülemedi: {e}")
                                audio_url = temp_url

                        # M3U formatına uygun şekilde ekle
                        if audio_url:
                            print(f"  + Eklendi: {title}")
                            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{img_url}", {title}')
                            m3u_lines.append(audio_url)
                            
                            # CANLI KAYIT: Olası GitHub timeout çökmesine karşı her şarkıda dosyayı güncelliyoruz
                            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                                f.write("\n".join(m3u_lines))
                        
                        # Sunucudan ban yememek için 1 saniye bekleme
                        time.sleep(1)

                    except Exception as e:
                        print(f"Sarki detayi islenirken hata ({full_url}): {e}")

                # Bir sonraki sayfaya geç
                sayfa += 1

            except Exception as e:
                print(f"Sayfa islenirken hata olustu ({guncel_url}): {e}")
                break

    print(f"\n✅ İŞLEM TAMAM! Toplam {len(islenmis_linkler)} tekil şarkı {OUTPUT_FILE} dosyasına kaydedildi.")

if __name__ == "__main__":
    scrape_songs()
