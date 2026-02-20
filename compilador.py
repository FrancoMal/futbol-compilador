# ⚽ Fútbol Clipper - Compilador v1.1
# Genera videos compilados por jugador a partir de timestamps y videos de cada tiempo.

APP_VERSION = "1.2"

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


# ─── Dark Theme Colors ───────────────────────────────────────────────
BG = "#1e1e2e"
BG2 = "#2a2a3c"
BG3 = "#353548"
FG = "#cdd6f4"
FG2 = "#a6adc8"
GREEN = "#a6e3a1"
GREEN_DARK = "#40b436"
ACCENT = "#89b4fa"
RED = "#f38ba8"

# ─── Tag Colors ───────────────────────────────────────────────────────
TAG_COLORS = {
    "Rojo": "#e74c3c",
    "Azul": "#3498db",
    "Verde": "#2ecc71",
    "Amarillo": "#f1c40f",
    "Naranja": "#e67e22",
    "Violeta": "#9b59b6",
    "Rosa": "#e91e8a",
    "Gris": "#95a5a6"
}

QUICK_TAGS = [
    ("Gol", "#2ecc71"),
    ("Asistencia", "#3498db"),
    ("Regate", "#e67e22"),
    ("Tiro", "#e74c3c"),
    ("Pase clave", "#9b59b6"),
    ("Defensa", "#f1c40f"),
]


