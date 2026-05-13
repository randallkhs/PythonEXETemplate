# ACS-Images-to-Image-Converter

Aplicación de escritorio en Python para convertir imágenes entre formatos con alta fidelidad de color, soporte de transparencia y conversión por lotes. Vive en la carpeta del proyecto ACS bajo `Custome-Scripts`, separada de la web canónica en `ACS-SITE-FILES/`.

## Propósito

Permite convertir archivos JPG, PNG, WebP y SVG entre sí, de forma individual o en lote, con una interfaz gráfica (GUI) en Tkinter. Está pensada para tareas operativas del sitio (optimizar assets, generar variantes, unificar formatos en una carpeta) sin depender de herramientas externas manuales.

## Ejecución

Desde la raíz de la app:

```bash
./run.sh
```

`run.sh` elige un intérprete de Python con Tkinter usable, crea o recrea `.venv` si hace falta, instala `requirements.txt` y lanza `main.py`.

Ruta absoluta en este equipo:

```bash
/Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-Images-to-Image-Converter/run.sh
```

Alternativa manual (solo si ya sabes qué Python usar):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

En macOS, la alternativa manual no sustituye a `run.sh` para la GUI: conviene usar siempre `run.sh` o un Python de Homebrew con `python-tk@` instalado.

## macOS, Tkinter y recuperación de la GUI

### Qué se corrigió (mayo 2026)

En macOS, el fallo más frecuente no era la conversión de imágenes sino el **arranque de la GUI**:

- **`ModuleNotFoundError: No module named '_tkinter'`** al usar solo el Python de Homebrew (`python@3.14`) sin el paquete `python-tk@3.14`.
- **Ventana gris o casi vacía** y aviso `DEPRECATION WARNING: The system version of Tk is deprecated...` al crear `.venv` con `/usr/bin/python3` (Tk **8.5.9** del sistema), incompatible con macOS recientes y con widgets `ttk`.

Cambios aplicados en el repo:

- **`run.sh`** prioriza intérpretes con **Tk moderno (8.6+)**, en este orden: `ACS_IMAGE_CONVERTER_PYTHON` (si está definida), Homebrew `python3.14` / `3.13` / `3.12` / `python3`, rutas en `/usr/local`, y solo al final `/usr/bin/python3`.
- **`run.sh`** recrea `.venv` automáticamente si falta Tkinter, si el Tk del venv es antiguo, o si la versión de Python del venv no coincide con la elegida.
- Si solo queda Tk legado del sistema, `run.sh` muestra advertencia y define `TK_SILENCE_DEPRECATION=1` para silenciar el aviso de deprecación (la GUI puede seguir siendo poco fiable).
- **`gui/app.py`**: en macOS usa el tema `aqua` y fondo de ventana del sistema para que los controles se dibujen correctamente con Tk reciente.

Configuración recomendada en Mac con Homebrew:

```bash
brew install python@3.14 python-tk@3.14
/Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-Images-to-Image-Converter/run.sh
```

Para forzar un intérprete concreto:

```bash
ACS_IMAGE_CONVERTER_PYTHON=/opt/homebrew/bin/python3.14 ./run.sh
```

### Si deja de funcionar otra vez

1. Ejecutar siempre **`run.sh`** desde la carpeta de la app, no `python3 main.py` a ciegas desde el PATH del sistema.
2. Comprobar que Homebrew sigue ofreciendo Tk para tu Python (sustituye `3.14` por la versión que uses):

```bash
/opt/homebrew/bin/python3.14 -c "import tkinter as tk; r=tk.Tk(); print(r.tk.call('info','patchlevel')); r.destroy()"
```

Deberías ver **8.6 o superior** (por ejemplo `9.0.3`). Si falla el import o la versión es **8.5.x**, reinstala soporte Tk:

```bash
brew install python-tk@3.14
```

3. Borrar el entorno virtual y dejar que `run.sh` lo regenere:

```bash
cd /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-Images-to-Image-Converter
rm -rf .venv
./run.sh
```

4. Si la ventana sigue en gris, forzar Homebrew 3.14 y repetir el paso 3:

```bash
ACS_IMAGE_CONVERTER_PYTHON=/opt/homebrew/bin/python3.14 ./run.sh
```

5. Si el error es **`No module named 'PIL'`** u otra dependencia, con el venv activo o vía ruta explícita:

```bash
cd /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-Images-to-Image-Converter
.venv/bin/pip install -r requirements.txt
```

6. Si fallan conversiones **desde o hacia SVG** (no la ventana), puede faltar Cairo en el sistema:

```bash
brew install cairo
rm -rf .venv
./run.sh
```

7. No instalar dependencias con `pip` en el Python global de macOS (PEP 668); usar solo `.venv` creado por `run.sh`.

