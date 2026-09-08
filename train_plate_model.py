from ultralytics import YOLO


def main():
    model = YOLO("yolov8n.pt")

    print("🚀 Plaka Tespiti Eğitimi Başlıyor...")

    results = model.train(
        data="D:/Plaka_Tespiti_Birlesik/data.yaml",
        epochs=50,
        imgsz=640,
        batch=16,
        device=0,
        name="plate_detector_v1"
    )

    print("✅ Plaka Tespiti Eğitimi Başarıyla Tamamlandı!")


if __name__ == '__main__':
    main()