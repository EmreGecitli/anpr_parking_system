import shutil
from pathlib import Path


def merge_plate_datasets(dataset1_dir, dataset2_dir, output_dir):
    dataset1_path = Path(dataset1_dir)
    dataset2_path = Path(dataset2_dir)
    out_path = Path(output_dir)

    splits = ['train', 'valid', 'val', 'test']
    data_types = ['images', 'labels']

    print("Hedef plaka klasörleri oluşturuluyor...")
    for split in splits:
        for dtype in data_types:
            (out_path / split / dtype).mkdir(parents=True, exist_ok=True)

    def process_dataset(ds_path, prefix):
        print(f"\n[{prefix}] etiketli plaka veri seti taranıyor: {ds_path}")

        for split in splits:
            for dtype in data_types:
                opt1 = ds_path / split / dtype
                opt2 = ds_path / dtype / split

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

    process_dataset(dataset1_path, "p1")
    process_dataset(dataset2_path, "p2")
    print(f"\n✅ Mükemmel! Plaka veri setleri birleştirildi:\n{out_path.resolve()}")


# ==========================================
# AYARLAR
# ==========================================
DATASET_1_YOLU = "D:/Plaka_Tespiti_1"
DATASET_2_YOLU = "D:/Plaka_Tespiti_2"
HEDEF_YENI_KLASOR = "D:/Plaka_Tespiti_Birlesik"

merge_plate_datasets(DATASET_1_YOLU, DATASET_2_YOLU, HEDEF_YENI_KLASOR)