from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Body, Request
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import secrets
import shutil
import os
import re
import difflib

# Yerel Modüller (Yapay Zeka ve Veritabanı)
from ocr_processor import process_image
from database import SessionLocal, engine
import models
import crud

from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------
# 1. BAŞLANGIÇ AYARLARI VE VERİTABANI BAĞLANTISI
# ---------------------------------------------------------
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Akıllı Otopark ANPR Sistemi", version="1.0.0")

# Bu satırı app tanımlandıktan hemen sonra ekle:
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Web Arayüzü (HTML) Şablon Motoru Bağlantısı
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------
# 2. GÜVENLİK (ADMIN AUTH) AYARLARI
# ---------------------------------------------------------
security = HTTPBasic()


def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "Otopark2026!")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ---------------------------------------------------------
# 3. PYDANTIC VERİ ŞEMALARI (VALIDATION)
# ---------------------------------------------------------
class VehicleCreate(BaseModel):
    plate_number: str
    owner_name: str
    vehicle_type: str


class AdminVehicleCreate(BaseModel):
    plate_number: str
    owner_name: str
    vehicle_type: str
    is_subscriber: bool = True
    is_blacklisted: bool = False


class AdminVehicleUpdate(BaseModel):
    owner_name: Optional[str] = None
    vehicle_type: Optional[str] = None
    is_subscriber: Optional[bool] = None
    is_blacklisted: Optional[bool] = None


# ---------------------------------------------------------
# 4. WEB ARAYÜZÜ VE ANA KULLANICI İŞLEMLERİ
# ---------------------------------------------------------
@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/scan-plate/")
async def scan_plate(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ocr_result = process_image(file_path)

    if not ocr_result.get("success"):
        return {"filename": file.filename, "status": "Hata", "message": ocr_result.get("error")}

    clean_plate = re.sub(r'[^A-Z0-9]', '', ocr_result["plate_text"].upper())
    registered_vehicles = db.query(models.Vehicle).all()

    owner, v_type = "Bilinmeyen / Misafir", "Normal"
    best_match_plate = clean_plate
    highest_ratio = 0.0

    for db_vehicle in registered_vehicles:
        db_plate = db_vehicle.plate_number
        ratio = difflib.SequenceMatcher(None, clean_plate, db_plate).ratio()

        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match_plate = db_plate
            owner = getattr(db_vehicle, "owner_name", "Bilinmeyen")
            v_type = getattr(db_vehicle, "vehicle_type", "Normal")

        # %85 eşik değeri barajı geçilemezse misafir araç olarak sıfırla
        if highest_ratio >= 0.85:
            final_plate_to_log = best_match_plate
        else:
            final_plate_to_log = clean_plate
            owner = "Bilinmeyen / Misafir"
            v_type = "Normal"

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
        "esrgan_used": ocr_result.get("esrgan_used", False),  # <-- YENİ EKLENEN SATIR
        "vehicle_owner": owner,
        "vehicle_type": v_type,
        "match_ratio": round(highest_ratio, 2),
        "action_status": db_result["status"],
        "action_message": db_result["message"]
    }


@app.post("/add-vehicle/")
def add_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db)):
    clean_plate = re.sub(r'[^A-Z0-9]', '', vehicle.plate_number.upper())
    if db.query(models.Vehicle).filter(models.Vehicle.plate_number == clean_plate).first():
        raise HTTPException(status_code=400, detail="Hata: Plaka zaten kayıtlı!")

    new_vehicle = models.Vehicle(
        plate_number=clean_plate, owner_name=vehicle.owner_name,
        vehicle_type=vehicle.vehicle_type, is_subscriber=True
    )
    db.add(new_vehicle)
    db.commit()
    return {"message": f"{clean_plate} plakalı araç eklendi."}


@app.get("/vehicles/")
def get_all_vehicles(db: Session = Depends(get_db)):
    return {"registered_vehicles": db.query(models.Vehicle).all()}


# ---------------------------------------------------------
# 5. YÖNETİCİ (ADMIN) İŞLEMLERİ
# ---------------------------------------------------------
@app.post("/admin/vehicles/")
def admin_add_vehicle(vehicle: AdminVehicleCreate, db: Session = Depends(get_db),
                      admin: str = Depends(get_current_admin)):
    clean_plate = re.sub(r'[^A-Z0-9]', '', vehicle.plate_number.upper())
    if db.query(models.Vehicle).filter(models.Vehicle.plate_number == clean_plate).first():
        raise HTTPException(status_code=400, detail="Bu plaka zaten sistemde kayıtlı.")

    new_vehicle = models.Vehicle(
        plate_number=clean_plate, owner_name=vehicle.owner_name,
        vehicle_type=vehicle.vehicle_type, is_subscriber=vehicle.is_subscriber,
        is_blacklisted=vehicle.is_blacklisted
    )
    db.add(new_vehicle)
    db.commit()
    return {"message": f"{clean_plate} sisteme eklendi."}


@app.put("/admin/vehicles/{plate_number}")
def admin_update_vehicle(plate_number: str, update_data: AdminVehicleUpdate, db: Session = Depends(get_db),
                         admin: str = Depends(get_current_admin)):
    clean_plate = re.sub(r'[^A-Z0-9]', '', plate_number.upper())
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == clean_plate).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")

    if update_data.owner_name is not None: vehicle.owner_name = update_data.owner_name
    if update_data.vehicle_type is not None: vehicle.vehicle_type = update_data.vehicle_type
    if update_data.is_subscriber is not None: vehicle.is_subscriber = update_data.is_subscriber
    if update_data.is_blacklisted is not None: vehicle.is_blacklisted = update_data.is_blacklisted
    db.commit()
    return {"message": f"{clean_plate} bilgileri güncellendi."}


@app.delete("/admin/vehicles/{plate_number}")
def delete_vehicle(plate_number: str, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    clean_plate = re.sub(r'[^A-Z0-9]', '', plate_number.upper())  # Bug giderildi
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == clean_plate).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")

    db.delete(vehicle)
    db.commit()
    return {"message": f"{clean_plate} sistemden silindi."}


@app.put("/admin/pricing/")
def update_pricing(first_hour: float, hourly: float, daily_max: float, db: Session = Depends(get_db),
                   admin: str = Depends(get_current_admin)):
    pricing = db.query(models.Pricing).first()
    if not pricing:
        pricing = models.Pricing()
        db.add(pricing)

    pricing.first_hour_rate = first_hour
    pricing.hourly_rate = hourly
    pricing.daily_max = daily_max
    db.commit()
    return {"message": "Fiyat tarifesi güncellendi."}


@app.put("/admin/settings/api-key")
def update_api_key(new_token: str = Body(..., embed=True), admin: str = Depends(get_current_admin)):
    with open(".env", "r") as file: lines = file.readlines()
    with open(".env", "w") as file:
        for line in lines:
            file.write(f"PLATE_API_TOKEN={new_token}\n" if line.startswith("PLATE_API_TOKEN=") else line)
    return {"message": "API anahtarı güncellendi."}