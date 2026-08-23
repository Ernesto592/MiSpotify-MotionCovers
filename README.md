# MiSpotify Motion Covers

Catálogo público de Motion Covers para MiSpotify.

La app descarga únicamente el manifiesto pequeño y, cuando una canción o álbum coincide, obtiene el asset animado necesario bajo demanda. Los archivos multimedia usan nombres versionados por hash y el cliente verifica tamaño y SHA-256 antes de guardarlos en caché.

## Estructura

```text
catalog/v1/manifest.json
covers/<artista>/<album>/<archivo-versionado>.mp4
```

## Primera portada publicada

- Artista: Bad Bunny
- Álbum: Un Verano Sin Ti
- Alcance: álbum
- Formato: MP4 H.264, 720×720, 24 FPS, 15 s, sin audio
- SHA-256: `90d0fb312f181de28d54bafa100da0a048779f6d80ae2b79b12ca9956920488f`

El formato del catálogo está versionado mediante `schema`. No se deben sobrescribir assets publicados: una nueva versión debe usar un nombre de archivo nuevo derivado de su hash y aumentar `revision` en el manifiesto.
