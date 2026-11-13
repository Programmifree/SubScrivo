# Deploy su GitHub

Questa guida descrive come pubblicare **SubScrivo 1.0.0** su GitHub con il
codice nel repository e i binari pesanti negli asset della Release.

## 1. Cosa va nel repository e cosa nella Release

GitHub rifiuta i file oltre 100 MB (e avvisa oltre 50 MB): per questo il
repository contiene **solo** testo e codice.

| Contenuto | Dove | Dimensione |
|-----------|------|------------|
| `app/`, `scripts/`, `docs/`, `config/`, `licenses/`, `samples/` | Repository | ~14 MB |
| `SubScrivo.cmd`, `SubScrivo-console.cmd`, `LICENSE`, `README.md`, `portable.ini`, `app.ico` | Repository | < 1 MB |
| `python/` (interprete + 122 MB di librerie) | Release (ZIP) | 175 MB |
| `ffmpeg/bin/` | Release (ZIP) | 256 MB |
| `native/` (DLL ggml, transcribe.dll, VAD) | Release (ZIP) | 55 MB |
| `models/` (Parakeet Ultra + WeSpeaker) | Release (ZIP) | 731 MB |
| `Avvia SubScrivo.lnk` | **Mai** (percorsi assoluti, ricreato all'avvio) | – |
| `work/`, `build/`, `dist/` | **Mai** (dati runtime) | – |

Il `.gitignore` incluso esclude già tutte queste voci: verifica prima del
primo commit con:

```powershell
# Nessun file tracciato deve superare 50 MB
git ls-files | ForEach-Object {
    if (Test-Path -LiteralPath $_) {
        $mb = (Get-Item -LiteralPath $_).Length / 1MB
        if ($mb -gt 50) { "{0:N1} MB  {1}" -f $mb, $_ }
    }
}
```

## 2. Struttura consigliata del repository

```
SubScrivo/
├── .gitignore
├── LICENSE
├── README.md
├── RIPRENDI-DA-QUI.md
├── SubScrivo.cmd
├── SubScrivo-console.cmd
├── Test-drag-and-drop.cmd
├── app.ico
├── portable.ini
├── app/
├── config/
├── docs/
├── licenses/
├── models/gguf/.gitkeep
├── models/embeddings/.gitkeep
├── samples/
└── scripts/
```

Le cartelle `models/gguf/` e `models/embeddings/` restano nel repository solo
con il file `.gitkeep`, così la struttura è chiara anche a chi legge il codice.

## 3. Creare il repository

### Opzione A - con GitHub CLI (consigliata)

```powershell
winget install --id GitHub.cli
gh auth login
cd C:\Users\Mavaf\SubScrivo
git init
git add .
git commit -m "SubScrivo 1.0.0 - versione semplificata (Parakeet Ultra, AGPLv3)"
gh repo create SubScrivo --public --source=. --remote=origin --push
```

### Opzione B - dal sito GitHub

1. Crea un repository pubblico chiamato `SubScrivo` (senza README, senza
   `.gitignore`, senza licenza: ci sono già).
2. Poi:

```powershell
cd C:\Users\Mavaf\SubScrivo
git init
git add .
git commit -m "SubScrivo 1.0.0 - versione semplificata (Parakeet Ultra, AGPLv3)"
git branch -M main
git remote add origin https://github.com/programmifree/SubScrivo.git
git push -u origin main
```

## 4. Creare il pacchetto distribuibile

Sul PC di sviluppo (il pacchetto deve essere completo, vedi
[`BUILD.md`](BUILD.md)):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Version 1.0.0
```

Produce:

```
dist\SubScrivo-1.0.0-win64\            cartella pronta all'uso
dist\SubScrivo-1.0.0-win64.zip         archivio (~600-700 MB)
dist\SubScrivo-1.0.0-win64.zip.sha256  impronta SHA-256
```

Lo script verifica che tutti i componenti esistano, che i `.cmd` abbiano fine
riga CRLF e non copia `work/`, `build/`, `dist/` né il collegamento `.lnk`.

## 5. Pubblicare la Release

### Con GitHub CLI

```powershell
gh release create v1.0.0 `
  "dist\SubScrivo-1.0.0-win64.zip" `
  "dist\SubScrivo-1.0.0-win64.zip.sha256" `
  --title "SubScrivo 1.0.0" `
  --notes-file RELEASE_NOTES.md
```

### Dal sito GitHub

1. Repository → **Releases** → **Draft a new release**.
2. Tag: `v1.0.0` (crea il tag sul commit `main`).
3. Titolo: `SubScrivo 1.0.0`.
4. Allega `SubScrivo-1.0.0-win64.zip` e il file `.sha256`.
5. Pubblica.

Il limite per singolo asset è 2 GB: il pacchetto da ~1,2 GB rientra
abbondantemente.

## 6. Note di rilascio (modello)

```markdown
# SubScrivo 1.0.0

Prima versione pubblica della versione semplificata.

## Contenuto
- Trascrizione con **Parakeet Ultra** (GGUF Q8_0, runtime transcribe.cpp).
- Diarizzazione opzionale con **WeSpeaker** (ONNX Runtime).
- Interfaccia Tkinter con drag & drop, export TXT/MD/SRT/JSON.
- 100% offline, portatile, nessun privilegio di amministratore.

## Requisiti
- Windows 10/11 a 64 bit.
- Nessuna installazione: scarica lo ZIP della Release, estrai tutto e avvia
  `SubScrivo.cmd`.

## Integrità
SHA-256 del pacchetto: `<hash>` (vedi file `.sha256` allegato).

## Licenza
GNU AGPLv3. Il codice sorgente è in questo repository.
```

## 7. Dopo la pubblicazione

- Aggiungi in cima al `README.md` un riquadro con il link all'ultima Release:

  ```markdown
  > **Download:** [SubScrivo 1.0.0 (Windows 64-bit)](https://github.com/programmifree/SubScrivo/releases/latest)
  ```

- Verifica che il repository non contenga file pesanti:
  lancia lo script della sezione 1 e controlla che non stampi nulla.
- Controlla che la pagina della Release mostri lo ZIP e il checksum.

## 8. Aggiornamenti futuri

1. Modifica il codice, aggiorna `portable.ini` (`version=`) e la costante in
   `app/portable.py` se serve.
2. Ripeti i test di [`VERIFICATION.md`](VERIFICATION.md).
3. Commit + push.
4. `scripts\make_release.ps1 -Version 1.0.1` e nuova Release `v1.0.1`.

## 9. GitHub Actions (opzionale)

I test end-to-end richiedono i modelli (~1 GB) e il runtime nativo, quindi non
possono girare su un runner pulito senza scaricarli. Se vuoi comunque la CI,
limitala a:

- controllo sintattico: `python -m compileall app scripts`;
- controllo che `.cmd` siano CRLF;
- `scripts/verify_offline.py` non è eseguibile senza modelli.

Un workflow minimo:

```yaml
name: lint
on: [push, pull_request]
jobs:
  compile:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m compileall app scripts
```
