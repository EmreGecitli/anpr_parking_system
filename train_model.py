from ultralytics import YOLO


def main():
    # Başlangıç için YOLOv8'in en hafif ve hızlı modeli olan Nano (n) versiyonunu yüklüyoruz
    model = YOLO("yolov8n.pt")

    print("🚀 Eğitim Başlıyor! Ekran kartı (RTX 3050) devreye giriyor...")

    # Eğitimi başlat
    results = model.train(
        data="D:/Karakter_Tespiti_Birlesik/data.yaml",  # Biraz önce ayarladığımız yol haritası
        epochs=50,  # Modelin tüm veri setini kaç kez baştan sona okuyacağı
        imgsz=640,  # Resimlerin eğitim sırasındaki çözünürlüğü
        batch=16,  # Ekran kartına tek seferde gönderilecek resim sayısı (VRAM'i şişirmemek için 16 idealdir)
        device=0,  # 0 numaralı cihazı (Yani RTX 3050 GPU'yu) kullanmaya zorla
        name="character_reader_v1"  # Eğitim sonuçlarının kaydedileceği klasörün İngilizce adı
    )

    print("✅ Eğitim Başarıyla Tamamlandı!")


if __name__ == '__main__':
    # Windows sistemlerinde çoklu işlem (multiprocessing) çakışmalarını önlemek için
    # eğitim kodunun her zaman bu if bloğu içinde çalıştırılması gerekir.
    main()