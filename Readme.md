# Convertidor de Reportes

Este proyecto es una herramienta de escritorio para convertir reportes a otro formato.

## Instalación

Para utilizar esta herramienta, puedes descargar el archivo ejecutable `Converter TrackSIM.exe` desde la sección de [releases](https://github.com/tu-usuario/tu-repositorio/releases). No se necesita instalación, solo ejecuta el archivo.

## Uso

1.  Abre la aplicación haciendo doble clic en `Converter TrackSIM.exe`.
2.  Sigue las instrucciones en la interfaz de la aplicación para convertir tus reportes.

## Building

Si deseas compilar la aplicación desde el código fuente, sigue estos pasos:

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

    Abrir la versión de desarrollo:
    python main.py
    ```

3.  Construye el ejecutable con PyInstaller usando el archivo de especificación generado:
    ```bash
    python build.py 
    ```

    Esto crear un ejecutable de acuerdo a la configuracion en convertidor_reportes.spec

    ```

## Licencia

Este proyecto no tiene una licencia especificada.