### Reinstalación limpia en otra Mac o tras mover la carpeta

1. Copiar o clonar la carpeta `ACS-Images-to-Image-Converter` (no es obligatorio conservar `.venv`).
2. Instalar Homebrew, Python y Tk acoplados (misma versión mayor, p. ej. `3.14`):

```bash
brew install python@3.14 python-tk@3.14 cairo
```

3. Dar permiso de ejecución al lanzador si hace falta:

```bash
chmod +x /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-Images-to-Image-Converter/run.sh
```

4. Arrancar una vez; `run.sh` creará `.venv` e instalará `Pillow` y `cairosvg`.
5. Verificar: la ventana muestra secciones Origen, Opciones, Registro y barra de progreso; una conversión de prueba con un PNG pequeño termina en `OK` en el registro.

### Señales rápidas de diagnóstico

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| `No module named '_tkinter'` | Python sin Tk de Homebrew | `brew install python-tk@3.14` y `./run.sh` |
| Ventana gris / vacía, aviso de Tk deprecado | `.venv` ligado a `/usr/bin/python3` y Tk 8.5 | `rm -rf .venv` y `./run.sh` con `python-tk@3.14` |
| `No module named 'PIL'` | venv incompleto o roto | `rm -rf .venv` o `.venv/bin/pip install -r requirements.txt` |
| Error al leer/escribir SVG | Cairo/CairoSVG en el entorno | `brew install cairo`, recrear `.venv` |
| La app abre pero no convierte | Rutas, permisos o formatos no soportados | Revisar registro `ERR` en la GUI y extensiones en `formats.py` |


## Estructura del proyecto

| Ruta | Responsabilidad |
|------|-----------------|
| `main.py` | Punto de entrada; delega en `gui.app.run`. |
| `run.sh` | Arranque con venv y dependencias. |
| `requirements.txt` | `Pillow`, `pillow-heif`, `cairosvg` (y transitivas: Cairo, cffi, etc.). |
| `converter/formats.py` | Registro de formatos, extensiones y detección por nombre de archivo. |
| `converter/engine.py` | Lógica de conversión, redimensionado, lote y callbacks de progreso. |
| `converter/__init__.py` | API pública del paquete de conversión. |
| `gui/app.py` | Ventana Tkinter, hilos, cola de progreso y registro. |
| `gui/__init__.py` | Marcador del paquete GUI. |
| `.venv/` | Entorno virtual local (no versionar en git salvo política explícita del repo). |

Convención de imports: ejecutar siempre desde el directorio de la app para que `from converter import ...` resuelva correctamente.

## Funcionalidades de la GUI

- **Origen:** agregar archivos sueltos, agregar una carpeta completa, quitar selección o limpiar la lista.
- **Formato de salida:** JPEG, PNG, WebP, HEIC o SVG (etiquetas legibles; internamente se usan claves `jpg`, `png`, `webp`, `heic`, `svg`).
- **Dimensiones opcionales:** ancho y/o alto; checkbox para activar; opción de mantener proporción.
- **Destino:** carpeta de salida elegida por el usuario.
- **Conversión:** botón que procesa todos los orígenes recopilados hacia el mismo formato y carpeta.
- **Progreso:** barra y texto `Procesando N de M` actualizados en tiempo real vía cola desde un hilo de trabajo.
- **Registro:** líneas `OK` / `ERR` por archivo; diálogos al finalizar (éxito total o con errores parciales).

La conversión corre en un `threading.Thread` daemon; la GUI no debe bloquearse. El progreso se comunica con `queue.Queue` y `after(120, _poll_progress_queue)`.

## Formatos soportados (actual)

| Clave | Extensiones | Alfa | Vector |
|-------|-------------|------|--------|
| `jpg` | `.jpg`, `.jpeg` | No | No |
| `png` | `.png` | Sí | No |
| `webp` | `.webp` | Sí | No |
| `heic` | `.heic`, `.heif` | Sí | No |
| `svg` | `.svg` | Sí | Sí |

La detección es **solo por extensión** (`detect_format` en `formats.py`), no por magic bytes.

## Comportamiento del motor de conversión

### Recolección de archivos (`collect_image_paths`)

- Acepta rutas de archivos y/o directorios.
- En carpetas: solo archivos directos (no recursivo en subcarpetas), ordenados por nombre, sin duplicados.
- Ignora extensiones no registradas en `FORMATS`.

### Rutas de conversión (`convert_single`)

