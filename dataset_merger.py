import shutil
from pathlib import Path


def merge_yolo_datasets(dataset1_dir, dataset2_dir, output_dir):
    dataset1_path = Path(dataset1_dir)
    dataset2_path = Path(dataset2_dir)
    out_path = Path(output_dir)

    # YOLO standart klasör isimleri
    splits = ['train', 'valid', 'val', 'test']
    data_types = ['images', 'labels']

    print("Hedef klasörler oluşturuluyor...")
    for split in splits:
        for dtype in data_types:
            # Standart YOLOv8 yapısı: split/dtype (Örn: train/images)
            (out_path / split / dtype).mkdir(parents=True, exist_ok=True)

    def process_dataset(ds_path, prefix):
        print(f"\n[{prefix}] etiketli veri seti taranıyor: {ds_path}")

        for split in splits:
            for dtype in data_types:
                # Roboflow'un iki farklı çıkartma formatını da kontrol ediyoruz
                opt1 = ds_path / split / dtype  # Örn: train/images
                opt2 = ds_path / dtype / split  # Örn: images/train

                source_dir = None
                if opt1.exists():
                    source_dir = opt1
                elif opt2.exists():
                    source_dir = opt2

                if not source_dir:
                    continue

                target_dir = out_path / split / dtype

                file_count = 0
                for file_path in source_dir.iterdir():
                    if file_path.is_file():
                        new_filename = f"{prefix}_{file_path.name}"
                        target_file_path = target_dir / new_filename
                        shutil.copy2(file_path, target_file_path)
                        file_count += 1

                if file_count > 0:
                    print(f"  -> {split}/{dtype} klasöründen {file_count} dosya kopyalandı.")

    # İşlemi başlat
    process_dataset(dataset1_path, "ds1")
    process_dataset(dataset2_path, "ds2")
    print(f"\n✅ Mükemmel! Veriler başarıyla birleştirildi.\nYeni setin şurada: {out_path.resolve()}")


# ==========================================
# AYARLAR
# ==========================================
DATASET_1_YOLU = "D:/Karakter_Seti_1"
DATASET_2_YOLU = "D:/Karakter_Seti_2"
HEDEF_YENI_KLASOR = "D:/Karakter_Tespiti_Birlesik"

merge_yolo_datasets(DATASET_1_YOLU, DATASET_2_YOLU, HEDEF_YENI_KLASOR)