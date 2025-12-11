# Imports estándar de Python
import os
import io
import shutil
import secrets
from datetime import datetime, date, timedelta
from typing import Optional
# Imports de librerías de terceros (pypi)
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd
# Imports de módulos locales de la aplicación
import models
import database
import auth
from models import TipoUsuario, EstadoProspecto
from sqlalchemy import func, or_, and_
from difflib import get_close_matches
import smtplib
from email.mime.text import MIMEText
import re




def enviar_notificacion_email(destinatario: str, asunto: str, cuerpo: str):
    """Envía una notificación por correo electrónico (Simulado por ahora)"""
    try:
        # En un entorno real, aquí se configurarían las credenciales SMTP
        # server = smtplib.SMTP('smtp.gmail.com', 587)
        # server.starttls()
        # server.login("tu_correo@gmail.com", "tu_password")
        # msg = MIMEText(cuerpo)
        # msg['Subject'] = asunto
        # msg['From'] = "sistema@prospectos.com"
        # msg['To'] = destinatario
        # server.send_message(msg)
        # server.quit()
        print(f"📧 [EMAIL SIMULADO] A: {destinatario} | Asunto: {asunto}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False

def parsear_fecha(fecha_str: str) -> Optional[date]:
    """Helper para parsear fechas en formatos DD/MM/YYYY o YYYY-MM-DD"""
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except ValueError:
        try:
            return datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"⚠️ Error parseando fecha: {fecha_str}")
            return None

app = FastAPI(title="Sistema de Prospectos")

# Configuración para upload de archivos
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory="templates")

# Almacenamiento simple de sesiones en memoria
active_sessions = {}

# Crear tablas al inicio
# Crear tablas al inicio
@app.on_event("startup")
def startup():
    # Para desarrollo: resetear base de datos si es necesario
    # database.reset_database()
    
    database.create_tables()
    db = next(database.get_db())
    try:
        # Crear medios de ingreso por defecto
        medios = ["REDES", "TEL TRAVEL", "RECOMPRA", "REFERIDO", "FIDELIZACION"]
        for medio in medios:
            if not db.query(models.MedioIngreso).filter(models.MedioIngreso.nombre == medio).first():
                db.add(models.MedioIngreso(nombre=medio))
        
        # Crear usuario administrador por defecto
        if not db.query(models.Usuario).filter(models.Usuario.username == "admin").first():
            admin_user = models.Usuario(
                username="admin",
                email="admin@empresa.com",
                hashed_password=auth.get_password_hash("admin123"),
                tipo_usuario=TipoUsuario.ADMINISTRADOR.value
            )
            db.add(admin_user)
        
        # Crear un agente de prueba
        if not db.query(models.Usuario).filter(models.Usuario.username == "agente1").first():
            agente_user = models.Usuario(
                username="agente1",
                email="agente1@empresa.com",
                hashed_password=auth.get_password_hash("agente123"),
                tipo_usuario=TipoUsuario.AGENTE.value
            )
            db.add(agente_user)
        
        db.commit()
        print("Datos iniciales creados correctamente")
        print("Usuario admin: admin / admin123")
        print("Usuario agente: agente1 / agente123")
        print("No se crearon prospectos de prueba. Puedes crearlos manualmente.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error inicializando datos: {e}")
    finally:
        db.close()




# Función simple para obtener usuario actual
async def get_current_user(request: Request, db: Session = Depends(database.get_db)):
    try:
        session_token = request.cookies.get("session_token")
        
        if not session_token:
            return None
        
        user_id = active_sessions.get(session_token)
        if not user_id:
            return None
        
        user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        return user
    except Exception as e:
        print(f"❌ Error in get_current_user: {e}")
        return None

# Verificar si usuario es admin
async def require_admin(user: models.Usuario = Depends(get_current_user)):
    if not user or user.tipo_usuario != TipoUsuario.ADMINISTRADOR.value:
        raise HTTPException(status_code=403, detail="No tiene permisos de administrador")
    return user

# Página de login
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(database.get_db)
):
    user = db.query(models.Usuario).filter(models.Usuario.username == username).first()
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Usuario no encontrado"
        })
    
    if not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Contraseña incorrecta"
        })
    
    session_token = secrets.token_urlsafe(32)
    active_sessions[session_token] = user.id
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=1800,
        path="/"
    )
    
    return response

# Logout
@app.get("/logout")
async def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


# Dashboard principal con filtros de fecha - VERSIÓN CORREGIDA
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    periodo: str = Query("mes"),  # dia, semana, mes, año, personalizado
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        # Determinar el rango de fechas según el periodo seleccionado
        fecha_inicio_obj, fecha_fin_obj = calcular_rango_fechas(periodo, fecha_inicio, fecha_fin)
        
        print(f"📊 Calculando estadísticas para periodo: {periodo}")
        print(f"📅 Rango: {fecha_inicio_obj} a {fecha_fin_obj}")
        
        # Convertir a datetime para consultas
        fecha_inicio_dt = datetime.combine(fecha_inicio_obj, datetime.min.time())
        fecha_fin_dt = datetime.combine(fecha_fin_obj, datetime.max.time())
        
        # Inicializar todas las variables
        total_prospectos = prospectos_con_datos = prospectos_sin_datos = 0
        clientes_sin_asignar = clientes_asignados = destinos_count = ventas_count = 0
        prospectos_nuevos = prospectos_seguimiento = prospectos_cotizados = prospectos_ganados = prospectos_perdidos = 0
        destinos_populares = []
        conversion_agentes = []
        
        # Estadísticas básicas
        if user.tipo_usuario in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]:
            print("👨‍💼 Usuario es Admin/Supervisor - mostrando estadísticas generales")
            
            # ✅ CORREGIDO: Total de prospectos en el periodo (NO filtrado por estado)
            total_prospectos = db.query(models.Prospecto).filter(
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📈 Total prospectos: {total_prospectos}")
            
            # ✅ NUEVO: Prospectos con datos completos
            prospectos_con_datos = db.query(models.Prospecto).filter(
                models.Prospecto.tiene_datos_completos == True,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📝 Prospectos con datos: {prospectos_con_datos}")
            
            # ✅ NUEVO: Prospectos sin datos (solo teléfono)
            prospectos_sin_datos = db.query(models.Prospecto).filter(
                models.Prospecto.tiene_datos_completos == False,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📱 Prospectos sin datos: {prospectos_sin_datos}")
            
            # Clientes nuevos sin asignar en el periodo
            clientes_sin_asignar = db.query(models.Prospecto).filter(
                models.Prospecto.estado == EstadoProspecto.NUEVO.value,
                models.Prospecto.agente_asignado_id == None,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"🆕 Clientes sin asignar: {clientes_sin_asignar}")
            
            # Clientes asignados en el periodo (cualquier estado)
            clientes_asignados = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id != None,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📅 Clientes asignados: {clientes_asignados}")
            
            # Destinos registrados en el periodo
            destinos_query = db.query(models.Prospecto.destino).filter(
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt,
                models.Prospecto.destino.isnot(None),
                models.Prospecto.destino != ''
            ).distinct().all()
            destinos_count = len(destinos_query)
            print(f"🌍 Destinos registrados: {destinos_count}")
            
            # Ventas registradas en el periodo
            ventas_count = db.query(models.Prospecto).filter(
                models.Prospecto.estado == EstadoProspecto.GANADO.value,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"💰 Ventas: {ventas_count}")
            
            # Destinos más solicitados en el periodo
            destinos_populares = db.query(
                models.Prospecto.destino,
                func.count(models.Prospecto.id).label('count')
            ).filter(
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt,
                models.Prospecto.destino.isnot(None),
                models.Prospecto.destino != ''
            ).group_by(models.Prospecto.destino).order_by(func.count(models.Prospecto.id).desc()).limit(5).all()
            print(f"🏆 Destinos populares: {len(destinos_populares)}")
            
            # Estadísticas por estado en el periodo
            prospectos_nuevos = db.query(models.Prospecto).filter(
                models.Prospecto.estado == EstadoProspecto.NUEVO.value,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            prospectos_seguimiento = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.estado_nuevo == EstadoProspecto.EN_SEGUIMIENTO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            prospectos_cotizados = db.query(models.EstadisticaCotizacion).filter(
                models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_obj,
                models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_obj
            ).count()
            
            prospectos_ganados = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.estado_nuevo == EstadoProspecto.GANADO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            prospectos_perdidos = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.estado_nuevo == EstadoProspecto.CERRADO_PERDIDO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            print(f"📊 Estados - Nuevos: {prospectos_nuevos}, Seguimiento: {prospectos_seguimiento}, Cotizados: {prospectos_cotizados}, Ganados: {prospectos_ganados}, Perdidos: {prospectos_perdidos}")
            
            # Conversión por agente en el periodo
            conversion_agentes = []
            agentes_con_prospectos = db.query(
                models.Usuario.id,
                models.Usuario.username
            ).filter(
                models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
            ).all()
            
            for agente in agentes_con_prospectos:
                total_agente = db.query(models.Prospecto).filter(
                    models.Prospecto.agente_asignado_id == agente.id,
                    models.Prospecto.fecha_registro >= fecha_inicio_dt,
                    models.Prospecto.fecha_registro <= fecha_fin_dt
                ).count()
                
                ganados_agente = db.query(models.HistorialEstado).filter(
                    models.HistorialEstado.usuario_id == agente.id,
                    models.HistorialEstado.estado_nuevo == EstadoProspecto.GANADO.value,
                    models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                    models.HistorialEstado.fecha_cambio <= fecha_fin_dt
                ).count()
                
                cotizados_agente = db.query(models.EstadisticaCotizacion).filter(
                    models.EstadisticaCotizacion.agente_id == agente.id,
                    models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_obj,
                    models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_obj
                ).count()

                conversion_agentes.append({
                    'id': agente.id,
                    'username': agente.username,
                    'total_prospectos': total_agente,
                    'cotizados': cotizados_agente,
                    'ganados': ganados_agente
                })
            
            print(f"👥 Conversión agentes: {len(conversion_agentes)} agentes")
            
        else:
            print("👤 Usuario es Agente - mostrando estadísticas personales")
            
            # Estadísticas para agente (solo sus datos) en el periodo
            total_prospectos = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📈 Total prospectos agente: {total_prospectos}")
            
            # ✅ AGREGADO: Prospectos con datos completos para agente
            prospectos_con_datos = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.tiene_datos_completos == True,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📝 Prospectos con datos agente: {prospectos_con_datos}")
            
            # ✅ AGREGADO: Prospectos sin datos para agente
            prospectos_sin_datos = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.tiene_datos_completos == False,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📱 Prospectos sin datos agente: {prospectos_sin_datos}")
            
            # Clientes asignados al agente en el periodo
            clientes_asignados = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            print(f"📅 Clientes asignados agente: {clientes_asignados}")
            
            # Destinos registrados por el agente en el periodo
            destinos_query = db.query(models.Prospecto.destino).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt,
                models.Prospecto.destino.isnot(None),
                models.Prospecto.destino != ''
            ).distinct().all()
            destinos_count = len(destinos_query)
            print(f"🌍 Destinos registrados agente: {destinos_count}")
            
            # Ventas del agente en el periodo
            # Ventas del agente en el periodo (Basado en historial de cambios)
            ventas_count = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.usuario_id == user.id,
                models.HistorialEstado.estado_nuevo == EstadoProspecto.GANADO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            print(f"💰 Ventas agente: {ventas_count}")
            
            # Destinos más solicitados por el agente en el periodo
            destinos_populares = db.query(
                models.Prospecto.destino,
                func.count(models.Prospecto.id).label('count')
            ).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt,
                models.Prospecto.destino.isnot(None),
                models.Prospecto.destino != ''
            ).group_by(models.Prospecto.destino).order_by(func.count(models.Prospecto.id).desc()).limit(5).all()
            print(f"🏆 Destinos populares agente: {len(destinos_populares)}")
            
            # Para agente, no mostrar estos datos generales
            clientes_sin_asignar = 0
            
            # Estadísticas por estado para agente en el periodo
            prospectos_nuevos = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id,
                models.Prospecto.estado == EstadoProspecto.NUEVO.value,
                models.Prospecto.fecha_registro >= fecha_inicio_dt,
                models.Prospecto.fecha_registro <= fecha_fin_dt
            ).count()
            prospectos_seguimiento = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.usuario_id == user.id,
                models.HistorialEstado.estado_nuevo == EstadoProspecto.EN_SEGUIMIENTO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            # Nota: Cotizados ya usa EstadisticaCotizacion (correcto)
            prospectos_cotizados = db.query(models.EstadisticaCotizacion).filter(
                models.EstadisticaCotizacion.agente_id == user.id,
                models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_obj,
                models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_obj
            ).count()
            
            prospectos_ganados = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.usuario_id == user.id,
                models.HistorialEstado.estado_nuevo == EstadoProspecto.GANADO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            prospectos_perdidos = db.query(models.HistorialEstado).filter(
                models.HistorialEstado.usuario_id == user.id,
                models.HistorialEstado.estado_nuevo == EstadoProspecto.CERRADO_PERDIDO.value,
                models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
                models.HistorialEstado.fecha_cambio <= fecha_fin_dt
            ).count()
            
            print(f"📊 Estados agente - Nuevos: {prospectos_nuevos}, Seguimiento: {prospectos_seguimiento}, Cotizados: {prospectos_cotizados}, Ganados: {prospectos_ganados}, Perdidos: {prospectos_perdidos}")
            
            conversion_agentes = []
        
    except Exception as e:
        print(f"❌ Error grave calculando estadísticas: {e}")
        import traceback
        traceback.print_exc()
        # Inicializar todas las variables con valores por defecto
        total_prospectos = prospectos_con_datos = prospectos_sin_datos = 0
        clientes_sin_asignar = clientes_asignados = destinos_count = ventas_count = 0
        prospectos_nuevos = prospectos_seguimiento = prospectos_cotizados = prospectos_ganados = prospectos_perdidos = 0
        destinos_populares = []
        conversion_agentes = []
        fecha_inicio_obj = date.today()
        fecha_fin_obj = date.today()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": user,
        "today": date.today().strftime("%d/%m/%Y"),
        
        # Filtros activos
        "periodo_activo": periodo,
        "fecha_inicio_activa": fecha_inicio,
        "fecha_fin_activa": fecha_fin,
        "fecha_inicio_formateada": fecha_inicio_obj.strftime("%d/%m/%Y") if fecha_inicio_obj else "",
        "fecha_fin_formateada": fecha_fin_obj.strftime("%d/%m/%Y") if fecha_fin_obj else "",
        
        # Estadísticas principales
        "total_prospectos": total_prospectos,
        "prospectos_con_datos": prospectos_con_datos,
        "prospectos_sin_datos": prospectos_sin_datos,
        "clientes_sin_asignar": clientes_sin_asignar,
        "clientes_asignados": clientes_asignados,
        "destinos_count": destinos_count,
        "ventas_count": ventas_count,
        
        # Estadísticas por estado
        "prospectos_nuevos": prospectos_nuevos,
        "prospectos_seguimiento": prospectos_seguimiento,
        "prospectos_cotizados": prospectos_cotizados,
        "prospectos_ganados": prospectos_ganados,
        "prospectos_perdidos": prospectos_perdidos,
        
        # Datos para gráficos
        "destinos_populares": destinos_populares,
        "conversion_agentes": conversion_agentes
    })

