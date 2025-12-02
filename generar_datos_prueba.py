import sys
import os
from datetime import datetime, timedelta
import random

# Agregar el directorio actual al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar después de agregar al path
from database import SessionLocal, engine, migrate_database, create_tables
from models import Base, Prospecto, Usuario, MedioIngreso, EstadoProspecto, TipoUsuario, EstadisticaCotizacion, HistorialEstado, Interaccion, Documento
from auth import get_password_hash
from sqlalchemy import func

def crear_datos_prueba():
    db = SessionLocal()
    
    try:
        print("🗃️ Creando datos de prueba avanzados...")
        
        # ✅ PRIMERO CREAR LAS TABLAS SI NO EXISTEN
        print("📋 Creando/actualizando tablas en la base de datos...")
        try:
            create_tables()
            migrate_database()
        except Exception as e:
            print(f"⚠️ Error en creación/migración: {e}")
            print("⚠️ Continuando con datos existentes...")
        
        print("✅ Base de datos lista")
        
        # Verificar si ya existen datos de prueba
        try:
            prospecto_count = db.query(Prospecto).count()
            if prospecto_count > 50:  # Si ya hay más de 50 prospectos, no crear más
                print(f"✅ Ya existen {prospecto_count} prospectos en la base de datos")
                return
        except Exception as e:
            print("ℹ️ Tabla de prospectos vacía, continuando con creación de datos...")
        
        # Crear medios de ingreso si no existen
        medios = ["REDES", "TEL TRAVEL", "RECOMPRA", "REFERIDO", "FIDELIZACION", "GOOGLE ADS", "FACEBOOK", "INSTAGRAM", "RECOMENDACIÓN"]
        for medio in medios:
            if not db.query(MedioIngreso).filter(MedioIngreso.nombre == medio).first():
                db.add(MedioIngreso(nombre=medio))
        db.commit()
        
        # Crear agentes de prueba si no existen
        agentes_data = [
            {"username": "maria_garcia", "email": "maria@agencia.com", "password": "agente123"},
            {"username": "carlos_rodriguez", "email": "carlos@agencia.com", "password": "agente123"},
            {"username": "ana_martinez", "email": "ana@agencia.com", "password": "agente123"},
            {"username": "javier_lopez", "email": "javier@agencia.com", "password": "agente123"},
            {"username": "laura_sanchez", "email": "laura@agencia.com", "password": "agente123"},
            {"username": "pedro_gomez", "email": "pedro@agencia.com", "password": "agente123"}
        ]
        
        agentes = []
        for agente_data in agentes_data:
            agente = db.query(Usuario).filter(Usuario.username == agente_data["username"]).first()
            if not agente:
                agente = Usuario(
                    username=agente_data["username"],
                    email=agente_data["email"],
                    hashed_password=get_password_hash(agente_data["password"]),
                    tipo_usuario=TipoUsuario.AGENTE.value
                )
                db.add(agente)
                db.commit()
                db.refresh(agente)
            agentes.append(agente)
        
        print(f"👥 {len(agentes)} agentes creados")
        
        # Datos realistas para agencia de viajes
        destinos = [
            "Cancún, México", "Punta Cana, República Dominicana", "Cartagena, Colombia",
            "Madrid, España", "Roma, Italia", "París, Francia", "Barcelona, España",
            "Buenos Aires, Argentina", "Rio de Janeiro, Brasil", "Miami, USA",
            "Orlando, USA", "Los Ángeles, USA", "Londres, UK", "Tokio, Japón",
            "Bali, Indonesia", "Phuket, Tailandia", "Dubai, UAE", "Lisboa, Portugal",
            "New York, USA", "Santiago, Chile", "Montevideo, Uruguay", "Lima, Perú",
            "Ciudad de México, México", "San José, Costa Rica", "Panamá, Panamá",
            "San Andrés, Colombia", "Santa Marta, Colombia", "San Bernardo, Colombia"
        ]
        
        ciudades_origen = [
            "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
            "Bucaramanga", "Pereira", "Manizales", "Cúcuta", "Santa Marta",
            "Villavicencio", "Ibagué", "Neiva", "Popayán", "Montería"
        ]
        
        nombres = [
            "Ana", "Carlos", "María", "José", "Laura", "Miguel", "Sofia", "David",
            "Elena", "Fernando", "Gabriela", "Héctor", "Isabel", "Javier", "Karen",
            "Luis", "Mónica", "Nicolás", "Olga", "Pablo", "Rosa", "Santiago", "Tatiana",
            "Andrea", "Beatriz", "Camilo", "Daniel", "Esteban", "Felipe", "Gloria",
            "Hugo", "Iván", "Julia", "Kevin", "Leonardo", "Martha", "Natalia", "Óscar",
            "Patricia", "Raúl", "Silvia", "Tomás", "Valentina", "Walter", "Ximena",
            "Yolanda", "Zacarías"
        ]
        
        apellidos = [
            "García", "Rodríguez", "Martínez", "López", "González", "Pérez", "Sánchez",
            "Ramírez", "Torres", "Flórez", "Díaz", "Hernández", "Moreno", "Muñoz",
            "Alvarez", "Romero", "Suarez", "Castillo", "Jiménez", "Ortega", "Rojas",
            "Vargas", "Castro", "Mendoza", "Silva", "Reyes", "Morales", "Ortiz",
            "Delgado", "Cruz", "Navarro", "Iglesias", "Medina", "Guerrero", "Ríos"
        ]
        
        # ✅ CREAR LISTA DE TELÉFONOS PARA CLIENTES RECURRENTES
        telefonos_recurrentes = []
        for _ in range(30):  # 30 teléfonos para clientes recurrentes
            telefono = f"3{random.randint(10,99)}{random.randint(1000000,9999999)}"
            telefonos_recurrentes.append(telefono)
        
        # ✅ FUNCIÓN PARA VERIFICAR DATOS COMPLETOS
        def verificar_datos_completos(prospecto):
            """Determina si un prospecto tiene datos completos"""
            tiene_email = bool(prospecto.correo_electronico and prospecto.correo_electronico.strip())
            tiene_fechas = bool(prospecto.fecha_ida)
            tiene_pasajeros = bool(prospecto.pasajeros_adultos > 1 or prospecto.pasajeros_ninos > 0 or prospecto.pasajeros_infantes > 0)
            tiene_destino = bool(prospecto.destino and prospecto.destino.strip())
            tiene_origen = bool(prospecto.ciudad_origen and prospecto.ciudad_origen.strip())
            
            return tiene_email or tiene_fechas or tiene_pasajeros or tiene_destino or tiene_origen
        
        # ✅ GENERAR 300 PROSPECTOS
        print(f"👤 Generando 300 prospectos con distribución realista...")
        
        prospectos = []
        clientes_recurrentes = {}  # Diccionario para trackear clientes recurrentes
        
        for i in range(1, 301):
            # Determinar si es cliente recurrente (15% de probabilidad)
            es_recurrente = random.random() < 0.15 and i > 30  # Solo después de los primeros 30
            
            # Fechas aleatorias en los últimos 60 días
            dias_atras = random.randint(0, 60)
            fecha_registro = datetime.now() - timedelta(days=dias_atras)
            
            # Estado aleatorio con distribución realista
            estados_distribucion = [
                (EstadoProspecto.NUEVO.value, 0.25),           # 25% nuevos
                (EstadoProspecto.EN_SEGUIMIENTO.value, 0.35), # 35% en seguimiento
                (EstadoProspecto.COTIZADO.value, 0.20),       # 20% cotizados
                (EstadoProspecto.GANADO.value, 0.12),         # 12% ganados
                (EstadoProspecto.CERRADO_PERDIDO.value, 0.08) # 8% perdidos
            ]
            
            estados = [e[0] for e in estados_distribucion]
            pesos = [e[1] for e in estados_distribucion]
            estado = random.choices(estados, weights=pesos)[0]
            
            # Agente aleatorio (algunos sin asignar)
            agente_asignado = random.choice(agentes + [None] * 3)  # 1/4 sin asignar
            
            # ✅ DETERMINAR SI TIENE DATOS COMPLETOS (70% con datos, 30% solo teléfono)
            tiene_datos = random.random() < 0.7
            
            # Datos para prospecto
            nombre = random.choice(nombres) if tiene_datos or random.random() < 0.5 else None
            apellido = random.choice(apellidos) if nombre else None
            correo = None
            if tiene_datos and random.random() < 0.8:
                if nombre and apellido:
                    correo = f"{nombre.lower()}.{apellido.lower()}{random.randint(10,99)}@gmail.com"
                else:
                    correo = f"cliente.viajero{random.randint(100,999)}@gmail.com"
            
            # Teléfono - si es recurrente, usar teléfono existente
            if es_recurrente and telefonos_recurrentes:
                telefono = random.choice(telefonos_recurrentes)
                # Registrar que este cliente ya ha hecho solicitudes previas
                if telefono not in clientes_recurrentes:
                    clientes_recurrentes[telefono] = []
                clientes_recurrentes[telefono].append(i)
            else:
                telefono = f"3{random.randint(10,99)}{random.randint(1000000,9999999)}"
            
            # Ciudad origen y destino (solo si tiene datos)
            ciudad_origen = random.choice(ciudades_origen) if tiene_datos and random.random() < 0.8 else None
            destino = random.choice(destinos) if tiene_datos and random.random() < 0.8 else None
            
            # Fechas de viaje (solo si tiene datos)
            if tiene_datos and random.random() < 0.6:
                fecha_ida = (datetime.now() + timedelta(days=random.randint(30, 365))).date()
                fecha_vuelta = (fecha_ida + timedelta(days=random.randint(5, 21))) if random.random() < 0.7 else None
            else:
                fecha_ida = None
                fecha_vuelta = None
            
            # Pasajeros (solo si tiene datos)
            if tiene_datos:
                pasajeros_adultos = random.randint(1, 6)
                pasajeros_ninos = random.randint(0, 3) if random.random() < 0.4 else 0
                pasajeros_infantes = random.randint(0, 2) if random.random() < 0.2 else 0
            else:
                pasajeros_adultos = 1
                pasajeros_ninos = 0
                pasajeros_infantes = 0
            
            # Observaciones (solo si tiene datos)
            observaciones = None
            if tiene_datos and random.random() < 0.5:
                observaciones_opciones = [
                    "Cliente interesado en todo incluido",
                    "Busca mejores tarifas",
                    "Viaje familiar",
                    "Luna de miel",
                    "Viaje de negocios",
                    "Presupuesto ajustado",
                    "Flexible en fechas",
                    "Requiere visa",
                    "Primer viaje internacional",
                    "Cliente frecuente",
                    "Interesado en excursiones",
                    "Prefiere hotel todo incluido",
                    "Busca vuelos directos",
                    "Viaje con niños pequeños",
                    "Aniversario de bodas"
                ]
                observaciones = random.choice(observaciones_opciones)
            
            # Determinar prospecto original si es recurrente
            prospecto_original_id = None
            if es_recurrente and telefono in clientes_recurrentes and len(clientes_recurrentes[telefono]) > 1:
                # El primer prospecto con este teléfono es el original
                primer_prospecto_id = clientes_recurrentes[telefono][0]
                if primer_prospecto_id != i:
                    prospecto_original_id = primer_prospecto_id
            
            # Crear prospecto
            prospecto = Prospecto(
                nombre=nombre,
                apellido=apellido,
                correo_electronico=correo,
                telefono=telefono,
                indicativo_telefono="57",
                telefono_secundario=f"3{random.randint(10,99)}{random.randint(1000000,9999999)}" if random.random() > 0.7 else None,
                indicativo_telefono_secundario="57" if random.random() > 0.7 else None,
                ciudad_origen=ciudad_origen,
                destino=destino,
                fecha_ida=fecha_ida,
                fecha_vuelta=fecha_vuelta,
                pasajeros_adultos=pasajeros_adultos,
                pasajeros_ninos=pasajeros_ninos,
                pasajeros_infantes=pasajeros_infantes,
                medio_ingreso_id=random.randint(1, len(medios)),
                observaciones=observaciones,
                agente_asignado_id=agente_asignado.id if agente_asignado else None,
                estado=estado,
                cliente_recurrente=es_recurrente,
                prospecto_original_id=prospecto_original_id,
                fecha_registro=fecha_registro,
                tiene_datos_completos=tiene_datos  # ✅ Asignar clasificación de datos
            )
            
            db.add(prospecto)
            
            # Mostrar progreso cada 50 prospectos
            if i % 50 == 0:
                print(f"   ✅ {i} prospectos creados...")
                db.commit()  # Commit parcial para no perder todo si hay error
        
        db.commit()
        print(f"✅ {len(prospectos)} prospectos creados exitosamente")
        
        # Ahora necesitamos actualizar los IDs de cliente
        print("🆔 Generando IDs de cliente únicos...")
        todos_prospectos = db.query(Prospecto).all()
        for prospecto in todos_prospectos:
            if not prospecto.id_cliente:
                prospecto.generar_id_cliente()
        db.commit()
        print("✅ IDs de cliente generados")
        
        # ✅ CREAR INTERACCIONES REALISTAS
        print("💬 Generando interacciones...")
        tipos_interaccion = ["llamada", "email", "whatsapp", "reunion", "general"]
        
        for prospecto in random.sample(todos_prospectos, min(200, len(todos_prospectos))):  # 200 prospectos con interacciones
            num_interacciones = random.randint(1, 5)
            
            for j in range(num_interacciones):
                # Fecha de interacción (después de fecha registro)
                dias_desde_registro = (datetime.now() - prospecto.fecha_registro).days
                if dias_desde_registro > 0:
                    dias_interaccion = random.randint(1, dias_desde_registro)
                    fecha_interaccion = prospecto.fecha_registro + timedelta(days=dias_interaccion)
                    
                    interaccion = Interaccion(
                        prospecto_id=prospecto.id,
                        usuario_id=prospecto.agente_asignado_id or random.choice(agentes).id,
                        tipo_interaccion=random.choice(tipos_interaccion),
                        descripcion=random.choice([
                            "Llamada de seguimiento al cliente",
                            "Enviada información solicitada",
                            "Cotización enviada por email",
                            "Reunión virtual para detalles del viaje",
                            "Confirmación de disponibilidad",
                            "Seguimiento post-cotización",
                            "Aclaración de dudas sobre el paquete",
                            "Negociación de precios"
                        ]),
                        fecha_creacion=fecha_interaccion,
                        estado_anterior=prospecto.estado,
                        estado_nuevo=prospecto.estado
                    )
                    db.add(interaccion)
        
        db.commit()
        print(f"✅ Interacciones generadas")
        
        # ✅ CREAR ESTADÍSTICAS DE COTIZACIONES
        print("📊 Generando estadísticas de cotizaciones...")
        
        # Prospectos que están cotizados o ganados
        prospectos_cotizados = [p for p in todos_prospectos if p.estado in [
            EstadoProspecto.COTIZADO.value, 
            EstadoProspecto.GANADO.value
        ]]
        
        if prospectos_cotizados:
            for prospecto in random.sample(prospectos_cotizados, min(80, len(prospectos_cotizados))):
                if prospecto.agente_asignado_id:
                    # Fecha de cotización (entre fecha registro y hoy)
                    dias_desde_registro = (datetime.now().date() - prospecto.fecha_registro.date()).days
                    if dias_desde_registro > 0:
                        dias_aleatorios = random.randint(1, dias_desde_registro)
                        fecha_cotizacion = prospecto.fecha_registro.date() + timedelta(days=dias_aleatorios)
                        
                        estadistica = EstadisticaCotizacion(
                            agente_id=prospecto.agente_asignado_id,
                            prospecto_id=prospecto.id,
                            fecha_cotizacion=fecha_cotizacion
                        )
                        db.add(estadistica)
            
            db.commit()
            
            # Generar IDs de cotización
            estadisticas = db.query(EstadisticaCotizacion).filter(EstadisticaCotizacion.id_cotizacion == None).all()
            for estadistica in estadisticas:
                estadistica.generar_id_cotizacion()
            db.commit()
            
            print(f"✅ {len(prospectos_cotizados)} estadísticas de cotizaciones generadas")
        
        # ✅ CREAR DOCUMENTOS (COTIZACIONES)
        print("📄 Generando documentos...")
        
        # Prospectos con cotizaciones
        prospectos_con_documentos = [p for p in todos_prospectos if p.estado in [
            EstadoProspecto.COTIZADO.value, 
            EstadoProspecto.GANADO.value
        ]]
        
        if prospectos_con_documentos:
            for prospecto in random.sample(prospectos_con_documentos, min(50, len(prospectos_con_documentos))):
                # Fecha de subida
                dias_desde_registro = (datetime.now() - prospecto.fecha_registro).days
                if dias_desde_registro > 0:
                    dias_documento = random.randint(1, dias_desde_registro)
                    fecha_subida = prospecto.fecha_registro + timedelta(days=dias_documento)
                    
                    documento = Documento(
                        prospecto_id=prospecto.id,
                        usuario_id=prospecto.agente_asignado_id or random.choice(agentes).id,
                        nombre_archivo=f"Cotizacion_{prospecto.destino or 'Viaje'}_{random.randint(1000,9999)}.pdf",
                        tipo_documento="cotizacion",
                        ruta_archivo=f"/uploads/prospecto_{prospecto.id}/cotizacion_{random.randint(1000,9999)}.pdf",
                        fecha_subida=fecha_subida,
                        descripcion=f"Cotización para viaje a {prospecto.destino or 'destino'}"
                    )
                    db.add(documento)
            
            db.commit()
            
            # Generar IDs de documento
            documentos = db.query(Documento).filter(Documento.id_documento == None).all()
            for documento in documentos:
                documento.generar_id_documento()
            db.commit()
            
            print(f"✅ {min(50, len(prospectos_con_documentos))} documentos generados")
        
        # ✅ CREAR HISTORIAL DE ESTADOS
        print("🔄 Generando historial de estados...")
        
        for prospecto in random.sample(todos_prospectos, min(150, len(todos_prospectos))):
            # Simular cambios de estado
            estados_secuencia = [EstadoProspecto.NUEVO.value]
            
            if prospecto.estado != EstadoProspecto.NUEVO.value:
                estados_secuencia.append(EstadoProspecto.EN_SEGUIMIENTO.value)
            
            if prospecto.estado in [EstadoProspecto.COTIZADO.value, EstadoProspecto.GANADO.value]:
                estados_secuencia.append(EstadoProspecto.COTIZADO.value)
            
            if prospecto.estado == EstadoProspecto.GANADO.value:
                estados_secuencia.append(EstadoProspecto.GANADO.value)
            elif prospecto.estado == EstadoProspecto.CERRADO_PERDIDO.value:
                estados_secuencia.append(EstadoProspecto.CERRADO_PERDIDO.value)
            
            # Crear historial para cada cambio
            fecha_base = prospecto.fecha_registro
            for i in range(1, len(estados_secuencia)):
                dias_cambio = random.randint(1, 7)
                fecha_cambio = fecha_base + timedelta(days=dias_cambio)
                
                historial = HistorialEstado(
                    prospecto_id=prospecto.id,
                    estado_anterior=estados_secuencia[i-1],
                    estado_nuevo=estados_secuencia[i],
                    usuario_id=prospecto.agente_asignado_id or random.choice(agentes).id,
                    fecha_cambio=fecha_cambio,
                    comentario=random.choice([
                        "Contacto inicial con cliente",
                        "Seguimiento iniciado",
                        "Cotización enviada",
                        "Venta concretada - ¡Felicidades!",
                        "Cliente no respondió después de múltiples intentos"
                    ])
                )
                db.add(historial)
                fecha_base = fecha_cambio
        
        db.commit()
        print(f"✅ Historial de estados generado")
        
        # ✅ RESULTADOS FINALES
        print("\n" + "="*60)
        print("📈 RESUMEN COMPLETO DE DATOS GENERADOS")
        print("="*60)
        
        total_prospectos = db.query(Prospecto).count()
        print(f"👤 Total prospectos: {total_prospectos}")
        
        # Prospectos por estado
        prospectos_por_estado = db.query(Prospecto.estado, func.count(Prospecto.id)).group_by(Prospecto.estado).all()
        print(f"📊 Prospectos por estado:")
        for estado, count in prospectos_por_estado:
            print(f"   - {estado.replace('_', ' ').title()}: {count}")
        
        # Clasificación por datos
        con_datos = db.query(Prospecto).filter(Prospecto.tiene_datos_completos == True).count()
        sin_datos = db.query(Prospecto).filter(Prospecto.tiene_datos_completos == False).count()
        print(f"📝 Clasificación por datos:")
        print(f"   - Con datos completos: {con_datos}")
        print(f"   - Solo teléfono: {sin_datos}")
        
        # Clientes recurrentes
        recurrentes = db.query(Prospecto).filter(Prospecto.cliente_recurrente == True).count()
        print(f"🔄 Clientes recurrentes: {recurrentes}")
        
        # Sin asignar
        sin_asignar = db.query(Prospecto).filter(Prospecto.agente_asignado_id == None).count()
        print(f"👥 Prospectos sin asignar: {sin_asignar}")
        
        # Cotizaciones y documentos
        total_cotizaciones = db.query(EstadisticaCotizacion).count()
        total_documentos = db.query(Documento).count()
        total_interacciones = db.query(Interaccion).count()
        
        print(f"💰 Total cotizaciones registradas: {total_cotizaciones}")
        print(f"📄 Total documentos: {total_documentos}")
        print(f"💬 Total interacciones: {total_interacciones}")
        print(f"👤 Agentes disponibles: {len(agentes)}")
        
        # Distribución por mes
        hoy = datetime.now()
        mes_actual = hoy.replace(day=1)
        mes_pasado = (mes_actual - timedelta(days=1)).replace(day=1)
        
        prospectos_mes_actual = db.query(Prospecto).filter(
            Prospecto.fecha_registro >= mes_actual
        ).count()
        
        prospectos_mes_pasado = db.query(Prospecto).filter(
            Prospecto.fecha_registro >= mes_pasado,
            Prospecto.fecha_registro < mes_actual
        ).count()
        
        print(f"📅 Distribución temporal:")
        print(f"   - Este mes: {prospectos_mes_actual}")
        print(f"   - Mes pasado: {prospectos_mes_pasado}")
        print(f"   - Mes anterior: {total_prospectos - prospectos_mes_actual - prospectos_mes_pasado}")
        
        print("="*60)
        print("\n🎯 DATOS DE PRUEBA PARA LOGIN:")
        print("👨‍💼 Admin: admin / admin123")
        for agente in agentes[:3]:  # Mostrar solo 3 agentes
            print(f"👤 Agente: {agente.username} / agente123")
        print(f"... y {len(agentes)-3} agentes más")
        
        print("\n📊 CARACTERÍSTICAS DE LOS DATOS GENERADOS:")
        print("• 300 prospectos en total")
        print("• Distribuidos en los últimos 60 días")
        print("• 15% clientes recurrentes con múltiples solicitudes")
        print("• 70% con datos completos, 30% solo con teléfono")
        print("• Estados distribuidos realísticamente")
        print("• Interacciones, documentos y cotizaciones realistas")
        print("\n¡Datos de prueba creados exitosamente! 🎉")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creando datos de prueba: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    crear_datos_prueba()
