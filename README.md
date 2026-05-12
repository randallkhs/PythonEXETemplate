# ACS-AI-Image-Reproducer

Aplicación de escritorio en Python (PySide6) para generar imágenes de alta calidad a partir de una imagen de referencia, usando modelos fijos de OpenAI y Gemini. Vive en `Custome-Scripts/ACS-AI-Image-Reproducer`, separada del sitio canónico en `ACS-SITE-FILES/`.

## Modelos fijos

| Proveedor | ID del modelo | Archivo |
|-----------|---------------|---------|
| OpenAI | `gpt-image-2` | `app/providers/openai_provider.py` |
| Gemini | `gemini-3.1-flash-image-preview` | `app/providers/gemini_provider.py` |

No cambiar estos IDs salvo que el usuario pida explícitamente actualizar modelos.

## Funcionalidades principales

- GUI moderna en PySide6.
- Imagen de referencia (`.png`, `.jpg`, `.jpeg`, `.webp`) y prompt detallado.
- Proveedor por defecto: **Gemini** (OpenAI opcional).
- Carpeta de salida y nombre opcional del candidato generado.
- Barra de progreso y ETA por etapas (con estimación dinámica en la fase de red).
- API keys en llavero del sistema (`keyring`); sin texto plano en el repo.
- Preview grande para aprobar o rechazar resultados.
- Flujo de reemplazo con aprobación: generar candidato, aprobar para sobrescribir un archivo local existente, o rechazar y regenerar sin límite.
- Respaldo opcional de la imagen antigua antes del reemplazo.
- Secciones colapsables: panel de API keys y **Test View** (log).
- Botones superiores: **Open Generated** (abrir última imagen en el visor del sistema) y **Reset Window** (tamaño recomendado y centrado en pantalla).

## Diseño de la interfaz (estado actual)

Orden vertical de arriba hacia abajo:

1. Título, descripción y toggles superiores (`Show API Keys & Validation`, `Test View`, `Open Generated`, `Reset Window`).
2. **Preview & Result** (área principal; prioridad de espacio).
3. Barra de acción horizontal: `Generate / Reproduce Image`, `Reject & Regenerate`, `Approve Replace`, más progreso, estado y ETA.
4. **Generation Settings** en dos columnas (modo landscape) para que inputs y checkboxes quepan en pantallas tipo iMac sin quedar fuera del viewport.
5. Panel de API keys solo si el toggle de keys está activado.

Límites de ventana: el tamaño máximo no supera el área disponible del monitor (`availableGeometry`). **Reset Window** vuelve al tamaño recomendado (aprox. 1380×920 o el tope del monitor si es menor) y centra la ventana.

Por defecto al abrir: Gemini seleccionado, keys y log ocultos, modo de reemplazo activado.

## Flujo de reemplazo de imagen local

1. Activa **Enable replacement workflow after approval** (por defecto activo).
2. En **Image to replace**, elige el archivo existente que quieres sustituir (por ejemplo `Limpieza_Alfombra.jpg`).
3. Genera con **Generate / Reproduce Image**; el candidato se guarda en la carpeta de salida (nombre opcional en **Output candidate name**).
4. Revisa el preview.
5. **Approve Replace**: si **Use target's same filename/path when approving replace** está activo, escribe sobre la ruta del objetivo con el mismo nombre; si **Keep backup of old image before replacing** está activo, guarda una copia con sufijo `.backup_YYYYMMDD_HHMMSS` antes de sobrescribir.
6. **Reject & Regenerate**: no modifica el archivo objetivo; puedes generar de nuevo las veces que quieras.
7. Si no apruebas, la imagen antigua permanece intacta.

La conversión al formato del archivo objetivo (JPEG, PNG, WebP) al aprobar usa Pillow en `app/gui.py` (`_write_candidate_as_target_format`).

## Instalación y arranque

```bash
cd /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-AI-Image-Reproducer
./run.sh
```

`run.sh` elige un intérprete Python, crea o repara `.venv`, instala `requirements.txt` y ejecuta `main.py`.

```bash
chmod +x /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-AI-Image-Reproducer/run.sh
```

Forzar intérprete:

```bash
ACS_AI_IMAGE_REPRODUCER_PYTHON=/opt/homebrew/bin/python3.14 ./run.sh
```

## Cómo obtener API keys

### OpenAI

1. Inicia sesión en OpenAI Platform.
2. Crea una API key en la sección de claves.
3. En la app (con **Show API Keys** activado): pega la clave, **Save**, luego **Validate**.

### Gemini

1. En Google AI Studio, crea una API key para tu proyecto.
2. En la app: pega la clave de Gemini, **Save**, **Validate** (debe poder usar `gemini-3.1-flash-image-preview`).

## Uso recomendado

1. Arranca con `./run.sh`.
2. Guarda y valida keys una vez; luego puedes ocultar el panel de keys.
3. Elige imagen de referencia, prompt, carpeta de salida, tamaño y calidad.
4. Si vas a reemplazar un asset del sitio, selecciona ese archivo en **Image to replace**.
5. Genera, revisa el preview grande.
6. Aprueba, rechaza y regenera, o abre el candidato con **Open Generated**.
7. Si moviste o redimensionaste mal la ventana, **Reset Window**.

