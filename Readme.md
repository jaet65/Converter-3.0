# TrackSIM Tools

**TrackSIM Tools** es una suite completa de escritorio diseñada para gestionar, extraer y convertir reportes generados por simuladores. Con una interfaz moderna y oscura construida sobre `CustomTkinter`, la aplicación centraliza varias herramientas en un solo lugar.

## Características Principales

La aplicación está dividida en tres pestañas principales:

1. **Data:**
   - Herramienta para conectarse directamente a la base de datos PostgreSQL.
   - Permite consultar y descargar sesiones en un rango de fechas especificado.
   - Soporte para incluir o excluir usuarios anónimos.

2. **Convertir:**
   - Permite seleccionar una carpeta de origen (con archivos `.csv`) y una carpeta de destino.
   - Convierte los reportes a formatos **Excel** y **PDF**.
   - Opción para limpiar de forma segura las carpetas de salida (`Converted` y `MinorReport`) antes de procesar.
   - Panel de Progreso y visualización de Log en tiempo real.

3. **Importar:**
   - Facilita la importación y validación de plantillas o sesiones, actualizando la base de datos de los reportes.
   - Generación de rutas y reestructuración de archivos del sistema.

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

## Automatización y Despliegue (CI/CD)

Este proyecto utiliza GitHub Actions para automatizar el proceso de construcción y liberación de la aplicación.

### Flujo de Trabajo (Workflow)

El flujo de trabajo se define en el archivo `.github/workflows/release.yml` y consta de dos trabajos principales: `build` y `release`.

#### 1. Construcción Automática (`build`)

-   **Disparador**: Se activa automáticamente con cada `push` a la rama `main` o al crear un `tag` que comience con `v*`.
-   **Proceso**:
    1.  El entorno se configura en una máquina virtual con `windows-latest`.
    2.  Se instala Python 3.9 y las dependencias del proyecto listadas en `requirements.txt`.
    3.  Se ejecuta el script `python build.py` para compilar la aplicación con PyInstaller.
    4.  El ejecutable resultante y otros archivos de la carpeta `dist/` se empaquetan y suben como un artefacto llamado `dist`.

#### 2. Creación de Releases (`release`)

-   **Disparador**: Se activa solo cuando se crea un nuevo `tag` con el formato `v*` (ej. `v1.0.25`).
-   **Proceso**:
    1.  Depende del trabajo `build` para asegurarse de que la construcción fue exitosa.
    2.  Descarga el artefacto `dist` que contiene el ejecutable.
    3.  Utiliza la herramienta `gh release create` para crear una nueva "Release" en GitHub.
    4.  El título y el nombre de la release se basan en el nombre del `tag`.
    5.  El archivo `dist/TrackSIM Tools.exe` se adjunta automáticamente a la release, dejándolo listo para que los usuarios lo descarguen.

## Scripts
1. **main.py:**
    - Script inicial desde este se arranca el sistema
2. **streamdb.py**
    - TAB DATA, gestiona la descarga de la informacion de DB de Lander
3. **gui.py**
    - TAB CONVERTIR, Convierte los archivos .CSV a .xlsx y .pdf
4. **app.py**
    - TAB IMPORTAR, Copia la imformacion de los archivos .xlsx al archivo maestro .xlsm
5. **build.py**
    - Automatizacion para empaquetar en archivo .exe
6. OTROS
    - config_utils.py
    - file_operations.py

## Licencia

Este proyecto no tiene una licencia especificada.