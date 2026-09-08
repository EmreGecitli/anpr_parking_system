import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# .env dosyasındaki değişkenleri sisteme yükle
load_dotenv()

# Şifreyi .env dosyasından güvenli bir şekilde çek
DB_PASSWORD = os.getenv("DB_PASSWORD", "varsayilan_sifre")
SQLALCHEMY_DATABASE_URL = f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/parking_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()