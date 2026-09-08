from database import engine, Base
# Tabloların Base objesine kaydedilmesi için models dosyasını import etmeliyiz
import models

print("PostgreSQL'e bağlanılıyor ve tablolar oluşturuluyor...")

# Modellerdeki (models.py) tablo yapılarını veritabanında fiziksel olarak yaratır
# (Eğer tablolar zaten varsa üzerine yazmaz, hata vermez)
Base.metadata.create_all(bind=engine)

print("İşlem tamam! Tablolar başarıyla oluşturuldu.")