import cv2
import numpy as np
from ultralytics import YOLO
import os
import re
import torch
import requests  # API istekleri için eklendi
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# ==========================================
# API AYARLARI (PLATE RECOGNIZER)
# ==========================================
# Token artık kodun içinde değil, güvenli .env dosyasından geliyor
PLATE_RECOGNIZER_TOKEN = os.getenv("PLATE_API_TOKEN")

# ==========================================
# BASİCSR HATASI İÇİN YAMA (MONKEY PATCH)
# ==========================================
import torchvision.transforms.functional
import sys

sys.modules['torchvision.transforms.functional_tensor'] = torchvision.transforms.functional
# ==========================================

# Real-ESRGAN kütüphaneleri
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

# ==========================================
# 1. MODELLERİ YÜKLE
# ==========================================
PLATE_MODEL_PATH = "runs/detect/plate_detector_v1/weights/best.pt"
CHAR_MODEL_PATH = "runs/detect/character_reader_v1/weights/best.pt"

plate_detector = YOLO(PLATE_MODEL_PATH)
char_reader = YOLO(CHAR_MODEL_PATH)

# --- AĞIR SİKLET YAPAY ZEKA (REAL-ESRGAN) YÜKLEMESİ ---
try:
    print("[SİSTEM] Real-ESRGAN modeli belleğe yükleniyor...")
    esrgan_model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=4,
        model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
        model=esrgan_model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=True,
        gpu_id=0
    )
    print("[SİSTEM] Real-ESRGAN başarıyla yüklendi ve hazır!")
except Exception as e:
    print(f"[HATA] Real-ESRGAN Yükleme Hatası: {e}")
    upsampler = None


# ==========================================
# YARDIMCI FONKSİYON: BULUT API ÇAĞRISI
# ==========================================
def call_plate_recognizer_api(image_path):
    """Görüntüyü Plate Recognizer API'sine gönderip sonucu döndürür."""
    print("  [İŞLEM] Orijinal görüntü Plate Recognizer API'sine yükleniyor...")
    try:
        with open(image_path, 'rb') as fp:
            response = requests.post(
                'https://api.platerecognizer.com/v1/plate-reader/',
                data=dict(regions=['tr']),  # Sadece Türkiye plakaları için optimize et
                files=dict(upload=fp),
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_TOKEN}'}
            )

        res = response.json()

        if res.get('results') and len(res['results']) > 0:
            # API plakayı bulduysa ilk sonucu al (ham küçük harfleri büyüt)
            best_plate = res['results'][0]['plate'].upper()
            confidence = res['results'][0]['score']

            # API'den gelen plakayı temizle (Sadece harf ve rakamlar)
            clean_plate = re.sub(r'[^A-Z0-9]', '', best_plate)

            print(f"  [BAŞARI] API Okumayı Tamamladı: {clean_plate} (Skor: {confidence:.2f})")
            return {"success": True, "plate_text": clean_plate, "confidence": confidence}
        else:
            print("  [HATA] API bu görselde herhangi bir plaka bulamadı!")
            return {"success": False, "plate_text": "", "confidence": 0.0}

    except Exception as e:
        print(f"  [HATA] API Bağlantı Hatası: {e}")
        return {"success": False, "plate_text": "", "confidence": 0.0}


