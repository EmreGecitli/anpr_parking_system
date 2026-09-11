from sqlalchemy.orm import Session
from models import Vehicle, ParkingLog
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def process_plate_detection(db: Session, plate_text: str, conf_score: str, img_path: str = None):
    """
    Kameradan okunan plakayı veritabanında işler. Giriş/Çıkış kararını verir ve spam okumaları engeller.
    """
    now = datetime.now(ZoneInfo("Europe/Istanbul")).replace(tzinfo=None)
    cooldown_seconds = 10  # Aynı plaka 10 saniye içinde tekrar okunursa yok say

    # 1. Bu plakanın en son log kaydını bul (Giriş mi yapmış, çıkış mı?)
    last_log = db.query(ParkingLog).filter(ParkingLog.plate_number == plate_text).order_by(ParkingLog.id.desc()).first()

    # 2. SPAM KONTROLÜ: Araç yeni işlem yaptıysa ve hala kameranın önündeyse işlemi yoksay
    if last_log:
        last_time = last_log.exit_time if last_log.exit_time else last_log.entry_time

        # HATA ÇÖZÜMÜ: Eski kayıtlarda saat dilimi etiketi varsa, matematiksel işlemden önce temizle
        if last_time and last_time.tzinfo is not None:
            last_time = last_time.replace(tzinfo=None)

        time_since_last_action = now - last_time

        if time_since_last_action < timedelta(seconds=cooldown_seconds):
            return {"status": "IGNORED", "message": f"{plate_text} - Çok yakın zamanda okundu, es geçiliyor."}

    # 3. GİRİŞ (IN) veya ÇIKIŞ (OUT) MANTIĞI
    if not last_log or last_log.status == "OUT":
        # Araç hiç gelmemiş veya en son çıkış yapmış. Demek ki şu an GİRİŞ yapıyor.
        new_log = ParkingLog(
            plate_number=plate_text,
            entry_time=now,
            status="IN",
            confidence_score=conf_score,
            image_path=img_path
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return {"status": "IN", "message": f"{plate_text} - Giriş Başarılı, Bariyer Açılıyor.", "data": new_log}

    elif last_log.status == "IN":
        # Araç en son giriş yapmış ve içeride görünüyor. Demek ki şu an ÇIKIŞ yapıyor.
        last_log.exit_time = now
        last_log.status = "OUT"
        last_log.confidence_score = conf_score
        last_log.image_path = img_path  # Çıkış anındaki kanıt fotoğrafını da güncelleyebiliriz

        db.commit()
        db.refresh(last_log)

        # İçeride kalınan süreyi hesapla
        duration = last_log.exit_time - last_log.entry_time
        duration_minutes = duration.total_seconds() / 60

        return {"status": "OUT", "message": f"{plate_text} - Çıkış Başarılı. Süre: {duration_minutes:.1f} dakika.",
                "data": last_log}