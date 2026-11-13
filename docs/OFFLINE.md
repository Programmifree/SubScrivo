# Funzionamento offline e portabilita'

## 1. Protezione offline e limiti

L'applicazione adotta piu' livelli di difesa:

| Livello | Meccanismo |
|---------|-----------|
| Modelli | Caricati **solo** da percorsi locali (`models/...`, `native/...`), mai da identificatori di repository |
| Cache | `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `XDG_CACHE_HOME`, `PYANNOTE_CACHE`, `NUMBA_CACHE_DIR` puntano tutti a `work/cache` |
| Proxy | `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` puntano a una porta chiusa (fallimento immediato) |
| FFmpeg / ffprobe | Tutte le invocazioni consentono solo i protocolli `file,pipe`: i file locali sono elaborabili, URL e risorse remote nei manifest vengono rifiutati |
| Network guard Python | Un hook su `socket.connect/connect_ex/sendto` rifiuta le connessioni non-loopback effettuate dal processo Python |
| transcribe.cpp (GGUF) | La libreria nativa e' in `native/` e il modello in `models/gguf/`: nessun download. Con backend `cpu` viene impostato `TRANSCRIBE_BACKENDS=cpu`, quindi il backend Vulkan non viene nemmeno inizializzato |
| ONNX Runtime | WeSpeaker (embedding) e Silero (VAD) sono file locali eseguiti con `CPUExecutionProvider` |

La whitelist di FFmpeg/ffprobe e' indipendente dal network guard Python. Sono
supportati i normali file audio/video locali; URL, streaming e playlist che
puntano a risorse remote non sono supportati. Il network guard Python e' attivo
di default, ma non e' un firewall e puo' essere disattivato con
`SUBSCRIVO_NETWORK_GUARD=0` oppure con `"network_guard": false` in
`work/config/settings.json`.

`scripts/fetch_models.py` scarica deliberatamente contenuti se eseguito sul PC
di sviluppo: non avviarlo sul PC offline. Per una garanzia a livello di sistema,
usa anche una regola firewall in uscita o scollega la rete.

## 2. Nessuna scrittura fuori dalla cartella portabile

L'applicazione imposta:

- `TMP`, `TEMP`, `TMPDIR` → `work/temp`
- cache delle librerie → `work/cache`
- `PYTHONDONTWRITEBYTECODE=1` → nessun `__pycache__` sparso
- `PYTHONNOUSERSITE=1` → nessun `site-packages` utente

Il pacchetto non usa il registro di Windows e non richiede privilegi di
amministratore: e' sufficiente avere il permesso di scrivere nella cartella in
cui si trova.

## 3. Portabilita' su un altro PC

La cartella e' autoconsistente: contiene Python (con `vcruntime140.dll`),
FFmpeg, i modelli e la libreria nativa `native/transcribe.dll` con le DLL
`ggml-*.dll`. Per spostarla:

1. Copia l'intera cartella `SubScrivo` su una chiavetta o su un altro PC
   Windows 10/11.
2. Avvia `SubScrivo.cmd` (o `Avvia SubScrivo.lnk`, ricreato automaticamente).

Non ci sono percorsi assoluti cablati: `app/portable.py` trova la radice
cercando il file `portable.ini` accanto ad `app/`.

> Se sposti la cartella mentre il programma e' in esecuzione, chiudilo prima.

## 4. File temporanei e recupero da interruzioni

- All'avvio viene scritto un sentinel `work/temp/.running`.
- All'avvio, se il sentinel e' ancora presente, significa che l'esecuzione
  precedente e' stata interrotta: `work/temp` viene svuotato automaticamente.
- Al termine di ogni elaborazione il WAV temporaneo viene eliminato.
- Alla chiusura il sentinel viene rimosso e `work/temp` ripulito.
- I log (`work/logs/subscrivo.log`) ruotano (max 1 MB + 2 copie) e
  **non contengono mai il testo delle trascrizioni**.

## 5. Cosa NON fare

- Non installare il pacchetto in `Program Files` (richiederebbe permessi di
  amministratore per scrivere `work/`).
- Non eseguire il programma da una cartella di rete lenta: la lettura del
  modello (~740 MB) sarebbe molto lenta.
- Non cancellare `work/cache` a ogni avvio: e' solo una cache, ma rigenerarla
  richiede tempo.
- Non spostare singoli file fuori dalla cartella: l'applicazione cerca `app/`,
  `python/`, `native/`, `models/` e `ffmpeg/` accanto a se'.
