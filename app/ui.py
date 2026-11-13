"""ui.py - Interfaccia grafica desktop (Tkinter)."""

from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from tkinterdnd2 import DND_FILES
except Exception:  # tkinterdnd2 opzionale: senza, niente drag and drop
    DND_FILES = None

from . import applog, diarization, export, engine, portable
from . import settings as app_settings
from . import transcription

# Backend per il modello GGUF Parakeet Ultra: solo CPU o automatico (GPU Vulkan).
ASR_BACKEND_LABELS = {
    "cpu": "solo CPU",
    "auto": "auto (GPU se disponibile)",
}
ASR_LABEL_TO_KEY = {v: k for k, v in ASR_BACKEND_LABELS.items()}

AUDIO_VIDEO_TYPES = (
    "File audio/video",
    "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma "
    "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv *.flv",
)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = app_settings.load()
        self.queue: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.result: engine.JobResult | None = None
        self.input_path: Path | None = None
        self.last_dir = ""
        self.started_at = 0.0

        self.root.title(f"SubScrivo {portable.VERSION} - Programmifree")
        self.root.geometry("980x780")
        self.root.minsize(860, 640)

        self._build_menu()
        self._build_widgets()
        self._apply_settings()

        crashed = portable.startup_cleanup()
        if crashed:
            self._log(
                "Rilevata un'interruzione precedente: i file temporanei sono "
                "stati rimossi."
            )

        self._check_models()
        self._enable_drag_and_drop()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(120, self._poll_queue)

    # ------------------------------------------------------------------ UI --
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Apri file...", command=self.select_file)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(
            label="Pulisci file temporanei", command=self._menu_cleanup
        )
        tools_menu.add_command(label="Apri cartella log", command=self._open_log_dir)
        menubar.add_cascade(label="Strumenti", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Informazioni", command=self._show_about)
        menubar.add_cascade(label="?", menu=help_menu)
        self.root.config(menu=menubar)

    def _build_widgets(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Ok.TLabel", foreground="#1a7f37")
        style.configure("Warn.TLabel", foreground="#b35c00")

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # --- File di input ---
        file_frame = ttk.LabelFrame(main, text=" File di input ", padding=10)
        file_frame.pack(fill=tk.X)
        self.file_var = tk.StringVar(value="Nessun file selezionato")
        entry = ttk.Entry(file_frame, textvariable=self.file_var, state="readonly")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(file_frame, text="Scegli file...", command=self.select_file).pack(
            side=tk.RIGHT
        )

        # --- Opzioni ---
        options = ttk.LabelFrame(main, text=" Opzioni ", padding=10)
        options.pack(fill=tk.X, pady=(10, 0))

        grid = ttk.Frame(options)
        grid.pack(fill=tk.X)

        # Riga 0: Modello (fisso) e accelerazione
        ttk.Label(grid, text="Modello:").grid(row=0, column=0, sticky="w", pady=4)
        self.model_var = tk.StringVar(value=transcription.MODEL_LABEL)
        ttk.Label(
            grid,
            textvariable=self.model_var,
            font=("Segoe UI", 9, "bold"),
            foreground="#0b5cad",
        ).grid(row=0, column=1, sticky="w", padx=(6, 24), pady=4)

        ttk.Label(grid, text="Accelerazione:").grid(row=0, column=2, sticky="w", pady=4)
        self.asr_backend_var = tk.StringVar()
        ttk.Combobox(
            grid,
            textvariable=self.asr_backend_var,
            values=list(ASR_BACKEND_LABELS.values()),
            state="readonly",
            width=24,
        ).grid(row=0, column=3, sticky="w", padx=(6, 24), pady=4)

        # Riga 1: Diarizzazione e Parlanti
        ttk.Label(grid, text="Diarizzazione:").grid(row=1, column=0, sticky="w", pady=4)
        self.diarization_var = tk.BooleanVar(value=False)
        self.diarization_check = ttk.Checkbutton(
            grid,
            text="Attiva distinzione parlanti",
            variable=self.diarization_var,
            command=self._on_diarization_toggle,
        )
        self.diarization_check.grid(row=1, column=1, sticky="w", padx=(6, 24), pady=4)

        ttk.Label(grid, text="N° parlanti (0=auto):").grid(row=1, column=2, sticky="w", pady=4)
        self.speakers_var = tk.IntVar()
        self.speakers_spin = ttk.Spinbox(
            grid, from_=0, to=20, textvariable=self.speakers_var, width=6, state="disabled"
        )
        self.speakers_spin.grid(row=1, column=3, sticky="w", padx=(6, 24), pady=4)

        ttk.Label(
            options,
            text="La lingua viene rilevata automaticamente dal modello. "
            "La distinzione parlanti e' opzionale: con \"N\u00b0 parlanti\" a 0 "
            "il numero viene stimato, altrimenti indica il valore esatto (se noto) "
            "per una separazione piu' precisa.",
            style="Hint.TLabel",
            wraplength=900,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(8, 0))

        # --- Controlli ---
        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(10, 0))
        self.start_btn = ttk.Button(
            controls, text="Avvia elaborazione", command=self.start
        )
        self.start_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(
            controls, text="Interrompi", command=self.stop, state="disabled"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(controls, text="Salva:").pack(side=tk.LEFT, padx=(20, 4))
        self.save_btns = {}
        for fmt, label in (("txt", "TXT"), ("md", "Markdown"), ("srt", "SRT"), ("json", "JSON")):
            btn = ttk.Button(
                controls,
                text=label,
                command=lambda f=fmt: self.save_result(f),
                state="disabled",
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.save_btns[fmt] = btn

        # --- Avanzamento ---
        progress_frame = ttk.LabelFrame(main, text=" Avanzamento ", padding=10)
        progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100.0
        ).pack(fill=tk.X)
        self.stage_var = tk.StringVar(value="Pronto.")
        ttk.Label(progress_frame, textvariable=self.stage_var, style="Header.TLabel").pack(
            anchor="w", pady=(6, 0)
        )
        self.detail_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.detail_var, style="Hint.TLabel").pack(
            anchor="w"
        )
        self.time_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.time_var, style="Hint.TLabel").pack(
            anchor="w"
        )

        # --- Risultato ---
        result_frame = ttk.LabelFrame(main, text=" Trascrizione ", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.result_text = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=("Consolas", 10), height=16
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.tag_configure(
            "speaker", foreground="#0b5cad", font=("Consolas", 10, "bold")
        )
        self.result_text.tag_configure("meta", foreground="#444444")

        # --- Diagnostica ---
        log_frame = ttk.LabelFrame(main, text=" Messaggi ", padding=6)
        log_frame.pack(fill=tk.X, pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("Consolas", 9), height=5
        )
        self.log_text.pack(fill=tk.X, expand=False)
        self.log_text.configure(state="disabled")

        # --- Barra di stato ---
        status = ttk.Frame(self.root)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="")
        ttk.Label(status, textvariable=self.status_var, style="Ok.TLabel").pack(
            pady=4, padx=8, anchor="w"
        )

    # -------------------------------------------------------------- helpers --
    def _apply_settings(self) -> None:
        self.model_var.set(transcription.MODEL_LABEL)
        self.diarization_var.set(bool(self.settings.get("diarization", False)))
        self._on_diarization_toggle()
        self.asr_backend_var.set(
            ASR_BACKEND_LABELS.get(self.settings.get("asr_backend", "cpu"), "solo CPU")
        )
        self.speakers_var.set(int(self.settings.get("num_speakers", 1)))

    def _persist_settings(self) -> None:
        self.settings.update(
            {
                "language": "auto",
                "diarization": bool(self.diarization_var.get()),
                "asr_backend": ASR_LABEL_TO_KEY.get(
                    self.asr_backend_var.get(), "cpu"
                ),
                "num_speakers": int(self.speakers_var.get() or 0),
            }
        )
        app_settings.save(self.settings)

    def _check_models(self) -> None:
        pieces = []
        if transcription.model_available():
            pieces.append(f"Modello: {transcription.MODEL_LABEL}")
        else:
            pieces.append("Modello: NON TROVATO")

        if diarization.available():
            pieces.append("Diarizzazione: pronta")
        else:
            pieces.append("Diarizzazione: non disponibile")

        pieces.append("100% Offline | Nessun privilegio admin")
        self.status_var.set("  |  ".join(pieces))

        if not transcription.model_available():
            self._log(
                f"ATTENZIONE: modello {transcription.MODEL_FILENAME} non trovato "
                "in models/gguf/."
            )
        if not diarization.available():
            self._log(
                "Diarizzazione non disponibile: manca il modello WeSpeaker in "
                "models/embeddings/."
            )

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _menu_cleanup(self) -> None:
        removed = portable.cleanup_temp()
        self._log(f"Pulizia temporanei: {len(removed)} elementi rimossi.")

    def _open_log_dir(self) -> None:
        try:
            os.startfile(str(portable.LOG_DIR))
        except Exception as exc:  # noqa: BLE001
            self._log(f"Impossibile aprire la cartella log: {exc}")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "Informazioni",
            "SubScrivo\n\n"
            "Conversione da parlato a testo (Speech-to-Text) portabile e 100% offline.\n"
            f"Modello: {transcription.MODEL_LABEL}\n"
            "Diarizzazione opzionale: WeSpeaker (offline)\n\n"
            "Open Source per Programmifree (licenza GNU AGPLv3)\n"
            f"Versione {portable.VERSION}",
        )

    def _on_diarization_toggle(self) -> None:
        """Abilita/disabilita lo spinbox parlanti in base alla checkbox."""
        if self.diarization_var.get():
            self.speakers_spin.configure(state="normal")
            # Al primo avvio il valore e' 1 (un solo parlante): se l'utente
            # attiva la distinzione, il caso tipico e' "rileva da solo".
            if int(self.speakers_var.get() or 0) <= 1:
                self.speakers_var.set(0)
        else:
            self.speakers_spin.configure(state="disabled")

    # ---------------------------------------------------------------- input --
    def _initial_dialog_dir(self) -> str:
        """Cartella di partenza per i dialoghi file.

        Preferisce la cartella dell'ultimo file usato; in alternativa la
        home utente. Partire dalla cartella del programma rende difficile
        navigare altrove e su alcune macchine il dialogo si impantana.
        """
        if self.last_dir and Path(self.last_dir).is_dir():
            return self.last_dir
        try:
            return str(Path.home())
        except Exception:  # noqa: BLE001
            return ""

    def _set_input_file(self, path_str: str) -> None:
        """Imposta il file di input (comune a dialog e drag-and-drop)."""
        self.input_path = Path(path_str)
        self.last_dir = str(self.input_path.parent)
        try:
            size_mb = self.input_path.stat().st_size / (1024 * 1024)
            self.file_var.set(f"{self.input_path.name}  ({size_mb:.1f} MB)")
        except Exception:
            self.file_var.set(self.input_path.name)
        self._log(f"File selezionato: {self.input_path.name}")
        self.stage_var.set("File pronto. Premi 'Avvia elaborazione'.")

    def _enable_drag_and_drop(self) -> None:
        """Registra il drag-and-drop su tutti i widget della finestra.

        Non basta registrare la root: essa e' completamente coperta dai
        widget figli e il drop su un widget non registrato non produce
        nessun evento. Si registra quindi ricorsivamente ogni widget.
        """
        if not DND_FILES:
            applog.get().warning(
                "Drag and drop non disponibile: tkinterdnd2 non importato"
            )
            return
        registered = 0
        failures: list[str] = []

        def _walk(widget) -> None:  # noqa: ANN001
            nonlocal registered
            try:
                widget.drop_target_register(DND_FILES)
                # NB: qui va dnd_bind(), NON bind(): tkinterdnd2 usa una
                # sostituzione di campi evento propria (_substitute_dnd);
                # con bind() standard Tkinter esplode su "%#" e il gestore
                # non viene mai chiamato.
                widget.dnd_bind("<<Drop>>", self._on_drop)
                registered += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{widget.winfo_class()}: {exc}")
            for child in widget.winfo_children():
                _walk(child)

        _walk(self.root)
        if registered:
            applog.get().info(
                "Drag and drop attivo su %d widget (root inclusa)", registered
            )
        if failures:
            applog.get().warning(
                "Registrazione DnD fallita su: %s", "; ".join(failures[:5])
            )
        if not registered and failures:
            applog.get().warning("Drag and drop non attivo")

    def _on_drop(self, event) -> None:  # noqa: ANN001
        """Gestisce i file trascinati sulla finestra."""
        applog.get().info("Evento drop ricevuto (dati: %r)", event.data[:200])
        if self.worker and self.worker.is_alive():
            return
        raw = event.data.strip()
        if not raw:
            return
        # Windows elenca i percorsi tra parentesi graffe quando contengono
        # spazi; tkdnd separa i percorsi multipli.
        try:
            if raw.startswith("{") and "} " in raw:
                parts = [p.strip("{}") for p in raw.split("} {") if p.strip("{}")]
                paths = [parts[0].lstrip("{")] if len(parts) == 1 else parts
            elif raw.startswith("{") and raw.endswith("}"):
                paths = [raw[1:-1]]
            else:
                paths = raw.split()
        except Exception as exc:  # noqa: BLE001
            applog.get().warning("Parsing dati drop fallito: %s (raw=%r)", exc, raw)
            return
        if not paths:
            applog.get().warning("Drop ricevuto ma nessun percorso riconosciuto")
            return
        applog.get().info("Drop: percorso riconosciuto: %s", paths[0])
        try:
            self._set_input_file(paths[0])
        except Exception as exc:  # noqa: BLE001
            applog.get().warning("Impostazione file dal drop fallita: %s", exc)

    def select_file(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        initial_dir = self._initial_dialog_dir()
        path = filedialog.askopenfilename(
            title="Seleziona un file audio o video",
            parent=self.root,
            initialdir=initial_dir,
            filetypes=[AUDIO_VIDEO_TYPES, ("Tutti i file", "*.*")],
        )
        if not path:
            return
        self._set_input_file(path)

    # ---------------------------------------------------------- elaborazione --
    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.input_path or not self.input_path.exists():
            messagebox.showerror("Errore", "Seleziona prima un file audio o video.")
            return
        if not transcription.model_available():
            messagebox.showerror(
                "Errore",
                f"Modello {transcription.MODEL_FILENAME} non trovato in models/gguf/.",
            )
            return

        diarize = bool(self.diarization_var.get())
        if diarize and not diarization.available():
            messagebox.showerror(
                "Diarizzazione non disponibile",
                diarization.unavailable_reason(),
            )
            return

        self._persist_settings()
        options = engine.JobOptions(
            model_name=transcription.MODEL_FILENAME,
            language="auto",
            diarize=diarize,
            asr_backend=ASR_LABEL_TO_KEY.get(self.asr_backend_var.get(), "cpu"),
            num_speakers=int(self.speakers_var.get() or 0) if diarize else 0,
            merge_gap_s=float(self.settings.get("merge_gap_s", 1.0)),
            cluster_threshold=float(self.settings.get("cluster_threshold", 0.60)),
            cpu_threads=int(self.settings.get("cpu_threads", 0)),
            delete_temp=bool(self.settings.get("delete_temp_after_job", True)),
        )

        self.cancel = threading.Event()
        self.result = None
        self.started_at = time.time()
        self.result_text.delete("1.0", tk.END)
        self.progress_var.set(0.0)
        self.stage_var.set("Avvio...")
        self.detail_var.set("")
        self.time_var.set("")
        for btn in self.save_btns.values():
            btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        portable.mark_running()
        self.worker = threading.Thread(
            target=self._worker_run, args=(self.input_path, options), daemon=True
        )
        self.worker.start()

    def _worker_run(self, input_path: Path, options: engine.JobOptions) -> None:
        def on_progress(fraction: float, stage: str, detail: str) -> None:
            self.queue.put(("progress", fraction, stage, detail))

        try:
            result = engine.run_job(
                input_path, options, cancel=self.cancel, on_progress=on_progress
            )
            self.queue.put(("done", result))
        except InterruptedError:
            self.queue.put(("cancelled",))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))
        finally:
            portable.clear_running()

    def stop(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel.set()
            self.stop_btn.configure(state="disabled")
            self.stage_var.set("Interruzione richiesta...")
            self.detail_var.set(
                "L'interruzione avviene al termine del passaggio in corso."
            )

    # ------------------------------------------------------------- polling --
    def _poll_queue(self) -> None:
        try:
            while True:
                message = self.queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    _, fraction, stage, detail = message
                    self.progress_var.set(fraction * 100.0)
                    self.stage_var.set(stage)
                    self.detail_var.set(detail)
                    self._update_timer(fraction)
                elif kind == "done":
                    self._on_done(message[1])
                elif kind == "cancelled":
                    self._on_cancelled()
                elif kind == "error":
                    self._on_error(message[1])
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_queue)

    def _update_timer(self, fraction: float) -> None:
        elapsed = time.time() - self.started_at
        text = f"Tempo trascorso: {_fmt_duration(elapsed)}"
        if 0.02 < fraction < 1.0:
            eta = elapsed * (1.0 - fraction) / fraction
            text += f"  |  Tempo stimato rimanente: {_fmt_duration(eta)}"
        self.time_var.set(text)

    def _on_done(self, result: engine.JobResult) -> None:
        self.result = result
        self._display_result(result)
        self.progress_var.set(100.0)
        self.stage_var.set("Elaborazione completata.")
        self.detail_var.set(
            f"{len(result.paragraphs)} paragrafi, {len(result.segments)} segmenti, "
            f"{len(result.speakers)} parlanti."
        )
        self._update_timer(1.0)
        for btn in self.save_btns.values():
            btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("Elaborazione completata. Salva il risultato con i pulsanti TXT/Markdown/SRT/JSON.")

    def _on_cancelled(self) -> None:
        self.stage_var.set("Elaborazione interrotta.")
        self.detail_var.set("I file temporanei sono stati rimossi.")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("Elaborazione interrotta dall'utente.")

    def _on_error(self, message: str) -> None:
        self.stage_var.set("Errore durante l'elaborazione.")
        self.detail_var.set(message)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log(f"ERRORE: {message}")
        messagebox.showerror("Errore", message)

    def _display_result(self, result: engine.JobResult) -> None:
        has_diar = getattr(result, "backend", "off") != "off"
        text = self.result_text
        text.delete("1.0", tk.END)
        text.insert(tk.END, f"File: {result.source_name}\n", "meta")
        text.insert(tk.END, f"Durata: {export.format_timestamp(result.duration)}  |  ", "meta")
        text.insert(tk.END, f"Lingua: {str(result.language).upper()}  |  ", "meta")
        text.insert(tk.END, f"Modello: {result.model}\n", "meta")
        if has_diar:
            speakers_str = ", ".join(result.speakers) if result.speakers else "nessuno"
            text.insert(tk.END, f"Diarizzazione: {result.backend}  |  Parlanti: {speakers_str}\n", "meta")
        text.insert(tk.END, "=" * 70 + "\n\n")

        for segment in result.paragraphs:
            text_value = str(segment.get("text", "")).strip()
            if not text_value:
                continue
            if has_diar and segment.get("speaker"):
                text.insert(tk.END, f"{segment['speaker']}: ", "speaker")
            text.insert(tk.END, text_value + "\n\n")
        text.see("1.0")

    # -------------------------------------------------------------- salvataggio --
    def save_result(self, fmt: str) -> None:
        if self.result is None:
            return
        ext = {"md": ".md", "markdown": ".md"}.get(fmt, f".{fmt}")
        default_name = Path(self.result.source_name).stem + "_trascrizione" + ext
        initial_dir = str(self.input_path.parent) if self.input_path else ""
        path = filedialog.asksaveasfilename(
            title=f"Salva come {fmt.upper()}",
            defaultextension=ext,
            initialfile=default_name,
            initialdir=initial_dir,
            parent=self.root,
            filetypes=[(f"File {fmt.upper()}", f"*{ext}"), ("Tutti i file", "*.*")],
        )
        if not path:
            return
        try:
            content = export.render(self.result, fmt)
            Path(path).write_text(content, encoding="utf-8")
            self._log(f"File salvato: {Path(path).name}")
            messagebox.showinfo("Salvataggio completato", f"File salvato:\n{path}")
        except Exception as exc:  # noqa: BLE001
            applog.log_error("Errore di salvataggio", exc)
            messagebox.showerror("Errore di salvataggio", str(exc))

    # ---------------------------------------------------------------- chiusura --
    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(
                "Conferma",
                "Elaborazione in corso.\nVuoi davvero uscire e interrompere?",
            ):
                return
            self.cancel.set()
            self.worker.join(timeout=5)
        portable.cleanup_temp()
        portable.clear_running()
        self.root.destroy()


def _fmt_duration(seconds: float) -> str:
    seconds = int(max(0.0, seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:d}h {m:02d}m {s:02d}s"
    if m:
        return f"{m:d}m {s:02d}s"
    return f"{s:d}s"