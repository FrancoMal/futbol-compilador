# ⚽ Fútbol Clipper - Compilador

Genera videos compilados por jugador a partir de timestamps exportados de la webapp.

## Requisitos

- **Python 3.8+**
- **ffmpeg** instalado y en PATH ([descargar](https://ffmpeg.org/download.html))

## Uso

```bash
python compilador.py
```

## Pasos

1. **Seleccionar JSON** con los timestamps exportados de la webapp
2. **Seleccionar los videos** del primer y segundo tiempo
3. **Configurar opciones** (padding, transiciones, marca de agua, etc.)
4. **Elegir jugadores** a compilar (vienen todos seleccionados por defecto)
5. **Clickear COMPILAR** y esperar

Los videos se guardan en la carpeta de salida con el formato:
`NombreJugador_Partido_Fecha.mp4`

## Formato del JSON

```json
{
  "match": "River vs Boca",
  "date": "2026-02-17",
  "players": [
    {
      "name": "Enzo Fernández",
      "intervals": [
        {"start": "12:30", "end": "12:58", "half": 1},
        {"start": "05:11", "end": "05:45", "half": 2}
      ]
    }
  ]
}
```

## Opciones

| Opción | Descripción | Default |
|--------|-------------|---------|
| Padding | Segundos extra antes/después de cada clip | 2s |
| Transición | Ninguna / Fade / CrossFade | Fade |
| Overlay de minuto | Muestra "1T 12:30" en pantalla | ON |
| Marca de agua | Texto centrado abajo (ej: @tucuenta) | - |
| Música de fondo | Audio que se mezcla de fondo | - |
