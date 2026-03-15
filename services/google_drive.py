import os
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Scopes requeridos para Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'google_credentials.json'

def get_drive_service():
    """Autentica la cuenta de servicio y retorna el objeto del servicio."""
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            import json
            # Cargar desde variable de entorno (Render)
            info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES)
        elif os.path.exists(CREDENTIALS_FILE):
            # Cargar desde archivo local (Desarrollo)
            creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=SCOPES)
        else:
            print(f"⚠️ ¡Atención! Falta el archivo {CREDENTIALS_FILE} o la variable GOOGLE_CREDENTIALS_JSON.")
            return None
            
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error autenticando con Google Drive: {e}")
        return None

def upload_to_drive(file_data: bytes, filename: str, mime_type: str, folder_id: str = None) -> str:
    """
    Sube un archivo a Google Drive y devuelve el ID del archivo.
    """
    service = get_drive_service()
    if not service:
        return None
        
    try:
        # Metadatos del archivo
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        # Preparar los bytes del archivo para subir
        media = MediaIoBaseUpload(BytesIO(file_data), mimetype=mime_type, resumable=True)
        
        # Subir
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        # Compartir para que cualquier persona con el link (o al menos nosotros) pueda verlo después
        try:
            service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except:
            pass # Si falla al dar permisos publicos, igual retornamos el ID
            
        return file.get('id')
    except Exception as e:
        print(f"Error subiendo archivo a Drive: {e}")
        return None

def get_file_url(file_id: str) -> str:
    """Retorna la URL de visualización en Drive"""
    return f"https://drive.google.com/file/d/{file_id}/view"

def delete_from_drive(file_id: str) -> bool:
    """Elimina un archivo de Google Drive dado su ID."""
    service = get_drive_service()
    if not service:
        return False
        
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception as e:
        print(f"Error borrando archivo de Drive: {e}")
        return False
