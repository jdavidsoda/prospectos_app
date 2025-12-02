from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class TipoUsuario(enum.Enum):
    ADMINISTRADOR = "administrador"
    SUPERVISOR = "supervisor"
    AGENTE = "agente"

class EstadoProspecto(enum.Enum):
    NUEVO = "nuevo"
    EN_SEGUIMIENTO = "en_seguimiento"
    COTIZADO = "cotizado"
    CERRADO_PERDIDO = "cerrado_perdido"
    GANADO = "ganado"

class MedioIngreso(Base):
    __tablename__ = "medios_ingreso"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)
    activo = Column(Integer, default=1)

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    tipo_usuario = Column(String(20), nullable=False, default=TipoUsuario.AGENTE.value)
    activo = Column(Integer, default=1)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

class Prospecto(Base):
    __tablename__ = "prospectos"
    
    id = Column(Integer, primary_key=True, index=True)
    # ✅ NUEVO: ID de cliente único
    id_cliente = Column(String(20), unique=True, nullable=True, index=True)
    nombre = Column(String(100), nullable=True)
    apellido = Column(String(100), nullable=True)
    correo_electronico = Column(String(100))
    telefono = Column(String(20))
    indicativo_telefono = Column(String(5), default="57")
    telefono_secundario = Column(String(20), nullable=True)
    indicativo_telefono_secundario = Column(String(5), default="57")
    ciudad_origen = Column(String(100))
    destino = Column(String(100))
    fecha_ida = Column(Date)
    fecha_vuelta = Column(Date)
    pasajeros_adultos = Column(Integer, default=1)
    pasajeros_ninos = Column(Integer, default=0)
    pasajeros_infantes = Column(Integer, default=0)
    medio_ingreso_id = Column(Integer, ForeignKey("medios_ingreso.id"))
    observaciones = Column(Text)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    agente_asignado_id = Column(Integer, ForeignKey("usuarios.id"))
    estado = Column(String(20), default=EstadoProspecto.NUEVO.value)
    # ✅ NUEVO: Clasificación de datos
    tiene_datos_completos = Column(Boolean, default=False)
    cliente_recurrente = Column(Boolean, default=False)
    prospecto_original_id = Column(Integer, ForeignKey("prospectos.id"), nullable=True)
    
    # Relaciones
    medio_ingreso = relationship("MedioIngreso")
    agente_asignado = relationship("Usuario")
    interacciones = relationship("Interaccion", back_populates="prospecto", order_by="desc(Interaccion.fecha_creacion)")
    documentos = relationship("Documento", back_populates="prospecto")
    
    # Relación recursiva
    prospectos_relacionados = relationship(
        "Prospecto",
        foreign_keys=[prospecto_original_id],
        remote_side=[id],
        backref="prospecto_original"
    )
    
    # ✅ MÉTODO: Generar ID de cliente único
    def generar_id_cliente(self):
        if not self.id_cliente:
            timestamp = datetime.now().strftime("%Y%m%d")
            self.id_cliente = f"CL-{timestamp}-{self.id:04d}"
        return self.id_cliente
    
    # ✅ MÉTODO: Determinar si tiene datos completos
    def verificar_datos_completos(self):
        """Verifica si el prospecto tiene datos completos (email, fechas o pasajeros)"""
        tiene_email = bool(self.correo_electronico and self.correo_electronico.strip())
        tiene_fechas = bool(self.fecha_ida)
        tiene_pasajeros = bool(self.pasajeros_adultos > 1 or self.pasajeros_ninos > 0 or self.pasajeros_infantes > 0)
        tiene_destino = bool(self.destino and self.destino.strip())
        tiene_origen = bool(self.ciudad_origen and self.ciudad_origen.strip())
        
        self.tiene_datos_completos = tiene_email or tiene_fechas or tiene_pasajeros or tiene_destino or tiene_origen
        return self.tiene_datos_completos
    
    def get_telefono_whatsapp(self, telefono_principal=True):
        """Obtiene el teléfono completo para WhatsApp"""
        if telefono_principal:
            indicativo = self.indicativo_telefono or "57"
            telefono = (self.telefono or "").replace(' ', '').replace('-', '')
            return f"{indicativo}{telefono}" if telefono else None
        else:
            if not self.telefono_secundario:
                return None
            indicativo = self.indicativo_telefono_secundario or "57"
            telefono = self.telefono_secundario.replace(' ', '').replace('-', '')
            return f"{indicativo}{telefono}"
    
    def get_whatsapp_link(self, telefono_principal=True):
        """Genera el enlace de WhatsApp"""
        telefono_completo = self.get_telefono_whatsapp(telefono_principal)
        if telefono_completo:
            return f"https://wa.me/{telefono_completo}"
        return "#"

class Interaccion(Base):
    __tablename__ = "interacciones"
    
    id = Column(Integer, primary_key=True, index=True)
    prospecto_id = Column(Integer, ForeignKey("prospectos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo_interaccion = Column(String(20))
    descripcion = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    estado_anterior = Column(String(20))
    estado_nuevo = Column(String(20))
    
    # Relaciones
    prospecto = relationship("Prospecto", back_populates="interacciones")
    usuario = relationship("Usuario")

class Documento(Base):
    __tablename__ = "documentos"
    
    id = Column(Integer, primary_key=True, index=True)
    # ✅ NUEVO: ID de documento único
    id_documento = Column(String(20), unique=True, nullable=True, index=True)
    prospecto_id = Column(Integer, ForeignKey("prospectos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    nombre_archivo = Column(String(255), nullable=False)
    tipo_documento = Column(String(20))
    ruta_archivo = Column(String(500), nullable=False)
    fecha_subida = Column(DateTime, default=datetime.utcnow)
    descripcion = Column(Text)
    
    # Relaciones
    prospecto = relationship("Prospecto", back_populates="documentos")
    usuario = relationship("Usuario")
    
    # ✅ MÉTODO: Generar ID de documento único
    def generar_id_documento(self):
        if not self.id_documento:
            timestamp = datetime.now().strftime("%Y%m%d")
            self.id_documento = f"DOC-{timestamp}-{self.id:04d}"
        return self.id_documento

class EstadisticaCotizacion(Base):
    __tablename__ = "estadisticas_cotizacion"
    
    id = Column(Integer, primary_key=True, index=True)
    # ✅ NUEVO: ID de cotización único
    id_cotizacion = Column(String(20), unique=True, nullable=True, index=True)
    agente_id = Column(Integer, ForeignKey("usuarios.id"))
    prospecto_id = Column(Integer, ForeignKey("prospectos.id"))
    fecha_cotizacion = Column(Date, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    agente = relationship("Usuario")
    prospecto = relationship("Prospecto")
    
    # ✅ MÉTODO: Generar ID de cotización único
    def generar_id_cotizacion(self):
        if not self.id_cotizacion:
            timestamp = datetime.now().strftime("%Y%m%d")
            self.id_cotizacion = f"COT-{timestamp}-{self.id:04d}"
        return self.id_cotizacion

class HistorialEstado(Base):
    __tablename__ = "historial_estados"
    
    id = Column(Integer, primary_key=True, index=True)
    prospecto_id = Column(Integer, ForeignKey("prospectos.id"))
    estado_anterior = Column(String(20))
    estado_nuevo = Column(String(20))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha_cambio = Column(DateTime, default=datetime.utcnow)
    comentario = Column(Text)
    
    # Relaciones
    prospecto = relationship("Prospecto")
    usuario = relationship("Usuario")
