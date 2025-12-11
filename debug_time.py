
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

# Configura la ruta correcta
sys.path.append(os.getcwd())

# Configuración base de datos
SQLALCHEMY_DATABASE_URL = "sqlite:///./prospectos.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print(f"Hora del Sistema (datetime.now): {datetime.now()}")
print(f"Hora UTC (datetime.utcnow): {datetime.utcnow()}")

# Obtener el último prospecto
ultimo = db.query(models.Prospecto).order_by(models.Prospecto.id.desc()).first()

if ultimo:
    print(f"Ultimo Prospecto ID: {ultimo.id}")
    print(f"Fecha Registro en DB: {ultimo.fecha_registro}")
    print(f"Nombre: {ultimo.nombre} {ultimo.apellido}")
else:
    print("No hay prospectos en la base de datos.")

db.close()