def calcular_rango_fechas(periodo: str, fecha_inicio: str = None, fecha_fin: str = None):
    """Calcula el rango de fechas según el periodo seleccionado"""
    hoy = date.today()
    
    fecha_inicio_obj = hoy
    fecha_fin_obj = hoy

    if periodo == "personalizado" and fecha_inicio and fecha_fin:
        # Usar fechas personalizadas
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, "%d/%m/%Y").date()
            fecha_fin_obj = datetime.strptime(fecha_fin, "%d/%m/%Y").date()
        except ValueError:
            # Si hay error en el formato, usar mes actual por defecto
            print("⚠️ Error en formato de fecha personalizada, usando mes actual")
            pass
    
    elif periodo == "dia":
        # Hoy
        fecha_inicio_obj = hoy
        fecha_fin_obj = hoy
    elif periodo == "semana":
        # Esta semana (lunes a domingo)
        fecha_inicio_obj = hoy - timedelta(days=hoy.weekday())
        fecha_fin_obj = fecha_inicio_obj + timedelta(days=6)
    elif periodo == "año":
        # Este año
        fecha_inicio_obj = date(hoy.year, 1, 1)
        fecha_fin_obj = date(hoy.year, 12, 31)
    else:
        # Mes actual (por defecto)
        fecha_inicio_obj = date(hoy.year, hoy.month, 1)
        if hoy.month == 12:
            fecha_fin_obj = date(hoy.year + 1, 1, 1) - timedelta(days=1)
        else:
            fecha_fin_obj = date(hoy.year, hoy.month + 1, 1) - timedelta(days=1)
    
    # Convertir a datetime con horas inicio/fin del día
    fecha_inicio_dt = datetime.combine(fecha_inicio_obj, datetime.min.time())
    fecha_fin_dt = datetime.combine(fecha_fin_obj, datetime.max.time())
    
    return fecha_inicio_dt, fecha_fin_dt




# ========== GESTIÓN DE PROSPECTOS (ACTUALIZADO) ==========

