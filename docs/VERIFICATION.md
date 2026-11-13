# Rapporto di verifica

> SubScrivo **1.0.0** - versione semplificata per Programmifree/GitHub.
> Ultima verifica: **13/11/2026**.

## 1. Ambiente di prova

- Windows 10/11 x64.
- Python 3.11 embedded (`python\python.exe`).
- Modello: `models\gguf\parakeet-ultra-Q8_0.gguf` (Parakeet Ultra, GGUF Q8_0).
- Diarizzazione: `models\embeddings\wespeaker-voxceleb-resnet34-LM.onnx`.
- Runtime nativo: `native\transcribe.dll` 0.4.0 + `native\silero-vad\`.
- Backend di calcolo: CPU (ggml `ggml-cpu-haswell.dll`), nessuna GPU.

## 2. Esito sintetico

| # | Prova | Esito |
|---|-------|-------|
| 1 | Import di tutti i moduli dell'app dopo la pulizia | **OK** |
| 2 | `scripts\verify_offline.py` (percorsi locali, offline, modelli) | **OK** |
| 3 | Pipeline completa su audio a 1 parlante (`smoke_test.py`) | **OK** |
| 4 | Pipeline completa con distinzione parlanti (`--diarize`) | **OK** |
| 5 | Export TXT / Markdown / SRT / JSON | **OK** |
| 6 | Pulizia dei file temporanei a fine lavoro | **OK** (nessun residuo) |
| 7 | Feature filterbank WeSpeaker (NumPy vs riferimento Kaldi a 80 canali) | **OK** (differenza max 1,3e-4) |
| 8 | Pacchetto `dist\SubScrivo-1.0.0-win64` creato con `make_release.ps1` | **OK** (1.206 MB, 4.797 file) |
| 9 | Test eseguiti **dentro** il pacchetto generato (python ridotto a 122 MB di site-packages) | **OK** |

## 3. Dettaglio delle prove

### 3.1 Offline e localizzazione dei dati

`python\python.exe scripts\verify_offline.py`:

```
Radice portabile: C:\Users\Mavaf\SubScrivo
TEMP: C:\Users\Mavaf\SubScrivo\work\temp
OK  TMP / TEMP / TMPDIR = work\temp
OK  HF_HOME, TORCH_HOME, MPLCONFIGDIR, PYANNOTE_CACHE, XDG_CACHE_HOME dentro la radice
OK  HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1
OK  network guard: destinazione esterna rifiutata senza traffico
OK  ffprobe / ffmpeg: file locale consentito, HTTP rifiutato
OK  loopback consentito
Modelli GGUF: ['parakeet-ultra-Q8_0.gguf']
WeSpeaker (diarizzazione): True
VERIFICA SUPERATA
```

### 3.2 Trascrizione a 1 parlante

`python\python.exe scripts\smoke_test.py samples\esempio_1_parlante.wav`

- Durata audio: 19,6 s; tempo totale: **8,4 s** (~0,43x).
- 1 segmento, testo con punteggiatura corretta.
- Export TXT/MD/SRT/JSON scritti in `build\testdata`.
- Nessun file temporaneo residuo.

### 3.3 Trascrizione con distinzione parlanti

`python\python.exe scripts\smoke_test.py samples\esempio_2_parlanti.wav --diarize --speakers 2`

- Durata audio: 89,1 s; tempo totale: **39,8 s** (~0,45x, trascrizione + diarizzazione).
- 7 segmenti, 4 paragrafi, **2 parlanti** rilevati.
- Cambio di parlante corretto a 24,4 s, 45,4 s, 70,0 s.
- Nessun file temporaneo residuo.

### 3.4 Export

Il file SRT contiene battute brevi sincronizzate (max ~42 caratteri, 4 s, 8
parole) con i timestamp a livello di parola forniti da Parakeet Ultra.

## 4. Pulizia eseguita in questa versione

- Rimossi da `models/` i modelli non utilizzati (Whisper, Parakeet ONNX,
  pyannote, cache HuggingFace): restano solo GGUF e WeSpeaker.
- Rimosso il motore Whisper/ONNX e il backend pyannote: unico motore
  Parakeet Ultra (GGUF) e diarizzazione WeSpeaker.
- Rimossi PyTorch/torchaudio/pyannote.audio/faster-whisper/scikit-learn dalle
  dipendenze: embedding e clustering sono implementati in NumPy + ONNX Runtime,
  il VAD Silero e' in `app\silero_vad.py` con i modelli in `native\silero-vad\`.
- `python\Lib\site-packages` alleggerito da **1450 MB a 122 MB** disinstallando
  le librerie non usate (torch, torchaudio, scipy, scikit-learn, pyannote,
  faster-whisper, huggingface-hub e dipendenze).
- `licenses/` allineato: rimossi PyTorch, torchaudio, faster-whisper, pyannote,
  Whisper, ONNX-ASR, Qwen3-ASR; aggiunti NumPy, soundfile e libsndfile.
- Interfaccia semplificata: lingua automatica, timestamp per parola sempre
  attivi, nessuna opzione ridondante.
- `LICENSE` riscritta in UTF-8 con intestazione AGPLv3 e testo integrale.
- `scripts\make_release.ps1` crea cartella + ZIP + SHA-256 verificando
  componenti e CRLF.

## 5. Cio' che resta da verificare

- Webinar reale (qualita' percepita su parlato lungo e rumoroso).
- Prova su un secondo PC senza Python installato (solo cartella copiata).
- Integrita' dell'archivio ZIP dopo il trasferimento (confronto SHA-256).
- Eventuale accelerazione Vulkan su una GPU compatibile.
