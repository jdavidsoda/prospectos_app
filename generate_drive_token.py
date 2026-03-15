import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Permisos completos de Drive para subir y borrar
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    """Muestra el flujo de login de Google y guarda el token.json"""
    creds = None
    
    # El archivo token.json almacena los tokens de acceso y actualización del usuario
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # Si no hay credenciales (o no son válidas), pedir inicio de sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refrescando el token...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ ERROR: No se encontró 'credentials.json'.")
                print("Por favor, descarga tu Cliente OAuth desde Google Cloud Console y nómbralo credentials.json")
                return
                
            print("🌐 Abriendo el navegador para autorizar la cuenta de Google...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guardar las credenciales para la próxima vez
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ ¡ÉXITO! El archivo token.json ha sido generado correctamente.")
    print("\n" + "="*50)
    print("INSTRUCCIONES PARA RENDER:")
    print("1. Abre el nuevo archivo 'token.json' que se acaba de crear.")
    print("2. Copia TODO su contenido.")
    print("3. Ve a Render -> Tu Web Service -> Environment Variables")
    print("4. Crea una variable llamada: GOOGLE_OAUTH_TOKEN_JSON")
    print("5. Pega el contenido como el valor de esa variable, y guarda.")
    print("="*50 + "\n")

if __name__ == '__main__':
    main()