@app.get("/prospectos", response_class=HTMLResponse)
async def listar_prospectos(
    request: Request,
    destino: str = Query(None),
    telefono: str = Query(None),
    medio_ingreso_id: str = Query(None),
    agente_asignado_id: str = Query(None),
    estado: str = Query(None),
    busqueda_global: str = Query(None),
    page: int = Query(1, ge=1),  # ✅ Paginación: Página actual
    limit: int = Query(10, ge=1, le=100),  # ✅ Paginación: Registros por página
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    # ✅ CONSTRUIR QUERY BASE SEGÚN ROL (SIN FILTRO DE ESTADO INICIAL)
    if user.tipo_usuario == TipoUsuario.AGENTE.value:
        query = db.query(models.Prospecto).filter(
            models.Prospecto.agente_asignado_id == user.id
        )
    else:
        query = db.query(models.Prospecto)
    
    # ✅ LÓGICA DE FILTROS POR DEFECTO Y EXPLÍCITOS
    filtros_aplicados = False

    if estado:
        filtros_aplicados = True
        if estado == "todos":
            pass
        else:
            query = query.filter(models.Prospecto.estado == estado)
    
    if agente_asignado_id:
        filtros_aplicados = True
        if agente_asignado_id == "todos":
            pass
        elif agente_asignado_id == "sin_asignar":
            query = query.filter(models.Prospecto.agente_asignado_id == None)
        else:
            query = query.filter(models.Prospecto.agente_asignado_id == int(agente_asignado_id))

    # ✅ APLICAR VALORES POR DEFECTO SI NO HAY ELEMENTOS DE FILTRO ESPECÍFICOS EN LA URL
    # Se considera "filtro activo" si el usuario envió algún parámetro en la URL
    # Pero para simplificar, si 'estado' y 'agente_asignado_id' son None, aplicamos defaults
    
    if estado is None and agente_asignado_id is None:
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            # Agente: Nuevo, Seguimiento, Cotizado
            query = query.filter(models.Prospecto.estado.in_([
                EstadoProspecto.NUEVO.value,
                EstadoProspecto.EN_SEGUIMIENTO.value,
                EstadoProspecto.COTIZADO.value
            ]))
        else:
            # Admin/Supervisor: Nuevo Y Sin Asignar
            query = query.filter(models.Prospecto.estado == EstadoProspecto.NUEVO.value)
            query = query.filter(models.Prospecto.agente_asignado_id == None)
            
            # Ajustar valores para que se reflejen en la vista
            estado = EstadoProspecto.NUEVO.value
            agente_asignado_id = "sin_asignar"

    # ✅ FILTRO DE BÚSQUEDA GLOBAL
    if busqueda_global:
        search_term = f"%{busqueda_global}%"
        query = query.filter(
            or_(
                models.Prospecto.nombre.ilike(search_term),
                models.Prospecto.apellido.ilike(search_term),
                models.Prospecto.telefono.ilike(search_term),
                models.Prospecto.telefono_secundario.ilike(search_term),
                models.Prospecto.correo_electronico.ilike(search_term),
                models.Prospecto.destino.ilike(search_term),
                models.Prospecto.ciudad_origen.ilike(search_term),
                models.Prospecto.observaciones.ilike(search_term)
            )
        )
        print(f"🔍 Aplicando búsqueda global: {busqueda_global}")
    
    # ✅ FILTRO POR TELÉFONO
    if telefono:
        telefono_term = f"%{telefono}%"
        query = query.filter(
            or_(
                models.Prospecto.telefono.ilike(telefono_term),
                models.Prospecto.telefono_secundario.ilike(telefono_term)
            )
        )
    
    # Otros filtros
    if destino:
        query = query.filter(models.Prospecto.destino.ilike(f"%{destino}%"))
    
    if medio_ingreso_id and medio_ingreso_id != "todos":
        query = query.filter(models.Prospecto.medio_ingreso_id == int(medio_ingreso_id))
    
    # ✅ ORDENAMIENTO: Del más nuevo al más antiguo
    # Se ordena después de todos los filtros y antes de la paginación
    query = query.order_by(models.Prospecto.fecha_registro.desc())
    
    # ✅ PAGINACIÓN
    total_registros = query.count()
    total_pages = (total_registros + limit - 1) // limit
    
    # Asegurar que la página solicitada sea válida
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    offset = (page - 1) * limit
    prospectos = query.offset(offset).limit(limit).all()
    
    # Obtener datos para filtros
    agentes = db.query(models.Usuario).filter(
        models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
    ).all()
    
    medios_ingreso = db.query(models.MedioIngreso).all()
    
    return templates.TemplateResponse("prospectos.html", {
        "request": request,
        "prospectos": prospectos,
        "current_user": user,
        "agentes": agentes,
        "medios_ingreso": medios_ingreso,
        "estados_prospecto": [estado.value for estado in EstadoProspecto],
        "filtros_activos": {
            "destino": destino,
            "telefono": telefono,
            "medio_ingreso_id": medio_ingreso_id,
            "agente_asignado_id": agente_asignado_id,
            "estado": estado,
            "busqueda_global": busqueda_global
        },
        # Info Paginación
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "total_registros": total_registros
    })

@app.post("/prospectos")
async def crear_prospecto(
    request: Request,
    telefono: str = Form(...),
    indicativo_telefono: str = Form("57"),
    medio_ingreso_id: int = Form(...),
    nombre: str = Form(None),
    apellido: str = Form(None),
    correo_electronico: str = Form(None),
    ciudad_origen: str = Form(None),
    destino: str = Form(None),
    fecha_ida: str = Form(None),
    fecha_vuelta: str = Form(None),
    pasajeros_adultos: int = Form(1),
    pasajeros_ninos: int = Form(0),
    pasajeros_infantes: int = Form(0),
    observaciones: str = Form(None),
    telefono_secundario: str = Form(None),
    indicativo_telefono_secundario: str = Form("57"),
    forzar_nuevo: bool = Form(False),
    agente_asignado_id: int = Form(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        # ✅ VALIDACIÓN DE INDICATIVOS
        if not indicativo_telefono.isdigit() or len(indicativo_telefono) > 4:
            return RedirectResponse(url="/prospectos?error=Indicativo principal inválido. Solo números, máximo 4 dígitos", status_code=303)
        
        if indicativo_telefono_secundario and (not indicativo_telefono_secundario.isdigit() or len(indicativo_telefono_secundario) > 4):
            return RedirectResponse(url="/prospectos?error=Indicativo secundario inválido. Solo números, máximo 4 dígitos", status_code=303)

        # ✅ DETECCIÓN MEJORADA: OBTENER TODOS LOS REGISTROS DEL CLIENTE
        # Buscar por teléfono principal
        clientes_existentes_principal = db.query(models.Prospecto).filter(
            or_(
                models.Prospecto.telefono == telefono,
                models.Prospecto.telefono_secundario == telefono
            )
        ).all()

        # Buscar por teléfono secundario (si existe)
        clientes_existentes_secundario = []
        if telefono_secundario:
            clientes_existentes_secundario = db.query(models.Prospecto).filter(
                or_(
                    models.Prospecto.telefono == telefono_secundario,
                    models.Prospecto.telefono_secundario == telefono_secundario
                )
            ).all()

        # Combinar resultados únicos
        clientes_existentes_set = set()
        todos_clientes_existentes = []

        # Agregar de principal
        for cliente in clientes_existentes_principal:
            if cliente.id not in clientes_existentes_set:
                clientes_existentes_set.add(cliente.id)
                todos_clientes_existentes.append(cliente)

        # Agregar de secundario
        for cliente in clientes_existentes_secundario:
            if cliente.id not in clientes_existentes_set:
                clientes_existentes_set.add(cliente.id)
                todos_clientes_existentes.append(cliente)

        # ✅ ORDENAR POR fecha_registro (nombre correcto en tu modelo)
        todos_clientes_existentes.sort(key=lambda x: x.fecha_registro, reverse=True)

        # Usar el más reciente como "cliente principal" para compatibilidad
        cliente_existente_principal = todos_clientes_existentes[0] if todos_clientes_existentes else None
        
        if todos_clientes_existentes and not forzar_nuevo:
            # Obtener datos de TODOS los registros del cliente
            todos_ids = [c.id for c in todos_clientes_existentes]
            
            interacciones_previas = db.query(models.Interaccion).filter(
                models.Interaccion.prospecto_id.in_(todos_ids)
            ).count()
            
            documentos_previos = db.query(models.Documento).filter(
                models.Documento.prospecto_id.in_(todos_ids)
            ).count()
            
            # Obtener últimas interacciones de TODOS los registros
            ultimas_interacciones = db.query(models.Interaccion).filter(
                models.Interaccion.prospecto_id.in_(todos_ids)
            ).order_by(models.Interaccion.fecha_creacion.desc()).limit(5).all()
            
            # Preparar datos para el template
            nuevos_datos = {
                "telefono": telefono,
                "indicativo_telefono": indicativo_telefono,
                "nombre": nombre,
                "apellido": apellido,
                "correo_electronico": correo_electronico,
                "ciudad_origen": ciudad_origen,
                "destino": destino,
                "fecha_ida": fecha_ida,
                "fecha_vuelta": fecha_vuelta,
                "pasajeros_adultos": pasajeros_adultos,
                "pasajeros_ninos": pasajeros_ninos,
                "pasajeros_infantes": pasajeros_infantes,
                "medio_ingreso_id": medio_ingreso_id,
                "telefono_secundario": telefono_secundario,
                "indicativo_telefono_secundario": indicativo_telefono_secundario,
                "observaciones": observaciones
            }
            
            # ✅ AGREGAR: Obtener lista de agentes para el select
            agentes = db.query(models.Usuario).filter(
                models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
            ).all()
            
            # Renderizar template de confirmación
            return templates.TemplateResponse("confirmar_cliente_existente.html", {
                "request": request,
                "cliente_existente_principal": cliente_existente_principal,
                "registros_previos": todos_clientes_existentes,
                "interacciones_previas": interacciones_previas,
                "documentos_previos": documentos_previos,
                "ultimas_interacciones": ultimas_interacciones,
                "nuevos_datos": nuevos_datos,
                "agentes": agentes  # ✅ Variable que faltaba
            })
        
        # ✅ DETERMINAR AGENTE ASIGNADO
        # 1. Si se especificó en el formulario, usar ese
        # 2. Si el usuario es agente, asignarse a sí mismo
        # 3. Si es admin/supervisor y no especificó, dejar sin asignar
        agente_final_id = None
        if agente_asignado_id and agente_asignado_id != 0:
            # Verificar que el agente exista
            agente = db.query(models.Usuario).filter(
                models.Usuario.id == agente_asignado_id,
                models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
            ).first()
            if agente:
                agente_final_id = agente_asignado_id
        elif user.tipo_usuario == TipoUsuario.AGENTE.value:
            agente_final_id = user.id

        # ✅ DETERMINAR DATOS PARA EL NUEVO REGISTRO
        # Prioridad: 1) Datos del formulario, 2) Datos del cliente más reciente, 3) Ninguno
        nombre_final = nombre
        apellido_final = apellido
        email_final = correo_electronico

        # Si no se proporcionaron en el formulario, intentar usar del cliente más reciente
        if not nombre_final and todos_clientes_existentes:
            for cliente in todos_clientes_existentes:
                if cliente.nombre:
                    nombre_final = cliente.nombre
                    break

        if not apellido_final and todos_clientes_existentes:
            for cliente in todos_clientes_existentes:
                if cliente.apellido:
                    apellido_final = cliente.apellido
                    break

        if not email_final and todos_clientes_existentes:
            for cliente in todos_clientes_existentes:
                if cliente.correo_electronico:
                    email_final = cliente.correo_electronico
                    break

        # ✅ CREAR NUEVO PROSPECTO CON INDICATIVOS Y DATOS MEJORADOS
        fecha_ida_date = parsear_fecha(fecha_ida)
        fecha_vuelta_date = parsear_fecha(fecha_vuelta)
        
        # Determinar si es cliente recurrente
        cliente_recurrente = len(todos_clientes_existentes) > 0

        prospecto = models.Prospecto(
            nombre=nombre_final,  # ✅ Usar nombre mejorado
            apellido=apellido_final,  # ✅ Usar apellido mejorado
            correo_electronico=email_final,  # ✅ Usar email mejorado
            telefono=telefono,
            indicativo_telefono=indicativo_telefono,
            telefono_secundario=telefono_secundario,
            indicativo_telefono_secundario=indicativo_telefono_secundario,
            ciudad_origen=ciudad_origen,
            destino=destino,
            fecha_ida=fecha_ida_date,
            fecha_vuelta=fecha_vuelta_date,
            pasajeros_adultos=pasajeros_adultos,
            pasajeros_ninos=pasajeros_ninos,
            pasajeros_infantes=pasajeros_infantes,
            medio_ingreso_id=medio_ingreso_id,
            observaciones=observaciones,
            agente_asignado_id=agente_final_id,  # ✅ USAR AGENTE DETERMINADO
            cliente_recurrente=cliente_recurrente,
            prospecto_original_id=todos_clientes_existentes[0].id if todos_clientes_existentes else None
        )
        
        # ✅ VERIFICAR Y ASIGNAR DATOS COMPLETOS
        prospecto.verificar_datos_completos()
        
        db.add(prospecto)
        db.flush()  # Para obtener el ID antes del commit
        
        # ✅ GENERAR ID DE CLIENTE ÚNICO
        prospecto.generar_id_cliente()
        
        db.commit()
        
        # Registrar interacción automática si es recurrente
        if cliente_recurrente:
            interaccion = models.Interaccion(
                prospecto_id=prospecto.id,
                usuario_id=user.id,
                tipo_interaccion="sistema",
                descripcion=f"Cliente recurrente registrado. Teléfono: {telefono}. Registros previos: {len(todos_clientes_existentes)}",
                estado_anterior=cliente_existente_principal.estado if cliente_existente_principal else None,
                estado_nuevo=EstadoProspecto.NUEVO.value
            )
            db.add(interaccion)
            db.commit()
        
        mensaje = "Prospecto creado correctamente" + (" (Cliente recurrente)" if cliente_recurrente else "")
        return RedirectResponse(url=f"/prospectos?success={mensaje}", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating prospect: {e}")
        return RedirectResponse(url="/prospectos?error=Error al crear prospecto", status_code=303)



@app.get("/prospectos/{prospecto_id}/editar")
async def mostrar_editar_prospecto(
    request: Request,
    prospecto_id: int,
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    # Buscar prospecto
    prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
    if not prospecto:
        return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
    
    # Verificar permisos: Agentes solo pueden editar sus propios prospectos
    if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
        prospecto.agente_asignado_id != user.id):
        return RedirectResponse(url="/prospectos?error=No tiene permisos para editar este prospecto", status_code=303)
    
    # Obtener medios de ingreso para el dropdown
    medios_ingreso = db.query(models.MedioIngreso).all()
    
    return templates.TemplateResponse("editar_prospecto.html", {
        "request": request,
        "prospecto": prospecto,
        "medios_ingreso": medios_ingreso,
        "user": user
    })


@app.post("/prospectos/{prospecto_id}/editar")
async def editar_prospecto(
    request: Request,
    prospecto_id: int,
    telefono: str = Form(...),
    indicativo_telefono: str = Form("57"),  # ✅ CORREGIDO: "57" sin +
    medio_ingreso_id: int = Form(...),
    nombre: str = Form(None),
    apellido: str = Form(None),
    correo_electronico: str = Form(None),
    ciudad_origen: str = Form(None),
    destino: str = Form(None),
    fecha_ida: str = Form(None),
    fecha_vuelta: str = Form(None),
    pasajeros_adultos: int = Form(1),
    pasajeros_ninos: int = Form(0),
    pasajeros_infantes: int = Form(0),
    observaciones: str = Form(None),
    telefono_secundario: str = Form(None),
    indicativo_telefono_secundario: str = Form("57"),  # ✅ CORREGIDO: "57" sin +
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        # ✅ AGREGAR VALIDACIÓN DE INDICATIVOS (COMO EN CREAR_PROSPECTO)
        if not indicativo_telefono.isdigit() or len(indicativo_telefono) > 4:
            return RedirectResponse(url="/prospectos?error=Indicativo principal inválido. Solo números, máximo 4 dígitos", status_code=303)
        
        if indicativo_telefono_secundario and (not indicativo_telefono_secundario.isdigit() or len(indicativo_telefono_secundario) > 4):
            return RedirectResponse(url="/prospectos?error=Indicativo secundario inválido. Solo números, máximo 4 dígitos", status_code=303)

        # Buscar prospecto
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
        
        # Verificar permisos: Agentes solo pueden editar sus propios prospectos
        if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(url="/prospectos?error=No tiene permisos para editar este prospecto", status_code=303)
        
        # Convertir fechas de string a date
        fecha_ida_date = parsear_fecha(fecha_ida)
        fecha_vuelta_date = parsear_fecha(fecha_vuelta)
        
        # Actualizar datos del prospecto
        prospecto.nombre = nombre
        prospecto.apellido = apellido
        prospecto.correo_electronico = correo_electronico
        prospecto.telefono = telefono
        prospecto.indicativo_telefono = indicativo_telefono  # ✅ NUEVO
        prospecto.telefono_secundario = telefono_secundario
        prospecto.indicativo_telefono_secundario = indicativo_telefono_secundario  # ✅ NUEVO
        prospecto.ciudad_origen = ciudad_origen
        prospecto.destino = destino
        prospecto.fecha_ida = fecha_ida_date
        prospecto.fecha_vuelta = fecha_vuelta_date
        prospecto.pasajeros_adultos = pasajeros_adultos
        prospecto.pasajeros_ninos = pasajeros_ninos
        prospecto.pasajeros_infantes = pasajeros_infantes
        prospecto.medio_ingreso_id = medio_ingreso_id
        prospecto.observaciones = observaciones
        
        db.commit()
        
        return RedirectResponse(url="/prospectos?success=Prospecto actualizado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating prospect: {e}")
        return RedirectResponse(url="/prospectos?error=Error al actualizar prospecto", status_code=303)

@app.post("/prospectos/{prospecto_id}/eliminar")
async def eliminar_prospecto(
    request: Request,
    prospecto_id: int,
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        # Buscar prospecto
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
        
        # Verificar permisos: Agentes solo pueden eliminar sus propios prospectos
        # Admin/Supervisor pueden eliminar cualquier prospecto
        if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(url="/prospectos?error=No tiene permisos para eliminar este prospecto", status_code=303)
        
        db.delete(prospecto)
        db.commit()
        
        return RedirectResponse(url="/prospectos?success=Prospecto eliminado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting prospect: {e}")
        return RedirectResponse(url="/prospectos?error=Error al eliminar prospecto", status_code=303)

@app.post("/prospectos/{prospecto_id}/asignar")
async def asignar_agente(
    request: Request,
    prospecto_id: int,
    agente_id: int = Form(None),  # ID del agente a asignar (0 para desasignar)
    # ✅ PARÁMETROS PARA MANTENER FILTROS
    destino: str = Form(None),
    telefono: str = Form(None),
    medio_ingreso_id: str = Form(None),
    estado: str = Form(None),
    busqueda_global: str = Form(None),
    agente_filtro_id: str = Form(None),  # ✅ CAMBIADO: Filtro de agente (no confundir con asignación)
    # ✅ PARÁMETROS DE FECHA PARA FILTROS DESDE DASHBOARD
    fecha_inicio: str = Form(None),
    fecha_fin: str = Form(None),
    periodo: str = Form(None),
    tipo_filtro: str = Form(None),  # Para filtros desde dashboard
    valor_filtro: str = Form(None),  # Para filtros desde dashboard
    pagina: str = Form("1"),  # Para mantener paginación
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user or user.tipo_usuario not in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]:
        raise HTTPException(status_code=403, detail="No tiene permisos para esta acción")
    
    try:
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        
        # Si agente_id es 0 o vacío, desasignar (establecer None)
        if not agente_id or agente_id == 0:
            prospecto.agente_asignado_id = None
            mensaje = "Prospecto desasignado correctamente"
        else:
            # Verificar que el agente exista
            agente = db.query(models.Usuario).filter(
                models.Usuario.id == agente_id,
                models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
            ).first()
            if not agente:
                raise HTTPException(status_code=404, detail="Agente no encontrado")
            
            prospecto.agente_asignado_id = agente_id
            mensaje = f"Agente {agente.username} asignado correctamente"
            
            # ✅ CREAR NOTIFICACIÓN DE ASIGNACIÓN
            notificacion = models.Notificacion(
                usuario_id=agente.id,
                prospecto_id=prospecto.id,
                tipo="asignacion",
                mensaje=f"Te han asignado un nuevo prospecto: {prospecto.nombre} {prospecto.apellido or ''}",
                email_enviado=False
            )
            db.add(notificacion)
            
            # ✅ ENVIAR EMAIL AL AGENTE
            if agente.email:
                asunto = "Nuevo Prospecto Asignado 🚀"
                cuerpo = f"Hola {agente.username},\n\nSe te ha asignado el prospecto {prospecto.nombre} {prospecto.apellido}.\n\nIngresa al sistema para gestionarlo."
                enviado = enviar_notificacion_email(agente.email, asunto, cuerpo)
                notificacion.email_enviado = enviado
        
        db.commit()
        
        # ✅ DETERMINAR A DÓNDE REDIRIGIR
        redirect_url = "/prospectos"  # Por defecto
        
        # Si viene de un filtro del dashboard, redirigir a esa vista
        if tipo_filtro and valor_filtro:
            redirect_url = "/prospectos/filtro"
        
        # ✅ CONSTRUIR PARÁMETROS DE CONSULTA
        params = []
        
        # Parámetros generales de filtros
        if destino:
            params.append(f"destino={destino}")
        if telefono:
            params.append(f"telefono={telefono}")
        if medio_ingreso_id and medio_ingreso_id != 'todos':
            params.append(f"medio_ingreso_id={medio_ingreso_id}")
        if estado and estado != 'todos':
            params.append(f"estado={estado}")
        if busqueda_global:
            params.append(f"busqueda_global={busqueda_global}")
        if agente_filtro_id and agente_filtro_id != 'todos':
            params.append(f"agente_asignado_id={agente_filtro_id}")
        
        # Parámetros específicos para filtros desde dashboard
        if tipo_filtro:
            params.append(f"tipo_filtro={tipo_filtro}")
        if valor_filtro:
            params.append(f"valor_filtro={valor_filtro}")
        if fecha_inicio:
            params.append(f"fecha_inicio={fecha_inicio}")
        if fecha_fin:
            params.append(f"fecha_fin={fecha_fin}")
        if periodo:
            params.append(f"periodo={periodo}")
        if pagina and pagina != "1":
            params.append(f"pagina={pagina}")
        
        # Agregar mensaje de éxito
        if params:
            redirect_url += "?" + "&".join(params) + f"&success={mensaje}"
        else:
            redirect_url += f"?success={mensaje}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error asignando agente: {e}")
        return RedirectResponse(url="/prospectos?error=Error al asignar agente", status_code=303)

# ========== GESTIÓN DE INTERACCIONES ==========

@app.get("/prospectos/{prospecto_id}/seguimiento")
async def ver_seguimiento(
    request: Request,
    prospecto_id: int,
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
    if not prospecto:
        return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
    
    # Verificar permisos
    if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
        prospecto.agente_asignado_id != user.id):
        return RedirectResponse(url="/prospectos?error=No tiene permisos para ver este prospecto", status_code=303)
    
    return templates.TemplateResponse("seguimiento_prospecto.html", {
        "request": request,
        "prospecto": prospecto,
        "current_user": user,
        "estados_prospecto": [estado.value for estado in EstadoProspecto]
    })

@app.post("/prospectos/{prospecto_id}/interaccion")
async def registrar_interaccion(
    request: Request,
    prospecto_id: int,
    descripcion: str = Form(...),
    tipo_interaccion: str = Form("general"),
    cambio_estado: str = Form(None),
    fecha_proximo_contacto: str = Form(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
        
        # Verificar permisos
        if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(url="/prospectos?error=No tiene permisos para este prospecto", status_code=303)
        
        # ✅ VALIDAR TRANSICIÓN DE ESTADOS (NO PERMITIR REGRESAR)
        if cambio_estado and prospecto.estado:
            estados_orden = [
                EstadoProspecto.NUEVO.value,
                EstadoProspecto.EN_SEGUIMIENTO.value, 
                EstadoProspecto.COTIZADO.value,
                # Estados finales (mismo nivel)
                EstadoProspecto.GANADO.value,
                EstadoProspecto.CERRADO_PERDIDO.value
            ]
            
            estado_actual_idx = estados_orden.index(prospecto.estado) if prospecto.estado in estados_orden else -1
            estado_nuevo_idx = estados_orden.index(cambio_estado) if cambio_estado in estados_orden else -1
            
            # No permitir regresar a estados anteriores (excepto reactivación por admin/supervisor)
            if (estado_nuevo_idx < estado_actual_idx and 
                estado_actual_idx >= 2 and  # Solo validar desde COTIZADO hacia atrás
                user.tipo_usuario not in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]):
                return RedirectResponse(
                    url=f"/prospectos/{prospecto_id}/seguimiento?error=No puede regresar a un estado anterior", 
                    status_code=303
                )
        
        # Validar cambio de estado a CERRADO_PERDIDO
        if cambio_estado == EstadoProspecto.CERRADO_PERDIDO.value and not descripcion.strip():
            return RedirectResponse(
                url=f"/prospectos/{prospecto_id}/seguimiento?error=Debe agregar un comentario al cerrar el prospecto", 
                status_code=303
            )
        
        # Registrar historial de estado ANTES del cambio
        if cambio_estado and cambio_estado != prospecto.estado:
            historial = models.HistorialEstado(
                prospecto_id=prospecto_id,
                estado_anterior=prospecto.estado,
                estado_nuevo=cambio_estado,
                usuario_id=user.id,
                comentario=descripcion
            )
            db.add(historial)
        
        # Registrar interacción
        estado_anterior = prospecto.estado
        interaccion = models.Interaccion(
            prospecto_id=prospecto_id,
            usuario_id=user.id,
            tipo_interaccion=tipo_interaccion,
            descripcion=descripcion,
            estado_anterior=estado_anterior,
            estado_nuevo=cambio_estado
        )
        
        db.add(interaccion)
        
        # ✅ CREAR NOTIFICACIÓN DE SEGUIMIENTO (SI SE PROGRAMA)
        if fecha_proximo_contacto:
            try:
                # El formato de input datetime-local es "YYYY-MM-DDTHH:MM"
                fecha_prog = datetime.strptime(fecha_proximo_contacto, "%Y-%m-%dT%H:%M")
                
                notificacion = models.Notificacion(
                    usuario_id=user.id,
                    prospecto_id=prospecto_id,
                    tipo="seguimiento",
                    mensaje=f"Recordatorio: {descripcion[:50]}...",
                    fecha_programada=fecha_prog,
                    email_enviado=False
                )
                db.add(notificacion)
                
                # Feedback visual en el log/email
                if user.email:
                    enviar_notificacion_email(
                        user.email, 
                        "Recordatorio Programado 📅", 
                        f"Has programado un seguimiento para el prospecto {prospecto.nombre} el {fecha_prog}."
                    )
            except ValueError:
                print(f"❌ Error formato fecha recordatorio: {fecha_proximo_contacto}")
        
        # ✅ REGISTRAR ESTADÍSTICA DE COTIZACIÓN
        if (cambio_estado == EstadoProspecto.COTIZADO.value and 
            estado_anterior != EstadoProspecto.COTIZADO.value and
            prospecto.agente_asignado_id):
            
            # Verificar si ya existe estadística para este prospecto
            existe_estadistica = db.query(models.EstadisticaCotizacion).filter(
                models.EstadisticaCotizacion.prospecto_id == prospecto_id
            ).first()
            
            if existe_estadistica:
                # Actualizar la fecha si ya existe (para asegurar que cuenta HOY)
                existe_estadistica.fecha_cotizacion = datetime.now().date()
            else:
                estadistica = models.EstadisticaCotizacion(
                    agente_id=prospecto.agente_asignado_id,
                    prospecto_id=prospecto_id,
                    fecha_cotizacion=datetime.now().date()
                )
                db.add(estadistica)
                
                # ✅ GENERAR ID DE COTIZACIÓN ÚNICO
                db.flush()
                estadistica.generar_id_cotizacion()
        
        # Actualizar estado del prospecto si hay cambio
        if cambio_estado:
            prospecto.estado = cambio_estado
        
        db.commit()
        
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?success=Interacción registrada", 
            status_code=303
        )
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error registrando interacción: {e}")
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?error=Error al registrar interacción", 
            status_code=303
        )
    

# ========== GESTIÓN DE DOCUMENTOS ==========

@app.post("/prospectos/{prospecto_id}/documento")
async def subir_documento(
    request: Request,
    prospecto_id: int,
    archivo: UploadFile = File(...),
    tipo_documento: str = Form("cotizacion"),
    descripcion: str = Form(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(url="/prospectos?error=Prospecto no encontrado", status_code=303)
        
        # Verificar permisos
        if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(url="/prospectos?error=No tiene permisos para este prospecto", status_code=303)
        
        # Validar que sea PDF
        if not archivo.filename.lower().endswith('.pdf'):
            return RedirectResponse(
                url=f"/prospectos/{prospecto_id}/seguimiento?error=Solo se permiten archivos PDF", 
                status_code=303
            )
        
        # Crear directorio para el prospecto
        prospecto_dir = os.path.join(UPLOAD_DIR, f"prospecto_{prospecto_id}")
        os.makedirs(prospecto_dir, exist_ok=True)
        
        # Generar nombre único para el archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{timestamp}_{archivo.filename}"
        ruta_archivo = os.path.join(prospecto_dir, nombre_archivo)
        
        # Guardar archivo
        with open(ruta_archivo, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)
        
        # ✅ REGISTRAR DOCUMENTO EN BD
        documento = models.Documento(
            prospecto_id=prospecto_id,
            usuario_id=user.id,
            nombre_archivo=archivo.filename,
            tipo_documento=tipo_documento,
            ruta_archivo=ruta_archivo,
            descripcion=descripcion
        )
        
        db.add(documento)
        db.flush()  # Para obtener el ID antes del commit
        
        # ✅ GENERAR ID DE DOCUMENTO ÚNICO
        documento.generar_id_documento()
        
        # ✅ CAMBIAR ESTADO A COTIZADO SI SE SUBE UNA COTIZACIÓN
        if tipo_documento == "cotizacion":
            estado_anterior = prospecto.estado
            prospecto.estado = EstadoProspecto.COTIZADO.value
            
            # ✅ REGISTRAR ESTADÍSTICA DE COTIZACIÓN
            # Verificar si ya existe estadística para este prospecto
            existe_estadistica = db.query(models.EstadisticaCotizacion).filter(
                models.EstadisticaCotizacion.prospecto_id == prospecto_id
            ).first()
            
            if existe_estadistica:
                # Actualizar la fecha si ya existe
                existe_estadistica.fecha_cotizacion = datetime.now().date()
            else:
                estadistica = models.EstadisticaCotizacion(
                    agente_id=prospecto.agente_asignado_id or user.id,
                    prospecto_id=prospecto_id,
                    fecha_cotizacion=datetime.now().date()
                )
                db.add(estadistica)
                db.flush()  # Para obtener el ID
                
                # ✅ GENERAR ID DE COTIZACIÓN ÚNICO
                estadistica.generar_id_cotizacion()
            
            # Registrar interacción automática de cambio de estado
            interaccion = models.Interaccion(
                prospecto_id=prospecto_id,
                usuario_id=user.id,
                tipo_interaccion="documento",
                descripcion=f"Se subió cotización: {archivo.filename}",
                estado_anterior=estado_anterior,
                estado_nuevo=EstadoProspecto.COTIZADO.value
            )
            db.add(interaccion)
        
        # Registrar interacción para el documento
        interaccion_doc = models.Interaccion(
            prospecto_id=prospecto_id,
            usuario_id=user.id,
            tipo_interaccion="documento",
            descripcion=f"Documento subido: {archivo.filename} ({tipo_documento})",
            estado_anterior=prospecto.estado,
            estado_nuevo=prospecto.estado
        )
        db.add(interaccion_doc)
        
        db.commit()
        
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?success=Documento subido correctamente", 
            status_code=303
        )
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error subiendo documento: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?error=Error al subir documento", 
            status_code=303
        )


# ✅ NUEVO ENDPOINT: Búsqueda por ID
@app.get("/busqueda_ids", response_class=HTMLResponse)
async def buscar_por_id(
    request: Request,
    tipo_id: str = Query("cliente"),  # cliente, cotizacion, documento
    valor_id: str = Query(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    resultados = []
    tipo_busqueda = ""
    
    if valor_id:
        valor_id = valor_id.upper().strip()
        
        if tipo_id == "cliente":
            # Buscar por ID de cliente
            resultados = db.query(models.Prospecto).filter(
                models.Prospecto.id_cliente.ilike(f"%{valor_id}%")
            ).all()
            tipo_busqueda = f"Clientes con ID: {valor_id}"
            
        elif tipo_id == "cotizacion":
            # Buscar por ID de cotización
            estadisticas = db.query(models.EstadisticaCotizacion).filter(
                models.EstadisticaCotizacion.id_cotizacion.ilike(f"%{valor_id}%")
            ).all()
            # Obtener prospectos relacionados
            for stats in estadisticas:
                prospecto = db.query(models.Prospecto).filter(
                    models.Prospecto.id == stats.prospecto_id
                ).first()
                if prospecto:
                    resultados.append(prospecto)
            tipo_busqueda = f"Cotizaciones con ID: {valor_id}"
            
        elif tipo_id == "documento":
            # Buscar por ID de documento
            documentos = db.query(models.Documento).filter(
                models.Documento.id_documento.ilike(f"%{valor_id}%")
            ).all()
            # Obtener prospectos relacionados
            for doc in documentos:
                prospecto = db.query(models.Prospecto).filter(
                    models.Prospecto.id == doc.prospecto_id
                ).first()
                if prospecto:
                    resultados.append(prospecto)
            tipo_busqueda = f"Documentos con ID: {valor_id}"
    
    return templates.TemplateResponse("busqueda_ids.html", {
        "request": request,
        "current_user": user,
        "resultados": resultados,
        "tipo_busqueda": tipo_busqueda,
        "tipo_id_activo": tipo_id,
        "valor_id_buscado": valor_id
    })




# ========== GESTIÓN DE USUARIOS (SOLO ADMIN) ==========

@app.get("/usuarios", response_class=HTMLResponse)
async def listar_usuarios(
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(require_admin)
):
    usuarios = db.query(models.Usuario).all()
    return templates.TemplateResponse("usuarios/lista.html", {
        "request": request,
        "current_user": user,
        "usuarios": usuarios,
        "tipos_usuario": [tipo.value for tipo in TipoUsuario]
    })

@app.post("/usuarios")
async def crear_usuario(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    tipo_usuario: str = Form(...),
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(require_admin)
):
    try:
        # Verificar si usuario ya existe
        existing_user = db.query(models.Usuario).filter(
            (models.Usuario.username == username) | (models.Usuario.email == email)
        ).first()
        
        if existing_user:
            return RedirectResponse(url="/usuarios?error=Usuario o email ya existen", status_code=303)
        
        # Crear usuario
        nuevo_usuario = models.Usuario(
            username=username,
            email=email,
            hashed_password=auth.get_password_hash(password),
            tipo_usuario=tipo_usuario
        )
        
        db.add(nuevo_usuario)
        db.commit()
        
        return RedirectResponse(url="/usuarios?success=Usuario creado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        return RedirectResponse(url="/usuarios?error=Error al crear usuario", status_code=303)

@app.post("/usuarios/{usuario_id}/editar")
async def editar_usuario(
    request: Request,
    usuario_id: int,
    username: str = Form(...),
    email: str = Form(...),
    tipo_usuario: str = Form(...),
    password: str = Form(None),
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(require_admin)
):
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        if not usuario:
            return RedirectResponse(url="/usuarios?error=Usuario no encontrado", status_code=303)
        
        # Verificar si username/email ya existen en otros usuarios
        existing_user = db.query(models.Usuario).filter(
            (models.Usuario.username == username) | (models.Usuario.email == email)
        ).filter(models.Usuario.id != usuario_id).first()
        
        if existing_user:
            return RedirectResponse(url="/usuarios?error=Usuario o email ya existen", status_code=303)
        
        # Actualizar datos
        usuario.username = username
        usuario.email = email
        usuario.tipo_usuario = tipo_usuario
        
        # Actualizar contraseña si se proporcionó
        if password:
            usuario.hashed_password = auth.get_password_hash(password)
        
        db.commit()
        
        return RedirectResponse(url="/usuarios?success=Usuario actualizado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating user: {e}")
        return RedirectResponse(url="/usuarios?error=Error al actualizar usuario", status_code=303)

@app.post("/usuarios/{usuario_id}/eliminar")
async def eliminar_usuario(
    request: Request,
    usuario_id: int,
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(require_admin)
):
    try:
        # No permitir eliminar el propio usuario
        if usuario_id == user.id:
            return RedirectResponse(url="/usuarios?error=No puede eliminar su propio usuario", status_code=303)
        
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        if not usuario:
            return RedirectResponse(url="/usuarios?error=Usuario no encontrado", status_code=303)
        
        db.delete(usuario)
        db.commit()
        
        return RedirectResponse(url="/usuarios?success=Usuario eliminado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting user: {e}")
        return RedirectResponse(url="/usuarios?error=Error al eliminar usuario", status_code=303)

# ========== HISTORIAL DE PROSPECTOS CERRADOS ==========

@app.get("/prospectos/cerrados", response_class=HTMLResponse)
async def listar_prospectos_cerrados(
    request: Request,
    fecha_registro_desde: str = Query(None),
    fecha_registro_hasta: str = Query(None),
    fecha_cierre_desde: str = Query(None),
    fecha_cierre_hasta: str = Query(None),
    destino: str = Query(None),
    agente_asignado_id: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    # Construir query para prospectos cerrados/ganados
    query = db.query(models.Prospecto).filter(
        models.Prospecto.estado.in_([EstadoProspecto.CERRADO_PERDIDO.value, EstadoProspecto.GANADO.value])
    )
    
    # Aplicar filtros según rol
    if user.tipo_usuario == TipoUsuario.AGENTE.value:
        query = query.filter(models.Prospecto.agente_asignado_id == user.id)
    
    # Filtros de fechas de registro
    if fecha_registro_desde:
        try:
            fecha_desde = datetime.strptime(fecha_registro_desde, "%d/%m/%Y").date()
            query = query.filter(models.Prospecto.fecha_registro >= fecha_desde)
        except ValueError:
            pass
    
    if fecha_registro_hasta:
        try:
            fecha_hasta = datetime.strptime(fecha_registro_hasta, "%d/%m/%Y").date()
            query = query.filter(models.Prospecto.fecha_registro <= fecha_hasta)
        except ValueError:
            pass
    
    # Filtros de fechas de cierre (última interacción con cambio de estado)
    if fecha_cierre_desde or fecha_cierre_hasta:
        subquery = db.query(models.Interaccion.prospecto_id).filter(
            models.Interaccion.estado_nuevo.in_([EstadoProspecto.CERRADO_PERDIDO.value, EstadoProspecto.GANADO.value])
        )
        
        if fecha_cierre_desde:
            try:
                fecha_cierre_desde_date = datetime.strptime(fecha_cierre_desde, "%d/%m/%Y").date()
                subquery = subquery.filter(models.Interaccion.fecha_creacion >= fecha_cierre_desde_date)
            except ValueError:
                pass
        
        if fecha_cierre_hasta:
            try:
                fecha_cierre_hasta_date = datetime.strptime(fecha_cierre_hasta, "%d/%m/%Y").date()
                subquery = subquery.filter(models.Interaccion.fecha_creacion <= fecha_cierre_hasta_date)
            except ValueError:
                pass
        
        query = query.filter(models.Prospecto.id.in_(subquery))
    
    # Otros filtros
    if destino:
        # ✅ BÚSQUEDA GENERAL EN CERRADOS (Nombre, Email, Teléfono, Destino)
        search_term = f"%{destino}%"
        query = query.filter(or_(
            models.Prospecto.destino.ilike(search_term),
            models.Prospecto.nombre.ilike(search_term),
            models.Prospecto.apellido.ilike(search_term),
            models.Prospecto.correo_electronico.ilike(search_term),
            models.Prospecto.telefono.ilike(search_term)
        ))
    
    if agente_asignado_id and agente_asignado_id != "todos" and user.tipo_usuario in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]:
        query = query.filter(models.Prospecto.agente_asignado_id == int(agente_asignado_id))
    
    # ✅ PAGINACIÓN
    query = query.order_by(models.Prospecto.fecha_registro.desc())
    
    total_registros = query.count()
    total_pages = (total_registros + limit - 1) // limit
    
    # Asegurar que la página solicitada sea válida
    if page > total_pages and total_pages > 0:
        page = total_pages
    if page < 1:
        page = 1
        
    offset = (page - 1) * limit
    prospectos_cerrados = query.offset(offset).limit(limit).all()
    
    # Obtener datos para filtros
    agentes = db.query(models.Usuario).filter(
        models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
    ).all()
    
    return templates.TemplateResponse("prospectos_cerrados.html", {
        "request": request,
        "prospectos": prospectos_cerrados,
        "current_user": user,
        "agentes": agentes,
        "filtros_activos": {
            "fecha_registro_desde": fecha_registro_desde,
            "fecha_registro_hasta": fecha_registro_hasta,
            "fecha_cierre_desde": fecha_cierre_desde,
            "fecha_cierre_hasta": fecha_cierre_hasta,
            "destino": destino,
            "agente_asignado_id": agente_asignado_id
        },
        # Info Paginación
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "total_registros": total_registros
    })

@app.post("/prospectos/{prospecto_id}/reactivar")
async def reactivar_prospecto(
    request: Request,
    prospecto_id: int,
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(url="/prospectos/cerrados?error=Prospecto no encontrado", status_code=303)
        
        # Verificar permisos
        if (user.tipo_usuario == TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(url="/prospectos/cerrados?error=No tiene permisos para reactivar este prospecto", status_code=303)
        
        # Reactivar prospecto
        estado_anterior = prospecto.estado
        prospecto.estado = EstadoProspecto.EN_SEGUIMIENTO.value
        
        # Registrar interacción de reactivación
        interaccion = models.Interaccion(
            prospecto_id=prospecto_id,
            usuario_id=user.id,
            tipo_interaccion="sistema",
            descripcion=f"Prospecto reactivado desde estado: {estado_anterior}",
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoProspecto.EN_SEGUIMIENTO.value
        )
        
        db.add(interaccion)
        db.commit()
        
        return RedirectResponse(url="/prospectos/cerrados?success=Prospecto reactivado correctamente", status_code=303)
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error reactivando prospecto: {e}")
        return RedirectResponse(url="/prospectos/cerrados?error=Error al reactivar prospecto", status_code=303)


# Endpoint para verificar autenticación
@app.get("/check-auth")
async def check_auth(request: Request, db: Session = Depends(database.get_db)):
    user = await get_current_user(request, db)
    if user:
        return {
            "authenticated": True, 
            "user": user.username,
            "user_type": user.tipo_usuario,
            "active_sessions": len(active_sessions)
        }
    else:
        return {
            "authenticated": False, 
            "active_sessions": len(active_sessions)
        }

#Exportar a Excel
@app.get("/prospectos/exportar/excel")
async def exportar_prospectos_excel(
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(get_current_user)
):
    try:
        # Obtener prospectos según permisos
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            prospectos = db.query(models.Prospecto).filter(
                models.Prospecto.agente_asignado_id == user.id
            ).all()
        else:
            prospectos = db.query(models.Prospecto).all()
        
        # Convertir a DataFrame
        data = []
        for p in prospectos:
            data.append({
                'ID': p.id,
                'Nombre': f"{p.nombre or ''} {p.apellido or ''}",
                'Email': p.correo_electronico or '',
                'Teléfono': p.telefono or '',
                'Destino': p.destino or '',
                'Estado': p.estado,
                'Agente': p.agente_asignado.username if p.agente_asignado else 'Sin asignar',
                'Fecha Registro': p.fecha_registro.strftime('%d/%m/%Y'),
                'Medio Ingreso': p.medio_ingreso.nombre
            })
        
        df = pd.DataFrame(data)
        
        # Crear Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Prospectos', index=False)
        
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=prospectos.xlsx"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exportando: {str(e)}")

# ✅ PANEL DE HISTORIAL DE CLIENTE MEJORADO
@app.get("/clientes/historial", response_class=HTMLResponse)
async def historial_cliente(
    request: Request,
    busqueda: str = Query(None),
    telefono: str = Query(None),
    fecha_busqueda: str = Query(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    cliente_principal = None
    prospectos = []
    
    query = db.query(models.Prospecto)
    
    # ✅ LÓGICA DE BÚSQUEDA AVANZADA
    filtros = []
    
    # 1. Búsqueda por término (Teléfono, Email, Nombre)
    if busqueda:
        term = f"%{busqueda}%"
        filtros.append(or_(
            models.Prospecto.telefono.ilike(term),
            models.Prospecto.telefono_secundario.ilike(term),
            models.Prospecto.correo_electronico.ilike(term),
            models.Prospecto.nombre.ilike(term),
            models.Prospecto.apellido.ilike(term)
        ))
    
    # 2. Búsqueda por teléfono específico (compatibilidad anterior)
    if telefono:
        filtros.append(or_(
            models.Prospecto.telefono == telefono,
            models.Prospecto.telefono_secundario == telefono
        ))
        
    # 3. Búsqueda por fecha exacta
    if fecha_busqueda:
        try:
            fecha_dt = datetime.strptime(fecha_busqueda, "%d/%m/%Y").date()
            # FIltrar por rango del día completo
            fecha_inicio = datetime.combine(fecha_dt, datetime.min.time())
            fecha_fin = datetime.combine(fecha_dt, datetime.max.time())
            filtros.append(and_(
                models.Prospecto.fecha_registro >= fecha_inicio,
                models.Prospecto.fecha_registro <= fecha_fin
            ))
        except ValueError:
            pass

    if filtros:
        query = query.filter(and_(*filtros))
        prospectos = query.order_by(models.Prospecto.fecha_registro.desc()).all()
        
        if prospectos:
            cliente_principal = prospectos[0]
            print(f"🔍 Encontrados {len(prospectos)} registros en historial")
    
    return templates.TemplateResponse("historial_cliente.html", {
        "request": request,
        "current_user": user,
        "cliente": cliente_principal,
        "prospectos": prospectos,
        "busqueda_activa": busqueda or telefono,
        "fecha_activa": fecha_busqueda
    })

# ✅ ACTUALIZAR INFORMACIÓN DE VIAJE
@app.post("/prospectos/{prospecto_id}/actualizar-viaje")
async def actualizar_viaje(
    request: Request,
    prospecto_id: int,
    nombre: str = Form(None),  
    apellido: str = Form(None),  
    correo_electronico: str = Form(None),
    telefono: str = Form(...),
    indicativo_telefono: str = Form("57"),
    indicativo_telefono_secundario: str = Form("57"),
    ciudad_origen: str = Form(None),
    destino: str = Form(None),
    fecha_ida: str = Form(None),
    fecha_vuelta: str = Form(None),
    pasajeros_adultos: int = Form(1),
    pasajeros_ninos: int = Form(0),
    pasajeros_infantes: int = Form(0),
    telefono_secundario: str = Form(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        prospecto = db.query(models.Prospecto).filter(models.Prospecto.id == prospecto_id).first()
        if not prospecto:
            return RedirectResponse(
                url=f"/prospectos/{prospecto_id}/seguimiento?error=Prospecto no encontrado", 
                status_code=303
            )
        
        # Verificar permisos
        if (user.tipo_usuario == models.TipoUsuario.AGENTE.value and 
            prospecto.agente_asignado_id != user.id):
            return RedirectResponse(
                url=f"/prospectos/{prospecto_id}/seguimiento?error=No tiene permisos para editar este prospecto", 
                status_code=303
            )
        
        # Convertir fechas
        fecha_ida_date = parsear_fecha(fecha_ida)
        fecha_vuelta_date = parsear_fecha(fecha_vuelta)
        
        # Actualizar información
        prospecto.nombre = nombre
        prospecto.apellido = apellido
        prospecto.correo_electronico = correo_electronico
        prospecto.ciudad_origen = ciudad_origen
        prospecto.destino = destino
        prospecto.telefono = telefono
        prospecto.indicativo_telefono = indicativo_telefono
        prospecto.telefono_secundario = telefono_secundario
        prospecto.indicativo_telefono_secundario = indicativo_telefono_secundario
        prospecto.fecha_ida = fecha_ida_date
        prospecto.fecha_vuelta = fecha_vuelta_date
        prospecto.pasajeros_adultos = pasajeros_adultos
        prospecto.pasajeros_ninos = pasajeros_ninos
        prospecto.pasajeros_infantes = pasajeros_infantes
        prospecto.telefono_secundario = telefono_secundario
        
        # Registrar interacción automática
        interaccion = models.Interaccion(
            prospecto_id=prospecto_id,
            usuario_id=user.id,
            tipo_interaccion="sistema",
            descripcion="Información de viaje actualizada",
            estado_anterior=prospecto.estado,
            estado_nuevo=prospecto.estado
        )
        
        db.add(interaccion)
        db.commit()
        
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?success=Información de viaje actualizada correctamente", 
            status_code=303
        )
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error actualizando viaje: {e}")
        return RedirectResponse(
            url=f"/prospectos/{prospecto_id}/seguimiento?error=Error al actualizar información", 
            status_code=303
        )

# Endpoint de salud
@app.get("/health")
async def health_check(db: Session = Depends(database.get_db)):
    try:
        user_count = db.query(models.Usuario).count()
        prospecto_count = db.query(models.Prospecto).count()
        return {
            "status": "healthy",
            "database": "connected", 
            "users_count": user_count,
            "prospectos_count": prospecto_count,
            "active_sessions": len(active_sessions)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# ========== FILTROS DESDE DASHBOARD ==========
# ✅ NUEVO: FILTRO POR DATOS COMPLETOS/SIN DATOS
@app.get("/prospectos/filtro", response_class=HTMLResponse)
async def prospectos_filtro_dashboard(
    request: Request,
    tipo_filtro: str = Query(...),  # estado, asignacion, destino, ventas, datos, total
    valor_filtro: str = Query(...),  # valor del filtro
    # ✅ AGREGAR PARÁMETROS DE FECHA
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
    periodo: str = Query("mes"),
    pagina: int = Query(1),
    agente_asignado_id: str = Query(None), # ✅ Nuevo filtro por agente
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    # Configurar paginación
    registros_por_pagina = 50
    offset = (pagina - 1) * registros_por_pagina
    
    # ✅ CALCULAR RANGO DE FECHAS (Ya devuelve datetimes con hora min/max)
    fecha_inicio_dt, fecha_fin_dt = calcular_rango_fechas(periodo, fecha_inicio, fecha_fin)
    
    # extraer objetos date para comparaciones que requieran solo fecha (como cotizaciones)
    fecha_inicio_date = fecha_inicio_dt.date()
    fecha_fin_date = fecha_fin_dt.date()
    
    # ✅ CONSTRUIR QUERY SEGÚN TIPO DE FILTRO Y FECHAS
    if tipo_filtro == "estado" and valor_filtro == EstadoProspecto.COTIZADO.value:
        # COTIZADOS: Usar EstadisticaCotizacion (comparar fechas, no datetimes)
        query = db.query(models.Prospecto).join(
            models.EstadisticaCotizacion, 
            models.EstadisticaCotizacion.prospecto_id == models.Prospecto.id
        ).filter(
            models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_date,
            models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_date
        )
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            query = query.filter(models.EstadisticaCotizacion.agente_id == user.id)
            
        titulo_filtro = "Prospectos Cotizados en el periodo"

    elif (tipo_filtro == "estado" and valor_filtro in [
            EstadoProspecto.EN_SEGUIMIENTO.value, 
            EstadoProspecto.GANADO.value, 
            EstadoProspecto.CERRADO_PERDIDO.value
        ]) or (tipo_filtro == "ventas"):
        
        # SEGUIMIENTO, GANADOS, PERDIDOS: Usar HistorialEstado
        target_state = valor_filtro
        if tipo_filtro == "ventas":
            target_state = EstadoProspecto.GANADO.value
            titulo_filtro = "Ventas realizadas en el periodo"
        else:
            titulo_filtro = f"Prospectos {valor_filtro.replace('_', ' ').title()} en el periodo"
            
        query = db.query(models.Prospecto).join(
            models.HistorialEstado,
            models.HistorialEstado.prospecto_id == models.Prospecto.id
        ).filter(
            models.HistorialEstado.estado_nuevo == target_state,
            models.HistorialEstado.fecha_cambio >= fecha_inicio_dt,
            models.HistorialEstado.fecha_cambio <= fecha_fin_dt
        )
        
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            query = query.filter(models.HistorialEstado.usuario_id == user.id)

    else:
        # OTROS (Nuevos, Total, Asignación, etc.): Usar Fecha de Registro
        query = db.query(models.Prospecto).filter(
            models.Prospecto.fecha_registro >= fecha_inicio_dt,
            models.Prospecto.fecha_registro <= fecha_fin_dt
        )
        
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            query = query.filter(models.Prospecto.agente_asignado_id == user.id)
    
    # ✅ Filtro por agente explicito (para Admin/Supervisor) - MOVIDO FUERA DEL ELSE
    if agente_asignado_id and agente_asignado_id != "todos":
        try:
            # Si estamos filtrando historia/stats, el filtro de agente es diferente
            if tipo_filtro == "estado" and valor_filtro == EstadoProspecto.COTIZADO.value:
                query = query.filter(models.EstadisticaCotizacion.agente_id == int(agente_asignado_id))
            elif (tipo_filtro == "estado" and valor_filtro in [EstadoProspecto.EN_SEGUIMIENTO.value, EstadoProspecto.GANADO.value, EstadoProspecto.CERRADO_PERDIDO.value]) or (tipo_filtro == "ventas"):
                query = query.filter(models.HistorialEstado.usuario_id == int(agente_asignado_id))
            else:
                query = query.filter(models.Prospecto.agente_asignado_id == int(agente_asignado_id))
        except ValueError:
            pass
            
    # Aplicar filtros específicos adicionales
    if tipo_filtro == "estado":  # Solo queda NUEVO o cualquier otro no manejado arriba
        query = query.filter(models.Prospecto.estado == valor_filtro)
        titulo_filtro = f"Prospectos en estado: {valor_filtro.replace('_', ' ').title()}"
        
    elif tipo_filtro == "asignacion":
        if valor_filtro == "sin_asignar":
            query = query.filter(models.Prospecto.agente_asignado_id == None)
            titulo_filtro = "Prospectos sin asignar"
        elif valor_filtro == "asignados":
            query = query.filter(models.Prospecto.agente_asignado_id != None)
            titulo_filtro = "Prospectos asignados"
    
    elif tipo_filtro == "destino":
        query = query.filter(models.Prospecto.destino.ilike(f"%{valor_filtro}%"))
        titulo_filtro = f"Prospectos con destino: {valor_filtro}"
    
    elif tipo_filtro == "datos":
        if valor_filtro == "con_datos":
            query = query.filter(models.Prospecto.tiene_datos_completos == True)
            titulo_filtro = "Prospectos con datos completos"
        elif valor_filtro == "sin_datos":
            query = query.filter(models.Prospecto.tiene_datos_completos == False)
            titulo_filtro = "Prospectos sin datos (solo teléfono)"
            
    elif tipo_filtro == "total":
        titulo_filtro = "Todos los prospectos registrados"
    
    # Obtener total y prospectos paginados
    total_prospectos = query.count()
    prospectos = query.offset(offset).limit(registros_por_pagina).all()
    
    # Calcular total de páginas
    total_paginas = (total_prospectos + registros_por_pagina - 1) // registros_por_pagina
    
    # Obtener datos para filtros
    agentes = db.query(models.Usuario).filter(
        models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
    ).all()
    
    medios_ingreso = db.query(models.MedioIngreso).all()
    
    return templates.TemplateResponse("prospectos_filtro.html", {
        "request": request,
        "prospectos": prospectos,
        "current_user": user,
        "agentes": agentes,
        "medios_ingreso": medios_ingreso,
        "titulo_filtro": titulo_filtro,
        "tipo_filtro": tipo_filtro,
        "valor_filtro": valor_filtro,
        "pagina_actual": pagina,
        "total_paginas": total_paginas,
        "total_prospectos": total_prospectos,
        "registros_por_pagina": registros_por_pagina,
        # ✅ PASAR DATOS DE FECHA
        "fecha_inicio_activa": fecha_inicio,
        "fecha_fin_activa": fecha_fin,
        "periodo_activo": periodo,
        "fecha_inicio_formateada": fecha_inicio_dt.strftime("%d/%m/%Y"),
        "fecha_fin_formateada": fecha_fin_dt.strftime("%d/%m/%Y")
    })


# ✅ ENDPOINT PARA AUTOCOMPLETADO DE DESTINOS
@app.get("/api/destinos/sugerencias")
async def sugerencias_destinos(
    q: str = Query("", min_length=2),
    limit: int = Query(10),
    db: Session = Depends(database.get_db)
):
    """Devuelve sugerencias de destinos existentes"""
    if len(q) < 2:
        return JSONResponse(content={"sugerencias": []})
    
    try:
        # Buscar destinos que contengan el texto (case-insensitive)
        destinos = db.query(models.Prospecto.destino).filter(
            models.Prospecto.destino.isnot(None),
            models.Prospecto.destino != '',
            models.Prospecto.destino.ilike(f"%{q}%")
        ).distinct().limit(limit).all()
        
        # Extraer solo los strings
        sugerencias = [destino[0] for destino in destinos if destino[0]]
        
        # Ordenar por relevancia (los que empiezan con la búsqueda primero)
        sugerencias.sort(key=lambda x: 
            0 if x.lower().startswith(q.lower()) else 
            1 if q.lower() in x.lower() else 2
        )
        
        return JSONResponse(content={"sugerencias": sugerencias[:limit]})
        
    except Exception as e:
        print(f"Error en sugerencias_destinos: {e}")
        return JSONResponse(content={"sugerencias": []})

# ✅ ENDPOINT PARA NORMALIZAR DESTINOS EXISTENTES
@app.post("/api/destinos/normalizar")
async def normalizar_destinos(
    destino_original: str = Form(...),
    destino_normalizado: str = Form(...),
    aplicar_a_todos: bool = Form(False),
    db: Session = Depends(database.get_db),
    user: models.Usuario = Depends(get_current_user)
):
    """Normaliza un destino existente"""
    if not user or user.tipo_usuario not in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]:
        raise HTTPException(status_code=403, detail="No tiene permisos")
    
    try:
        if aplicar_a_todos:
            # Actualizar todos los prospectos con este destino
            prospectos = db.query(models.Prospecto).filter(
                models.Prospecto.destino.ilike(f"%{destino_original}%")
            ).all()
            
            for prospecto in prospectos:
                prospecto.destino = destino_normalizado
            
            count = len(prospectos)
            mensaje = f"Se normalizaron {count} prospectos"
        else:
            # Actualizar solo los exactos
            prospectos = db.query(models.Prospecto).filter(
                models.Prospecto.destino == destino_original
            ).all()
            
            for prospecto in prospectos:
                prospecto.destino = destino_normalizado
            
            count = len(prospectos)
            mensaje = f"Se normalizaron {count} prospectos"
        
        db.commit()
        
        # Registrar acción en historial
        if count > 0:
            accion = models.Interaccion(
                prospecto_id=None,  # Acción global
                usuario_id=user.id,
                tipo_interaccion="sistema",
                descripcion=f"Normalización de destinos: '{destino_original}' → '{destino_normalizado}' ({count} registros)",
                estado_anterior=None,
                estado_nuevo=None
            )
            db.add(accion)
            db.commit()
        
        return {"success": True, "message": mensaje, "count": count}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ========== ESTADÍSTICAS AVANZADAS ==========

@app.get("/estadisticas/cotizaciones", response_class=HTMLResponse)
async def estadisticas_cotizaciones(
    request: Request,
    periodo: str = Query("mes"),  # dia, semana, mes, año, personalizado
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
    agente_id: str = Query(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        # Determinar rango de fechas
        fecha_inicio_dt, fecha_fin_dt = calcular_rango_fechas(periodo, fecha_inicio, fecha_fin)
        fecha_inicio_obj = fecha_inicio_dt.date()
        fecha_fin_obj = fecha_fin_dt.date()
        
        # Construir query base
        query = db.query(
            models.EstadisticaCotizacion,
            models.Usuario.username
        ).join(
            models.Usuario, models.EstadisticaCotizacion.agente_id == models.Usuario.id
        ).filter(
            models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_obj,
            models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_obj
        )
        
        # Filtro por agente
        if agente_id and agente_id != "todos":
            query = query.filter(models.EstadisticaCotizacion.agente_id == int(agente_id))
        elif user.tipo_usuario == TipoUsuario.AGENTE.value:
            # Agente solo ve sus propias estadísticas
            query = query.filter(models.EstadisticaCotizacion.agente_id == user.id)
        
        # Agrupar por agente y fecha
        # ✅ CAMBIO: Obtener lista detallada de cotizaciones individualmente
        estadisticas = query.add_columns(
            models.Prospecto.id.label('prospecto_id'),
            models.Prospecto.nombre,
            models.Prospecto.apellido,
            models.Prospecto.telefono
        ).join(
            models.Prospecto, models.EstadisticaCotizacion.prospecto_id == models.Prospecto.id
        ).order_by(
            models.EstadisticaCotizacion.fecha_cotizacion.desc(),
            models.Usuario.username
        ).all()
        
        # Estadísticas resumidas por agente
        resumen_agentes = db.query(
            models.Usuario.id,
            models.Usuario.username,
            func.count(models.EstadisticaCotizacion.id).label('total')
        ).join(
            models.EstadisticaCotizacion, models.EstadisticaCotizacion.agente_id == models.Usuario.id
        ).filter(
            models.EstadisticaCotizacion.fecha_cotizacion >= fecha_inicio_obj,
            models.EstadisticaCotizacion.fecha_cotizacion <= fecha_fin_obj
        )
        
        if user.tipo_usuario == TipoUsuario.AGENTE.value:
            resumen_agentes = resumen_agentes.filter(models.EstadisticaCotizacion.agente_id == user.id)
        
        resumen_agentes = resumen_agentes.group_by(models.Usuario.username).all()
        
        # Obtener lista de agentes para filtro
        agentes = db.query(models.Usuario).filter(
            models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value
        ).all()
        
        return templates.TemplateResponse("estadisticas_cotizaciones.html", {
            "request": request,
            "current_user": user,
            "estadisticas": estadisticas,
            "resumen_agentes": resumen_agentes,
            "agentes": agentes,
            "periodo_activo": periodo,
            "fecha_inicio_activa": fecha_inicio,
            "fecha_fin_activa": fecha_fin,
            "agente_id_activo": agente_id,
            "fecha_inicio_formateada": fecha_inicio_obj.strftime("%d/%m/%Y"),
            "fecha_fin_formateada": fecha_fin_obj.strftime("%d/%m/%Y")
        })
    
    except Exception as e:
        print(f"❌ Error en estadísticas: {e}")
        return RedirectResponse(url="/dashboard?error=Error al cargar estadísticas", status_code=303)


# ========== SISTEMA DE NOTIFICACIONES ==========

def check_inactivity(db: Session):
    """Verifica prospectos nuevos sin gestión por más de 4 horas"""
    limite = datetime.now() - timedelta(hours=4)
    
    # Prospectos nuevos creados antes del limite
    prospectos_inactivos = db.query(models.Prospecto).filter(
        models.Prospecto.estado == EstadoProspecto.NUEVO.value,
        models.Prospecto.fecha_registro <= limite
    ).all()
    
    count = 0
    for p in prospectos_inactivos:
        # Verificar si ya tiene alerta de inactividad reciente (últimas 24h)
        existe_alerta = db.query(models.Notificacion).filter(
            models.Notificacion.prospecto_id == p.id,
            models.Notificacion.tipo == "inactividad",
            models.Notificacion.fecha_creacion >= datetime.now() - timedelta(hours=24)
        ).first()
        
        if not existe_alerta:
            # Buscar supervisor/admin para notificar (o al agente si está asignado, aunque nuevos suelen estar sin asignar)
            # Si tiene agente, notificamos al agente. Si no, a todos los admins/supervisores.
            destinatarios = []
            if p.agente_asignado_id:
                destinatarios.append(p.agente_asignado_id)
            else:
                # Notificar a admins/supervisores
                admins = db.query(models.Usuario).filter(
                    models.Usuario.tipo_usuario.in_([TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value])
                ).all()
                destinatarios = [u.id for u in admins]
            
            for uid in destinatarios:
                notificacion = models.Notificacion(
                    usuario_id=uid,
                    prospecto_id=p.id,
                    tipo="inactividad",
                    mensaje=f"⚠️ Prospecto inactivo > 4h: {p.nombre} {p.apellido or ''}",
                    email_enviado=False
                )
                db.add(notificacion)
                count += 1
    
    db.commit()
    return count

@app.get("/api/notificaciones/check-inactivity")
async def api_check_inactivity(
    db: Session = Depends(database.get_db)
):
    """Endpoint para activar la verificación manual o por cron"""
    try:
        count = check_inactivity(db)
        return {"status": "ok", "alertas_generadas": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/notificaciones", response_class=HTMLResponse)
async def ver_notificaciones(
    request: Request,
    filtro_agente_id: str = Query(None),
    db: Session = Depends(database.get_db)
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    
    # Trigger inactividad check al cargar (para asegurar alertas frescas)
    check_inactivity(db)
    
    query = db.query(models.Notificacion).filter(
        models.Notificacion.leida == False
    )
    
    if user.tipo_usuario == TipoUsuario.AGENTE.value:
        query = query.filter(models.Notificacion.usuario_id == user.id)
    elif filtro_agente_id and filtro_agente_id != "todos":
        query = query.filter(models.Notificacion.usuario_id == int(filtro_agente_id))
        
    notificaciones = query.order_by(models.Notificacion.fecha_creacion.desc()).all()
    
    # Calcular tiempos
    for n in notificaciones:
        if n.fecha_programada:
            delta = n.fecha_programada - datetime.now()
            # Formatear tiempo restante
            dias = delta.days
            horas, resto = divmod(delta.seconds, 3600)
            minutos, _ = divmod(resto, 60)
            
            if delta.total_seconds() > 0:
                if dias > 0:
                    n.tiempo_restante_str = f"{dias}d {horas}h"
                else:
                    n.tiempo_restante_str = f"{horas}h {minutos}m"
                n.es_tarde = False
            else:
                n.tiempo_restante_str = "Vencida"
                n.es_tarde = True
        else:
            delta = datetime.now() - n.fecha_creacion
            dias = delta.days
            horas, resto = divmod(delta.seconds, 3600)
            n.tiempo_restante_str = f"Hace {dias}d {horas}h" if dias > 0 else f"Hace {horas}h"
            n.es_tarde = False
            
    agentes = []
    if user.tipo_usuario in [TipoUsuario.ADMINISTRADOR.value, TipoUsuario.SUPERVISOR.value]:
        agentes = db.query(models.Usuario).filter(models.Usuario.tipo_usuario == TipoUsuario.AGENTE.value).all()
        
    return templates.TemplateResponse("notificaciones.html", {
        "request": request,
        "current_user": user,
        "notificaciones": notificaciones,
        "agentes": agentes,
        "filtro_agente_id": filtro_agente_id
    })

@app.post("/notificaciones/{notificacion_id}/leer")
async def marcar_notificacion_leida(
    notificacion_id: int,
    db: Session = Depends(database.get_db),
    request: Request = None 
):
    notif = db.query(models.Notificacion).filter(models.Notificacion.id == notificacion_id).first()
    if notif:
        notif.leida = True
        db.commit()
    
    return RedirectResponse(url="/notificaciones", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")