1. **SVG → SVG:** copia o ajusta `width`/`height` (y `viewBox` si faltaba) sin rasterizar; el contenido vectorial se conserva.
2. **SVG → raster:** `cairosvg.svg2png` → Pillow; salida RGBA cuando el destino admite alfa.
3. **Raster → SVG:** PNG embebido en SVG como `data:image/png;base64,...` dentro de `<image>` (fidelidad de píxeles; no es trazado vectorial).
4. **Raster → raster:** Pillow; redimensionado con `Image.Resampling.LANCZOS` si hay dimensiones.

### Transparencia y color

- Destinos con alfa (PNG, WebP, SVG): se preserva RGBA.
- JPEG: composición sobre fondo blanco (`flatten_alpha`) antes de guardar.
- WebP: `lossless=True` si hay transparencia parcial; si no, calidad 95.
- JPEG: calidad 95, `subsampling=0`, `optimize=True`.
- PNG: `compress_level=6`.
- Modos Pillow no RGB/RGBA se normalizan antes de procesar (evitar salida monocroma accidental).

### Redimensionado (`ConversionOptions`)

- `width` / `height` opcionales; al menos uno si el usuario activa dimensiones en la GUI.
- Con `preserve_aspect_ratio=True`, el lado no especificado se calcula proporcionalmente.
- Sin dimensiones: tamaño intrínseco (raster) o tamaño leído del SVG (`width`/`height`/`viewBox`; fallback 1024×1024).

### Lote (`convert_batch`)

- Crea la carpeta de salida si no existe.
- Un fallo por archivo no detiene el resto; cada resultado es `ConversionResult` con `success` y `message`.
- Callback de progreso: `(done, total, current_filename)` antes y después de cada archivo.

Los nombres de salida conservan el `stem` del origen y usan la primera extensión ordenada del formato destino en `FORMATS`.

## Limitaciones conocidas (importante para mantenimiento)

- **Raster → SVG:** el SVG resultante escala el contenedor, pero el contenido sigue siendo bitmap embebido; ampliar mucho puede verse pixelado. No hay vectorización (potrace/vtracer).
- **SVG → raster:** depende de CairoSVG; SVG muy complejos, fuentes externas o efectos poco soportados pueden fallar o diferir del navegador.
- **SVG → SVG con resize:** `xml.etree.ElementTree` puede alterar namespaces o metadatos en casos raros; no reescribe paths matemáticamente.
- **Carpetas:** no se escanean subdirectorios.
- **Entrada:** no hay arrastrar-y-soltar; solo diálogos de archivo/carpeta.
- **Concurrencia:** una sola conversión a la vez; el botón se deshabilita mientras el hilo está vivo.

## Cómo añadir formatos en el futuro

El diseño separa **metadatos de formato** (`formats.py`) de **codificación** (`engine.py`). Para un formato nuevo (por ejemplo AVIF o GIF):

1. **Registrar en `FORMATS`** (`converter/formats.py`):
   - `key` estable (usado en código y GUI).
   - `label` para el combobox.
   - `extensions` (conjunto de extensiones con punto).
   - `supports_alpha` y `is_vector` según el formato.

   `EXTENSION_TO_FORMAT` se reconstruye al importar el módulo; no editar a mano.

2. **Guardado raster en `save_raster`** (`converter/engine.py`):
   - Rama `elif target_format == "..."` con parámetros Pillow adecuados (calidad, lossless, etc.).
   - Si el formato no admite alfa, la rama genérica ya usa `flatten_alpha` vía `supports_alpha`.

3. **Entrada vectorial:** si el formato es vectorial, añadir ramas en `convert_single` (análogo a SVG) y funciones de carga/escritura dedicadas; probablemente nuevas dependencias en `requirements.txt`.

4. **Entrada raster:** Pillow suele bastar si `Image.open` lo soporta; verificar modos de color al cargar.

5. **Salida vectorial desde raster:** reutilizar `write_raster_as_svg` solo si el contenedor SVG+bitmap es aceptable; si se necesita verdadero vector, implementar otro pipeline (no mezclar con el embed actual sin documentar el cambio de comportamiento).

6. **GUI:** `format_choices()` alimenta el combobox; al añadir a `FORMATS`, la lista debería actualizarse sola. Revisar `filetypes` en `_add_files` si la extensión debe aparecer en el diálogo.

7. **Pruebas manuales recomendadas:** round-trip de color RGBA, origen con alfa → JPEG, lote mixto, resize con y sin proporción, y un SVG real del repo (p. ej. bajo `ACS-SITE-FILES/images/`).

No modificar `ACS-SITE-FILES/` desde esta app salvo que el usuario lo pida; la app solo lee/escribe rutas que el usuario elige.

## Dependencias

- **Pillow:** JPEG, PNG, WebP y manipulación raster.
- **pillow-heif:** lectura y escritura HEIC/HEIF (registro del opener en `converter/engine.py`).
- **cairosvg:** rasterización de SVG de entrada; requiere bibliotecas del sistema (Cairo). En macOS, si falla la importación, instalar Cairo vía Homebrew y reinstalar el venv.

