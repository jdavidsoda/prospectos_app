from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base
import os

# Configuración de la base de datos
SQLALCHEMY_DATABASE_URL = "sqlite:///./prospectos.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

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
    print("✅ Tablas creadas correctamente")

def reset_database():
    """Eliminar y recrear todas las tablas (solo para desarrollo)"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos reiniciada")

def migrate_database():
    """Migrar base de datos existente agregando nuevas columnas"""
    try:
        with engine.connect() as conn:
            print("🔄 Iniciando migración de base de datos...")
            
            # Verificar si existe la columna id_cliente en prospectos
            result = conn.execute(text("PRAGMA table_info(prospectos)"))
            columns = [row[1] for row in result]
            
            # Agregar columnas faltantes a prospectos
            if 'id_cliente' not in columns:
                print("  ➕ Agregando columna: id_cliente")
                conn.execute(text("ALTER TABLE prospectos ADD COLUMN id_cliente VARCHAR(20)"))
            
            if 'tiene_datos_completos' not in columns:
                print("  ➕ Agregando columna: tiene_datos_completos")
                conn.execute(text("ALTER TABLE prospectos ADD COLUMN tiene_datos_completos BOOLEAN DEFAULT 0"))
            
            # Verificar tabla estadisticas_cotizacion
            try:
                result = conn.execute(text("PRAGMA table_info(estadisticas_cotizacion)"))
                columns = [row[1] for row in result]
                
                if 'id_cotizacion' not in columns:
                    print("  ➕ Agregando columna: id_cotizacion")
                    conn.execute(text("ALTER TABLE estadisticas_cotizacion ADD COLUMN id_cotizacion VARCHAR(20)"))
            except Exception as e:
                print(f"  ⚠️ Tabla estadisticas_cotizacion no existe o tiene error: {e}")
            
            # Verificar tabla documentos
            try:
                result = conn.execute(text("PRAGMA table_info(documentos)"))
                columns = [row[1] for row in result]
                
                if 'id_documento' not in columns:
                    print("  ➕ Agregando columna: id_documento")
                    conn.execute(text("ALTER TABLE documentos ADD COLUMN id_documento VARCHAR(20)"))
            except Exception as e:
                print(f"  ⚠️ Tabla documentos no existe o tiene error: {e}")
            
            conn.commit()
            print("✅ Migración completada exitosamente")
            
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        raise

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
