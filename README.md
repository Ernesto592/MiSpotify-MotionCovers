# MiSpotify Motion Covers

Catálogo público de **Motion Covers** para MiSpotify. La aplicación descarga el manifiesto pequeño y solo obtiene el asset animado que necesita. Cada descarga se valida por tamaño y SHA-256 antes de entrar a la caché local.

## Estructura

```text
catalog/v1/manifest.json
covers/<artista>/<album>/<archivo-versionado-por-hash>.mp4
.github/workflows/validate-motion-cover.yml
tools/validate_motion_cover.py
```

## Portada publicada actualmente

El catálogo `schema: 1`, revisión `2`, publica un único asset compartido por dos identidades:

- Canción: **Un Coco — Bad Bunny** (`track`)
- Álbum: **Un Verano Sin Ti — Bad Bunny** (`album`)
- Formato: MP4, H.264, `yuv420p`
- Resolución: 720×720
- Velocidad: 24 FPS
- Duración: 15 s
- Audio: ninguno
- SHA-256: `90d0fb312f181de28d54bafa100da0a048779f6d80ae2b79b12ca9956920488f`

Ambas entradas apuntan al mismo archivo, por lo que no se duplica el vídeo en el repositorio ni en la caché del teléfono.

## Validación automática

GitHub Actions ejecuta **Validate Motion Covers** en cada pull request o push a `main` que modifique `catalog/`, `covers/`, `tools/` o el propio workflow. También se puede lanzar manualmente desde la pestaña **Actions**.

La validación comprueba, entre otras cosas:

- `schema: 1`, revisión válida, referencias `assetId` existentes e identidades básicas coherentes.
- Rutas relativas seguras: se rechazan rutas absolutas y `..`.
- Existencia del asset, `sizeBytes` exacto y SHA-256 exacto.
- El nombre del archivo debe terminar con los primeros 8 caracteres del SHA declarado.
- Tamaño máximo oficial: 5 MiB.
- Motion Cover cuadrada y como máximo 720×720.
- Máximo 24 FPS y 20 segundos.
- Cero streams de audio.
- MP4 oficial: H.264 + `yuv420p`.
- Los metadatos declarados (`width`, `height`, `fps`, `durationMs`) deben coincidir con el archivo real.

El validador usa Python estándar y `ffprobe`; no añade dependencias de Python al repositorio.

## Validar localmente

Con Python 3 y FFmpeg/ffprobe instalados:

```bash
python -m unittest discover -s tools/tests -p "test_*.py" -v
python tools/validate_motion_cover.py catalog/v1/manifest.json
```

Un catálogo correcto termina con una salida parecida a:

```text
Catalog OK: schema=1 revision=2 assets=1 entries=2
  ✓ uvst-motion-90d0fb31: mp4 720x720 24fps 15000ms ...
```

## Publicar una Motion Cover nueva

1. Preparar el asset oficial. Para MP4: 720×720, H.264, `yuv420p`, 24 FPS o menos, sin audio, máximo 20 s y máximo 5 MiB.
2. Calcular el SHA-256 del archivo.
3. Guardarlo dentro de `covers/<artista>/<album>/` con un nombre inmutable que termine en los primeros 8 caracteres del hash, por ejemplo `portada-90d0fb31.mp4`.
4. Añadir el asset y una o más entradas en `catalog/v1/manifest.json`.
5. Aumentar `revision` del catálogo. No reutilizar una revisión anterior para contenido distinto.
6. Ejecutar el validador localmente o abrir un pull request y esperar a que **Validate Motion Covers** quede verde.

Los assets ya publicados **no se sobrescriben**. Si cambia el contenido, cambia el SHA, el nombre del archivo y la revisión del catálogo.

## Relación con MiSpotify

Este repositorio es independiente del código fuente Android. MiSpotify consume el manifiesto vía HTTPS desde GitHub y los assets vía jsDelivr. No es necesario añadir este repositorio como `git remote` del proyecto Android.
