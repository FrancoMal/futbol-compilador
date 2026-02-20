# ⚽ Fútbol Compilador

Herramienta para crear compilados de video de jugadores de fútbol. Toma timestamps marcados durante el partido y los videos de cada tiempo para generar compilados automáticos por jugador.

> 🎯 Pensada para quienes hacen compilados de jugadores después de cada partido — sin necesidad de terminal ni conocimientos técnicos.

<!-- TODO: Agregar screenshots de la interfaz -->

---

## ✨ Características

- **GUI amigable** — Interfaz gráfica completa, no necesita terminal
- **Importa timestamps desde JSON** — Exportados de [Fútbol Clipper](https://francomal.github.io/futbol-clipper/) webapp
- **Videos por tiempo** — Soporta videos separados de primer y segundo tiempo, o un solo video completo con minuto de inicio configurable
- **Padding configurable** — Segundos extra antes/después de cada clip
- **Transiciones entre clips** — Ninguna, Fade o CrossFade
- **Overlay de minuto** — Muestra el minuto del partido en cada clip (ej: "1T 12:30")
- **Marca de agua** — Texto personalizable con opacidad configurable
- **Música de fondo** — Con control de volumen independiente
- **Quitar audio original** — Opción para silenciar el audio del partido
- **Sistema de etiquetas con colores** — Gol, Asistencia, Regate, Tiro, Pase clave, Defensa, y más
- **IDs fijos cronológicos** — Cada clip mantiene su ID aunque se reordene
- **Reordenar clips** — Con drag & drop o flechas arriba/abajo
- **Editar timestamps manualmente** — Ajustar inicio/fin de cada clip
- **Drag & drop de archivos** — Arrastrá JSON, videos y música directamente a la app
- **Configuración persistente** — Recuerda tus opciones entre sesiones
- **Export** — Guardá los timestamps editados en JSON o TXT

---

## 📋 Requisitos

- **Windows 10/11**
- **FFmpeg** instalado y en PATH — [Descargar FFmpeg](https://ffmpeg.org/download.html)

### Para ejecutar con Python (Opción B)

```bash
pip install -r requirements.txt
```

Dependencias:
- `pillow` — Procesamiento de imágenes
- `tkinterdnd2` — Drag & drop en la interfaz
- `mutagen` — Lectura de metadatos de audio

---

## 🚀 Instalación

### Opción A: Ejecutable (recomendado)

Descargá `FutbolCompilador.exe` desde la sección [Releases](../../releases) y ejecutalo directamente. No necesita Python ni instalación.

### Opción B: Ejecutar con Python

```bash
python compilador.py
```

Requiere Python 3.8+ con `tkinter` (incluido en la instalación estándar de Python en Windows).

---

## 📖 Uso

### Paso a paso

1. **Marcar timestamps durante el partido** usando la webapp companion [Fútbol Clipper](https://francomal.github.io/futbol-clipper/)
2. **Exportar el JSON** desde la webapp
3. **Abrir Fútbol Compilador** (el .exe o `python compilador.py`)
4. **Cargar el JSON** — Arrastralo a la app o usá el botón de selección
5. **Seleccionar los videos** del primer y segundo tiempo
6. **Configurar opciones** — Padding, transiciones, marca de agua, música, etc.
7. **Revisar y editar clips** — Reordenar, cambiar etiquetas, ajustar timestamps
8. **Elegir jugadores** a compilar (vienen todos seleccionados por defecto)
9. **Clickear COMPILAR** y esperar

Los videos se guardan en la carpeta de salida con el formato:
```
NombreJugador_Partido_Fecha.mp4
```

---

## 🌐 Webapp Companion

Usá [**Fútbol Clipper**](https://francomal.github.io/futbol-clipper/) para marcar los timestamps durante el partido desde el celular o la PC. Después exportá el JSON y cargalo en el compilador.

---

## 📄 Formato JSON esperado

```json
{
  "match": "River vs Boca",
  "date": "2026-02-17",
  "players": [
    {
      "name": "Enzo Fernández",
      "intervals": [
        { "start": "12:30", "end": "12:58", "half": 1, "tags": [] },
        { "start": "05:11", "end": "05:45", "half": 2, "tags": [] }
      ]
    }
  ]
}
```

Cada intervalo tiene:
- `start` / `end` — Timestamps en formato `MM:SS`
- `half` — Tiempo del partido (1 o 2)

---

## 🏷️ Etiquetas disponibles

| Etiqueta | Color |
|----------|-------|
| Gol | 🟢 Verde |
| Asistencia | 🔵 Azul |
| Regate | 🟠 Naranja |
| Tiro | 🔴 Rojo |
| Pase clave | 🟣 Violeta |
| Defensa | 🟡 Amarillo |

También podés crear etiquetas personalizadas con colores custom.

---

## 📝 Licencia

MIT
