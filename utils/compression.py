import os
from io import BytesIO
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter

def comprimir_imagen(archivo_bytes: bytes, formato: str, calidad: int = 70, max_dimension: int = 1920) -> bytes:
    """
    Comprime una imagen reduciendo su calidad y, si es necesario, su resolución máxima.
    Formatos soportados: JPEG, PNG, WEBP.
    """
    try:
        # Abrir imagen desde bytes
        img = Image.open(BytesIO(archivo_bytes))
        
        # Convertir a RGB si es necesario (ej. PNG con transparencia a JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Redimensionar si es muy grande manteniendo la proporción
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int((height / width) * max_dimension)
            else:
                new_height = max_dimension
                new_width = int((width / height) * max_dimension)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Guardar en memoria
        output = BytesIO()
        # Si es PNG y queremos comprimir de verdad, a menudo es mejor pasarlo a WEBP o JPEG
        # Pero respetamos el formato original lo más posible
        if formato.upper() == "PNG":
            # PNG no usa "quality" de la misma forma, usamos optimize
            img.save(output, format="PNG", optimize=True)
        else:
            save_format = formato.upper() if formato.upper() != "JPG" else "JPEG"
            img.save(output, format=save_format, quality=calidad, optimize=True)
            
        return output.getvalue()
    except Exception as e:
        print(f"Error comprimiendo imagen: {e}")
        return archivo_bytes  # Devuelve original si falla

def comprimir_pdf(archivo_bytes: bytes) -> bytes:
    """
    Desactivado temporalmente.
    PyPDF2 a menudo corrompe o blanquea PDFs que son puramente imágenes escaneadas
    al intentar reescribirlos. Es más seguro subir el PDF original de momento.
    """
    return archivo_bytes

def procesar_archivo_para_subida(archivo_bytes: bytes, filename: str) -> bytes:
    """
    Recibe los bytes de un archivo y su nombre, determina si se puede comprimir y lo hace.
    Devuelve los bytes (optimizados o los originales).
    """
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
        # Comprimir imagen
        formato = "JPEG" if ext in ['.jpg', '.jpeg'] else ext.replace(".", "").upper()
        return comprimir_imagen(archivo_bytes, formato)
        
    elif ext == '.pdf':
        # Intentar optimizar PDF
        return comprimir_pdf(archivo_bytes)
        
    else:
        # Word, Excel, etc (ya están comprimidos o no soportados)
        return archivo_bytes
