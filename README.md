# ✈️ ZARITA! - Sistema de Gestión de Prospectos

Bienvenido a **ZARITA!**, una aplicación web moderna diseñada para optimizar la gestión de prospectos y clientes en agencias de viajes. Este sistema permite realizar un seguimiento detallado de cada oportunidad de venta, desde el primer contacto hasta el cierre, facilitando la colaboración entre agentes y supervisores.

## 🚀 Características Principales

### 📊 Dashboard Interactivo
- **Vista General:** Resumen en tiempo real de prospectos por estado (Nuevos, Seguimiento, Cotizados, Ganados, Perdidos).
- **KPIs:** Conversión por agente y destinos más solicitados.
- **Filtros Temporales:** Visualización de datos por día, semana, mes, año o rangos personalizados.

### 👥 Gestión de Prospectos
- **Pipeline de Ventas:** Flujo de trabajo claro con estados definidos.
- **Asignación de Leads:** Distribución de prospectos a agentes (manual o filtro de "Nuevos").
- **Historial Completo:** Registro automático de interacciones, cambios de estado y notas.
- **Integración con WhatsApp:** Enlaces directos para iniciar conversaciones con clientes.

### 📝 Seguimiento y Documentación
- **Bitácora de Interacciones:** Registro de llamadas, correos y mensajes.
- **Gestión de Archivos:** Carga y almacenamiento de cotizaciones y documentos del cliente.
- **Alertas de Seguimiento:** Identificación rápida de prospectos que requieren atención.

### 🛡️ Roles y Seguridad
- **Administrador/Supervisor:** Acceso total a métricas, reasignación de leads y gestión de usuarios.
- **Agente:** Vista enfocada en sus prospectos asignados y herramientas de venta diaria.

---

## 🛠️ Tecnologías Utilizadas

- **Backend:** Python 3.9+ con [FastAPI](https://fastapi.tiangolo.com/).
- **Base de Datos:** SQLite con SQLAlchemy ORM.
- **Frontend:** HTML5, Jinja2 Templates, Bootstrap 5.
- **Servidor:** Uvicorn.

---

## 🔧 Instalación y Configuración

Sigue estos pasos para desplegar la aplicación en tu entorno local:

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/prospectos_app.git
cd prospectos_app
```

### 2. Crear Entorno Virtual (Recomendado)
```bash
# En Windows
python -m venv venv
.\venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Inicializar Base de Datos (Opcional)
El sistema creará automáticamente el archivo `prospectos.db` al iniciar, pero si deseas cargar datos de prueba:
```bash
python generar_datos_prueba.py
```

### 5. Ejecutar la Aplicación
```bash
uvicorn main:app --reload
```
La aplicación estará disponible en: `http://127.0.0.1:8000`

---

## 📖 Guía de Uso Rápida

1.  **Ingreso:** Inicia sesión con tus credenciales. (Usuarios por defecto creados por el script de prueba: `admin` / `admin`).
2.  **Crear Prospecto:** Usa el botón "Nuevo Prospecto" en la barra superior.
3.  **Gestionar:** Haz clic en "📋" para ver el detalle y registrar seguimiento.
4.  **Cerrar Venta:** Cambia el estado a "Ganado" cuando se concrete el viaje.

---

## 📂 Estructura del Proyecto

```text
prospectos_app/
├── main.py                 # Punto de entrada de la aplicación
├── models.py               # Modelos de base de datos (SQLAlchemy)
├── database.py             # Configuración de conexión a BD
├── auth.py                 # Lógica de autenticación
├── requirements.txt        # Dependencias del proyecto
├── templates/              # Plantillas HTML (Jinja2)
│   ├── base.html           # Layout principal
│   ├── dashboard.html      # Panel de control
│   └── ...
├── static/                 # Archivos estáticos (CSS, JS, Imágenes)
├── uploads/                # Directorio de almacenamiento de documentos
└── prospectos.db           # Base de datos SQLite
```

---

Desarrollado para **ZARITA! Travel Agency**.
