from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base

class Vehicle(Base):
    """Sisteme kayıtlı veya daha önce giriş yapmış araçların listesi"""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True)  # Plaka numarası (Benzersiz)
    owner_name = Column(String, nullable=True)              # YENİ: Araç Sahibinin Adı
    vehicle_type = Column(String, nullable=True)            # YENİ: Araç Tipi (Binek, SUV vb.)
    is_subscriber = Column(Boolean, default=False)          # Abone mi?
    is_blacklisted = Column(Boolean, default=False)         # Kara listede mi?

class ParkingLog(Base):
    """Giriş-Çıkış hareketlerinin (loglarının) tutulduğu tablo"""
    __tablename__ = "parking_logs"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, index=True)               # Okunan plaka
    entry_time = Column(DateTime(timezone=True), server_default=func.now()) # Giriş Saati
    exit_time = Column(DateTime(timezone=True), nullable=True)              # Çıkış Saati
    status = Column(String, default="IN")                   # Durum: "IN" (İçeride) veya "OUT" (Çıktı)
    confidence_score = Column(String, nullable=True)        # Yapay zeka okuma skoru
    image_path = Column(String, nullable=True)              # Kanıt fotoğrafının dosya yolu