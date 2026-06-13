"""
BLUE_AI — Base Intent Builder
Temel veri setini programatik olarak olusturur.
140+ kategori, her birinde 20-30 ornek.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "training"
DATA_DIR.mkdir(parents=True, exist_ok=True)

data = []

def add(intent, examples):
    for ex in examples:
        data.append({"text": ex, "intent": intent})

# ================================================================
# 1. SISTEM YONETIMI
# ================================================================

add("system_status", [
    "sistem durumu", "bilgisayar nasil", "pc durumu ne", "sistem nasil",
    "bilgisayarin durumu nedir", "genel durum", "sistem bilgisi",
    "bilgisayar sagligi", "sistem ozeti", "makine durumu",
    "pc ne durumda", "bilgisayar iyi mi", "sistem kontrolu",
    "sistem performansi", "donanim durumu", "genel sistem durumu",
    "her sey yolunda mi", "bilgisayar saglikli mi", "sistem raporu",
    "bilgisayarimin durumunu goster", "ne durumda sistem",
    "makinenin hali ne", "bilgisayar hakkinda bilgi",
    "sistem diagnostik", "performans ozeti",
])

add("cpu_info", [
    "cpu kullanimi", "islemci durumu", "islemci ne kadar calisiyor",
    "cpu yuzde kac", "islemci yuklenmis mi", "cpu bilgisi",
    "islemci performansi", "cpu sicakligi", "islemci modeli",
    "islemci hizi ne kadar", "cpu ne kadar kullaniliyor",
    "islemci kapasite", "cpu detaylari", "islemci durumunu goster",
    "cpu kullanim orani", "islemci yuzdesi", "processor bilgisi",
    "islemci cekirdek sayisi", "cpu frekans", "islemci performans raporu",
])

add("ram_info", [
    "ram durumu", "bellek kullanimi", "ram ne kadar", "hafiza durumu",
    "bellek bilgisi", "ram doluluk orani", "kullanilan ram",
    "bos ram ne kadar", "bellek yeterli mi", "ram yuzde kac",
    "ram detaylari", "bellek miktari", "hafiza ne kadar dolu",
    "ram kullanim orani", "bellek performansi", "ram bilgisi goster",
    "toplam ram ne kadar", "kullanilabilir ram", "bellek durumunu kontrol et",
    "hafiza saglikli mi", "ram sorun var mi",
])

add("disk_info", [
    "disk durumu", "disk alani", "depolama ne kadar",
    "disk doluluk orani", "bos alan ne kadar", "disk bilgisi",
    "hard disk durumu", "ssd durumu", "disk kullanimi",
    "depolama alani goster", "disk saglikli mi", "disk kapasitesi",
    "c surucusu ne kadar dolu", "d surucusu durumu", "disk detaylari",
    "depolama performansi", "disk okuma hizi", "disk yazma hizi",
    "suruculer hakkinda bilgi", "disk alan raporu",
])

add("battery_info", [
    "pil durumu", "batarya ne kadar", "sarj yuzde kac",
    "pil bilgisi", "sarj durumu", "batarya sagligi",
    "pil ne kadar kaldi", "sarjda mi", "pil yuzde kac",
    "batarya seviyesi", "pil omru", "ne kadar sureli pil var",
    "sarj suresi ne kadar", "pil tasarruf modu", "batarya raporu",
    "pil doluluk orani", "batarya detaylari", "pil saglikli mi",
    "ne zaman dolar pil", "sarj yuzdesi",
])

add("network_info", [
    "ag durumu", "internet baglantisi", "wifi durumu",
    "internet hizi", "ag bilgisi", "baglanti var mi",
    "internet calisiyor mu", "wifi sinyal gucu", "ag performansi",
    "indirme hizi", "yukleme hizi", "ping degeri",
    "internet kesintisi var mi", "ag detaylari", "ip adresim ne",
    "baglanti hizi", "ethernet durumu", "wifi sifresini goster",
    "ag istatistikleri", "internet kullanimi", "veri kullanimi",
])

add("process_list", [
    "surecleri goster", "calisan programlar", "aktif uygulamalar",
    "surec listesi", "neler calisiyor", "gorev yoneticisi",
    "calisanlari listele", "top surecler", "en cok cpu kullanan",
    "en cok ram kullanan surec", "arka plan surecleri",
    "calisan servisleri goster", "aktif gorevler",
    "hangi programlar acik", "calisan uygulamalar listesi",
    "surec durumu", "process list", "gorevleri goster",
    "calisan yazilimlari listele", "sistem surecleri",
])

add("process_kill", [
    "sureci sonlandir", "programi kapat", "uygulamayi durdur",
    "sureci oldur", "gorev sonlandir", "programi bitir",
    "zorla kapat", "calismayi durdur", "sureci kapat",
    "kill process", "end task", "programi zorla kapat",
    "donan programi kapat", "yanit vermeyen uygulamayi kapat",
    "cokmus programi sonlandir", "gorev iptal et",
    "islem durdur", "programi sonlandir",
])

add("clean_system", [
    "temizle", "temizlik yap", "cache sil", "gecici dosyalari temizle",
    "temp dosyalari sil", "sistemi temizle", "disk temizligi",
    "gereksiz dosyalari sil", "cop kutusunu bosalt", "tarayici onbellegi sil",
    "log dosyalarini temizle", "eski dosyalari sil", "temizlik modu",
    "sistem temizligi baslat", "depolama temizle", "alan ac",
    "yer ac", "gereksizleri kaldir", "dosya temizligi yap",
    "bilgisayari temizle", "derin temizlik",
])

add("optimize_system", [
    "optimize et", "sistemi hizlandir", "performansi artir",
    "bilgisayari hizlandir", "optimizasyon yap", "sistemi iyilestir",
    "hiz artir", "performans artir", "kaynaklari optimize et",
    "bellek optimize et", "disk optimize et", "sistemi guclendir",
    "hizlandirma yap", "performans moduna gec", "turbo mod",
    "bilgisayar yavas optimize et", "sistem optimizasyonu",
    "kaynak yonetimi", "ram temizle", "cpu hafiflet",
])

add("startup_manage", [
    "baslangic programlarini yonet", "startup uygulamalar",
    "otomatik baslayan programlar", "baslangicta calisanlari goster",
    "startup devre disi birak", "baslangic programi ekle",
    "baslangic programi kaldir", "otomatik acilan uygulamalar",
    "bilgisayar acilisinda calisanlar", "startup yonetimi",
    "acilista calisan servisleri goster", "otomatik baslatmayi kapat",
    "startup optimizasyonu", "acilis hizini artir",
    "gereksiz startup programlari kapat",
])

# ================================================================
# 2. PROFIL DEGISIMI
# ================================================================

add("gaming_mode", [
    "oyun moduna gec", "gaming modu", "oyun profili",
    "oyun modu ac", "gaming profili aktif et", "oyun performans modu",
    "oyun icin optimize et", "fps artir", "oyun ayarlari",
    "gaming mode", "oyun optimize", "oyun modunu aktif et",
    "yuksek performans oyun modu", "oyun icin hizlandir",
    "oyun baslatma modu", "oyun performansi artir",
])

add("work_mode", [
    "is moduna gec", "calisma modu", "is profili",
    "ofis modu", "uretkenlik modu", "calisma profili aktif et",
    "is icin optimize et", "work mode", "profesyonel mod",
    "verimlilik modu", "is modu ac", "calisma ayarlari",
    "ofis performans modu", "kurumsal profil",
])

add("power_saver_mode", [
    "tasarruf modu", "enerji tasarrufu", "pil tasarrufu",
    "guc tasarrufu", "dusuk guc modu", "batarya tasarrufu",
    "enerji tasarruf modunu ac", "power saver", "pil koruma modu",
    "sari isigi ac", "enerjiyi koru", "pil omrunu uzat",
    "tasarruf moduna gec", "dusuk performans modu",
])

add("balanced_mode", [
    "dengeli mod", "normal mod", "standart mod",
    "varsayilan profil", "balanced mode", "orta performans",
    "dengeli profil", "normal ayarlara don", "standart profili yukle",
    "dengeli moda gec", "normal performans", "default profil",
])

add("night_mode", [
    "gece modu", "karanlik mod", "gece isigi",
    "mavi isik filtresi", "gece gorunumu", "dark mode",
    "karartma modu", "gece profili", "goz koruma modu",
    "gece renk sicakligi", "mavi isik azalt", "gece ekrani",
])

# ================================================================
# 3. BELGE ISLEMLERI
# ================================================================

add("create_document", [
    "word belgesi olustur", "belge hazirla", "dokuman yaz",
    "rapor olustur", "word dosyasi yap", "metin belgesi hazirla",
    "yazi yaz", "makale olustur", "belge yap",
    "word ac yeni belge", "rapor yaz", "dokuman hazirla",
    "resmi yazi olustur", "ozgecmis hazirla", "cv yaz",
    "word belgesi hazirla", "yeni dokuman olustur",
    "metin dosyasi olustur", "yazi belgesi hazirla",
    "word'de belge yap", "belge tasarla",
    "mektup yaz", "dilekce hazirla", "sozlesme olustur",
    "tutanak hazirla", "karar yazisi yaz",
])

add("create_spreadsheet", [
    "excel tablosu olustur", "tablo yap", "hesap cizelgesi hazirla",
    "excel dosyasi olustur", "veri tablosu yap", "spreadsheet hazirla",
    "excel ac yeni tablo", "mali tablo olustur", "butce tablosu yap",
    "excel'de tablo hazirla", "veri girisi yap", "hesaplama tablosu",
    "satis tablosu olustur", "envanter tablosu yap", "stok listesi hazirla",
    "fiyat listesi olustur", "maas tablosu hazirla", "butce plani yap",
    "gelir gider tablosu", "istatistik tablosu olustur",
])

add("create_presentation", [
    "sunum hazirla", "powerpoint olustur", "slayt yap",
    "prezentasyon hazirla", "sunum dosyasi olustur", "slayt tasarla",
    "powerpoint sunumu yap", "toplanti sunumu hazirla", "pptx olustur",
    "is sunumu hazirla", "egitim sunumu olustur", "tanitim sunumu yap",
    "proje sunumu hazirla", "satis sunumu olustur", "yillik rapor sunumu",
    "ders sunumu yap", "konferans sunumu hazirla",
])

add("read_pdf", [
    "pdf oku", "pdf dosyasini ac", "pdf icerigini goster",
    "pdf ozetle", "pdf'i analiz et", "pdf'den metin cikar",
    "pdf dosyasini goruntule", "pdf icerigini oku", "pdf tarama",
    "pdf belgesini incele", "pdf'deki bilgileri cikar",
    "pdf dosyasini kontrol et", "pdf icerik analizi",
])

add("edit_document", [
    "belgeyi duzenle", "dokumani guncelle", "dosyayi degistir",
    "belge uzerinde calis", "dokuman revize et", "metni duzenle",
    "icerik guncelle", "belgeyi edit et", "yaziyi degistir",
    "dokumani aç ve duzenle", "belge icerigini degistir",
    "dosyada degisiklik yap", "metni guncelle",
])

add("print_document", [
    "yazdir", "belgeyi yazdir", "cikti al", "sayfayi yazdir",
    "printer'a gonder", "baskiya gonder", "print et",
    "dokuman yazdir", "sayfa ciktisi al", "yazicidan cikart",
    "belgeyi bastir", "yazici ile cikti al", "kopya cikart",
])

# ================================================================
# 4. DOSYA ISLEMLERI
# ================================================================

add("file_search", [
    "dosya ara", "dosya bul", "belge ara", "dosya tara",
    "aradigim dosya", "dosya nerede", "dosyayi bul",
    "dosya konumu", "dosyayi ara", "dosya arama yap",
    "bilgisayarda dosya ara", "dosyalari tara", "belge bul",
    "kayip dosyayi bul", "dosya arastir", "dosya ismi ile ara",
    "uzantiya gore dosya ara", "dosyalari filtrele",
    "dosya konumunu bul", "masaustunde dosya ara",
])

add("file_organize", [
    "dosyalari duzenle", "dosyalari sirala", "dosyalari organize et",
    "masaustunu duzenle", "dosyalari kategorize et", "dosya duzenleme",
    "dosyalari tarihine gore sirala", "dosyalari boyutuna gore sirala",
    "dosyalari turune gore ayir", "klasorlere ayir",
    "dosyalari gruplandi", "masaustu temizle",
    "indirilenler klasorunu duzenle", "dosya organizasyonu yap",
    "otomatik dosya duzenleme", "dosyalari isimlendirerek sirala",
])

add("file_info", [
    "dosya bilgisi", "dosya boyutu", "buyuk dosyalar",
    "dosya detaylari", "dosya ozellikleri", "dosya tarihi",
    "dosyanin boyutunu goster", "en buyuk dosyalar",
    "dosya istatistikleri", "dosya meta bilgisi", "dosya boyut raporu",
    "alan kullanan dosyalar", "agir dosyalari bul",
    "dosya turlerini goster", "dosya sayisi", "klasor boyutu",
])

add("file_delete", [
    "dosya sil", "dosyayi kaldir", "gereksiz dosyalari sil",
    "eski dosyalari temizle", "dosyayi cop kutusuna at",
    "dosya silme", "belgeyi sil", "dosyayi at",
    "dosyayi kalici olarak sil", "dosya cikar",
    "gereksiz belgeleri sil", "eski kayitlari temizle",
])

add("file_copy", [
    "dosya kopyala", "dosyayi kopyala", "belge kopyala",
    "dosyayi baska yere kopyala", "dosya cogalt",
    "kopyasini olustur", "yedek kopyala", "dosya yedekle",
    "klasor kopyala", "dizin kopyala", "dosyayi cokla",
])

add("file_move", [
    "dosya tasi", "dosyayi tasi", "belgeyi tasi",
    "dosyayi baska klasore tasi", "dosya tasima",
    "dosyayi yeni konuma tasi", "dosyayi aktar",
    "klasor tasi", "dosya yer degistir", "dosyayi surukle",
])

add("file_rename", [
    "dosya adini degistir", "dosyayi yeniden adlandir",
    "dosya isim degisikligi", "rename dosya",
    "dosyayi yeniden isimlendir", "dosya adi guncelle",
    "toplu isim degistir", "dosya adini duzenle",
])

add("file_compress", [
    "dosya sikistir", "zip yap", "rar olustur",
    "dosya arsivle", "sikistirmis dosya olustur",
    "zip dosyasi yap", "arsiv olustur", "dosyalari zip'le",
    "klasoru sikistir", "dosyayi paketele",
])

add("file_extract", [
    "zip ac", "arsivi cikar", "rar ac",
    "sikistirilmis dosyayi ac", "unzip yap", "arsiv cikar",
    "zip dosyasini ac", "paketlenfi dosyayi ac",
    "rar dosyasini cikar", "compressed dosyayi ac",
])

add("folder_create", [
    "yeni klasor olustur", "klasor yap", "dizin olustur",
    "yeni dosya klasoru ac", "folder olustur", "yeni dizin yap",
    "proje klasoru olustur", "alt klasor yap",
    "masaustune klasor olustur", "bos klasor ac",
])

# ================================================================
# 5. UYGULAMA KONTROLU
# ================================================================

add("open_app", [
    "chrome ac", "firefox baslat", "notepad ac", "word ac",
    "excel ac", "tarayici ac", "hesap makinesi ac",
    "paint ac", "calculator ac", "vscode ac",
    "spotify ac", "discord ac", "telegram ac",
    "steam ac", "zoom ac", "teams ac",
    "uygulama ac", "program baslat", "uygulama calistir",
    "browser ac", "dosya yoneticisi ac", "gorev yoneticisi ac",
    "cmd ac", "powershell ac", "terminal ac",
    "media player ac", "vlc ac", "muzik uygulamasini ac",
])

add("close_app", [
    "chrome kapat", "uygulamayi kapat", "programi kapat",
    "tarayiciyi kapat", "firefox kapat", "word kapat",
    "tum uygulamalari kapat", "calisanlari kapat",
    "programlari sonlandir", "uygulamayi zorla kapat",
    "acik pencereyi kapat", "tum pencereleri kapat",
    "arka plan uygulamalarini kapat", "gereksiz uygulamalari kapat",
])

add("open_url", [
    "google.com ac", "youtube'u ac", "web sayfasi ac",
    "siteyi ac", "url ac", "link ac",
    "twitter'i ac", "instagram'i ac", "github'i ac",
    "linkedin ac", "facebook ac", "haber sitesini ac",
    "mail sayfasini ac", "google maps ac", "alisveris sitesini ac",
])

add("install_app", [
    "uygulama yukle", "program kur", "yazilim indir",
    "app yukle", "yeni program kur", "uygulama indir",
    "store'dan indir", "market'ten yukle",
    "program indir ve kur", "kurulum yap",
])

# ================================================================
# 6. WEB / ARASTIRMA
# ================================================================

add("web_search", [
    "google'da ara", "internette ara", "web'de arastir",
    "google'a sor", "internet araması yap", "online ara",
    "google arama", "web araması", "internetten bul",
    "arastirma yap", "bilgi ara", "google'dan bul",
    "web taramasi yap", "internet uzerinden ara",
    "konuyu arastir", "detayli arastirma yap",
    "kaynak ara", "bilgi topla", "internetten arastir",
    "google'da arama yap", "arama motoru kullan",
])

add("web_news", [
    "haberleri goster", "son haberler", "guncel haberler",
    "son dakika haberleri", "bugunun haberleri", "haber bulteni",
    "spor haberleri", "ekonomi haberleri", "dunya haberleri",
    "teknoloji haberleri", "turkiye haberleri", "sicak gelismeler",
    "gundem ne", "neler oluyor", "bugun ne oldu",
])

add("web_weather", [
    "hava durumu", "hava nasil", "bugun hava nasil",
    "yarin hava durumu", "haftalik hava durumu", "sicaklik kac derece",
    "yagmur yagacak mi", "hava tahmini", "meteoroloji",
    "hava durumunu goster", "disarisi nasil", "kar yagacak mi",
    "ruzgar hizi", "nem orani", "istanbul hava durumu",
    "ankara hava durumu", "hava sicakligi",
])

add("web_download", [
    "dosya indir", "internetten indir", "sayfa indir",
    "video indir", "resim indir", "muzik indir",
    "pdf indir", "program indir", "dosya cek",
    "indirme baslat", "download yap", "icerik indir",
])

# ================================================================
# 7. WHATSAPP ISLEMLERI
# ================================================================

add("whatsapp_send", [
    "whatsapp'tan mesaj gonder", "whatsapp mesaj at",
    "whatsapp'tan yaz", "whatsapp ile mesaj gonder",
    "whatsapp mesaj yolla", "wp mesaj at",
    "whatsapp'tan mesaj yolla", "wp'den yaz",
    "whatsapp uzerinden mesaj at", "whatsapp ilet",
    "whatsapp'ta mesaj gonder", "wp gonder",
    "whatsapp bildirim gonder", "whatsapp mesajlasma",
    "whatsapp'tan haber ver", "wp mesaj gonder",
    "whatsapp ile iletisim kur", "whatsapp yazisma",
    "whatsapp'tan bilgi gonder", "wp'den mesaj at",
])

add("whatsapp_read", [
    "whatsapp mesajlarini oku", "whatsapp bildirimler",
    "whatsapp gelen mesajlar", "wp mesajlari goster",
    "whatsapp'taki mesajlari kontrol et", "whatsapp okunmamislar",
    "wp mesajlarimi oku", "whatsapp son mesajlar",
    "whatsapp mesaj kutusunu ac", "wp bildirimleri goster",
    "whatsapp'ta ne var", "gelen whatsapp mesajlari",
    "wp'deki mesajlari goruntule", "whatsapp kontrol et",
])

add("whatsapp_call", [
    "whatsapp'tan ara", "whatsapp arama yap", "wp ile ara",
    "whatsapp sesli arama", "whatsapp goruntulu arama",
    "wp goruntulu ara", "whatsapp'tan telefon et",
    "whatsapp video arama", "wp sesli gorushme",
    "whatsapp ile konusma baslat", "wp arama yap",
    "whatsapp gorushme baslat", "whatsapp ile iletisime gec",
])

add("whatsapp_group", [
    "whatsapp grup olustur", "whatsapp grubuna mesaj at",
    "wp grup yaz", "whatsapp grup kurr",
    "whatsapp grubuma mesaj gonder", "wp gruba yaz",
    "whatsapp toplu mesaj", "whatsapp gruplara bildirim",
    "wp grup mesaji at", "whatsapp grubunda paylas",
])

add("whatsapp_media", [
    "whatsapp'tan foto gonder", "whatsapp resim at",
    "wp video gonder", "whatsapp dosya paylas",
    "whatsapp ses kaydi gonder", "wp belge gonder",
    "whatsapp'tan konum paylas", "wp fotograf at",
    "whatsapp dokuman gonder", "whatsapp medya paylas",
])

# ================================================================
# 8. EMAIL / GMAIL ISLEMLERI
# ================================================================

add("gmail_send", [
    "mail gonder", "e-posta gonder", "email at",
    "gmail'den mail gonder", "mail yolla", "e-posta yolla",
    "mail at", "email gonder", "gmail ile gonder",
    "elektronik posta gonder", "gmail uzerinden mail at",
    "mail ilet", "e-posta postalat", "gmail'dan yaz",
    "is maili gonder", "resmi email gonder", "mail yaz ve gonder",
    "eposta at", "gmail mesaj gonder", "mail hazirla ve gonder",
])

add("gmail_read", [
    "mailleri oku", "gelen kutusunu kontrol et", "e-postalari goster",
    "gmail aç", "gelen mailler", "yeni mail var mi",
    "mail kutusunu kontrol et", "e-postalari oku",
    "gmail'i kontrol et", "okunmamis mailler",
    "gelen e-postalar", "gmail bildirimler",
    "son gelen mailler", "mail kutusuna bak",
    "mail kutusundakileri goster", "e-posta bildirimleri",
])

add("gmail_reply", [
    "maile cevap yaz", "e-postaya yanit ver", "mail cevapla",
    "gelen maile don", "email'e cevap yaz", "gmail cevapla",
    "maile yanit gonder", "e-postaya cevap at", "mail cevap ver",
    "reply yaz", "geri donus yap maile", "maile geri yaz",
])

add("gmail_forward", [
    "maili ilet", "e-postayi yonlendir", "mail forward et",
    "maili baskasina gonder", "e-postayi aktar", "maili paylas",
    "forward mail", "maili yonlendir", "e-postayi ilet",
])

add("gmail_draft", [
    "mail taslagi hazirla", "e-posta taslagi olustur",
    "mail taslak kaydet", "gmail taslak yaz",
    "resmi mail taslagi hazirla", "is maili taslagi olustur",
    "e-posta sablonu hazirla", "mail formati olustur",
    "mail icerigi hazirla", "mail metni yaz",
    "profesyonel mail yaz", "resmi e-posta hazirla",
    "kurumsal mail taslagi", "basvuru maili hazirla",
])

add("gmail_search", [
    "mail ara", "e-postada ara", "gmail'de ara",
    "eski mailleri bul", "mail arama yap", "e-posta filtrele",
    "belirli maili bul", "gmail arama", "mail ic araması",
    "gonderdiklerimi ara", "gelen kutusunda ara",
])

# ================================================================
# 9. MESAJ YAZMA / ILETISIM
# ================================================================

add("write_message", [
    "mesaj yaz", "cevap hazirla", "mesaj hazirla",
    "kisa mesaj yaz", "metin hazirla", "yazi yaz",
    "mesaj olustur", "iletisim metni yaz", "bilgilendirme mesaji yaz",
    "resmi mesaj hazirla", "samimi mesaj yaz", "tebrik mesaji yaz",
    "davet mesaji olustur", "bildirim mesaji hazirla",
    "duyuru metni yaz", "mesaj tasarla",
])

add("write_letter", [
    "mektup yaz", "dilekce hziala", "resmi yazi hazirla",
    "basvuru mektubu yaz", "onay yazisi hazirla", "talep yazisi olustur",
    "resmi dilekce yaz", "istifa mektubu hazirla",
    "referans mektubu yaz", "tanitim mektubu olustur",
    "sikayet mektubu yaz", "tebrik mektubu hazirla",
    "davet mektubu olustur", "bilgilendirme yazisi",
])

add("sms_send", [
    "sms gonder", "kisa mesaj at", "telefona mesaj gonder",
    "sms yolla", "mesaj at", "kisa mesaj gonder",
    "sms mesaj at", "telefon mesaji gonder",
    "numraya mesaj at", "sms ilet",
])

# ================================================================
# 10. BILGI / TAVSIYE / EGITIM
# ================================================================

add("explain_topic", [
    "acikla", "anlat", "nedir", "ne demek",
    "konu hakkinda bilgi ver", "detayli acikla",
    "bu konu hakkinda bilgi", "bana anlat", "ogretir misin",
    "ne anlama geliyor", "ne ise yarar",
    "nasil calisir", "mantigi ne", "konuyu acikla",
    "basitce anlat", "ornekle acikla", "ozet bilgi ver",
    "kisa aciklama yap", "tanimi ne",
])

add("give_advice", [
    "tavsiye ver", "ne onerirsin", "oneride bulun",
    "ne yapmami onerirsin", "fikrin ne", "tavsiye eder misin",
    "ne yapmaliyim", "onerilerin neler", "senin dusuncen ne",
    "yol goster", "rehberlik et", "danismanlik yap",
    "en iyisi ne olur", "ne tavsiye edersin", "nasil daha iyi olur",
    "ipucu ver", "puf noktasi ne", "trick ne",
])

add("translate_text", [
    "cevir", "tercume et", "ingilizce'ye cevir",
    "turkce'ye cevir", "translate", "dil ceviri yap",
    "bu cumleyi ingilizce yaz", "almanca'ya cevir",
    "metin cevirisi", "yabanci dile cevir",
    "ingilizce anlami ne", "turkce anlami ne",
    "sozluk bak", "kelime ceviri", "cumle cevirisi yap",
])

add("calculate_math", [
    "hesapla", "kac yapar", "toplami ne",
    "cikarma yap", "carpma islemi", "bolme yap",
    "yuzde hesapla", "faiz hesapla", "kdv hesapla",
    "kur cevirisi", "birim cevirisi", "alan hesapla",
    "hacim hesapla", "ort hesapla", "matematik islem",
    "karekoku ne", "ussu ne", "logaritma hesapla",
    "2 arti 2 kac", "100'un yuzde 15'i", "matematik sorusu coz",
])

add("define_word", [
    "anlami ne", "ne demek", "tanimi ne",
    "ne anlama gelir", "manasi ne", "sozluk anlami",
    "kelime anlami", "kavram ne demek", "terim aciklamasi",
    "ne oldugunu acikla", "sozlukte ne demek",
])

add("compare_things", [
    "farki ne", "karsilastir", "hangisi daha iyi",
    "avantaj dezavantaj", "aralarindaki fark", "mukayese et",
    "hangisini secmeliyim", "karsilastirma yap",
    "hangisi daha uygun", "versus", "artilari eksileri",
])

add("summarize_text", [
    "ozetle", "kisa anlat", "ozet cikar",
    "ana fikir ne", "kisaca acikla", "kisa versiyon",
    "ozet yaz", "metnin ozeti", "hizli ozet",
    "temel noktalar", "onemli kisimlar", "ozet gecir",
])

add("list_steps", [
    "adimlari yaz", "nasil yapilir", "adim adim anlat",
    "prosedur acikla", "sureci anlat", "yol haritasi",
    "yapilacaklar listesi", "islem adimlari", "rehber yaz",
    "kilavuz hazirla", "howto acikla", "tutorial yaz",
])

add("recipe_search", [
    "yemek tarifi", "nasil yapilir tarifi", "yemek tarifleri",
    "tatli tarifi", "corba tarifi", "pasta tarifi",
    "yemek pisirir misin tarifleriyle", "ne pisireyim",
    "aksam yemegi tarifi", "kolay yemek tarifleri",
    "saglikli yemek tarifi", "diyet tarifi",
])

add("fact_check", [
    "dogru mu", "gercek mi", "bu bilgi dogru mu",
    "dogrulaayabilir misin", "kontrol et dogru mu",
    "emin misin", "kaynagi ne", "kaniti ne",
    "bu iddia dogru mu", "dogruluk kontrolu yap",
])

# ================================================================
# 11. SOSYAL MEDYA
# ================================================================

add("social_post", [
    "tweet at", "paylasim yap", "sosyal medyada paylas",
    "instagram'a yukle", "facebook'ta paylas", "post at",
    "story paylas", "durum guncelle", "linkedin'de paylas",
    "sosyal medya postu hazirla", "icerik paylas",
])

add("youtube_search", [
    "youtube'da ara", "youtube video bul", "youtube arama",
    "video ara", "youtube'dan bul", "youtube video arama yap",
    "youtube'da konu ara", "video icerik bul",
    "youtube kanal ara", "youtube'da izle",
])

add("youtube_play", [
    "youtube video ac", "video oynat", "youtube'da izle",
    "video baslat", "youtube izle", "video ac",
    "youtube'dan video oynat", "acik video oynat",
    "video play", "video calistir",
])

# ================================================================
# 12. SISTEM AYARLARI
# ================================================================

add("change_volume", [
    "sesi ac", "sesi kis", "ses seviyesini ayarla",
    "sesi artir", "sesi azalt", "volumu yukselt",
    "sessize al", "mute yap", "ses ac",
    "ses kapat", "volum ayarla", "ses seviyesi",
    "hoparlor sesini artir", "ses yukari", "ses asagi",
])

add("change_brightness", [
    "parlakligi artir", "parlakligi azalt", "ekrani karart",
    "parlaklik ayarla", "ekran parlakligi", "isigi artir",
    "isigi azalt", "ekrani aydinlat", "parlaklik seviyesi",
    "ekran karartma", "brightness ayarla", "monitor parlakligi",
])

add("change_wallpaper", [
    "duvarkagidini degistir", "arka plani degistir",
    "masaustu resmi degistir", "wallpaper degistir",
    "ekran arka planini ayarla", "yeni arka plan koy",
    "masaustu gorseli degistir", "duvar kagidi ayarla",
])

add("take_screenshot", [
    "ekran goruntusu al", "screenshot al", "ekrani kaydet",
    "ekran yakalama", "snapshoth al", "ekran fotografi cek",
    "print screen", "ekran resmi al", "goruntuyu yakala",
    "ss al", "ekran goruntusu kaydet",
])

add("screen_record", [
    "ekran kaydi baslat", "ekrani kaydet", "screen record",
    "video kaydini baslat", "ekran videosu cek",
    "ekran kayit yap", "recording baslat",
    "ekran kaydini durdur", "kaydi bitir",
])

add("shutdown_pc", [
    "bilgisayari kapat", "sistemi kapat", "pc kapat",
    "bilgisayari durdur", "shutdown", "kapan",
    "bilgisayar kapansin", "sistemi kapat lutfen",
    "makineyi kapat", "pc'yi durdur",
])

add("restart_pc", [
    "yeniden baslat", "bilgisayari restart et", "sistemi yeniden baslat",
    "restart at", "reboot yap", "bilgisayari tekrar ac",
    "sistemi yenile", "yeniden baslatma", "pc restart",
])

add("lock_screen", [
    "ekrani kilitle", "bilgisayari kilitle", "kilitle",
    "ekran kilidi", "lock screen", "masaustunu kilitle",
    "oturumu kilitle", "guvenlik kilidi", "ekrani kapat",
])

add("sleep_mode", [
    "uyku moduna al", "sleep mode", "bilgisayari uyut",
    "uyku modu", "beklet", "standby modu",
    "hazirda beklet", "hibernate", "uyku moduna gec",
])

add("toggle_wifi", [
    "wifi ac", "wifi kapat", "kablosuz ag ac",
    "interneti ac", "wifi baglantisi", "wifi ayarlari",
    "wifi'yi aktif et", "wifi'yi devre disi birak",
    "kablosuz baglanti", "wifi toggle",
])

add("toggle_bluetooth", [
    "bluetooth ac", "bluetooth kapat", "bluetooth ayarlari",
    "bluetooth'u aktif et", "bluetooth eslesme",
    "bluetooth cihaz bagla", "bluetooth devre disi birak",
    "bluetooth Toggle", "bluetooth baglantisi",
])

# ================================================================
# 13. ZAMAN / TAKVIM
# ================================================================

add("show_time", [
    "saat kac", "simdi saat kac", "zaman ne",
    "su anki saat", "gunun saati", "saat kacti",
    "turkiye'de saat kac", "saati goster", "saat bilgisi",
])

add("show_date", [
    "bugun tarih ne", "tarih kac", "gunun tarihi",
    "bugun ayin kaci", "hangi gun", "bugun ne",
    "bu gun hangi gun", "tarih bilgisi", "bugunun tarihi",
    "ay ve yil", "takvim tarihi",
])

add("set_alarm", [
    "alarm kur", "alarmi ayarla", "sabah alarmi kur",
    "saat yedide alarm", "alarm olustur", "uyandirma alarmi",
    "gunluk alarm", "alarm ekle", "calar saat ayarla",
    "alarm koy", "alarmi aktif et",
])

add("set_reminder", [
    "hatirlatici kur", "hatirlat", "hatirlatma olustur",
    "beni hatirlat", "not birak", "gorev hatirlatma",
    "toplanti hatirlatici", "ilac hatirlatma", "randevu hatirlat",
    "hatirlatici ekle", "bana hatirlat", "sonra hatırlat",
])

add("set_timer", [
    "zamanlayici baslat", "timer kur", "geri sayim baslat",
    "krondometre baslat", "sure tut", "zamanlayici ayarla",
    "5 dakika sayaci", "countdown baslat", "sure ol",
    "kronometre calistir",
])

add("calendar_event", [
    "takvime etkinlik ekle", "toplanti planla", "randevu kaydet",
    "takvim etkinligi olustur", "takvime not ekle",
    "toplanti ayarla", "etkinlik olustur", "takvimi guncelle",
    "randevu olustur", "is toplantisi planla",
    "gorusme zamani ayarla", "program ekle",
])

# ================================================================
# 14. EGLENCE
# ================================================================

add("play_music", [
    "muzik cal", "sarki calistir", "muzik ac",
    "playlist cal", "sarki ac", "muzik oynat",
    "radyo ac", "sarki cal", "muzik play",
    "spotify'da cal", "muzik baslat", "parça cal",
    "album cal", "sanatciyi cal", "rastgele muzik cal",
])

add("tell_joke", [
    "fikra anlat", "espri yap", "guldur beni",
    "komik bir sey anlat", "saka yap", "bir fikra soyle",
    "gulumsett", "beni eglendirr", "komik ol",
    "mizah yap", "esprili bir sey soyle",
])

add("tell_story", [
    "hikaye anlat", "masal anlat", "oykü anlat",
    "bir hikaye soyle", "masall anlat", "kisa hikaye yaz",
    "macera hikayesi", "korku hikayesi", "ask hikayesi",
    "cocuk masali anlat", "uyku masali",
])

add("random_fact", [
    "ilginc bilgi ver", "biliyor muydun", "enteresan bilgi",
    "sasirtici bilgi", "gunun bilgisi", "fun fact",
    "ilginc bir sey soyle", "egitici bilgi", "merak bilgisi",
    "ansiklopedik bilgi", "bilgi kapsulu",
])

add("play_game", [
    "oyun oynayalim", "kelime oyunu", "bilmece sor",
    "zeka sorusu sor", "bulmaca", "quiz yap",
    "oyun baslat", "oynamak istiyorum", "bir oyun oher",
    "tahmimn oyunu", "sayi tahmin", "trivias sor",
])

# ================================================================
# 15. FINANS / EKONOMI
# ================================================================

add("currency_convert", [
    "doviz kuru", "dolar kac tl", "euro ne kadar",
    "kur cevirisi", "dolar tl cevir", "doviz hesapla",
    "sterlin kac lira", "kur bilgisi", "dolar euro paritesi",
    "kripto fiyatlari", "bitcoin kac dolar", "altin fiyati",
    "guncel kur", "doviz cevir", "para birimi cevir",
])

add("budget_track", [
    "butce takibi", "harcama kaydet", "gelir gider takibi",
    "butce plani yap", "harcamalari listele", "butce durumu",
    "para yonetimi", "tasarruf plani", "mali durum",
    "butce raporu", "aylik harcamalar", "gelir tablosu",
])

add("price_compare", [
    "fiyat karsilastir", "en ucuz fiyat", "fiyat kontrolu",
    "fiyat arastirmasi", "uygun fiyat bul", "fiyatlari karsilastir",
    "en iyi fiyat", "ucuz alternatif bul", "fiyat analizi",
])

# ================================================================
# 16. SAGLIK / YASAM
# ================================================================

add("health_tip", [
    "saglikli yasam ipuclari", "saglik tavsiyesi",
    "saglikli beslenme", "saglik onerisi", "saglik bilgisi",
    "saglikli olabilmek icin ne yapmaliyim", "saglik rehberi",
    "saglik kontrolu", "saglik ipucu", "yasam kalitesi",
])

add("exercise_suggest", [
    "egzersiz oner", "spor hareketi goster", "antrenman programi",
    "ev egzersizi", "kardiyo onerileri", "kas gelistirme",
    "esneme hareketleri", "yoga hareketleri", "fitness program",
    "kilo verme egzersizi", "gunluk egzersiz",
])

add("calorie_info", [
    "kalori hesapla", "besin degeri", "kalori bilgisi",
    "yemek kalorisi", "diyet kalori hesabi", "gunluk kalori ihtiyaci",
    "kalori cetveli", "kalori sayaci", "obezite hesapla",
    "vucut kitle indeksi", "bmi hesapla",
])

add("water_reminder", [
    "su ic hatirlatici", "su icmeyi hatirlat", "su zamani",
    "su icme hatirlatmasi", "gunluk su tuketimi",
    "ne kadar su icmeliyim", "su takibi", "hidrasyon hatirlatici",
])

# ================================================================
# 17. SEYAHAT / KONUM
# ================================================================

add("find_place", [
    "yakin yer bul", "restoran bul", "kafe bul",
    "eczane nerede", "hastane bul", "market bul",
    "en yakin benzinlik", "park yeri bul", "otel bul",
    "atm nerede", "yakin yerleri goster", "mekan onerileri",
])

add("get_directions", [
    "yol tarifi al", "navigasyon baslat", "nasil gidilir",
    "yol tarifi goster", "rota olustur", "trafiği goster",
    "en kisa yol", "ulasim bilgisi", "yol haritasi",
    "araba ile nasil gidilir", "toplu tasima rotasi",
])

add("travel_plan", [
    "seyahat planla", "tatil planı yap", "gezi programi olustur",
    "ucak bileti bul", "otel onerileri", "seyahat liustesi hazirla",
    "vize bilgisi", "pasaport islemleri", "seyahat onerileri",
    "hafta sonu gezi", "yurt disi seyahat plani",
])

# ================================================================
# 18. KODLAMA / GELISTIRME
# ================================================================

add("explain_code", [
    "kodu acikla", "bu kod ne yapar", "kod analizi",
    "script aciklama", "program ne ise yarar", "fonksiyon acikla",
    "algoritma acikla", "kodu anlat", "syntax aciklama",
    "hata mesaji ne anlama geliyor", "error acikla",
])

add("write_code", [
    "kod yaz", "script olustur", "program yaz",
    "fonksiyon yaz", "python kodu yaz", "javascript kodu",
    "script hazirla", "otomasyon kodu yaz", "bot yaz",
    "api kodu olustur", "veritabani sorgusu yaz",
])

add("debug_help", [
    "hata duzelt", "bug bul", "debug yap",
    "kod hatasi nedir", "neden calismıyor", "hata coz",
    "sorun gider", "cozum oner", "error fix",
    "kod duzeltme", "debugging yardimi",
])

# ================================================================
# 19. GUVENLIK
# ================================================================

add("virus_scan", [
    "virus taramasi yap", "guvenlik taramasi", "malware kontrol",
    "antiviurs tarama", "bilgisayari tara", "tehdit taramasi",
    "guvenlik kontrolu", "zararli yazilim tara", "virus kontrol",
])

add("password_generate", [
    "sifre olustur", "guclu parola uret", "rastgele sifre",
    "guvenli parola yap", "sifre onerisi", "password generate",
    "yeni sifre olustur", "sifre yap", "karmasik sifre uret",
])

add("privacy_check", [
    "gizlilik kontrolu", "izleme kontrol", "kisisel veri guvenligi",
    "gizlilik ayarlari", "privacy check", "takip engelle",
    "cerezleri temizle", "iz birakma modu", "incognito mod",
])

# ================================================================
# 20. SOHBET / KONUSMA
# ================================================================

add("greeting", [
    "merhaba", "selam", "gunaydin", "iyi gunler",
    "iyi aksamlar", "iyi geceler", "nasilsin",
    "naber", "hey", "sa", "selamun aleykum",
    "hosgeldin", "merhabalar", "selamlar",
    "gunaydinn", "iyi sabahlar", "hayirli gunler",
    "herkese merhaba", "hosgeldiniz", "esenlikler",
])

add("farewell", [
    "gorusuruz", "hosca kal", "bye", "gule gule",
    "iyi gunler", "iyi geceler", "kendine iyi bak",
    "gorusuruz tekrar", "bay bay", "hoscakal",
    "elveda", "sonra gorusuruz", "yarin gorusuruz",
    "hayirli geceler", "iyi aksamlar", "gorusmek uzere",
])

add("thanks", [
    "tesekkurler", "sagol", "tesekkur ederim",
    "cok tesekkurler", "ellerin dert gormesin", "eyv",
    "sagolasin", "minnattarim", "cok iyisin",
    "harika tesekkurler", "supersin sagol", "adamsın",
    "eline saglik", "gozune saglik", "tesekkur",
])

add("who_are_you", [
    "sen kimsin", "adin ne", "ne yapabilirsin",
    "kendini tanit", "sen ne tur bir yapay zekasin",
    "kimsin sen", "sen bir bot musun", "ne isi yapiyorsun",
    "ne isine yariyorsun", "seninle ne yapabilirim",
    "yeteneklerin ne", "gorevlerin ne", "nasil bir asistansin",
])

add("how_are_you", [
    "nasilsin", "nasil gidiyor", "iyi misin",
    "keyfin nasil", "ne haber", "nasil hissediyorsun",
    "durumun nasil", "iyi mi gidiyor", "hayat nasil",
    "her sey yolunda mi", "nasil gidiyorsun", "ne var ne yok",
])

add("compliment", [
    "harika is cikardin", "cok iyisin", "mukemmelsin",
    "bravo sana", "aferin", "super yaptin",
    "muhtesemsin", "cok yardimci oldun", "seni seviyorum",
    "harika bir asistansin", "olaganustu", "enfessin",
])

add("small_talk", [
    "sohbet edelim", "konusalim", "bana bir sey anlat",
    "can sikintisi", "sikiliyorum", "bir seyler soyle",
    "muhabbet edelim", "ilginc bir sey bilir misin",
    "beni eglendirr", "ne konusalim", "ilginc bir bilgi ver",
])

add("help", [
    "yardim", "yardim et", "ne yapabilirsin",
    "komutlar neler", "nasil kullanilir", "help",
    "menu goster", "komut listesi", "destek",
    "yardim menusü", "rehber", "kilavuz",
    "bana yol goster", "nasil kullanayim", "n yapabilirim seninle",
])

add("general_question", [
    "bir sorum var", "merak ettim", "sormak istiyorum",
    "bilgi almak istiyorum", "aciklar misin", "ogrenebilir miyim",
    "cevap ver", "soru sormak istiyorum", "fikir almak istiyorum",
    "senin gorusun ne", "dusuncen nedir", "ne dersin",
])

# ================================================================
# 20+. EKSTRA KATEGORILER
# ================================================================

add("note_take", [
    "not al", "not yaz", "kaydet sunu", "not defterine yaz",
    "onemli not", "hatirlatma notu al", "kisa not yaz",
    "bilgi kaydet", "not olustur", "memo yaz",
    "hatirlama notu", "aklima gelen notu kaydet",
])

add("todo_add", [
    "yapilacaklara ekle", "gorev ekle", "todo ekle",
    "listeye ekle", "yapilacak is ekle", "gorev olustur",
    "is listesine ekle", "plan ekle", "gorev kaydet",
])

add("todo_list", [
    "yapilacaklar listesi", "gorevlerimi goster", "todo list",
    "is listesi", "planlanin gorevi", "bugunku gorevler",
    "bekleyen isler", "tamamlanmamis gorevler", "acik gorevler",
])

add("pomodoro_start", [
    "pomodoro baslat", "odaklanma zamanlayicisi", "calisma zamanlayicisi",
    "25 dakika calisma modu", "pomodoro tekniki",
    "odaklanma modu", "konsantrasyon zamanlayicisi",
    "calisma suresi baslat", "fokus mod",
])

add("focus_mode", [
    "rahatsiz etme modu", "sessiz mod", "odaklanma modu",
    "bildirimleri kapat", "do not disturb", "dikkat dagitmadan",
    "odak modu ac", "konsantrasyon modu", "sessizlik modu",
    "bildirim engelle", "rahatsiz etme",
])

add("clipboard_manage", [
    "panoya kopyala", "panoyu goster", "pano gecmisi",
    "son kopyalananlar", "clipboard temizle", "pano yonetimi",
    "kopyalananlar listesi", "yapistirma gecmisi",
])

add("system_info_detailed", [
    "donanim bilgisi", "bios bilgisi", "anakart bilgisi",
    "ekran karti bilgisi", "gpu bilgisi", "ses karti bilgisi",
    "usb cihazlari", "bagli cihazlar", "surucu bilgileri",
    "windows surumu", "isletim sistemi bilgisi", "sistem ozellikleri",
])

add("schedule_meeting", [
    "toplanti planla", "gorusme ayarla", "meeting olustur",
    "zoom toplanti kur", "teams toplanti", "online gorusme planla",
    "video konferans ayarla", "toplanti zamani belirle",
    "toplanti davetiyesi gonder", "toplanti organize et",
])

add("convert_unit", [
    "birim cevir", "kilogram pound cevir", "metre feet cevir",
    "celsius fahrenheit cevir", "litre galon cevir",
    "km mile cevir", "gram ons cevir", "birim donusturme",
    "santimetre inc cevir", "agirlik cevirisi",
])

# ================================================================
# KAYDET
# ================================================================

output = {
    "meta": {
        "version": "1.0",
        "total_base_examples": len(data),
        "num_intents": len(set(d["intent"] for d in data)),
        "intents": sorted(set(d["intent"] for d in data)),
    },
    "data": data,
}

output_path = DATA_DIR / "base_intents.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Base dataset olusturuldu!")
print(f"  Toplam ornek: {len(data)}")
print(f"  Toplam intent: {output['meta']['num_intents']}")
print(f"  Dosya: {output_path}")
print(f"\nIntent dagilimi:")
from collections import Counter
counts = Counter(d["intent"] for d in data)
for intent, count in sorted(counts.items()):
    print(f"  {intent}: {count} ornek")
