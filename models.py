from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

# Türkiye saatini döndüren yardımcı fonksiyon
def get_turkey_time():
    return datetime.now(ZoneInfo("Europe/Istanbul")).replace(tzinfo=None)

class Pricing(Base):
    __tablename__ = "pricing"
    id = Column(Integer, primary_key=True, index=True)
    first_hour_rate = Column(Float, default=50.0)
    hourly_rate = Column(Float, default=20.0)
    daily_max = Column(Float, default=300.0)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True)
    owner_name = Column(String, nullable=True)
    vehicle_type = Column(String, nullable=True)
    is_subscriber = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)

class ParkingLog(Base):
    __tablename__ = "parking_logs"
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, index=True)
    # server_default yerine Python tabanlı default parametresi kullanıyoruz
    entry_time = Column(DateTime, default=get_turkey_time)
    exit_time = Column(DateTime, nullable=True)
    status = Column(String, default="IN")
    confidence_score = Column(String, nullable=True)
    image_path = Column(String, nullable=True)