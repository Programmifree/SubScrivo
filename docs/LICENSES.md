# Licenze di software e modelli

SubScrivo è rilasciato sotto licenza **GNU Affero General Public License v3 (AGPLv3)**.  
Il pacchetto include software e modelli di terze parti con licenze permissive
compatibili.

---

## 1. Componenti inclusi

| Componente | Ruolo | Licenza | Riferimento in `licenses/` |
|------------|-------|---------|----------------------------|
| **SubScrivo** | Codice applicativo e UI | **GNU AGPLv3** | [`LICENSE`](../LICENSE) |
| **Python** (python-build-standalone) | Interprete Python 3.11 embedded | PSF-2.0 | `01-Python-PSF.txt` |
| **FFmpeg** (build BtbN) | Estrazione e conversione audio | LGPL-3.0-or-later | `02-FFmpeg-LGPLv3.txt` |
| **transcribe.cpp** (runtime ggml) | Motore nativo di inferenza C++ | MIT | `16-transcribe.cpp-MIT.txt` |
| **ONNX Runtime** | Inferenza modelli ONNX (embedding e VAD) | MIT | `06-onnxruntime-MIT.txt` |
| **NumPy** | Calcolo numerico | BSD-3-Clause | `21-numpy-BSD-3-Clause.txt` |
| **soundfile** | Lettura/scrittura audio | BSD-3-Clause | `22-soundfile-BSD-3-Clause.txt` |
| **libsndfile** (incluso da soundfile) | Codec audio WAV/FLAC | LGPL-2.1 | `23-libsndfile-LGPL-2.1.txt` |
| **tkinterdnd2** (TkDND 2.10.3) | Supporto Drag & Drop per file | MIT | `20-tkinterdnd2-MIT.txt` |
| **Silero VAD** | Voice Activity Detection | MIT | `15-SileroVAD-MIT.txt` |
| **faster-whisper** (codice VAD adattato) | Origine del modulo `app/silero_vad.py` | MIT | `03-faster-whisper-MIT.txt` |

---

## 2. Modelli AI e attribuzioni

### Modello di trascrizione: Parakeet Ultra

* **Architettura e pesi originali**: NVIDIA Corporation (`nvidia/parakeet-tdt-0.6b-v3`)
* **Post-training e punteggiatura**: Moondream (`moondream/parakeet-ultra`)
* **Conversione GGUF**: handy-computer (`handy-computer/parakeet-ultra-gguf`)
* **Licenza**: **Creative Commons Attribution 4.0 International (CC-BY-4.0)**
* **Attribuzione obbligatoria**: l'uso e la ridistribuzione del modello
  riconoscono pieno credito a NVIDIA Corporation e Moondream. Testo della
  licenza in `licenses/18-Parakeet-CC-BY-4.0.txt`.

### Modello di diarizzazione: WeSpeaker

* **Modello**: `hbredin/wespeaker-voxceleb-resnet34-LM`
* **Autori**: WeSpeaker Project
* **Licenza**: **Apache 2.0** (`licenses/13-WeSpeaker-Apache-2.0.txt`)

---

## 3. Esclusione di responsabilità (disclaimer "AS IS")

Il software è fornito "COSÌ COM'È" (**AS IS**), senza alcuna garanzia esplicita
o implicita.  
Gli autori e Programmifree non si assumono alcuna responsabilità per danni
diretti, indiretti, accidentali, perdita di dati o qualsiasi altro problema
derivante dall'utilizzo o dal mancato funzionamento del software. L'uso è
interamente a carico dell'utente finale.
