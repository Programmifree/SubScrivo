# SubScrivo

[![License: AGPL v3](https://img.shields.io/badge/license-AGPLv3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Platform: Windows 10/11 x64](https://img.shields.io/badge/platform-Windows%2010%2F11%20x64-lightgrey.svg)](#-avvio-rapido)
[![Offline: 100%](https://img.shields.io/badge/offline-100%25-success.svg)](docs/OFFLINE.md)
[![Download: Release](https://img.shields.io/badge/download-v1.0.0--win64-brightgreen.svg)](https://github.com/programmifree/SubScrivo/releases/latest)

> **Download immediato:** https://github.com/Programmifree/SubScrivo/releases/download/untagged-2fb5544663e57121f5f1/SubScrivo-1.0.0-win64.zip

Software portabile per Windows (64-bit) per la conversione automatica **da parlato a testo** (Speech-to-Text) con esportazione immediata in testo e sottotitoli **SRT sincronizzati**, ottimizzato per la distribuzione open source su GitHub e [Programmifree](https://www.programmifree.com).

---

## 🎯 Caratteristiche principali
* **Semplicità immediata**: Interfaccia grafica essenziale, supporto completo **Drag & Drop** per file audio e video, esportazione con un clic in **TXT**, **Markdown**, **SRT** e **JSON**.
* **Sottotitoli SRT intelligenti**: Segmentazione automatica a battute brevi (2–4 secondi, max ~40 caratteri) sincronizzate al millisecondo grazie ai timestamp per parola di Parakeet Ultra.
* **Unico motore integrato**: **Parakeet Ultra** (`parakeet-ultra-Q8_0.gguf`, ~700 MB):
  * Altissima velocità anche su CPU datate (circa 0,35× la durata reale dell'audio).
  * Punteggiatura accurata e rilevamento automatico della lingua.
  * Accelerazione opzionale Vulkan (se è presente una scheda video compatibile).
* **Diarizzazione opzionale**: Distinzione parlanti (*Speaker 1*, *Speaker 2*, ...) attivabile con una spunta tramite WeSpeaker.
* **100% Portabile e Offline**: Nessuna installazione, nessun account, nessuna connessione Internet richiesta durante l'uso.
* **Privacy totale**: Nessuna telemetria, nessun file scritto fuori dalla cartella del programma, pulizia automatica dei file temporanei.

---

## 🚀 Avvio rapido

1. **Estrai l'intero pacchetto** in una cartella qualsiasi (es. `C:\SubScrivo`).
   Non spostare singoli file fuori dalla cartella: l'applicazione cerca
   `python\`, `models\`, `native\` e `ffmpeg\` accanto a sé.
2. Fai doppio clic su **`SubScrivo.cmd`** oppure sul collegamento
   **`Avvia SubScrivo.lnk`**.
3. Trascina un file audio o video nella finestra, scegli il formato di
   esportazione e avvia la trascrizione.

* Sistema richiesto: **Windows 10/11 a 64 bit**. Nessuna installazione,
  nessun privilegio di amministratore, nessuna connessione Internet.
* Se la finestra non si apre, avvia **`SubScrivo-console.cmd`**: mostra
  l'errore direttamente a video.
* Il log tecnico è in **`work\logs\subscrivo.log`**.
* Il collegamento `Avvia SubScrivo.lnk` viene creato o riparato
  automaticamente a ogni avvio: se sposti la cartella, continua a funzionare.

---

## 🎵 Formati supportati

* **Ingresso**: MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA, MP4, MKV, MOV,
  AVI, WEBM, M4V, WMV, FLV.
* **Uscita**: TXT, Markdown, SRT, JSON.

---

## 📁 Struttura della cartella
```
SubScrivo/
├── SubScrivo.cmd               # Avvio applicazione (senza console)
├── SubScrivo-console.cmd       # Avvio diagnostico (con finestra console)
├── Avvia SubScrivo.lnk         # Collegamento rapido (ricreato all'avvio)
├── app.ico                     # Icona dell'applicazione e del collegamento
├── LICENSE                     # Licenza completa GNU AGPLv3 e disclaimer
├── app/                        # Codice sorgente dell'applicazione
├── models/
│   ├── gguf/                   # Modello ASR: parakeet-ultra-Q8_0.gguf
│   └── embeddings/             # Modello diarizzazione: WeSpeaker ONNX
├── native/                     # Runtime C++ (transcribe.dll / ggml) e VAD Silero
├── python/                     # Interprete Python embedded con librerie essenziali
├── ffmpeg/bin/                 # ffmpeg.exe e ffprobe.exe per estrazione audio
├── docs/                       # Documentazione tecnica
├── scripts/                    # Script di manutenzione (modelli, icona, test)
├── samples/                    # Audio di prova per i test end-to-end
├── work/                       # Dati runtime: log, impostazioni, file temporanei
└── licenses/                   # Licenze open source dei componenti inclusi
```

---

## 📚 Documentazione

| Documento | Contenuto |
|-----------|-----------|
| [`docs/BUILD.md`](docs/BUILD.md) | Preparare il pacchetto (Python, FFmpeg, runtime, modelli) |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Pubblicare su GitHub con Release e ZIP |
| [`docs/UPDATE.md`](docs/UPDATE.md) | Aggiornare codice, dipendenze e modelli |
| [`docs/OFFLINE.md`](docs/OFFLINE.md) | Come funziona la modalità offline e la portabilità |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Errori comuni e soluzioni |
| [`docs/VERIFICATION.md`](docs/VERIFICATION.md) | Test eseguiti e risultati |
| [`docs/LICENSES.md`](docs/LICENSES.md) | Licenze di software e modelli inclusi |

---

## 📜 Licenza e Condizioni d'Uso

Questo software è distribuito sotto licenza **GNU Affero General Public License v3 (AGPLv3)**.  
Il testo completo della licenza è disponibile nel file [`LICENSE`](LICENSE).

> **Nota sul nome**: *SubScrivo* è un nome indipendente scelto per questo progetto.
> Il programma non è affiliato, approvato o sponsorizzato da NVIDIA Corporation
> o Moondream. I nomi dei modelli citati (Parakeet, WeSpeaker, Silero) appartengono
> ai rispettivi titolari e sono usati solo per descrivere il software incluso.

### ⚠️ Esclusione di Responsabilità (Disclaimer "AS IS")
IL PROGRAMMA È FORNITO "COSÌ COM'È" (**AS IS**), SENZA ALCUNA GARANZIA DI NESSUN TIPO, ESPLICITA O IMPLICITA.  
IN NESSUN CASO GLI AUTORI O PROGRAMMIFREE SARANNO RESPONSABILI PER QUALSIASI DANNO DIRETTO, INDIRETTO, ACCIDENTALE O CONSEQUENZIALE (INCLUSI, A TITOLO ESEMPLIFICATIVO: GUASTI HARDWARE, PERDITA DI DATI O INTERRUZIONE DI ATTIVITÀ) DERIVANTE DALL'USO O DALL'INCAPACITÀ DI USARE QUESTO PROGRAMMA. L'UTILIZZO È A ESCLUSIVO RISCHIO DELL'UTENTE.

---

## 🙏 Attribuzioni e Riconoscimenti (CC-BY 4.0)

Si riconosce pieno merito agli autori e progetti che hanno reso possibile questa applicazione:

* **[NVIDIA Corporation](https://github.com/NVIDIA/NeMo)**: per l'architettura FastConformer / TDT e i pesi originali del modello `nvidia/parakeet-tdt-0.6b-v3` rilasciati con licenza **Creative Commons Attribution 4.0 International (CC-BY-4.0)**.
* **[Moondream](https://huggingface.co/moondream)**: per il post-training e l'ottimizzazione del modello `moondream/parakeet-ultra`, anch'esso distribuito sotto licenza **Creative Commons Attribution 4.0 International (CC-BY-4.0)**.
* **[handy-computer / transcribe.cpp](https://github.com/handy-computer/transcribe.cpp)**: per la conversione GGUF e il motore nativo di inferenza C++/ggml (Licenza MIT).
* **[WeSpeaker Project](https://github.com/wenet-e2e/wespeaker)**: per il modello di embedding e identificazione vocale (Licenza Apache-2.0).
* **[Silero VAD](https://github.com/snakers4/silero-vad)**: per l'algoritmo di Voice Activity Detection (Licenza MIT).
* **[FFmpeg Project](https://ffmpeg.org)**: per i tool di decodifica audio (Licenza LGPLv3).

---

*SubScrivo 1.0.0 — ultimo aggiornamento: 13/11/2026.*
