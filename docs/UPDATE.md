# Aggiornare il pacchetto

Tutti gli aggiornamenti si fanno sul **PC di sviluppo**; il pacchetto viene poi
ricostruito e ricopiato. Sul PC di destinazione non deve mai essere necessario
scaricare nulla.

## 1. Aggiornare il codice dell'applicazione

I file Python modificati stanno in `app/`. Per provare subito:

```powershell
python\python.exe -m app.main
```

Poi ripeti i test di [`BUILD.md`](BUILD.md) §6 prima di ridistribuire.

## 2. Aggiornare le dipendenze Python

1. Modifica le versioni in `config\requirements-top.txt`.
2. Reinstalla nel Python portabile:

```powershell
python\python.exe -m pip install -r config\requirements-top.txt
```

L'elenco e' volutamente minimo: se aggiungi una libreria, verifica che non
scriva fuori da `work\` e che funzioni offline (vedi
[`OFFLINE.md`](OFFLINE.md)).

## 3. Aggiornare il modello di trascrizione

```powershell
# Riscarica solo il modello ASR (sovrascrive se assente)
python\python.exe scripts\fetch_models.py --gguf-only --out .
```

Il nome del file deve restare `parakeet-ultra-Q8_0.gguf` (costante
`MODEL_FILENAME` in `app\transcription.py`). Se cambi modello, aggiorna anche
`MODEL_LABEL` e i testi di README/docs.

## 4. Aggiornare l'embedding per la distinzione parlanti

```powershell
python\python.exe scripts\fetch_models.py --embedding-only --out .
```

Il file atteso e' `models\embeddings\wespeaker-voxceleb-resnet34-LM.onnx`
(costante in `app\diarization.py`).

## 5. Aggiornare il runtime nativo transcribe.cpp

DLL e binding Python devono avere la **stessa versione**:

```powershell
python\python.exe scripts\fetch_transcribe_cpp.py --root native --python python\python.exe
```

Controlla `native\contract.json` dopo l'aggiornamento.

## 6. Misurare qualita' e velocita'

```powershell
python\python.exe scripts\bench_models.py "video.mp4" `
    --language it --ref riferimento.txt --out-dir build\testdata\bench
```

Il WER e' calcolato rispetto a `--ref`. Il testo prodotto finisce in
`<out-dir>\parakeet-ultra.txt`, i segmenti in
`<out-dir>\parakeet-ultra.segments.json`.

## 7. Controllo finale dopo ogni aggiornamento

```powershell
python\python.exe scripts\verify_offline.py
python\python.exe scripts\smoke_test.py samples\esempio_1_parlante.wav
python\python.exe scripts\smoke_test.py samples\esempio_2_parlanti.wav --diarize --speakers 2
```

Poi avvia `SubScrivo.cmd`, prova un file reale e aggiorna
[`VERIFICATION.md`](VERIFICATION.md) con data e risultati.
