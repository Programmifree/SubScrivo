"""test_dnd.py - Test isolato del drag-and-drop con tkinterdnd2.

Apre una finestra minimale: trascina un file sopra e stampa a video
(esempio: "DROP: {C:\percorso\file.mp3}").
Chiudi la finestra per terminare.

Uso (dal pacchetto):
    python\python.exe scripts\test_dnd.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception as exc:  # noqa: BLE001
    print(f"ERRORE: tkinterdnd2 non importabile: {exc}")
    print(f"sys.path: {sys.path[:3]}")
    input("Premi Invio per chiudere...")
    raise SystemExit(1)


def main() -> int:
    root = TkinterDnD.Tk()
    root.title("TEST drag and drop")
    root.geometry("500x220")

    import tkinter as tk

    label = tk.Label(
        root,
        text="Trascina qui un file.\nIl percorso apparira' qui sotto e in console.",
        font=("Segoe UI", 11),
        padx=20,
        pady=30,
    )
    label.pack(fill="both", expand=True)

    info = tk.Label(root, text="(nessun drop ricevuto)", fg="#444444")
    info.pack(fill="x", pady=8)

    targets = 0

    def walk(widget) -> None:  # noqa: ANN001
        nonlocal targets
        try:
            widget.drop_target_register(DND_FILES)
            targets += 1
        except Exception as exc:  # noqa: BLE001
            print(f"registrazione fallita su {widget.winfo_class()}: {exc}")
        for child in widget.winfo_children():
            walk(child)

    def on_drop(event) -> None:  # noqa: ANN001
        print(f"DROP RICEVUTO: {event.data!r}")
        info.config(text=f"DROP: {event.data}")

    walk(root)
    # tkinterdnd2 usa dnd_bind(), NON bind(): con bind() la sostituzione
    # evento standard di Tkinter esplode con "expected integer but got '%#'".
    label.dnd_bind("<<Drop>>", on_drop)
    info.dnd_bind("<<Drop>>", on_drop)
    root.dnd_bind("<<Drop>>", on_drop)
    print(f"Widget registrati: {targets}")
    print("Trascina un file sulla finestra. Chiudi per terminare.")

    root.mainloop()
    print("Test terminato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
