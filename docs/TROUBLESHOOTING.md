# Risoluzione dei problemi

## La finestra non si apre

1. Avvia `SubScrivo-console.cmd`: mostra l'errore a video.
2. Controlla `work\logs\subscrivo.log`.
3. Verifica che la cartella non sia in `Program Files` o in un percorso di rete.

## Il trascinamento dei file (drag and drop) non funziona

Il drag-and-drop richiede `tkinterdnd2`, incluso nel pacchetto. Se in
`work\logs\subscrivo.log` compare:

```
Drag and drop non disponibile: tkinterdnd2 non importato
```

allora manca `python\Lib\site-packages\tkinterdnd2`.

1. Esegui **`Test-drag-and-drop.cmd`**: apre una finestra minimale e stampa
   ogni file trascinato (`DROP: {C:\percorso\file.mp3}`).
2. Se il test dice `tkinterdnd2 non importabile`, il pacchetto e' incompleto:
   ricopialo per intero (non solo `app\` o `python\`).
3. Se il test funziona ma l'app no, controlla nel log la riga
   `Drag and drop attivo su N widget`: se manca, la finestra non ha
   completato l'avvio.

## "Modello NON TROVATO" nella barra di stato

Serve il file `models\gguf\parakeet-ultra-Q8_0.gguf` (~740 MB). Preparalo sul
PC di sviluppo con:

```powershell
python\python.exe scripts\fetch_models.py --gguf-only --out .
```

## "Libreria nativa transcribe.dll non trovata"

La trascrizione usa la cartella `native\` accanto ad `app\`, con
`transcribe.dll` e le DLL `ggml-*.dll`. Copia la cartella `native\` da un
pacchetto completo oppure esegui `scripts\fetch_transcribe_cpp.py` (vedi
[`BUILD.md`](BUILD.md)).

## "Diarizzazione non disponibile"

Manca `models\embeddings\wespeaker-voxceleb-resnet34-LM.onnx`. La trascrizione
funziona lo stesso: la distinzione parlanti e' opzionale. Per attivarla:

```powershell
python\python.exe scripts\fetch_models.py --embedding-only --out .
```

## Errore "OutOfMemory" / Vulkan

Succede scegliendo "Accelerazione: auto (GPU se disponibile)" quando il modello
non entra nella memoria video. Imposta "Accelerazione: **solo CPU**": funziona
sempre, con prestazioni prevedibili.

## L'elaborazione e' molto lenta

- Parakeet Ultra GGUF lavora a circa 0,4-0,6x la durata audio su CPU recenti;
  CPU molto vecchie possono essere 2-3 volte piu' lente.
- Apri `work\config\settings.json` e imposta `"cpu_threads"` pari ai core
  fisici disponibili (0 = automatico).
- Chiudi altri programmi pesanti.
- Se hai una GPU compatibile, prova "Accelerazione: auto".

## Memoria esaurita (out of memory)

- Chiudi le altre applicazioni: il modello GGUF Q8_0 occupa ~740 MB su disco
  e circa 1 GB di RAM durante l'uso.
- Con "Accelerazione: solo CPU" la memoria video non viene usata.
- I file molto lunghi possono richiedere piu' RAM: dividili in parti.

## Errore FFmpeg / file non leggibile

- Il file potrebbe avere un codec non supportato o essere danneggiato.
- Prova a convertirlo prima con FFmpeg:
  ```
  ffmpeg\bin\ffmpeg.exe -i input.mkv -vn -ac 1 -ar 16000 output.wav
  ```
- Verifica che `ffmpeg\bin\ffmpeg.exe` esista.

## "Il file non contiene una traccia audio"

Alcuni video vengono distribuiti con video e audio in due stream separati
(DASH). Se il download ha salvato **solo la traccia video**, il file `.mp4`
e' valido ma non ha audio: non c'e' nulla da trascrivere. Il programma lo
segnala esplicitamente.

1. Verifica gli stream con l'`ffprobe` incluso:
   ```
   ffmpeg\bin\ffprobe.exe -v error -show_entries stream=codec_type,codec_name -of default=noprint_wrappers=1 "video.mp4"
   ```
   Deve comparire una riga `codec_type=audio`.
2. Se manca, procurati il file completo di audio.
3. In alternativa estrai l'audio da un'altra fonte e trascrivi il `.wav`/`.mp3`.

Il programma non scarica da URL: l'elaborazione avviene solo su file gia'
presenti sul disco (vedi [`OFFLINE.md`](OFFLINE.md)).

## Errore "OfflineViolation"

Significa che una libreria ha tentato una connessione di rete e il *network
guard* l'ha bloccata. E' il comportamento voluto in modalita' offline. Se
succede durante il normale funzionamento, annota il messaggio e apri una
segnalazione: indica il componente che ha tentato la connessione.

## Windows Defender / antivirus rallenta l'avvio

Il primo avvio puo' essere rallentato dalla scansione di migliaia di file in
`python\`. Se possibile aggiungi la cartella tra le esclusioni dell'antivirus.

## OneDrive / cartelle sincronizzate

Non eseguire il programma da una cartella sincronizzata (OneDrive, Dropbox,
Resilio...): la sincronizzazione dei file temporanei e dei modelli puo'
causare errori di accesso e rallentamenti. Copia la cartella in una posizione
locale.

## I file temporanei non vengono eliminati

Verifica di avere i permessi di scrittura nella cartella. L'applicazione
ripulisce `work\temp` all'avvio successivo se rileva un'interruzione.

## La diarizzazione confonde i parlanti

- Se conosci il numero di parlanti, impostalo esplicitamente nel campo
  "N° parlanti" (0 = automatico): migliora sensibilmente il risultato.
- Con voci molto simili, audio rumoroso o parlato sovrapposto la distinzione
  e' intrinsecamente difficile.
- La qualita' del testo non cambia: la diarizzazione assegna solo le etichette
  "Speaker 1", "Speaker 2", ...
