# Mi Spotify v2 Dev

Aplicación Android nativa construida con Kotlin, Jetpack Compose y Media3.

## Estado actual

### Etapa 1 — interfaz nativa

- Inicio, Buscar y Biblioteca.
- Navegación inferior.
- Minirreproductor y reproductor completo.
- Listas perezosas y estado de desplazamiento conservado.

### Etapa 2 — reproducción Android

- ExoPlayer y Media3.
- `MediaLibraryService` y `MediaSession`.
- Segundo plano, notificación, Bluetooth y pantalla bloqueada.
- Seis audios locales originales para pruebas independientes de Internet.

### Etapa 3 — persistencia

- Room 2.8.4 con esquema exportado.
- DataStore para pestaña y filtros.
- Biblioteca, favoritos, historial, playlists, cola y snapshot de reproducción.
- Inicio, búsqueda y biblioteca alimentados por `Flow` reactivo.
- Restauración de cola y posición después de cerrar el proceso.

### Etapa 4 — proveedores y streaming online

- Contrato `MusicProvider` independiente de la interfaz y del reproductor.
- Registro de proveedores con timeout, aislamiento de errores y deduplicación.
- Búsqueda local inmediata y búsqueda online asíncrona.
- Persistencia de pistas online en Room antes de favoritos, historial o cola.
- Media3 resuelve recursos locales y streams HTTPS sin mezclar lógica de proveedor con Compose.

## Verificación

```bat
cd /d C:\Users\HALION\AndroidStudioProjects\MiSpotifyv2Dev

gradlew.bat testDebugUnitTest
gradlew.bat assembleDebug
gradlew.bat connectedSafeAndroidTest
```

La Etapa 4 no añade una biblioteca HTTP externa; usa HTTPS del sistema y mantiene la búsqueda local disponible si la red o el proveedor fallan.

## Etapa 4: motor musical embebido

La búsqueda online usa `ytmusicapi` y la resolución de audio usa `yt-dlp` dentro del APK mediante Chaquopy. No requiere claves de API, servidor ni PC encendida. Python se inicia de forma perezosa para no perjudicar el arranque nativo.

## Actualización 0.7.2

El modo DJ usa exclusivamente música de streaming. La narración fue ampliada, se filtran partes de razonamiento/formatos estructurados antes del TTS y se añadieron intervenciones automáticas entre bloques musicales. Consulta `FIX_0.7.2_NARRACION_STREAMING.md`.

## Actualización 0.8.0

Las superficies completas ahora son modales, el reproductor usa un fondo opaco desenfocado a partir de la portada y solicita carátulas de mayor resolución. El DJ lee favoritos, historial, reproducciones y artistas seguidos para construir cinco bloques de cinco canciones; las peticiones de artista son estrictas, los moods se personalizan y la cola queda inaccesible durante el modo DJ. Consulta `FIX_0.8.0_PERSONALIZACION_UI.md`.

## Actualización 0.9.0

Las nuevas peticiones detienen la sesión anterior mientras el DJ prepara y presenta el reemplazo. Cada bloque de cinco canciones se presenta antes de que su primera pista empiece a sonar. Se añadieron sesiones de 20 canciones para peticiones de un tema exacto, clasificación Gemini de mood/género/energía/bailabilidad, panel de texto adaptable al teclado, cierre directo al reproductor y un `sessionActivity` explícito para que el control multimedia de Android abra MiSpotify. Consulta `FIX_0.9.0_SESIONES_CANCION_NOTIFICACION.md`.
## Actualización 0.10.0

El DJ interpreta situaciones por significado musical en vez de buscar palabras literales (por ejemplo, “discoteca” se traduce a club/bailable/alta energía). Las sesiones normales ahora duran 5 o 6 canciones y, al terminar, el DJ vuelve a la vista inmersiva, presenta en silencio la siguiente tanda y luego inicia la música. La tarjeta DJ abre el reproductor si ya existe una sesión activa, se amplió la personalización con favoritos/historial/redescubrimiento/afinidad, se reforzó la variedad por artista y álbum, y el reproductor usa una barra de progreso fina con thumb circular. Consulta `FIX_0.10.0_SEMANTICA_SESIONES_VARIEDAD.md`.

## Actualización 0.11.0

Letras mantiene la pantalla encendida mientras está abierta. El streaming filtra globalmente a audios oficiales del catálogo y bloquea lives, acústicos, reuploads/videos y mixes largos. Inicio incorpora perfil local `E` y Configuración > Reproducción pasa a ser el único lugar para modificar el crossfade.

## Actualización 0.11.1

Se corrigió la búsqueda online tras detectar que el filtro de audio oficial exigía metadatos que las búsquedas de canciones de YouTube Music no siempre entregan. Las pruebas instrumentadas ahora usan un `applicationId` aislado para no desinstalar ni borrar los datos de la app de desarrollo. La importación de Spotify ya no usa Web API/PKCE: lee el ZIP/JSON de “Descargar tus datos” y crea referencias perezosas que se resuelven contra el catálogo musical solo cuando el usuario reproduce cada tema. Consulta `FIX_0.11.1_BUSQUEDA_DATOS_IMPORT_SPOTIFY.md`.
