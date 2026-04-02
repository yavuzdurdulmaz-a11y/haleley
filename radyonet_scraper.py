import cloudscraper
from bs4 import BeautifulSoup
import re
import sys
import time

# Cloudflare engelini aşmak için scraper nesnesi oluşturuyoruz
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def get_mp3_link(detail_url):
    """Detay sayfasından mp3 bağlantısını Regex ile çıkarır."""
    try:
        response = scraper.get(detail_url, timeout=15)
        if response.status_code != 200:
            return None
        
        # JS içindeki mp3: "URL" yapısını yakalar
        match = re.search(r'mp3:\s*["\'](https://.*?\.mp3)["\']', response.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Hata ({detail_url}): {e}")
    return None

def ilk_harf_kategori(isim):
    """Sanatçı isminin ilk harfini alıp düzgün bir kategori adı oluşturur."""
    if not isim:
        return "Belirsiz"
    
    ilk_harf = isim[0]
    
    # Türkçe karakter küçük harf dönüşüm düzeltmeleri
    if ilk_harf == 'i':
        ilk_harf = 'İ'
    elif ilk_harf == 'ı':
        ilk_harf = 'I'
    else:
        ilk_harf = ilk_harf.upper()

    # Eğer ilk karakter bir rakamsa "0-9" kategorisine at
    if ilk_harf.isdigit():
        return "0-9"
    elif ilk_harf.isalpha():
        return ilk_harf
    else:
        return "Diğer"

def main():
    sayfa = 1
    MAX_SAYFA = 300 
    
    # Tüm şarkıları sıralamak için önce bir listede toplayacağız
    tum_sarkilar = []

    while sayfa <= MAX_SAYFA:
        print(f"\n--- Sayfa {sayfa} İşleniyor ---")
        
        if sayfa == 1:
            url = "https://radyonet.net/mp3dinle"
        else:
            url = f"https://radyonet.net/mp3dinle?en-cok-dinlenenler-sayfa={sayfa}"

        response = scraper.get(url)
        
        if response.status_code != 200:
            print(f"Hata: Sayfa {sayfa} erişilemedi. Döngü durduruluyor.")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        
        hedef_tablo = soup.find('table', class_='enCokDinlenenlerTablo')
        
        if not hedef_tablo:
            print(f"Sayfa {sayfa}'de hedef tablo bulunamadı. Son sayfaya ulaşılmış olabilir.")
            break
            
        songs = hedef_tablo.find_all('div', class_='mp3dinletabloSatir')
        
        if not songs:
            print(f"Sayfa {sayfa} boş. Tarama tamamlandı.")
            break
            
        for song in songs:
            try:
                img_tag = song.find('img', class_='lazy')
                img_url = img_tag.get('data-src') if img_tag else ""
                
                artist_tag = song.find('div', class_='mp3dinleSanatciAdi')
                artist_a = artist_tag.find('a') if artist_tag else None
                
                title_tag = song.find('div', class_='mp3dinleSarkiAdi')
                title_a = title_tag.find('a') if title_tag else None
                
                artist = artist_a.text.strip() if artist_a else "Bilinmeyen Sanatçı"
                title = title_a.text.strip() if title_a else "Bilinmeyen Şarkı"
                
                detail_url = artist_a['href'] if artist_a else None
                
                if detail_url:
                    if not detail_url.startswith('http'):
                        detail_url = "https://radyonet.net" + detail_url
                        
                    print(f"-> {artist} - {title}")
                    mp3_url = get_mp3_link(detail_url)
                    
                    if mp3_url:
                        # Kategori adını bul (A, B, C, 0-9 vb.)
                        kategori = ilk_harf_kategori(artist)
                        
                        # Listeye ekle (daha sonra sıralamak için dict yapısı kullanıyoruz)
                        tum_sarkilar.append({
                            'artist': artist,
                            'title': title,
                            'img_url': img_url,
                            'mp3_url': mp3_url,
                            'kategori': kategori
                        })
                    
                    # Ban yememek için 1 saniye bekle
                    time.sleep(1)
                        
            except Exception as e:
                print(f"Şarkı işlenirken hata: {e}")
        
        sayfa += 1

    print("\nTüm sayfalar tarandı. Liste alfabetik olarak sıralanıyor...")
    
    # Toplanan şarkıları önce Sanatçı adına, sonra Şarkı adına göre alfabetik sıralıyoruz
    tum_sarkilar = sorted(tum_sarkilar, key=lambda x: (x['artist'].lower(), x['title'].lower()))

    # M3U içeriğini oluşturuyoruz
    playlist_content = "#EXTM3U\n"
    
    for sarki in tum_sarkilar:
        # group-title parametresi ile klasör mantığını yaratıyoruz
        playlist_content += f'#EXTINF:-1 group-title="{sarki["kategori"]}" tvg-logo="{sarki["img_url"]}", {sarki["artist"]} - {sarki["title"]}\n'
        playlist_content += f'{sarki["mp3_url"]}\n'

    # Dosyayı kaydet
    with open("radyonet.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
        
    print(f"✅ İşlem Başarılı! Toplam {len(tum_sarkilar)} şarkı gruplandırılarak radyonet.m3u dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
