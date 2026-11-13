# Costruzione del pacchetto portabile

Tutta la preparazione avviene **una sola volta** sul PC di sviluppo, che deve
avere accesso a Internet. Il pacchetto prodotto funziona poi offline.

Il repository contiene solo il codice e gli script: Python, FFmpeg, la libreria
nativa e i modelli non sono versionati (vedi `.gitignore`) e vengono presi dalle
Release o preparati qui.

## 1. Prerequisiti del PC di sviluppo

- Windows 10/11 x64.
- Accesso a Internet (solo per il download iniziale).
- Circa 3 GB liberi (Python, FFmpeg, runtime nativo e modelli).

## 2. Componenti da preparare

| Componente | Origine | Destinazione |
|------------|---------|--------------|
| Python 3.11 embedded | [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | `python/` |
| FFmpeg + ffprobe (LGPL) | build BtbN | `ffmpeg/bin/` |
| `transcribe.dll` + DLL `ggml-*.dll` | Release di `handy-computer/transcribe.cpp` | `native/` |
| Modello ASR | `scripts/fetch_models.py` | `models/gguf/parakeet-ultra-Q8_0.gguf` |
| WeSpeaker ONNX | `scripts/fetch_models.py` | `models/embeddings/wespeaker-voxceleb-resnet34-LM.onnx` |
| VAD Silero | modelli ONNX v5 inclusi nel progetto | `native/silero-vad/` |

I due file ONNX del VAD (`silero_encoder_v5.onnx`, `silero_decoder_v5.onnx`)
sono gli stessi distribuiti da `faster-whisper` (MIT), ma sono copiati
direttamente nel pacchetto: `faster-whisper` **non** è una dipendenza.

## 3. Installare le dipendenze Python

```powershell
python\python.exe -m pip install --upgrade pip
python\python.exe -m pip install -r config\requirements-top.txt
```

Il binding `transcribe-cpp` deve avere la **stessa versione** della DLL in
`native/`: il file `native/contract.json` riporta versione e hash attesi.
In alternativa si usa `scripts\fetch_transcribe_cpp.py`:

```powershell
python\python.exe scripts\fetch_transcribe_cpp.py --root native --python python\python.exe
```

## 4. Scaricare i modelli

```powershell
python\python.exe scripts\fetch_models.py --out .
```

Lo script mette i file nelle cartelle giuste e salta quelli gia' presenti.
Usa `--gguf-only` o `--embedding-only` per scaricarne uno solo.

## 5. Struttura finale

```
SubScrivo/
├── SubScrivo.cmd / SubScrivo-console.cmd
├── app.ico
├── LICENSE
├── app/                  # codice
├── config/               # requirements
├── docs/
├── ffmpeg/bin/           # ffmpeg.exe, ffprobe.exe
├── licenses/             # licenze di terze parti
├── models/gguf/          # parakeet-ultra-Q8_0.gguf
├── models/embeddings/    # wespeaker-voxceleb-resnet34-LM.onnx
├── native/               # transcribe.dll, ggml-*.dll, silero-vad/
├── python/               # interprete + site-packages
├── samples/              # audio di prova
├── scripts/              # manutenzione e test
└── work/                 # creato al primo avvio (log, cache, temp)
```

`Avvia SubScrivo.lnk` **non** va incluso: contiene percorsi assoluti e viene
ricreato automaticamente da `scripts\make_shortcut.ps1` al primo avvio.

## 6. Verifica del pacchetto

```powershell
# Offline, percorsi locali, modelli presenti
python\python.exe scripts\verify_offline.py

# Pipeline completa (trascrizione + export)
python\python.exe scripts\smoke_test.py samples\esempio_1_parlante.wav

# Pipeline completa con distinzione parlanti
python\python.exe scripts\smoke_test.py samples\esempio_2_parlanti.wav --diarize --speakers 2
```

## 7. Creare lo ZIP distribuibile

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Version 1.0.0
```

Lo script:

1. verifica che tutti i componenti (Python, FFmpeg, `transcribe.dll`, VAD,
   modello ASR, embedding) siano presenti;
2. controlla che i file `.cmd` abbiano fine riga **CRLF**;
3. copia il pacchetto in `dist\SubScrivo-1.0.0-win64\`, escludendo `work\`,
   `build\`, `dist\`, `__pycache__`, `Avvia SubScrivo.lnk` e i file `.gitkeep`;
4. normalizza i timestamp 1970 delle DLL native (il formato ZIP parte dal
   1980);
5. crea `dist\SubScrivo-1.0.0-win64.zip` e il file `.sha256`.

Usa `-SkipZip` per creare solo la cartella, senza comprimere (utile per i
test). Il risultato è pronto per la Release (vedi
[`DEPLOY.md`](DEPLOY.md)).

## 8. Versioni di riferimento

| Componente | Versione |
|------------|----------|
| Python | 3.11.x (python-build-standalone) |
| FFmpeg | build LGPL x64 (BtbN) |
| transcribe.cpp (runtime ggml) | 0.4.0 |
| onnxruntime | 1.31.0 |
| numpy | 1.26.4 |
| soundfile | 0.12.1 |
| tkinterdnd2 | 0.6.4 |