# ==========================================
# 2. MODÜLER OCR FONKSİYONU (YEREL)
# ==========================================
def extract_plate_text(cropped_plate_img, pass_num=1):
    """Verilen plaka kırpmasından metin ve güven skoru çıkaran yerel fonksiyon."""
    print(f"  [İŞLEM] Yerel OCR Okuma Süreci Başladı (Geçiş {pass_num})...")

    gray_plate = cv2.cvtColor(cropped_plate_img, cv2.COLOR_BGR2GRAY)
    dark_pixels = np.sum(gray_plate < 80)
    total_pixels = gray_plate.shape[0] * gray_plate.shape[1]
    dark_percentage = (dark_pixels / total_pixels) * 100

    if dark_percentage > 70:
        inverted = cv2.bitwise_not(gray_plate)
        final_plate_for_ocr = cv2.cvtColor(inverted, cv2.COLOR_GRAY2BGR)
        print(f"  [BİLGİ] Siyah plaka algılandı (Siyah Oranı: %{dark_percentage:.1f}). Renkler tersine çevrildi.")
    else:
        final_plate_for_ocr = cropped_plate_img
        print(f"  [BİLGİ] Normal plaka işleniyor (Siyah Oranı: %{dark_percentage:.1f}).")

    char_results = char_reader(final_plate_for_ocr, device=0, verbose=False, conf=0.15)
    detected_chars = []

    for char_box in char_results[0].boxes:
        cx1, cy1, cx2, cy2 = map(float, char_box.xyxy[0])
        class_id = int(char_box.cls[0])
        char_name = char_reader.names[class_id]
        conf = float(char_box.conf[0])
        detected_chars.append({"char": char_name, "x_pos": cx1, "y_pos": cy1, "height": cy2 - cy1, "conf": conf})

    if not detected_chars:
        print("  [UYARI] Model çerçeve içinde hiçbir harf/rakam bulamadı!")
        return {"success": False, "plate_text": "", "confidence": 0.0}

    print(f"  [BİLGİ] Toplam {len(detected_chars)} karakter tespit edildi. Satır sıralaması yapılıyor...")

    detected_chars.sort(key=lambda item: item["y_pos"])
    lines = []
    for char in detected_chars:
        placed = False
        for line in lines:
            if abs(char["y_pos"] - line[0]["y_pos"]) < (line[0]["height"] * 0.6):
                line.append(char)
                placed = True
                break
        if not placed:
            lines.append([char])

    plate_text = ""
    for line in lines:
        line.sort(key=lambda item: item["x_pos"])
        plate_text += "".join([item["char"] for item in line])

    print(f"  [İŞLEM] İlk okuma sonucu birleştirildi: {plate_text}")

    ph, pw = final_plate_for_ocr.shape[:2]
    aspect_ratio = pw / ph

    if plate_text and not re.match(r'^\d{2}[A-Z]', plate_text):
        print(f"  [UYARI] Türkiye plaka formatı ihlali ({plate_text}). Eksik kısım aranıyor...")

        if aspect_ratio < 2.0:
            target_part = final_plate_for_ocr[0:int(ph * 0.60), 0:int(pw * 0.45)]
        else:
            target_part = final_plate_for_ocr[0:int(ph * 0.65), 0:int(pw * 0.55)]

        zoomed_part = cv2.resize(target_part, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        zoomed_part = cv2.copyMakeBorder(zoomed_part, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        cv2.imwrite(os.path.join("static", "uploads", "debug_zoom.jpg"), zoomed_part)

        print("  [İŞLEM] Derin tarama modeli (düşük eşik ile) çalıştırılıyor...")
        deep_results = char_reader(zoomed_part, device=0, verbose=False, conf=0.05)
        missing_digits = []

        for d_box in deep_results[0].boxes:
            cls_id = int(d_box.cls[0])
            c_name = char_reader.names[cls_id]
            if c_name.isdigit():
                cx1 = float(d_box.xyxy[0][0])
                missing_digits.append({"char": c_name, "x_pos": cx1})

        if missing_digits:
            missing_digits.sort(key=lambda item: item["x_pos"])
            extracted_numbers = "".join([item["char"] for item in missing_digits])

            if len(extracted_numbers) >= 2:
                city_code = extracted_numbers[:2]
                clean_remainder = re.sub(r'^\d+', '', plate_text)
                plate_text = city_code + clean_remainder
                print(f"  [BAŞARI] Şehir kodu ({city_code}) başarıyla ana metne eklendi!")
            else:
                print(f"  [UYARI] Yeterli rakam bulunamadı.")
        else:
            print("  [HATA] Derin taramada hiçbir rakam bulunamadı!")

    avg_conf = sum(item["conf"] for item in detected_chars) / len(detected_chars)
    print(f"  [SONUÇ] Yerel Modül Çıkışı -> Plaka: {plate_text} | Skor: {avg_conf:.2f}")

    return {"success": True, "plate_text": plate_text, "confidence": avg_conf}


# ==========================================
# 3. ANA İŞLEM AKIŞI (ÜÇ KADEMELİ HİBRİT MİMARİ)
# ==========================================
def process_image(image_path):
    print("\n" + "=" * 60)
    print(f"[BAŞLANGIÇ] Yeni İstek Alındı: {image_path}")
    print("=" * 60)

    img = cv2.imread(image_path)
    if img is None:
        print("[HATA] Görüntü okunamadı, yol kontrol edilmeli.")
        return {"success": False, "error": "Resim okunamadı. Yol doğru mu?"}

    print("[İŞLEM] Plaka tespiti yapılıyor (YOLO)...")
    plate_results = plate_detector(img, device=0, verbose=False)

    if len(plate_results[0].boxes) == 0:
        print("[HATA] Bu resimde herhangi bir plaka kutusu tespit edilemedi.")
        return {"success": False, "error": "Bu resimde herhangi bir plaka tespit edilemedi."}

    box = plate_results[0].boxes[0]
    x1, y1, x2, y2 = map(int, box.xyxy[0])

    margin = 10
    h, w = img.shape[:2]
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)

    print(f"[BİLGİ] Plaka kırpıldı (Margin: {margin}) ve sisteme kaydedildi.")
    cropped_plate = img[y1:y2, x1:x2]
    cv2.imwrite(os.path.join("static", "uploads", "debug_crop_pass1.jpg"), cropped_plate)

    best_local_result = {"success": False, "plate_text": "", "confidence": 0.0}

    # ----------------------------------------------------
    # BİRİNCİ GEÇİŞ (PASS 1) - YEREL HIZLI TARAMA
    # ----------------------------------------------------
    print("\n--- [AŞAMA 1] Yerel Hızlı Tarama Başlatılıyor ---")
    result_pass1 = extract_plate_text(cropped_plate, pass_num=1)

    if result_pass1["success"]:
        best_local_result = result_pass1
        if result_pass1["confidence"] >= 0.85:
            print(f"\n[FİNAL] Skor mükemmel (>= 0.85). Sistem yorulmadan 1. aşamada tamamlandı.")
            return best_local_result

    # ----------------------------------------------------
    # İKİNCİ GEÇİŞ (PASS 2) - YEREL YAPAY ZEKA NETLEŞTİRME
    # ----------------------------------------------------
    if upsampler is not None:
        print(f"\n--- [AŞAMA 2] Skor düşük. Yerel Real-ESRGAN Başlatılıyor ---")
        try:
            print("[İŞLEM] Görüntü yapay zeka ile 2 kat büyütülüp netleştiriliyor...")
            upscaled_plate, _ = upsampler.enhance(cropped_plate, outscale=2)
            cv2.imwrite(os.path.join("static", "uploads", "debug_crop_pass2.jpg"), upscaled_plate)
            print("[BAŞARI] Görüntü netleştirildi. İkinci okuma yapılıyor...")

            result_pass2 = extract_plate_text(upscaled_plate, pass_num=2)

            if result_pass2["success"]:
                print("\n[İŞLEM] Yerel Skor Karşılaştırması Yapılıyor...")
                print(f"  -> 1. Geçiş Skoru: {result_pass1['confidence'] if result_pass1['success'] else 0.0:.2f}")
                print(f"  -> 2. Geçiş Skoru: {result_pass2['confidence']:.2f}")

                if result_pass2["confidence"] > best_local_result["confidence"]:
                    print("[BİLGİ] Real-ESRGAN skoru artırdı! En iyi yerel sonuç güncellendi.")
                    best_local_result = result_pass2
                else:
                    print("[BİLGİ] Netleştirme skoru artırmadı. İlk sonuç korundu.")
        except Exception as e:
            print(f"[HATA] Real-ESRGAN işleme sırasında hata: {e}")

    # ----------------------------------------------------
    # ÜÇÜNCÜ GEÇİŞ (PASS 3) - ÜCRETLİ BULUT API (SON ÇARE)
    # ----------------------------------------------------
    if best_local_result["confidence"] < 0.81:
        print(f"\n--- [AŞAMA 3] KRİTİK SEVİYE! En iyi yerel skor {best_local_result['confidence']:.2f} (0.81 altı) ---")
        print("[UYARI] Hatalı okumayı önlemek için Plate Recognizer Bulut API'si tetikleniyor...")

        # Orijinal görüntüyü (kırpılmamış olanı) API'ye yollamak başarı oranını artırır
        api_result = call_plate_recognizer_api(image_path)

        if api_result["success"]:
            print(f"\n[FİNAL] API, plaka sorununu çözdü. Bulut sonucu veritabanına gönderiliyor.")
            return api_result
        else:
            print(f"\n[FİNAL] API bile plakayı okuyamadı. Yerel en iyi tahmin veritabanına gönderiliyor.")
            return best_local_result

    else:
        print(
            f"\n[FİNAL] Yerel sistem skoru {best_local_result['confidence']:.2f} barajı geçti (>= 0.80). API çağrılmadan işlem tamamlandı.")
        return best_local_result