## Ejecutable Windows (.exe) sin instalar Python

No se puede generar un `.exe` nativo de Windows desde macOS en este entorno. El empaquetado se hace **en una PC con Windows 10/11** con PyInstaller; el resultado incluye Python, Tkinter, Pillow, `pillow-heif`, CairoSVG y DLLs necesarias dentro del ejecutable (un solo `.exe`).

### Archivos de build

- `requirements-build.txt` — PyInstaller.
- `build/windows/acs_images_converter.spec` — receta de empaquetado.
- `build/windows/build_windows.ps1` — script principal.
- `build/windows/build_windows.bat` — atajo para doble clic o CMD.
- `build/windows/pyi_rth_heif.py` — registro HEIC al arrancar el bundle.

### Pasos en Windows

1. Copiar la carpeta `ACS-Images-to-Image-Converter` a la PC Windows.
2. Instalar [Python 3.12 para Windows](https://www.python.org/downloads/windows/) marcando **Add python.exe to PATH** y **tcl/tk** (Tkinter).
3. Abrir PowerShell en la carpeta del app y ejecutar:

```powershell
cd C:\ruta\ACS-Images-to-Image-Converter
.\build\windows\build_windows.ps1
```

4. El ejecutable queda en `dist\ACS-Images-to-Image-Converter.exe`.
5. Copiar solo ese `.exe` a otra máquina Windows; no hace falta `pip install` ni Python en el destino.

Python concreto (opcional):

```powershell
$env:ACS_IMAGE_CONVERTER_PYTHON = "C:\Python312\python.exe"
.\build\windows\build_windows.ps1
```

### Verificación recomendada en Windows

Tras el build, probar en la misma PC: abrir el `.exe`, convertir PNG→JPEG, HEIC→PNG y un SVG de prueba. Si falla SVG, recompilar en la misma máquina donde se probó (Cairo embebido vía wheels de `cairocffi`).

### Limitaciones del bundle

- El `.exe` es **solo para Windows** (x64 habitual en GitHub Actions / PC moderna).
- Primera ejecución puede tardar unos segundos (PyInstaller extrae en temporal).
- Antivirus ocasional: falsos positivos en ejecutables PyInstaller; firmar el binario reduce avisos en despliegue corporativo.

## Notas para otro agente en un chat futuro

- **Alcance:** herramienta local en `Custome-Scripts/ACS-Images-to-Image-Converter`; no forma parte del sitio Webflow ni de `acs-enhancements.js`.
- **Idioma de la UI:** español en etiquetas y mensajes; el código y docstrings están en inglés en varios módulos.
- **Cambios de calidad:** priorizar ajustes en `save_raster`, `apply_resize` y parámetros de `cairosvg.svg2png` antes de añadir dependencias pesadas.
- **Errores en GUI:** las excepciones por archivo se capturan en `convert_batch` y se muestran en el registro; no hay logging a archivo.
- **Extensibilidad sin tocar GUI:** importar `convert_batch`, `ConversionOptions` y `collect_image_paths` desde `converter` para scripts o tests.
- **PEP 668:** no instalar paquetes en el Python del sistema; usar siempre `.venv` o `run.sh`.
- **GUI en macOS:** mantener `run.sh` como fuente de verdad para elegir Python+Tk; no priorizar `/usr/bin/python3` en documentación ni scripts auxiliares. Si se toca `gui/app.py`, conservar tema `aqua` en Darwin salvo prueba explícita en Tk moderno.
- **Verificación rápida tras cambios:** smoke test PNG→WebP y SVG→PNG con un asset de `ACS-SITE-FILES/images/`; abrir la GUI y confirmar barra de progreso y cero errores en consola al convertir un lote pequeño; en Mac, confirmar `patchlevel` de Tk ≥ 8.6 en el intérprete del `.venv`.

## Historial breve

- **Implementación inicial:** GUI Tkinter, cuatro formatos, lote por carpeta no recursiva, transparencia en PNG/WebP/SVG, SVG salida desde raster por PNG embebido, y extensión vía `FORMATS` + `save_raster` / ramas en `convert_single`.
- **Mayo 2026 (macOS):** `run.sh` elige Python con Tk ≥ 8.6 (Homebrew `python-tk@` antes que `/usr/bin/python3`), recrea `.venv` si Tk o versión de Python no cuadran; ajustes de tema `aqua` en `gui/app.py`; documentación de recuperación y reinstalación en este README.
- **Mayo 2026:** soporte HEIC/HEIF (`pillow-heif`) y scripts de empaquetado Windows (`build/windows/*`, `requirements-build.txt`).
