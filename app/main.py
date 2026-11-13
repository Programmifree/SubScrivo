"""main.py - Punto di ingresso dell'applicazione.

Uso (dalla radice del pacchetto):
    python\\python.exe -m app.main
Il launcher SubScrivo.cmd imposta gia' il percorso corretto.
"""

from __future__ import annotations

import sys


def main() -> int:
    # Ordine importante: ambiente portabile PRIMA di qualsiasi libreria AI.
    from . import portable

    portable.setup_environment()

    from . import settings as app_settings

    try:
        current = app_settings.load()
    except Exception:
        current = {}

    if current.get("network_guard", True):
        portable.install_network_guard()

    from . import applog

    applog.setup()
    applog.get().info("Avvio applicazione (versione %s)", portable.VERSION)

    try:
        # Se tkinterdnd2 e' disponibile usiamo TkinterDnD.Tk per abilitare
        # il drag-and-drop dei file; altrimenti si degrada con tk.Tk normale.
        try:
            from tkinterdnd2 import TkinterDnD

            root = TkinterDnD.Tk()
        except Exception:
            import tkinter as tk

            root = tk.Tk()

        from .ui import App
        # Icona della finestra (non solo del collegamento): usa l'.ico del
        # pacchetto. Non critico: se fallisce si continua senza.
        try:
            icon = portable.ROOT / "app.ico"
            if icon.is_file():
                root.iconbitmap(str(icon))
        except Exception:
            pass
        App(root)
        root.mainloop()
        applog.get().info("Chiusura applicazione")
        return 0
    except Exception as exc:  # noqa: BLE001
        applog.log_error("Errore fatale all'avvio", exc)
        try:
            import tkinter.messagebox as messagebox

            messagebox.showerror(
                "Errore fatale",
                f"Impossibile avviare l'applicazione:\n\n{exc}\n\n"
                "Vedi work/logs/subscrivo.log per i dettagli.",
            )
        except Exception:
            sys.stderr.write(f"Errore fatale: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())