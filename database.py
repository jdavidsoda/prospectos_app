from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos PostgreSQL
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Producto24*")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "prospectos_crm")

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente")

def reset_database():
    """Eliminar y recrear todas las tablas (solo para desarrollo)"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos reiniciada")

def migrate_database():
    """Migrar base de datos - PostgreSQL maneja esto automáticamente con SQLAlchemy"""
    print("✅ PostgreSQL: Las migraciones se manejan con SQLAlchemy automáticamente")

def check_and_migrate():
    """Verificar y ejecutar migración si es necesario"""
    try:
        # Primero crear tablas si no existen
        create_tables()
        
        # Luego ejecutar migración
        migrate_database()
        return True
    except Exception as e:
        print(f"⚠️ Error en migración: {e}")
        return False
