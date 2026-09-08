from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import shutil
import os
import re
import difflib

# Yapay Zeka (OCR) ve Veritabanı Modülleri
from ocr_processor import process_image
from database import SessionLocal, engine
import models
import crud

# Tabloları oluştur (Eğer PostgreSQL'de yoksa yaratır)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Akıllı Otopark ANPR Sistemi")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Pydantic Modeli: Dışarıdan gelecek verinin şeması
# SQLAlchemy modeli ile çakışmaması için adını VehicleCreate yaptık
class VehicleCreate(BaseModel):
    plate_number: str
    owner_name: str
    vehicle_type: str


# Veritabanı Oturumu (Dependency)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "ANPR Otopark Sistemi Çalışıyor!"}


@app.post("/scan-plate/")
async def scan_plate(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Dosyayı kaydet
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. YOLO (RTX 3050) OCR ile plakayı oku
    ocr_result = process_image(file_path)

    if not ocr_result.get("success"):
        return {
            "filename": file.filename,
            "status": "Hata",
            "message": ocr_result.get("error")
        }

    # Görünmez karakterleri, boşlukları vs. tamamen yok et
    plate_text = ocr_result["plate_text"]
    clean_plate = re.sub(r'[^A-Z0-9]', '', plate_text.upper())

    # 3. ESNEK EŞLEŞTİRME (Fuzzy Matching)
    # PostgreSQL'den tüm araçları çek
    registered_vehicles = db.query(models.Vehicle).all()

    owner = "Bilinmeyen / Misafir"
    v_type = "Normal"
    best_match_plate = clean_plate
    highest_ratio = 0.0

    for db_vehicle in registered_vehicles:
        # SQLAlchemy objesinden verileri al
        db_plate = db_vehicle.plate_number

        # Eğer models.py içine owner_name eklemediysen hata vermemesi için getattr kullandık
        db_owner = getattr(db_vehicle, "owner_name", "Bilinmeyen")
        db_type = getattr(db_vehicle, "vehicle_type", "Normal")

        ratio = difflib.SequenceMatcher(None, clean_plate, db_plate).ratio()

        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match_plate = db_plate
            owner = db_owner
            v_type = db_type

    # %85 eşik değeri
    if highest_ratio >= 0.85:
        final_plate_to_log = best_match_plate
    else:
        owner = "Bilinmeyen / Misafir"
        v_type = "Normal"
        final_plate_to_log = clean_plate

    # 4. YENİ VERİTABANI İŞLEMİ (Giriş/Çıkış ve Spam Kontrolü)
    # crud.py içindeki akıllı fonksiyonumuzu çağırıyoruz
    db_result = crud.process_plate_detection(
        db=db,
        plate_text=final_plate_to_log,
        conf_score=str(round(ocr_result["confidence"], 2)),
        img_path=file_path
    )

    return {
        "filename": file.filename,
        "detected_plate": final_plate_to_log,
        "ai_raw_plate": clean_plate,
        "ai_confidence": round(ocr_result["confidence"], 2),
        "vehicle_owner": owner,
        "vehicle_type": v_type,
        "match_ratio": round(highest_ratio, 2),
        "action_status": db_result["status"],  # IN, OUT veya IGNORED
        "action_message": db_result["message"]
    }


@app.post("/add-vehicle/")
def add_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db)):
    clean_plate = re.sub(r'[^A-Z0-9]', '', vehicle.plate_number.upper())

    # Plaka zaten var mı kontrol et
    existing_vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == clean_plate).first()
    if existing_vehicle:
        raise HTTPException(status_code=400, detail=f"Hata: {clean_plate} plakası zaten sistemde kayıtlı!")

    # Yeni aracı SQLAlchemy objesi olarak oluştur
    new_vehicle = models.Vehicle(
        plate_number=clean_plate,
        owner_name=vehicle.owner_name,
        vehicle_type=vehicle.vehicle_type,
        is_subscriber=True
    )

    db.add(new_vehicle)
    db.commit()

    return {"message": f"{clean_plate} plakalı araç başarıyla standart formata çevrilip eklendi."}


@app.get("/vehicles/")
def get_all_vehicles(db: Session = Depends(get_db)):
    """Veritabanındaki tüm kayıtlı araçları listeler."""
    vehicles = db.query(models.Vehicle).all()
    return {"registered_vehicles": vehicles}