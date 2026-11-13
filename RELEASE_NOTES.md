# SubScrivo 1.0.0

Prima versione pubblica della versione semplificata di SubScrivo:
trascrizione da parlato a testo portatile, offline e senza installazione.

## Contenuto

- **Trascrizione** con **Parakeet Ultra** (GGUF Q8_0, runtime nativo
  transcribe.cpp/ggml) con timestamp per parola e punteggiatura.
- **Diarizzazione opzionale** (distinzione parlanti) con **WeSpeaker ONNX**,
  eseguita su CPU senza PyTorch.
- **Interfaccia Tkinter** con drag & drop, avanzamento, interruzione ed export
  in **TXT**, **Markdown**, **SRT** e **JSON**.
- **100% offline**: nessun download, nessuna telemetria, nessuna scrittura
  fuori dalla cartella del programma.
- **Portatile**: nessuna installazione e nessun privilegio di amministratore.

## Requisiti

- Windows 10/11 a 64 bit.
- ~2,5 GB liberi su disco (dopo l'estrazione).
- Nessuna connessione Internet.

## Installazione

1. Scarica `SubScrivo-1.0.0-win64.zip` dagli asset di questa Release.
2. Estrai **tutto** lo ZIP in una cartella locale (es. `C:\SubScrivo`).
   Evita `Program Files`, OneDrive e cartelle di rete.
3. Avvia `SubScrivo.cmd` (oppure `Avvia SubScrivo.lnk`, creato al primo avvio).

Se la finestra non si apre, avvia `SubScrivo-console.cmd`: mostra l'errore a
video. I dettagli tecnici sono in `work\logs\subscrivo.log`.

## Integrità

Il file `.sha256` allegato contiene l'impronta del pacchetto:

```powershell
Get-FileHash .\SubScrivo-1.0.0-win64.zip -Algorithm SHA256
```

## Licenza

GNU Affero General Public License v3 (AGPLv3). Il codice sorgente è in questo
repository, nella cartella `app/`.

## Attribuzioni

Parakeet Ultra: NVIDIA Corporation e Moondream (pesi CC-BY-4.0), conversione
GGUF di handy-computer/transcribe.cpp (MIT). WeSpeaker (Apache-2.0), Silero VAD
(MIT), FFmpeg (LGPLv3). Dettagli in `docs/LICENSES.md`.
