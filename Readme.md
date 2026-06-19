# TrackSIM Tools

**TrackSIM Tools** es una suite completa de escritorio diseñada para gestionar, extraer y convertir reportes generados por simuladores. Con una interfaz moderna y oscura construida sobre `CustomTkinter`, la aplicación centraliza varias herramientas en un solo lugar.

## Características Principales

La aplicación está dividida en tres pestañas principales:

1. **Convertir:**
   - Permite seleccionar una carpeta de origen (con archivos `.csv`) y una carpeta de destino.
   - Convierte los reportes a formatos **Excel** y **PDF**.
   - Opción para limpiar de forma segura las carpetas de salida (`Converted` y `MinorReport`) antes de procesar.
   - Panel de Progreso y visualización de Log en tiempo real.

2. **Importar:**
   - Facilita la importación y validación de plantillas o sesiones, actualizando la base de datos de los reportes.
   - Generación de rutas y reestructuración de archivos del sistema.

3. **Data:**
   - Herramienta para conectarse directamente a la base de datos PostgreSQL.
   - Permite consultar y descargar sesiones en un rango de fechas especificado.
   - Soporte para incluir o excluir usuarios anónimos.

## Instalación y Uso

Para utilizar esta herramienta de forma directa, descarga el archivo ejecutable `TrackSIM Tools.exe` (cuando esté disponible en releases) y ejecútalo. No se necesita instalación adicional.

1.  Abre la aplicación haciendo doble clic en `TrackSIM Tools.exe`.
2.  Navega entre las pestañas según lo que necesites realizar y sigue las instrucciones en pantalla.

## Entorno de Desarrollo (Building)

Si deseas compilar la aplicación desde el código fuente o hacer modificaciones:

1.  Clona el repositorio:
    ```bash
    git clone https://github.com/tu-usuario/tu-repositorio.git
    cd tu-repositorio
    ```

2.  Crea un entorno virtual e instala las dependencias:
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```

3.  Abrir la versión de desarrollo:
    ```bash
    python main.py
    ```

4.  Construye el ejecutable final:
    ```bash
    python build.py 
    ```
    Este comando ejecuta PyInstaller bajo el archivo `convertidor_reportes.spec`, generando la carpeta `dist/` con el nuevo `TrackSIM Tools.exe` listo para distribuir.

## Licencia

Este proyecto no tiene una licencia especificada.