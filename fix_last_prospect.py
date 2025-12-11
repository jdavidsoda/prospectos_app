
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

# Configurar path
sys.path.append(os.getcwd())

# DB Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./prospectos.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Obtener último prospecto
ultimo = db.query(models.Prospecto).order_by(models.Prospecto.id.desc()).first()

if ultimo and ultimo.fecha_registro.day == 11: # Verificar que es el del problema (día 11 UTC vs 10 Local)
    print(f"Corrigiendo fecha para Prospecto {ultimo.id} ({ultimo.nombre})")
    print(f"   Fecha Actual (UTC): {ultimo.fecha_registro}")
    
    # Restar 5 horas (ajuste manual para Colombia/Local)
    nueva_fecha = ultimo.fecha_registro - timedelta(hours=5)
    ultimo.fecha_registro = nueva_fecha
    
    db.commit()
    print(f"Fecha Corregida: {ultimo.fecha_registro}")
    print("   Ahora deberia aparecer en el Dashboard de 'Hoy' (10/12/2025).")
else:
    print("No se encontro el prospecto o ya tiene la fecha correcta.")
    if ultimo:
        print(f"   Fecha actual: {ultimo.fecha_registro}")

db.close()
