# Akıllı Otopark ANPR Sistemi

Bu proje, otopark giriş-çıkışlarını yönetmek için geliştirilmiş üç kademeli (Hibrit) Yapay Zeka destekli Otomatik Plaka Tanıma (ANPR) sistemidir. Sistem sırasıyla yerel YOLO modellerini, Real-ESRGAN görüntü netleştirme algoritmalarını ve zorunlu hallerde bulut tabanlı Plate Recognizer API'sini kullanır.

## Özellikler
* **Hibrit OCR Mimarisi:** YOLO ile hızlı tarama, Real-ESRGAN ile netleştirme ve zorlu okumalar için API yedeği.
* **Esnek Eşleştirme (Fuzzy Matching):** Veritabanındaki plakalarla okunan plakalar arasında %85 benzerlik oranına dayalı akıllı eşleştirme.
* **Spam Koruması:** Aynı plakanın peş peşe defalarca okunmasını engelleyen log yönetimi.
* **Kurumsal Güvenlik:** Tüm hassas veriler (Veritabanı şifreleri, API anahtarları) `.env` dosyası ile korunmaktadır.

---

# Kurulum Adımları (Yerel Ortam)

Projeyi sıfırdan bir bilgisayara kurmak ve çalıştırmak için aşağıdaki adımları sırasıyla uygulayın.

## 1. Projeyi Bilgisayarınıza İndirin (Clone)
Terminali açın ve projeyi GitHub'dan çekin:

* git clone [https://github.com/](https://github.com/)<kullanici_adiniz>/<repo_adiniz>.git
cd <repo_adiniz>

## 2. Sanal Ortam (Virtual Environment) ve Kütüphaneler
Proje bağımlılıklarının sisteminizle çakışmaması için bir sanal ortam oluşturun ve gerekli kütüphaneleri yükleyin:  
* python -m venv venv
### Windows için sanal ortamı aktif etme:
* venv\Scripts\activate
### MacOS/Linux için:
* source venv/bin/activate
### Gerekli kütüphaneleri kurun:
* pip install -r requirements.txt

## 3. Veritabanı Kurulumu
Proje PostgreSQL kullanmaktadır.
* Bilgisayarınızda PostgreSQL yüklü değilse kurun.
* pgAdmin veya komut satırı üzerinden parking_db adında boş bir veritabanı oluşturun.  
* Tabloları manuel oluşturmanıza gerek yoktur, sunucu başlatıldığında SQLAlchemy tüm tabloları otomatik yaratacaktır.

## 4. Çevre Değişkenleri (.env) Ayarları
* Projenin kök dizininde (main.py ile aynı yerde) .env adında yeni bir dosya oluşturun ve içine kendi bilgilerinizi ekleyin:  
```env
DB_PASSWORD=veritabani_sifrenizi_buraya_yazin
PLATE_API_TOKEN=plate_recognizer_api_token_buraya 
```
* (Not: Bu dosya .gitignore listesinde olduğu için GitHub'a yüklenmez, her yeni kurulumda yerelde elle oluşturulmalıdır.)

## 5. Sunucuyu Başlatma
* Tüm ayarlar tamamlandıktan sonra FastAPI sunucusunu başlatmak için aşağıdaki komutu çalıştırın:
uvicorn main:app --reload
* Terminalde Application startup complete. mesajını gördüğünüzde sistem kullanıma hazırdır!

## 6. API Uç Noktaları (Endpoints)
* Sunucu çalıştıktan sonra http://127.0.0.1:8000/docs adresine giderek Swagger UI üzerinden tüm API'yi görsel olarak test edebilirsiniz.
* **POST /scan-plate/:** Kameradan gelen fotoğrafı yükler, plakayı yapay zeka ile analiz eder ve veritabanına giriş/çıkış logunu işler.  
* **POST /add-vehicle/:** Sisteme manuel olarak yeni bir abone araç kaydeder.  
* **GET /vehicles/:** Sistemde kayıtlı olan tüm araçların listesini JSON formatında getirir.  