def _text_color_for_bg(hex_color):
    """Return white or black text depending on background luminance."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"


# ─── Helpers ──────────────────────────────────────────────────────────
def ts_to_seconds(ts: str) -> float:
    """Convert 'MM:SS' or 'HH:MM:SS' to seconds."""
    parts = ts.strip().split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0.0


def seconds_to_ts(s: float) -> str:
    """Seconds to MM:SS."""
    m = int(s) // 60
    sec = int(s) % 60
    return f"{m:02d}:{sec:02d}"


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def get_video_duration(path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


# ─── Compilation Engine ──────────────────────────────────────────────
class Compiler:
    def __init__(self, config: dict, on_progress=None, on_done=None, on_error=None):
        self.cfg = config
        self.on_progress = on_progress or (lambda *a: None)
        self.on_done = on_done or (lambda: None)
        self.on_error = on_error or (lambda e: None)
        self.cancelled = False

    def run(self):
        try:
            self._compile()
        except Exception as e:
            self.on_error(str(e))

    def _compile(self):
        cfg = self.cfg
        data = cfg["data"]
        players = cfg["selected_players"]
        match_name = sanitize_filename(data.get("match", "partido"))
        date = sanitize_filename(data.get("date", ""))
        vid1 = cfg["video1"]
        vid2 = cfg["video2"]
        out_dir = cfg["output_dir"]
        padding = cfg["padding"]
        transition = cfg["transition"]
        trans_dur = cfg["transition_duration"]
        overlay = cfg["overlay"]
        watermark = cfg["watermark"].strip()
        wm_size = cfg.get("watermark_size", "mediano")
        wm_font = cfg.get("watermark_font", "Segoe UI")
        music = cfg["music"]
        music_vol = cfg["music_volume"] / 100.0
        remove_audio = cfg.get("remove_audio", False)
        
        # Modo partido completo
        modo_archivo = cfg.get("modo_archivo", "2archivos")
        video_full = cfg.get("video_full", "")
        minuto_inicio_1t = cfg.get("minuto_inicio_1t", 0)
        minuto_inicio_2t = cfg.get("minuto_inicio_2t", 45)
        
        # Calcular duraciones de videos
        if modo_archivo == "1completo" and video_full and os.path.isfile(video_full):
            dur_full = get_video_duration(video_full)
            dur1 = dur_full  # No se usa directamente, pero por compatibilidad
            dur2 = dur_full
        else:
            dur1 = get_video_duration(vid1)
            dur2 = get_video_duration(vid2)

        total_players = len(players)
        tmpdir = tempfile.mkdtemp(prefix="futclip_")

        try:
            for pi, player in enumerate(players):
                if self.cancelled:
                    return
                name = player["name"]
                intervals = player["intervals"]
                total_clips = len(intervals)

                clip_files = []
                for ci, iv in enumerate(intervals):
                    if self.cancelled:
                        return
                    self.on_progress(f"Procesando {name} clip {ci+1}/{total_clips}...",
                                     (pi * total_clips + ci) / (total_players * total_clips))

                    half = iv["half"]
                    
                    # Determinar video de origen según modo
                    if modo_archivo == "1completo" and video_full and os.path.isfile(video_full):
                        # Modo partido completo: usar un solo video
                        vid = video_full
                        dur = dur_full
                        
                        # Calcular timestamps reales en el video completo
                        if half == 1:
                            # 1T: el timestamp start/end está en minutos relativos al inicio del 1T
                            # Agregar minuto_inicio_1t para obtener el minuto real del video
                            offset_segundos = minuto_inicio_1t  # Ya viene en segundos
                        else:
                            # 2T: el timestamp start/end está en minutos relativos al inicio del 2T
                            # Agregar minuto_inicio_2t para obtener el minuto real del video
                            offset_segundos = minuto_inicio_2t  # Ya viene en segundos
                        
                        # Convertir minutos a segundos y agregar el offset
                        start_ts_seconds = ts_to_seconds(iv["start"])
                        end_ts_seconds = ts_to_seconds(iv["end"])
                        
                        # Los timestamps del JSON son relativos al tiempo (0:00 = inicio del periodo)
                        # offset_segundos ya viene en segundos
                        start = max(0, offset_segundos + start_ts_seconds - padding)
                        end = min(dur, offset_segundos + end_ts_seconds + padding) if dur > 0 else offset_segundos + end_ts_seconds + padding
                        clip_dur = end - start
                    else:
                        # Modo 2 archivos (original)
                        vid = vid1 if half == 1 else vid2
                        dur = dur1 if half == 1 else dur2
                        start = max(0, ts_to_seconds(iv["start"]) - padding)
                        end = min(dur, ts_to_seconds(iv["end"]) + padding) if dur > 0 else ts_to_seconds(iv["end"]) + padding
                        clip_dur = end - start

                    clip_path = os.path.join(tmpdir, f"clip_{pi}_{ci}.mp4")

                    # Build filter
                    filters = []
                    if overlay:
                        real_min = iv["start"]
                        label = f"{half}T {real_min}"
                        # Add tags to overlay if present
                        tags = iv.get("tags", [])
                        if tags:
                            tag_texts = " | ".join(t["text"] for t in tags)
                            label = f"{label}  [{tag_texts}]"
                            # Use first tag color for text, or white if none
                            tag_color = tags[0].get("color", "#ffffff").lstrip("#")
                            # Convert hex to ffmpeg color name or use hex
                            if len(tag_color) == 6:
                                tag_color = f"#{tag_color}"
                        else:
                            tag_color = "white"
                        escaped = label.replace(":", r"\:")
                        filters.append(
                            f"drawtext=text='{escaped}':fontsize=36:fontcolor={tag_color}:"
                            f"borderw=2:bordercolor=black:x=30:y=30"
                        )
                    if watermark:
                        wm_escaped = watermark.replace("'", "'\\''").replace(":", r"\:")
                        sizes = {"pequeño": 24, "mediano": 32, "grande": 48}
                        fs = sizes.get(wm_size, 32)
                        wm_opacity = cfg.get("watermark_opacity", 70) / 100
                        
                        # Fuentes: Windows + locales
                        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
                        font_map = {
                            "Segoe UI": "C\\:/Windows/Fonts/segoeui.ttf",
                            "Arial": "C\\:/Windows/Fonts/arial.ttf",
                            "Verdana": "C\\:/Windows/Fonts/verdana.ttf",
                            "Tahoma": "C\\:/Windows/Fonts/tahoma.ttf",
                            "Georgia": "C\\:/Windows/Fonts/georgia.ttf",
                            "Impact": "C\\:/Windows/Fonts/impact.ttf",
                            "Inter": os.path.join(font_dir, "inter", "extras", "ttf", "Inter-Regular.ttf"),
                            "Core Sans": os.path.join(font_dir, "CoreSansA45Regular.otf"),
                        }
                        fontfile = font_map.get(wm_font, "")
                        
                        # Buscar fuente en ruta absoluta o relativa
                        if fontfile:
                            if not os.path.isabs(fontfile):
                                # Ruta relativa: buscar desde la ubicación del script
                                fontfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", fontfile)
                            if os.path.exists(fontfile):
                                font_str = f"fontfile='{fontfile}':"
                            else:
                                font_str = ""
                        else:
                            font_str = ""
                        
                        filters.append(
                            f"drawtext=text='{wm_escaped}':{font_str}fontsize={fs}:fontcolor=white@{wm_opacity:.2f}:"
                            f"borderw=2:bordercolor=black@{wm_opacity:.2f}:x=(w-text_w)/2:y=h-th-20"
                        )

                    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", vid,
                           "-t", str(clip_dur)]
                    if filters:
                        cmd += ["-vf", ",".join(filters)]
                    cmd += ["-c:v", "libx264", "-crf", "20", "-preset", "fast"]
                    if remove_audio:
                        cmd += ["-an"]
                    else:
                        cmd += ["-c:a", "aac", "-b:a", "192k"]
                    cmd += [clip_path]

                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if r.returncode != 0:
                        raise RuntimeError(f"ffmpeg error cortando clip: {r.stderr[-500:]}")
                    clip_files.append(clip_path)

                if not clip_files:
                    continue

                # Concatenation
                self.on_progress(f"Concatenando {name}...",
                                 ((pi + 1) * total_clips - 1) / (total_players * total_clips))

                out_name = f"{sanitize_filename(name)}_{match_name}_{date}.mp4"
                out_path = os.path.join(out_dir, out_name)

                if len(clip_files) == 1:
                    concat_path = clip_files[0]
                elif transition == "CrossFade" and len(clip_files) > 1:
                    concat_path = self._xfade_concat(clip_files, trans_dur, tmpdir, pi)
                else:
                    if transition == "Fade":
                        faded = self._apply_fades(clip_files, trans_dur, tmpdir, pi)
                    else:
                        faded = clip_files
                    concat_path = self._simple_concat(faded, tmpdir, pi)

                # Music mix
                if music and os.path.isfile(music):
                    self.on_progress(f"Mezclando música para {name}...",
                                     (pi + 0.9) / total_players)
                    final_path = os.path.join(tmpdir, f"final_{pi}.mp4")
                    if remove_audio:
                        # No original audio, just add music track
                        cmd = [
                            "ffmpeg", "-y", "-i", concat_path, "-stream_loop", "-1",
                            "-i", music, "-filter_complex",
                            f"[1:a]volume={music_vol}[a]",
                            "-map", "0:v", "-map", "[a]",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-shortest", final_path
                        ]
                    else:
                        cmd = [
                            "ffmpeg", "-y", "-i", concat_path, "-stream_loop", "-1",
                            "-i", music, "-filter_complex",
                            f"[1:a]volume={music_vol}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                            "-map", "0:v", "-map", "[a]",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-shortest", final_path
                        ]
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                    if r.returncode != 0:
                        raise RuntimeError(f"ffmpeg error música: {r.stderr[-500:]}")
                    shutil.copy2(final_path, out_path)
                else:
                    shutil.copy2(concat_path, out_path)

            self.on_progress("¡Listo!", 1.0)
            self.on_done()

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _apply_fades(self, clips, dur, tmpdir, pi):
        """Apply fade in/out to each clip."""
        faded = []
        for i, clip in enumerate(clips):
            clip_dur = get_video_duration(clip)
            if clip_dur <= 0:
                faded.append(clip)
                continue
            out = os.path.join(tmpdir, f"faded_{pi}_{i}.mp4")
            vf = f"fade=t=in:st=0:d={dur},fade=t=out:st={max(0, clip_dur - dur)}:d={dur}"
            af = f"afade=t=in:st=0:d={dur},afade=t=out:st={max(0, clip_dur - dur)}:d={dur}"
            cmd = ["ffmpeg", "-y", "-i", clip, "-vf", vf, "-af", af,
                   "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                   "-c:a", "aac", "-b:a", "192k", out]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                faded.append(clip)
            else:
                faded.append(out)
        return faded

    def _simple_concat(self, clips, tmpdir, pi):
        """Concat via demuxer."""
        list_file = os.path.join(tmpdir, f"list_{pi}.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for c in clips:
                f.write(f"file '{c}'\n")
        out = os.path.join(tmpdir, f"concat_{pi}.mp4")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
               "-c", "copy", out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg concat error: {r.stderr[-500:]}")
        return out

    def _xfade_concat(self, clips, dur, tmpdir, pi):
        """Crossfade using xfade filter chain."""
        if len(clips) < 2:
            return clips[0]

        durations = [get_video_duration(c) for c in clips]
        current = clips[0]
        offset = durations[0] - dur

        for i in range(1, len(clips)):
            out = os.path.join(tmpdir, f"xfade_{pi}_{i}.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", current, "-i", clips[i],
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={dur}:offset={max(0, offset)}[v];"
                f"[0:a][1:a]acrossfade=d={dur}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                "-c:a", "aac", "-b:a", "192k", out
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg xfade error: {r.stderr[-500:]}")
            current = out
            current_dur = get_video_duration(current)
            if i + 1 < len(clips):
                offset = current_dur - dur

        return current


# ─── GUI ──────────────────────────────────────────────────────────────
# ─── Config Persistence ───────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compilador_config.json")


class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"⚽ Fútbol Clipper - Compilador v{APP_VERSION}")
        self.geometry("700x850")
        self.configure(bg=BG)
        self.resizable(False, True)

        self.json_path = tk.StringVar()
        self.video1_path = tk.StringVar()
        self.video2_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.padding = tk.DoubleVar(value=2.0)
        self.transition = tk.StringVar(value="Fade")
        self.trans_dur = tk.DoubleVar(value=0.5)
        self.overlay = tk.BooleanVar(value=True)
        self.music_path = tk.StringVar()
        self.music_vol = tk.IntVar(value=20)
        self.watermark = tk.StringVar()
        self.wm_size = tk.StringVar(value="mediano")
        self.wm_font = tk.StringVar(value="Segoe UI")
        self.wm_opacity = tk.IntVar(value=70)
        self.remove_audio = tk.BooleanVar(value=False)
        
        # Modo de archivo: "2archivos" (default) o "1completo"
        self.modo_archivo = tk.StringVar(value="2archivos")
        self.minuto_inicio_1t = tk.IntVar(value=0)
        self.minuto_inicio_2t = tk.IntVar(value=45)
        self.video_full_path = tk.StringVar()

        self.player_vars = []
        self.json_data = None

        self._build_ui()
        self._load_config()

        if not HAS_DND:
            print("💡 Tip: Instalá tkinterdnd2 para drag & drop: pip install tkinterdnd2")

        # Save config on window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._save_config()
        self.destroy()

    def _toggle_modo_archivo(self):
        """Toggle between 2 files mode and 1 full match mode."""
        modo = self.modo_archivo.get()
        if modo == "2archivos":
            self.frame_2archivos.pack(fill="x", expand=True)
            self.frame_1completo.pack_forget()
        else:
            self.frame_2archivos.pack_forget()
            self.frame_1completo.pack(fill="x", expand=True)

    def _save_config(self):
        config = {
            "padding": self.padding.get(),
            "transition": self.transition.get(),
            "transition_duration": self.trans_dur.get(),
            "overlay": self.overlay.get(),
            "remove_audio": self.remove_audio.get(),
            "music_volume": self.music_vol.get(),
            "watermark": self.watermark.get(),
            "watermark_size": self.wm_size.get(),
            "watermark_font": self.wm_font.get(),
            "watermark_opacity": self.wm_opacity.get(),
            "output_dir": self.output_dir.get(),
            "json_path": self.json_path.get(),
            "video1_path": self.video1_path.get(),
            "video2_path": self.video2_path.get(),
            "music_path": self.music_path.get(),
            "modo_archivo": self.modo_archivo.get(),
            "minuto_inicio_1t": self.minuto_inicio_1t.get(),
            "minuto_inicio_2t": self.minuto_inicio_2t.get(),
            "video_full_path": self.video_full_path.get(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_config(self):
        if not os.path.isfile(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            return

        self.padding.set(config.get("padding", 2.0))
        self.transition.set(config.get("transition", "Fade"))
        self.trans_dur.set(config.get("transition_duration", 0.5))
        self.overlay.set(config.get("overlay", True))
        self.remove_audio.set(config.get("remove_audio", False))
        self.music_vol.set(config.get("music_volume", 20))
        self.watermark.set(config.get("watermark", ""))
        self.wm_size.set(config.get("watermark_size", "mediano"))
        self.wm_font.set(config.get("watermark_font", "Segoe UI"))
        self.wm_opacity.set(config.get("watermark_opacity", 70))

        # Restore paths only if files still exist
        for key, var in [("output_dir", self.output_dir), ("music_path", self.music_path),
                         ("json_path", self.json_path), ("video1_path", self.video1_path),
                         ("video2_path", self.video2_path), ("video_full_path", self.video_full_path)]:
            val = config.get(key, "")
            if val and os.path.exists(val):
                var.set(val)

        # Restore modo archivo settings
        self.modo_archivo.set(config.get("modo_archivo", "2archivos"))
        self.minuto_inicio_1t.set(config.get("minuto_inicio_1t", 0))
        self.minuto_inicio_2t.set(config.get("minuto_inicio_2t", 45))
        self._toggle_modo_archivo()

        # Auto-load JSON if restored
        if self.json_path.get() and os.path.isfile(self.json_path.get()):
            self._load_json(self.json_path.get())

    def _setup_dnd(self, widget, var, is_dir=False):
        """Setup drag and drop on an Entry widget."""
        if not HAS_DND:
            return

        def _on_drop(event):
            path = event.data.strip()
            # tkdnd wraps paths with spaces in {}
            if path.startswith("{") and path.endswith("}"):
                path = path[1:-1]
            var.set(path)
            widget.configure(highlightbackground=BG2, highlightcolor=BG2)
            # Auto-load JSON if dropped on json field
            if var is self.json_path and path.lower().endswith(".json"):
                self.output_dir.set(os.path.dirname(path))
                self._load_json(path)

        def _on_enter(event):
            widget.configure(highlightbackground=GREEN, highlightcolor=GREEN)
            return event.action

        def _on_leave(event):
            widget.configure(highlightbackground=BG2, highlightcolor=BG2)

        widget.configure(highlightthickness=2, highlightbackground=BG2, highlightcolor=BG2)
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<DropEnter>>", _on_enter)
        widget.dnd_bind("<<DropLeave>>", _on_leave)
        widget.dnd_bind("<<Drop>>", _on_drop)

    def _style_btn(self, parent, text, command, bg=BG3, fg=FG, width=None):
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                        activebackground=BG2, activeforeground=FG, relief="flat",
                        font=("Segoe UI", 10), cursor="hand2", padx=10, pady=4)
        if width:
            btn.configure(width=width)
        return btn

    def _label(self, parent, text, **kw):
        fg = kw.pop("fg", FG)
        return tk.Label(parent, text=text, bg=BG, fg=fg,
                        font=kw.pop("font", ("Segoe UI", 10)), **kw)

    def _entry_row(self, parent, label_text, var, btn_text, btn_cmd, is_dir=False):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", pady=3)
        self._label(frame, label_text).pack(side="left")
        e = tk.Entry(frame, textvariable=var, bg=BG2, fg=FG, insertbackground=FG,
                     relief="flat", font=("Segoe UI", 9))
        e.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self._style_btn(frame, btn_text, btn_cmd).pack(side="right")
        self._setup_dnd(e, var, is_dir=is_dir)
        return e

    def _build_ui(self):
        # Title
        tk.Label(self, text="⚽ Fútbol Clipper - Compilador", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(pady=(15, 10))

        main = tk.Frame(self, bg=BG, padx=20)
        main.pack(fill="both", expand=True)

        # ── File selectors ──
        self._label(main, "📁 Archivos", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 2))
        
        # Project buttons row
        proj_btn_frame = tk.Frame(main, bg=BG)
        proj_btn_frame.pack(fill="x", pady=(0, 3))
        self._style_btn(proj_btn_frame, "💾 Guardar proyecto", self._save_project, bg=BG3, width=18).pack(side="left")
        self._style_btn(proj_btn_frame, "📂 Abrir proyecto", self._open_project, bg=BG3, width=18).pack(side="left", padx=5)
        
        self._entry_row(main, "JSON:", self.json_path, "Seleccionar...", self._pick_json)
        
        # ── Modo de archivo ──
        modo_frame = tk.Frame(main, bg=BG)
        modo_frame.pack(fill="x", pady=(5, 5))
        self._label(modo_frame, "📹 Archivos de video:").pack(anchor="w")
        
        modo_radio_frame = tk.Frame(modo_frame, bg=BG)
        modo_radio_frame.pack(anchor="w", pady=(2, 5))
        rb1 = tk.Radiobutton(modo_radio_frame, text="2 archivos (1T y 2T separados)", 
                             variable=self.modo_archivo, value="2archivos",
                             bg=BG, fg=FG, selectcolor=BG2, activebackground=BG, activeforeground=FG,
                             font=("Segoe UI", 10), command=self._toggle_modo_archivo)
        rb1.pack(side="left", padx=(0, 15))
        rb2 = tk.Radiobutton(modo_radio_frame, text="1 archivo (partido completo)", 
                             variable=self.modo_archivo, value="1completo",
                             bg=BG, fg=FG, selectcolor=BG2, activebackground=BG, activeforeground=FG,
                             font=("Segoe UI", 10), command=self._toggle_modo_archivo)
        rb2.pack(side="left")
        
        # Frame contenedor para videos - SIEMPRE packeado
        self.video_container = tk.Frame(main, bg=BG)
        self.video_container.pack(fill="x")
        
        # Frame para modo 2 archivos
        self.frame_2archivos = tk.Frame(self.video_container, bg=BG)
        self.frame_2archivos.pack(fill="x", expand=True)
        self._entry_row(self.frame_2archivos, "1er Tiempo:", self.video1_path, "Seleccionar...", self._pick_v1)
        self._entry_row(self.frame_2archivos, "2do Tiempo:", self.video2_path, "Seleccionar...", self._pick_v2)
        
        # Frame para modo 1 archivo completo
        self.frame_1completo = tk.Frame(self.video_container, bg=BG)
        self._entry_row(self.frame_1completo, "Video completo:", self.video_full_path, "Seleccionar...", self._pick_vfull)
        
        # Inputs de minutos DENTRO del frame_1completo
        self.minutos_frame = tk.Frame(self.frame_1completo, bg=BG)
        
        # Minuto inicio 1T - formato MM:SS
        tk.Frame(self.minutos_frame, bg=BG).pack(side="left")  # spacer para alinear con label
        self._label(self.minutos_frame, "Minuto inicio 1T:").pack(side="left")
        self.minuto_inicio_1t = tk.StringVar(value="0:00")
        tk.Entry(self.minutos_frame, textvariable=self.minuto_inicio_1t,
                 width=8, bg=BG2, fg=FG, font=("Segoe UI", 10), relief="flat").pack(side="left", padx=(5, 15))
        
        # Minuto inicio 2T - formato MM:SS
        self._label(self.minutos_frame, "Minuto inicio 2T:").pack(side="left")
        self.minuto_inicio_2t = tk.StringVar(value="45:00")
        tk.Entry(self.minutos_frame, textvariable=self.minuto_inicio_2t,
                 width=8, bg=BG2, fg=FG, font=("Segoe UI", 10), relief="flat").pack(side="left", padx=5)
        
        # Labels de ayuda
        self._label(self.minutos_frame, "(MM:SS)", font=("Segoe UI", 8), fg=FG2).pack(side="left", padx=(5, 0))
        
        self.minutos_frame.pack(fill="x", pady=(5, 0), padx=28)
        
        # Ocultar inicialmente frame_1completo
        self.frame_1completo.pack_forget()
        
        # Frame para carpeta de salida
        self.carpeta_salida_frame = tk.Frame(main, bg=BG)
        self._entry_row(self.carpeta_salida_frame, "📁 Carpeta salida:", self.output_dir, "Seleccionar...", self._pick_outdir, is_dir=True)
        self.carpeta_salida_frame.pack(fill="x")

        # ── Options ──
        sep = tk.Frame(main, bg=BG3, height=1)
        sep.pack(fill="x", pady=10)

        self._label(main, "⚙️ Opciones", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

        opts = tk.Frame(main, bg=BG)
        opts.pack(fill="x")

        # Row 1: padding + transition
        r1 = tk.Frame(opts, bg=BG)
        r1.pack(fill="x", pady=2)
        self._label(r1, "Padding (s):").pack(side="left")
        tk.Spinbox(r1, from_=0, to=10, increment=0.5, textvariable=self.padding,
                   width=5, bg=BG2, fg=FG, font=("Segoe UI", 10), relief="flat").pack(side="left", padx=(5, 20))
        self._label(r1, "Transición:").pack(side="left")
        cb = ttk.Combobox(r1, textvariable=self.transition, values=["Ninguna", "Fade", "CrossFade"],
                          width=10, state="readonly")
        cb.pack(side="left", padx=5)
        self._label(r1, "Duración (s):").pack(side="left", padx=(10, 0))
        tk.Spinbox(r1, from_=0.1, to=3.0, increment=0.1, textvariable=self.trans_dur,
                   width=5, bg=BG2, fg=FG, font=("Segoe UI", 10), relief="flat").pack(side="left", padx=5)

        # Row 2: overlay + watermark
        r2 = tk.Frame(opts, bg=BG)
        r2.pack(fill="x", pady=2)
        tk.Checkbutton(r2, text="Overlay de minuto", variable=self.overlay,
                       bg=BG, fg=FG, selectcolor=BG2, activebackground=BG,
                       activeforeground=FG, font=("Segoe UI", 10)).pack(side="left")

        r3 = tk.Frame(opts, bg=BG)
        r3.pack(fill="x", pady=2)
        self._label(r3, "Marca de agua:").pack(side="left")
        tk.Entry(r3, textvariable=self.watermark, bg=BG2, fg=FG, insertbackground=FG,
                 relief="flat", font=("Segoe UI", 9), width=18).pack(side="left", padx=5)
        self._label(r3, "Fuente:").pack(side="left", padx=(5, 0))
        ttk.Combobox(r3, textvariable=self.wm_font, values=["Segoe UI", "Arial", "Inter", "Core Sans", "Verdana", "Tahoma", "Georgia", "Impact"],
                     width=10, state="readonly").pack(side="left", padx=3)
        self._label(r3, "Tamaño:").pack(side="left", padx=(5, 0))
        ttk.Combobox(r3, textvariable=self.wm_size, values=["pequeño", "mediano", "grande"],
                     width=8, state="readonly").pack(side="left", padx=3)
        self._label(r3, "Opacidad:").pack(side="left", padx=(5, 0))
        tk.Scale(r3, variable=self.wm_opacity, from_=10, to=100, orient="horizontal",
                 bg=BG, fg=FG, troughcolor=BG2, highlightthickness=0, length=60,
                 showvalue=False, sliderlength=12).pack(side="left", padx=2)
        self.wm_opacity_label = self._label(r3, "70%", font=("Segoe UI", 9))
        self.wm_opacity_label.pack(side="left")
        self.wm_opacity.trace_add("write", lambda *_: self.wm_opacity_label.config(text=f"{self.wm_opacity.get()}%"))

        # Row 4: music
        r4 = tk.Frame(opts, bg=BG)
        r4.pack(fill="x", pady=2)
        self._label(r4, "🎵 Música:").pack(side="left")
        music_entry = tk.Entry(r4, textvariable=self.music_path, bg=BG2, fg=FG, insertbackground=FG,
                 relief="flat", font=("Segoe UI", 9), width=25)
        music_entry.pack(side="left", padx=5, fill="x", expand=True)
        self._style_btn(r4, "Seleccionar...", self._pick_music).pack(side="left")
        self._setup_dnd(music_entry, self.music_path)

        r5 = tk.Frame(opts, bg=BG)
        r5.pack(fill="x", pady=2)
        self._label(r5, "Volumen música:").pack(side="left")
        tk.Scale(r5, from_=0, to=100, orient="horizontal", variable=self.music_vol,
                 bg=BG, fg=FG, troughcolor=BG3, highlightthickness=0, length=200,
                 font=("Segoe UI", 8)).pack(side="left", padx=5)
        self._label(r5, "%").pack(side="left")

        # Row 6: remove original audio
        r6 = tk.Frame(opts, bg=BG)
        r6.pack(fill="x", pady=2)
        tk.Checkbutton(r6, text="🔇 Quitar audio original", variable=self.remove_audio,
                       bg=BG, fg=FG, selectcolor=BG2, activebackground=BG,
                       activeforeground=FG, font=("Segoe UI", 10)).pack(side="left")

        # ── Players ──
        sep2 = tk.Frame(main, bg=BG3, height=1)
        sep2.pack(fill="x", pady=10)

        self._label(main, "👥 Jugadores", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

        self.players_frame = tk.Frame(main, bg=BG2, relief="flat", padx=10, pady=5)
        self.players_frame.pack(fill="x")
        self._label(self.players_frame, "Cargá un JSON para ver los jugadores", fg=FG2).pack()

        # ── Compile button ──
        sep3 = tk.Frame(main, bg=BG3, height=1)
        sep3.pack(fill="x", pady=10)

        self.compile_btn = tk.Button(
            main, text="▶  COMPILAR", command=self._compile,
            bg=GREEN_DARK, fg="white", activebackground=GREEN, activeforeground="black",
            font=("Segoe UI", 14, "bold"), relief="flat", cursor="hand2", pady=8
        )
        self.compile_btn.pack(fill="x", pady=(5, 5))

        # Progress
        self.progress_label = self._label(main, "", fg=FG2)
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(main, mode="determinate", length=400)
        self.progress_bar.pack(fill="x", pady=(2, 5))

        self.open_folder_btn = self._style_btn(main, "📂 Abrir carpeta de salida",
                                                self._open_output, bg=BG3)
        self.open_folder_btn.pack(fill="x", pady=(0, 10))
        self.open_folder_btn.pack_forget()

    # ── File pickers ──
    def _pick_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if p:
            self.json_path.set(p)
            self.output_dir.set(os.path.dirname(p))
            self._load_json(p)

    def _save_project(self):
        """Save current project to .fcproj file."""
        if not self.json_data:
            messagebox.showwarning("Atención", "No hay datos del proyecto para guardar.")
            return
        
        # Get players with their intervals and tags
        players_to_save = []
        for p, var in self.player_vars:
            players_to_save.append({
                "name": p["name"],
                "selected": var.get(),
                "intervals": p.get("intervals", [])
            })
        
        project_data = {
            "appVersion": APP_VERSION,
            "match": self.json_data.get("match", ""),
            "date": self.json_data.get("date", ""),
            "players": players_to_save,
            "config": {
                "video1": self.video1_path.get(),
                "video2": self.video2_path.get(),
                "output_dir": self.output_dir.get(),
                "padding": self.padding.get(),
                "transition": self.transition.get(),
                "transition_duration": self.trans_dur.get(),
                "overlay": self.overlay.get(),
                "watermark": self.watermark.get(),
                "watermark_size": self.wm_size.get(),
                "watermark_font": self.wm_font.get(),
                "watermark_opacity": self.wm_opacity.get(),
                "music": self.music_path.get(),
                "music_volume": self.music_vol.get(),
                "remove_audio": self.remove_audio.get(),
                "modo_archivo": self.modo_archivo.get(),
                "video_full_path": self.video_full_path.get(),
                "minuto_inicio_1t": self.minuto_inicio_1t.get(),
                "minuto_inicio_2t": self.minuto_inicio_2t.get(),
            }
        }
        
        default_name = sanitize_filename(self.json_data.get("match", "proyecto"))
        p = filedialog.asksaveasfilename(
            defaultextension=".fcproj",
            filetypes=[("Fútbol Clipper Project", "*.fcproj"), ("Todos", "*.*")],
            initialfile=f"{default_name}.fcproj"
        )
        if p:
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Guardado", f"Proyecto guardado:\n{p}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el proyecto:\n{e}")

    def _open_project(self):
        """Open a .fcproj file."""
        p = filedialog.askopenfilename(
            filetypes=[("Fútbol Clipper Project", "*.fcproj"), ("Todos", "*.*")]
        )
        if not p:
            return
        
        try:
            with open(p, "r", encoding="utf-8") as f:
                project_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el proyecto:\n{e}")
            return
        
        # Restore config
        config = project_data.get("config", {})
        self.video1_path.set(config.get("video1", ""))
        self.video2_path.set(config.get("video2", ""))
        self.output_dir.set(config.get("output_dir", ""))
        self.padding.set(config.get("padding", 2.0))
        self.transition.set(config.get("transition", "Fade"))
        self.trans_dur.set(config.get("transition_duration", 0.5))
        self.overlay.set(config.get("overlay", True))
        self.watermark.set(config.get("watermark", ""))
        self.wm_size.set(config.get("watermark_size", "mediano"))
        self.wm_font.set(config.get("watermark_font", "Segoe UI"))
        self.wm_opacity.set(config.get("watermark_opacity", 70))
        self.music_path.set(config.get("music", ""))
        self.music_vol.set(config.get("music_volume", 20))
        self.remove_audio.set(config.get("remove_audio", False))
        
        # Restore modo archivo settings
        self.modo_archivo.set(config.get("modo_archivo", "2archivos"))
        self.video_full_path.set(config.get("video_full_path", ""))
        self.minuto_inicio_1t.set(config.get("minuto_inicio_1t", 0))
        self.minuto_inicio_2t.set(config.get("minuto_inicio_2t", 45))
        self._toggle_modo_archivo()
        
        # Restore JSON data structure
        self.json_data = {
            "match": project_data.get("match", ""),
            "date": project_data.get("date", ""),
            "players": []
        }
        
        # Restore players
        for p_data in project_data.get("players", []):
            player_entry = {
                "name": p_data["name"],
                "intervals": p_data.get("intervals", [])
            }
            self.json_data["players"].append(player_entry)
        
        # Rebuild UI
        self._build_players_list(project_data.get("players", []))
        
        messagebox.showinfo("Cargado", f"Proyecto cargado:\n{p}")

    def _build_players_list(self, players_data):
        """Build players list UI from loaded project data."""
        # Clear players frame
        for w in self.players_frame.winfo_children():
            w.destroy()
        self.player_vars.clear()
        
        if not players_data:
            self._label(self.players_frame, "No se encontraron jugadores", fg=RED).pack()
            return
        
        # Select all button
        btn_frame = tk.Frame(self.players_frame, bg=BG2)
        btn_frame.pack(fill="x", pady=(0, 5))
        self._style_btn(btn_frame, "Seleccionar todos", self._select_all).pack(side="left")
        self._style_btn(btn_frame, "Deseleccionar todos", self._deselect_all).pack(side="left", padx=5)
        
        for p_data in players_data:
            p = {"name": p_data["name"], "intervals": p_data.get("intervals", [])}
            # Ensure tags exist
            for iv in p.get("intervals", []):
                if "tags" not in iv:
                    iv["tags"] = []
            
            var = tk.BooleanVar(value=p_data.get("selected", True))
            clips = len(p.get("intervals", []))
            row = tk.Frame(self.players_frame, bg=BG2)
            row.pack(fill="x", anchor="w")
            cb = tk.Checkbutton(
                row,
                text=f"{p['name']} ({clips} clips)",
                variable=var, bg=BG2, fg=FG, selectcolor=BG3,
                activebackground=BG2, activeforeground=FG,
                font=("Segoe UI", 10)
            )
            cb.pack(side="left")
            edit_btn = tk.Button(
                row, text="✏️", command=lambda pl=p, cb_w=cb: self._edit_timestamps(pl, cb_w),
                bg=BG2, fg=ACCENT, activebackground=BG3, activeforeground=ACCENT,
                relief="flat", font=("Segoe UI", 10), cursor="hand2", padx=4, pady=0, bd=0
            )
            edit_btn.pack(side="left", padx=(4, 0))
            self.player_vars.append((p, var))

    def _pick_v1(self):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("Todos", "*.*")])
        if p:
            self.video1_path.set(p)

    def _pick_v2(self):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("Todos", "*.*")])
        if p:
            self.video2_path.set(p)

    def _pick_vfull(self):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("Todos", "*.*")])
        if p:
            self.video_full_path.set(p)

    def _pick_outdir(self):
        p = filedialog.askdirectory()
        if p:
            self.output_dir.set(p)

    def _pick_music(self):
        p = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.aac *.m4a"), ("Todos", "*.*")])
        if p:
            self.music_path.set(p)

    def _load_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.json_data = data
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el JSON:\n{e}")
            return

        # Clear players frame
        for w in self.players_frame.winfo_children():
            w.destroy()
        self.player_vars.clear()

        players = data.get("players", [])
        if not players:
            self._label(self.players_frame, "No se encontraron jugadores en el JSON", fg=RED).pack()
            return

        # Assign fixed chronological IDs to intervals
        for p in players:
            for i, iv in enumerate(p.get("intervals", [])):
                if "id" not in iv:
                    iv["id"] = i + 1
                if "tags" not in iv:
                    iv["tags"] = []

        # Select all button
        btn_frame = tk.Frame(self.players_frame, bg=BG2)
        btn_frame.pack(fill="x", pady=(0, 5))
        self._style_btn(btn_frame, "Seleccionar todos", self._select_all).pack(side="left")
        self._style_btn(btn_frame, "Deseleccionar todos", self._deselect_all).pack(side="left", padx=5)

        for p in players:
            var = tk.BooleanVar(value=True)
            clips = len(p.get("intervals", []))
            row = tk.Frame(self.players_frame, bg=BG2)
            row.pack(fill="x", anchor="w")
            cb = tk.Checkbutton(
                row,
                text=f"{p['name']} ({clips} clips)",
                variable=var, bg=BG2, fg=FG, selectcolor=BG3,
                activebackground=BG2, activeforeground=FG,
                font=("Segoe UI", 10)
            )
            cb.pack(side="left")
            edit_btn = tk.Button(
                row, text="✏️", command=lambda pl=p, cb_w=cb: self._edit_timestamps(pl, cb_w),
                bg=BG2, fg=ACCENT, activebackground=BG3, activeforeground=ACCENT,
                relief="flat", font=("Segoe UI", 10), cursor="hand2", padx=4, pady=0, bd=0
            )
            edit_btn.pack(side="left", padx=(4, 0))
            self.player_vars.append((p, var))

    def _select_all(self):
        for _, v in self.player_vars:
            v.set(True)

    def _deselect_all(self):
        for _, v in self.player_vars:
            v.set(False)

    # ── Timestamp Editor ──
    def _edit_timestamps(self, player, checkbox_widget):
        win = tk.Toplevel(self)
        win.title(f"Editar intervalos - {player['name']}")
        win.configure(bg=BG)
        win.geometry("580x550")
        win.resizable(False, True)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text=f"⏱ Intervalos de {player['name']}", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(pady=(10, 5))

        # Reorder checkbox
        reorder_var = tk.BooleanVar(value=False)

        reorder_frame = tk.Frame(win, bg=BG)
        reorder_frame.pack(fill="x", padx=10, pady=(0, 5))
        reorder_cb = tk.Checkbutton(
            reorder_frame, text="🔀 Modificar línea de tiempo (reordenar clips)",
            variable=reorder_var, bg=BG, fg=FG, selectcolor=BG2,
            activebackground=BG, activeforeground=FG, font=("Segoe UI", 10),
            command=lambda: _render_intervals()
        )
        reorder_cb.pack(side="left")

        # Scrollable area
        container = tk.Frame(win, bg=BG)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas_w = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas_w.yview)
        scroll_frame = tk.Frame(canvas_w, bg=BG)

        scroll_frame.bind("<Configure>", lambda e: canvas_w.configure(scrollregion=canvas_w.bbox("all")))
        canvas_w.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas_w.configure(yscrollcommand=scrollbar.set)

        canvas_w.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mousewheel
        def _on_mousewheel(event):
            canvas_w.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas_w.bind_all("<MouseWheel>", _on_mousewheel)

        # Data list: each item is a dict {id, half, start, end, tags}
        intervals_data = []
        for iv in player.get("intervals", []):
            intervals_data.append({
                "id": iv.get("id", 0),
                "half": iv["half"],
                "start": iv["start"],
                "end": iv["end"],
                "tags": list(iv.get("tags", []))
            })

        # Track next available ID
        def _next_id():
            if not intervals_data:
                return 1
            return max(d["id"] for d in intervals_data) + 1

        def _move_interval_up(idx):
            if idx <= 0:
                return
            intervals_data[idx], intervals_data[idx - 1] = intervals_data[idx - 1], intervals_data[idx]
            _render_intervals()

        def _move_interval_down(idx):
            if idx >= len(intervals_data) - 1:
                return
            intervals_data[idx], intervals_data[idx + 1] = intervals_data[idx + 1], intervals_data[idx]
            _render_intervals()

        def _delete_interval(idx):
            intervals_data.pop(idx)
            _render_intervals()

        def _sync_from_widgets():
            """Read current widget values back into intervals_data before re-render."""
            for i, (half_var, se, ee, row) in enumerate(interval_widgets):
                if i < len(intervals_data):
                    try:
                        intervals_data[i]["half"] = half_var.get()
                    except Exception:
                        pass
                    intervals_data[i]["start"] = se.get().strip()
                    intervals_data[i]["end"] = ee.get().strip()

        interval_widgets = []  # list of (half_var, start_entry, end_entry, frame)

        # ── Tag popup ──
        def _open_tag_popup(idx):
            """Open a tag management popup for the interval at idx."""
            _sync_from_widgets()
            iv_data = intervals_data[idx]
            popup = tk.Toplevel(win)
            popup.title(f"Etiquetas - #{iv_data['id']}")
            popup.configure(bg=BG)
            popup.geometry("360x400")
            popup.resizable(False, True)
            popup.transient(win)
            popup.grab_set()

            tk.Label(popup, text=f"🏷 Etiquetas del clip #{iv_data['id']}", bg=BG, fg=ACCENT,
                     font=("Segoe UI", 12, "bold")).pack(pady=(10, 5))

            # Current tags display
            tags_container = tk.Frame(popup, bg=BG)
            tags_container.pack(fill="x", padx=10, pady=5)

            def _refresh_tags():
                for w in tags_container.winfo_children():
                    w.destroy()
                if not iv_data["tags"]:
                    tk.Label(tags_container, text="Sin etiquetas", bg=BG, fg=FG2,
                             font=("Segoe UI", 9, "italic")).pack(anchor="w")
                else:
                    row = tk.Frame(tags_container, bg=BG)
                    row.pack(fill="x")
                    for ti, tag in enumerate(iv_data["tags"]):
                        chip = tk.Frame(row, bg=tag["color"], padx=6, pady=2)
                        chip.pack(side="left", padx=2, pady=2)
                        tc = _text_color_for_bg(tag["color"])
                        tk.Label(chip, text=tag["text"], bg=tag["color"], fg=tc,
                                 font=("Segoe UI", 9, "bold")).pack(side="left")
                        tk.Button(chip, text="×", bg=tag["color"], fg=tc,
                                  activebackground=tag["color"], activeforeground=tc,
                                  relief="flat", font=("Segoe UI", 9, "bold"), bd=0, padx=2,
                                  cursor="hand2",
                                  command=lambda t=ti: (_remove_tag(t))).pack(side="left")

            def _remove_tag(ti):
                iv_data["tags"].pop(ti)
                _refresh_tags()

            _refresh_tags()

            # Quick tags
            tk.Label(popup, text="Etiquetas rápidas:", bg=BG, fg=FG,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(10, 3))
            quick_frame = tk.Frame(popup, bg=BG)
            quick_frame.pack(fill="x", padx=10)
            for qt_text, qt_color in QUICK_TAGS:
                tc = _text_color_for_bg(qt_color)
                tk.Button(quick_frame, text=qt_text, bg=qt_color, fg=tc,
                          activebackground=qt_color, activeforeground=tc,
                          relief="flat", font=("Segoe UI", 9, "bold"), padx=6, pady=2,
                          cursor="hand2",
                          command=lambda t=qt_text, c=qt_color: (_add_tag(t, c))).pack(side="left", padx=2, pady=2)

            # Custom tag section
            sep = tk.Frame(popup, bg=BG3, height=1)
            sep.pack(fill="x", padx=10, pady=8)

            tk.Label(popup, text="Etiqueta personalizada:", bg=BG, fg=FG,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(0, 3))

            custom_frame = tk.Frame(popup, bg=BG)
            custom_frame.pack(fill="x", padx=10)

            # Color selector
            selected_color = tk.StringVar(value="#3498db")

            color_frame = tk.Frame(custom_frame, bg=BG)
            color_frame.pack(fill="x", pady=3)
            tk.Label(color_frame, text="Color:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
            for cname, cval in TAG_COLORS.items():
                def _make_sel(c=cval):
                    selected_color.set(c)
                    _update_color_indicator()
                btn = tk.Button(color_frame, text="  ", bg=cval, activebackground=cval,
                                relief="flat", width=2, cursor="hand2", command=_make_sel)
                btn.pack(side="left", padx=1)

            color_indicator = tk.Frame(color_frame, bg=selected_color.get(), width=16, height=16)
            color_indicator.pack(side="left", padx=(6, 0))
            color_indicator.pack_propagate(False)

            def _update_color_indicator():
                color_indicator.configure(bg=selected_color.get())

            # Text input
            text_frame = tk.Frame(custom_frame, bg=BG)
            text_frame.pack(fill="x", pady=3)
            tk.Label(text_frame, text="Texto:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
            tag_text_entry = tk.Entry(text_frame, bg=BG2, fg=FG, insertbackground=FG,
                                      relief="flat", font=("Segoe UI", 9), width=20)
            tag_text_entry.pack(side="left", padx=5, fill="x", expand=True)

            def _add_tag(text, color):
                if text.strip():
                    iv_data["tags"].append({"text": text.strip(), "color": color})
                    _refresh_tags()

            def _add_custom():
                _add_tag(tag_text_entry.get(), selected_color.get())
                tag_text_entry.delete(0, "end")

            tk.Button(text_frame, text="Agregar", bg=BG3, fg=GREEN,
                      activebackground=BG2, activeforeground=GREEN,
                      relief="flat", font=("Segoe UI", 9), cursor="hand2", padx=8,
                      command=_add_custom).pack(side="left", padx=5)

            # Close
            tk.Button(popup, text="Cerrar", bg=BG3, fg=FG,
                      activebackground=BG2, activeforeground=FG,
                      relief="flat", font=("Segoe UI", 10), cursor="hand2", padx=15, pady=4,
                      command=lambda: (popup.grab_release(), popup.destroy())).pack(pady=10)

        # ── Drag & Drop state ──
        drag_state = {"active": False, "from_idx": -1, "indicator": None, "drop_idx": -1}
        outer_widgets = []  # list of outer frames, parallel to intervals_data

        def _drag_start(event, idx):
            """Start dragging interval at idx."""
            if not reorder_var.get():
                return
            _sync_from_widgets()
            drag_state["active"] = True
            drag_state["from_idx"] = idx
            drag_state["drop_idx"] = idx
            # Highlight the dragged row
            if idx < len(outer_widgets):
                outer_widgets[idx].configure(bg="#3a3a5c")
                for child in outer_widgets[idx].winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(highlightbackground=ACCENT, highlightthickness=2)

        def _drag_motion(event, idx):
            """Track mouse during drag."""
            if not drag_state["active"]:
                return
            # Remove old indicator
            if drag_state["indicator"]:
                drag_state["indicator"].destroy()
                drag_state["indicator"] = None

            # Calculate drop position based on mouse Y in scroll_frame coords
            mouse_y = event.widget.winfo_rooty() + event.y
            drop_idx = len(outer_widgets)  # default: end
            for i, ow in enumerate(outer_widgets):
                ow_y = ow.winfo_rooty()
                ow_h = ow.winfo_height()
                mid = ow_y + ow_h // 2
                if mouse_y < mid:
                    drop_idx = i
                    break

            drag_state["drop_idx"] = drop_idx

            # Draw indicator line
            if drop_idx < len(outer_widgets):
                ref_widget = outer_widgets[drop_idx]
                indicator = tk.Frame(scroll_frame, bg=GREEN, height=3)
                # Insert before the target
                indicator.pack(before=ref_widget, fill="x", pady=0)
            else:
                indicator = tk.Frame(scroll_frame, bg=GREEN, height=3)
                indicator.pack(fill="x", pady=0)
            drag_state["indicator"] = indicator

        def _drag_end(event, idx):
            """Drop the interval."""
            if not drag_state["active"]:
                return
            drag_state["active"] = False

            # Clean up indicator
            if drag_state["indicator"]:
                drag_state["indicator"].destroy()
                drag_state["indicator"] = None

            from_idx = drag_state["from_idx"]
            drop_idx = drag_state["drop_idx"]

            # Adjust drop index if dropping after the original position
            if from_idx < drop_idx:
                drop_idx -= 1

            if from_idx != drop_idx and 0 <= drop_idx <= len(intervals_data) - 1:
                item = intervals_data.pop(from_idx)
                intervals_data.insert(drop_idx, item)
                _render_intervals()
            else:
                # Reset visual without re-render
                _render_intervals()

        def _render_intervals():
            """Rebuild all interval rows from intervals_data."""
            # Clear existing widgets
            for w in scroll_frame.winfo_children():
                w.destroy()
            interval_widgets.clear()
            outer_widgets.clear()

            show_reorder = reorder_var.get()

            for idx, iv_data in enumerate(intervals_data):
                # Outer container for row + tags
                outer = tk.Frame(scroll_frame, bg=BG, pady=1)
                outer.pack(fill="x", pady=1)
                outer_widgets.append(outer)

                row = tk.Frame(outer, bg=BG2, padx=8, pady=4)
                row.pack(fill="x")

                # Drag handle (only when reorder is ON)
                if show_reorder:
                    handle = tk.Label(row, text="⠿", bg=BG2, fg=FG2,
                                      font=("Segoe UI", 12), cursor="fleur", padx=2)
                    handle.pack(side="left", padx=(0, 4))
                    handle.bind("<ButtonPress-1>", lambda e, i=idx: _drag_start(e, i))
                    handle.bind("<B1-Motion>", lambda e, i=idx: _drag_motion(e, i))
                    handle.bind("<ButtonRelease-1>", lambda e, i=idx: _drag_end(e, i))
                    # Hover effect
                    handle.bind("<Enter>", lambda e, h=handle: h.configure(fg=ACCENT))
                    handle.bind("<Leave>", lambda e, h=handle: h.configure(fg=FG2))

                # Fixed ID label
                tk.Label(row, text=f"#{iv_data['id']}", bg=BG2, fg=ACCENT,
                         font=("Segoe UI", 10, "bold"), width=3).pack(side="left")

                half_var = tk.IntVar(value=iv_data["half"])
                tk.Label(row, text="T:", bg=BG2, fg=FG, font=("Segoe UI", 9)).pack(side="left")
                tk.Spinbox(row, from_=1, to=2, width=2, textvariable=half_var,
                           bg=BG3, fg=FG, font=("Segoe UI", 9), relief="flat").pack(side="left", padx=(2, 8))

                tk.Label(row, text="De:", bg=BG2, fg=FG, font=("Segoe UI", 9)).pack(side="left")
                se = tk.Entry(row, bg=BG3, fg=FG, insertbackground=FG, relief="flat",
                              font=("Segoe UI", 9), width=7)
                se.insert(0, iv_data["start"])
                se.pack(side="left", padx=(2, 8))

                tk.Label(row, text="A:", bg=BG2, fg=FG, font=("Segoe UI", 9)).pack(side="left")
                ee = tk.Entry(row, bg=BG3, fg=FG, insertbackground=FG, relief="flat",
                              font=("Segoe UI", 9), width=7)
                ee.insert(0, iv_data["end"])
                ee.pack(side="left", padx=(2, 8))

                interval_widgets.append((half_var, se, ee, row))

                # Right side buttons: tag, reorder, delete
                tk.Button(row, text="🗑", command=lambda i=idx: (_sync_from_widgets(), _delete_interval(i)),
                          bg=BG2, fg=RED, activebackground=BG3, activeforeground=RED, relief="flat",
                          font=("Segoe UI", 10), cursor="hand2", bd=0, padx=4).pack(side="right")

                if show_reorder:
                    _idx = idx
                    tk.Button(row, text="▼", command=lambda i=_idx: (_sync_from_widgets(), _move_interval_down(i)),
                              bg=BG2, fg=FG2, activebackground=BG3, activeforeground=FG,
                              relief="flat", font=("Segoe UI", 8), cursor="hand2", bd=0, padx=2, width=2).pack(side="right")
                    tk.Button(row, text="▲", command=lambda i=_idx: (_sync_from_widgets(), _move_interval_up(i)),
                              bg=BG2, fg=FG2, activebackground=BG3, activeforeground=FG,
                              relief="flat", font=("Segoe UI", 8), cursor="hand2", bd=0, padx=2, width=2).pack(side="right")

                tk.Button(row, text="🏷", command=lambda i=idx: (_sync_from_widgets(), _open_tag_popup(i)),
                          bg=BG2, fg=FG, activebackground=BG3, activeforeground=ACCENT, relief="flat",
                          font=("Segoe UI", 10), cursor="hand2", bd=0, padx=4).pack(side="right")

                # Tag chips below the row
                if iv_data.get("tags"):
                    tags_row = tk.Frame(outer, bg=BG)
                    tags_row.pack(fill="x", anchor="w", padx=(45, 10), pady=(0, 4))
                    for tag in iv_data["tags"]:
                        tc = _text_color_for_bg(tag["color"])
                        chip = tk.Frame(tags_row, bg=tag["color"], padx=6, pady=2,
                                        highlightbackground=tag["color"], highlightthickness=0,
                                        bd=0)
                        chip.pack(side="left", padx=(0, 4), pady=1)
                        tk.Label(chip, text=tag["text"], bg=tag["color"], fg=tc,
                                 font=("Segoe UI", 8, "bold"), padx=2).pack()

        # Initial render
        _render_intervals()

        # Add button
        def _add_new():
            _sync_from_widgets()
            intervals_data.append({"id": _next_id(), "half": 1, "start": "00:00", "end": "00:00", "tags": []})
            _render_intervals()

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(btn_frame, text="+ Agregar intervalo", command=_add_new,
                  bg=BG3, fg=GREEN, activebackground=BG2, activeforeground=GREEN,
                  relief="flat", font=("Segoe UI", 10), cursor="hand2", padx=10, pady=4).pack(side="left")

        def _validate_ts(ts):
            return bool(re.match(r'^\d{1,2}:\d{2}$', ts.strip()))

        def _save():
            _sync_from_widgets()
            for iv_data in intervals_data:
                if not _validate_ts(iv_data["start"]) or not _validate_ts(iv_data["end"]):
                    messagebox.showwarning("Formato inválido",
                                           f"Usá formato MM:SS. Encontrado: '{iv_data['start']}' → '{iv_data['end']}'",
                                           parent=win)
                    return
            player["intervals"] = [
                {"id": d["id"], "half": d["half"], "start": d["start"], "end": d["end"], "tags": d.get("tags", [])}
                for d in intervals_data
            ]
            checkbox_widget.configure(text=f"{player['name']} ({len(intervals_data)} clips)")
            canvas_w.unbind_all("<MouseWheel>")
            win.destroy()

        tk.Button(btn_frame, text="💾 Guardar", command=_save,
                  bg=GREEN_DARK, fg="white", activebackground=GREEN, activeforeground="black",
                  relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2", padx=15, pady=4).pack(side="right")

        # Cleanup mousewheel binding on close
        def _on_close():
            canvas_w.unbind_all("<MouseWheel>")
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

    # ── Compile ──
    def _compile(self):
        # Validation
        if not self.json_data:
            messagebox.showwarning("Atención", "Seleccioná un archivo JSON primero.")
            return
        
        modo = self.modo_archivo.get()
        if modo == "2archivos":
            # Validación modo 2 archivos
            if not self.video1_path.get() or not os.path.isfile(self.video1_path.get()):
                messagebox.showwarning("Atención", "Seleccioná el video del 1er tiempo.")
                return
            if not self.video2_path.get() or not os.path.isfile(self.video2_path.get()):
                messagebox.showwarning("Atención", "Seleccioná el video del 2do tiempo.")
                return
        else:
            # Validación modo 1 archivo completo
            if not self.video_full_path.get() or not os.path.isfile(self.video_full_path.get()):
                messagebox.showwarning("Atención", "Seleccioná el video del partido completo.")
                return
            
            # Convertir MM:SS a segundos para validar
            def parse_time(s):
                try:
                    if ":" in s:
                        parts = s.split(":")
                        return int(parts[0]) * 60 + int(parts[1])
                    return int(s)
                except:
                    return 0
            
            t1 = parse_time(self.minuto_inicio_1t.get())
            t2 = parse_time(self.minuto_inicio_2t.get())
            if t2 <= t1:
                messagebox.showwarning("Atención", "El minuto de inicio del 2T debe ser mayor que el del 1T.")
                return

        # Check ffmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        except FileNotFoundError:
            messagebox.showerror("Error", "ffmpeg no encontrado. Instalalo y asegurate que esté en PATH.")
            return

        selected = [p for p, v in self.player_vars if v.get()]
        if not selected:
            messagebox.showwarning("Atención", "Seleccioná al menos un jugador.")
            return

        out_dir = self.output_dir.get() or os.path.dirname(self.json_path.get())
        os.makedirs(out_dir, exist_ok=True)

        config = {
            "data": self.json_data,
            "selected_players": selected,
            "video1": self.video1_path.get(),
            "video2": self.video2_path.get(),
            "output_dir": out_dir,
            "padding": self.padding.get(),
            "transition": self.transition.get(),
            "transition_duration": self.trans_dur.get(),
            "overlay": self.overlay.get(),
            "watermark": self.watermark.get(),
            "watermark_size": self.wm_size.get(),
            "watermark_font": self.wm_font.get(),
            "watermark_opacity": self.wm_opacity.get(),
            "music": self.music_path.get(),
            "music_volume": self.music_vol.get(),
            "remove_audio": self.remove_audio.get(),
            # Nuevos parámetros para modo partido completo
            "modo_archivo": self.modo_archivo.get(),
            "video_full": self.video_full_path.get(),
        }
        
        # Convertir MM:SS a segundos para modo 1completo
        def parse_time_to_seconds(s):
            try:
                if ":" in s:
                    parts = s.split(":")
                    return int(parts[0]) * 60 + int(parts[1])
                return int(s) * 60  # si no tiene :, assume minutos
            except:
                return 0
        
        if self.modo_archivo.get() == "1completo":
            config["minuto_inicio_1t"] = parse_time_to_seconds(self.minuto_inicio_1t.get())
            config["minuto_inicio_2t"] = parse_time_to_seconds(self.minuto_inicio_2t.get())
        else:
            config["minuto_inicio_1t"] = 0
            config["minuto_inicio_2t"] = 45 * 60  # default 45 minutos en segundos

        self._save_config()

        self.compile_btn.configure(state="disabled")
        self.open_folder_btn.pack_forget()
        self.progress_bar["value"] = 0

        def on_progress(text, pct):
            self.after(0, lambda: self._update_progress(text, pct))

        def on_done():
            self.after(0, self._on_done)

        def on_error(e):
            self.after(0, lambda: self._on_error(e))

        compiler = Compiler(config, on_progress, on_done, on_error)
        t = threading.Thread(target=compiler.run, daemon=True)
        t.start()

    def _update_progress(self, text, pct):
        self.progress_label.configure(text=text)
        self.progress_bar["value"] = pct * 100

    def _on_done(self):
        self.compile_btn.configure(state="normal")
        self.progress_label.configure(text="✅ ¡Compilación terminada!")
        self.progress_bar["value"] = 100
        self.open_folder_btn.pack(fill="x", pady=(0, 10))
        messagebox.showinfo("Listo", "¡Videos compilados exitosamente!")

    def _on_error(self, e):
        self.compile_btn.configure(state="normal")
        self.progress_label.configure(text=f"❌ Error: {e}")
        messagebox.showerror("Error", f"Hubo un error:\n{e}")

    def _open_output(self):
        d = self.output_dir.get()
        if d and os.path.isdir(d):
            os.startfile(d)


if __name__ == "__main__":
    print(f"⚽ Fútbol Clipper - Compilador v{APP_VERSION}")
    app = App()
    app.mainloop()
