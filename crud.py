from sqlalchemy.orm import Session
from models import Vehicle, ParkingLog
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def process_plate_detection(db: Session, plate_text: str, conf_score: str, img_path: str = None,
                            is_blacklisted: bool = False):
    now = datetime.now(ZoneInfo("Europe/Istanbul")).replace(tzinfo=None)
    cooldown_seconds = 10

    # 1. SPAM KONTROLÜ İÇİN: En son log ne olursa olsun (IN, OUT, REJECTED) kameranın önünde bekleme kontrolü yap
    last_any_log = db.query(ParkingLog).filter(ParkingLog.plate_number == plate_text).order_by(ParkingLog.id.desc()).first()

    if last_any_log:
        last_time = last_any_log.exit_time if last_any_log.exit_time else last_any_log.entry_time
        if last_time and last_time.tzinfo is not None:
            last_time = last_time.replace(tzinfo=None)

        time_since_last_action = now - last_time
        if time_since_last_action < timedelta(seconds=cooldown_seconds):
            return {"status": "IGNORED", "message": f"{plate_text} - Çok yakın zamanda okundu, es geçiliyor."}

    # 2. KARA LİSTE: İşlemi durdur ve REJECTED olarak kaydet
    if is_blacklisted:
        new_log = ParkingLog(
            plate_number=plate_text, entry_time=now, status="REJECTED",
            confidence_score=conf_score, image_path=img_path
        )
        db.add(new_log)
        db.commit()
        return {"status": "BLACKLISTED", "message": f"DİKKAT! {plate_text} Kara Listede. Bariyer Açılmadı!"}

    # 3. GERÇEK KONUM BULMA: Hatalı (REJECTED) denemeleri atlayıp aracın gerçekten içeride mi dışarıda mı olduğunu bul
    last_valid_log = db.query(ParkingLog).filter(
        ParkingLog.plate_number == plate_text,
        ParkingLog.status.in_(["IN", "OUT"])
    ).order_by(ParkingLog.id.desc()).first()

    # GİRİŞ MANTIĞI: Araç daha önce hiç geçerli giriş yapmamış veya en son başarılı hareketi ÇIKIŞ ise
    if not last_valid_log or last_valid_log.status == "OUT":
        new_log = ParkingLog(
            plate_number=plate_text, entry_time=now, status="IN",
            confidence_score=conf_score, image_path=img_path
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return {"status": "IN", "message": f"{plate_text} - Giriş Başarılı, Bariyer Açılıyor.", "data": new_log}

    # ÇIKIŞ MANTIĞI: Aracın en son başarılı hareketi GİRİŞ ise (Yani araç fiziki olarak içerideyken çıkıyorsa)
    elif last_valid_log.status == "IN":
        last_valid_log.exit_time = now
        last_valid_log.status = "OUT"
        last_valid_log.confidence_score = conf_score
        last_valid_log.image_path = img_path

        db.commit()
        db.refresh(last_valid_log)

        duration_minutes = (last_valid_log.exit_time - last_valid_log.entry_time).total_seconds() / 60
        return {"status": "OUT", "message": f"{plate_text} - Çıkış Başarılı. Süre: {duration_minutes:.1f} dakika.",
                "data": last_valid_log}