## Progreso y ETA

Etapas aproximadas: validación, carga de key, espera de red del proveedor (ETA dinámico según promedios en `app/config.py`), guardado, finalización. Las APIs no devuelven progreso granular de píxeles; la barra refleja etapas y tiempo histórico por proveedor.

## Estructura del proyecto

| Ruta | Rol |
|------|-----|
| `main.py` | Entrada |
| `run.sh` | Lanzador y venv |
| `requirements.txt` | PySide6, requests, keyring, Pillow |
| `app/gui.py` | UI, reemplazo, preview, botones superiores |
| `app/tasks.py` | Worker en hilo, progreso, guardado del candidato |
| `app/config.py` | Última carpeta de salida y promedios para ETA |
| `app/key_store.py` | Keyring (`ACS-AI-Image-Reproducer`) |
| `app/providers/openai_provider.py` | Edición/generación OpenAI |
| `app/providers/gemini_provider.py` | `generateContent` Gemini |

## Correcciones y cambios documentados

### Gemini: payload de imagen (`imageConfig`)

**Síntoma:** error al generar, por ejemplo `Invalid JSON payload ... Unknown name "responseFormat" at 'generation_config'`.

**Causa:** el endpoint REST de Gemini en este flujo no acepta `generationConfig.responseFormat` como en algunos ejemplos del SDK.

**Solución:** en `app/providers/gemini_provider.py`, la configuración de imagen va en `generationConfig.imageConfig` (`aspectRatio`, `imageSize`), con `responseModalities: ["TEXT", "IMAGE"]`. No reintroducir `responseFormat` en REST sin verificar la documentación vigente.

### GUI: ventana demasiado alta y controles fuera de pantalla

**Síntoma:** en iMac no se alcanzaban botones o campos inferiores; preview y settings competían en vertical.

**Solución:** preview arriba; botones de acción en fila horizontal bajo el preview; **Generation Settings** en dos columnas con altura máxima acotada; prompt con altura limitada; límite de tamaño de ventana al monitor; **Reset Window** para restaurar layout.

### Proveedor por defecto

Gemini aparece primero en el combo y queda seleccionado al iniciar.

### Botones superiores añadidos

- **Reset Window**: `_configure_window_bounds()` + `_center_on_screen()` en `app/gui.py`.
- **Open Generated**: abre `_latest_generated_path` con `open` en macOS, `startfile` en Windows, `xdg-open` en Linux.

### Flujo de aprobación de reemplazo

Implementado en `app/gui.py` (`_approve_replacement`, `_reject_generated`, `_build_backup_path`). El worker en `app/tasks.py` solo escribe el candidato; el overwrite del archivo objetivo ocurre solo tras **Approve Replace**.

## Seguridad

- Keys solo en keyring; no en README, logs ni JSON de config.
- Errores de API sin volcar secretos.

## Solución de problemas

### Dependencias o venv roto

```bash
cd /Users/randyr/ACS_AI_WEBAPP_T/Custome-Scripts/ACS-AI-Image-Reproducer
rm -rf .venv
./run.sh
```

### Validación de API key fallida

Revisa proveedor, cuota, facturación y que el modelo fijo esté habilitado en tu cuenta.

### Error Gemini de JSON / generation_config

Confirma que `gemini_provider.py` usa `imageConfig`, no `responseFormat`. Reinstala dependencias si el código local está desactualizado.

### Reemplazo no aplicado

Comprueba que **Image to replace** apunta a un archivo existente y que pulsaste **Approve Replace**, no solo generar candidato.

### Keyring en macOS

Keychain desbloqueado; si falla, borra y vuelve a guardar keys con el panel de keys visible.

### Ventana descolocada o recortada

Pulsa **Reset Window**.

### Reinstalación limpia

Borrar `.venv`, ejecutar `./run.sh`, volver a guardar keys en la GUI.

## Notas para otro agente

- Modelos fijos en `app/providers/*`; GUI y layout en `app/gui.py`; hilo y candidato en `app/tasks.py`; ETA en `app/config.py`.
- Cualquier cambio de layout debe preservar: preview prioritario, acciones horizontales bajo preview, settings en dos columnas, toggles de keys y Test View.
- Tras tocar Gemini REST, probar generación real con key del usuario; el error de `responseFormat` es regresión conocida.
- Verificación rápida: import/`compileall`, instanciar `MainWindow`, comprobar proveedor default `gemini`, toggles keys/log ocultos por defecto, botones **Reset Window** y **Open Generated** presentes.
- No modificar `ACS-SITE-FILES/` desde la app salvo que el usuario elija rutas allí al reemplazar.

## Historial breve

- Implementación inicial: PySide6, OpenAI y Gemini, keyring, progreso por etapas, modelos fijos.
- Corrección Gemini REST (`imageConfig`).
- Flujo de reemplazo con aprobación, rechazo y backup opcional; Gemini por defecto.
- Reorganización de UI: preview grande arriba, acciones horizontales, settings en landscape, límites de ventana, **Reset Window** y **Open Generated**.
