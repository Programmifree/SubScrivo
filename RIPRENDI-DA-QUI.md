# RIPRENDI DA QUI — Versione Semplificata Programmifree

> Aggiornato il **13/11/2026**.
> Questo repository/cartella (`SubScrivo`) è la **versione semplificata**
> derivata da `PortableWhisperDiarization` (che rimane intatta come versione
> avanzata originale).

---

## 1. Decisioni

* **Scopo**: versione leggera e intuitiva da distribuire open source su GitHub
  e Programmifree.
* **Nome**: **SubScrivo** (deciso il 01/11/2026). "Parakeet" è il nome della
  famiglia ASR NVIDIA: nei testi di attribuzione resta il riferimento ai
  modelli, non al programma.
* **Licenza**: **GNU AGPLv3** (`LICENSE` nella root, testo integrale + header
  italiano in UTF-8).
* **Unico modello integrato**: **Parakeet Ultra**
  (`models/gguf/parakeet-ultra-Q8_0.gguf`, ~740 MB) eseguito dal runtime
  nativo **transcribe.cpp** (ggml).
* **Diarizzazione**: opzionale, **WeSpeaker ONNX** (`models/embeddings/`),
  eseguita con ONNX Runtime + clustering NumPy.
* **Nessuna dipendenza da PyTorch**: embedding e clustering sono in NumPy,
  il VAD Silero è in `app/silero_vad.py` con i modelli in `native/silero-vad/`.

---

## 2. Stato: pulizia e adattamento completati (13/11/2026)

* `models/` ripulita: restano solo `gguf/` e `embeddings/` (rimossi Whisper,
  Parakeet ONNX, pyannote e cache HuggingFace).
* Motore unico GGUF: eliminati `app/parakeet.py`, il percorso Whisper
  (`Transcriber`) e il ramo Qwen3-ASR senza timestamp.
* Diarizzazione semplificata al solo backend WeSpeaker; rimossi pyannote
  pipeline e dipendenza da `sklearn` (k-means + silhouette in NumPy).
* VAD locale (`app/silero_vad.py`) al posto di `faster_whisper.vad`.
* UI semplificata: modello fisso, lingua automatica, timestamp per parola
  sempre attivi, solo accelerazione CPU/auto e diarizzazione.
* `settings.py` ridotto alle opzioni reali; i vecchi `settings.json` vengono
  filtrati automaticamente.
* Variabili d'ambiente rinominate `PWD_*` → `SUBSCRIVO_*`.
* `config/requirements-top.txt` minimo (transcribe-cpp, onnxruntime,
  numpy, soundfile, tkinterdnd2); rimossi `requirements-torch.txt` e il lock
  obsoleto.
* Script aggiornati: `fetch_models.py`, `smoke_test.py`, `bench_models.py`,
  `verify_offline.py`.
* Docs riscritti: `BUILD.md`, `UPDATE.md`, `OFFLINE.md`,
  `TROUBLESHOOTING.md`, `VERIFICATION.md`.
* Aggiunti `.gitignore` e `.gitkeep` per `models/gguf` e `models/embeddings`.
* `python/Lib/site-packages` ripulito: rimosse le librerie non più usate
  (torch, torchaudio, scipy, scikit-learn, pyannote, faster-whisper,
  huggingface-hub, ...). Da **1450 MB** a **122 MB**; restano solo numpy,
  onnxruntime, soundfile, tkinterdnd2, transcribe-cpp e le rispettive
  dipendenze.
* Licenze allineate ai componenti reali (`licenses/`): rimossi i file di
  PyTorch, faster-whisper, pyannote, Whisper, ONNX-ASR e Qwen3-ASR; aggiunte
  le licenze di NumPy, soundfile e libsndfile.
* `docs/LICENSES.md` riscritto con la tabella aggiornata dei componenti reali.
* Nuovo `scripts/make_release.ps1`: crea `dist\SubScrivo-<versione>-win64\`,
  il `.zip` e il checksum SHA-256, verificando componenti, CRLF e assenza di
  dati runtime.
* Nuovo `docs/DEPLOY.md`: procedura completa per pubblicare su GitHub.
* Test superati: `verify_offline.py`, smoke test 1 parlante e 2 parlanti con
  diarizzazione, e gli stessi test eseguiti **dentro** il pacchetto generato
  da `make_release.ps1` (vedi `docs/VERIFICATION.md`).

---

## 3. Deploy GitHub (deciso il 13/11/2026)

* **Licenza confermata: AGPLv3** ("SGPLv3" era un refuso).
* **Repository**: solo codice, docs, script, licenze, campioni audio
  (~14 MB). Nessun binario, nessun modello.
* **Release `v1.0.0`**: un unico ZIP `SubScrivo-1.0.0-win64.zip` (~600-700 MB)
  con `python/`, `ffmpeg/`, `native/` e `models/`, più il file `.sha256`.
* Procedura dettagliata in [`docs/DEPLOY.md`](docs/DEPLOY.md).

### Comandi riassuntivi

```powershell
# 1. repository
cd C:\Users\Mavaf\SubScrivo
git init
git add .
git commit -m "SubScrivo 1.0.0 - versione semplificata (Parakeet Ultra, AGPLv3)"
gh repo create SubScrivo --public --source=. --remote=origin --push

# 2. pacchetto
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Version 1.0.0

# 3. release
gh release create v1.0.0 dist\SubScrivo-1.0.0-win64.zip dist\SubScrivo-1.0.0-win64.zip.sha256 --title "SubScrivo 1.0.0" --notes-file RELEASE_NOTES.md
```

---

## 4. Note di manutenzione

* I file `.cmd` devono restare con fine riga **CRLF** (`make_release.ps1` lo
  verifica e si ferma in caso contrario).
* `Avvia SubScrivo.lnk` non va mai distribuito: contiene percorsi assoluti e
  viene ricreato da `scripts\make_shortcut.ps1` al primo avvio.
* `scripts\make_icon.ps1 -Force` ricostruisce `app.ico` dal master con le 10
  misure (16, 20, 24, 32, 40, 48, 64, 96, 128, 256).
* Se ricrei `python/` da zero, usa `config/requirements-top.txt`: include già
  tutto il necessario. Le dipendenze un tempo mancanti (PyAV, torchaudio,
  einops, narwhals) non servono più perché sono state eliminate dal codice.
