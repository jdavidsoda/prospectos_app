from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base
import os
from dotenv import load_dotenv

# Cargar variables de entorno (solo para local, en la nube las toma automáticamente)
load_dotenv()

# 1. Intentar usar DATABASE_URL primero (Render, Railway y Heroku usan esto por defecto)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Limpiar espacios en blanco o comillas accidentales
    DATABASE_URL = DATABASE_URL.strip().strip("'").strip('"')
    
    # SQLAlchemy 1.4+ requiere 'postgresql://' y algunas plataformas aún entregan 'postgres://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
else:
    # 2. Si no hay DATABASE_URL, arma la URL con las variables separadas (Desarrollo local)
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Producto24*")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "prospectos_crm")
    
    # Usaremos psycopg2 como driver por ser el más estándar para despliegues
    SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
