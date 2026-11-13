@echo off
rem ===========================================================================
rem  SubScrivo - launcher senza finestra console
rem  Funziona da qualsiasi percorso, senza privilegi di amministratore.
rem ===========================================================================
setlocal EnableExtensions

rem Entra sempre nella cartella del launcher, anche se il doppio clic
rem viene fatto da un collegamento con "Esegui in" diverso.
cd /d "%~dp0"
if errorlevel 1 (
    echo ERRORE: impossibile aprire la cartella del programma:
    echo   %~dp0
    pause
    exit /b 1
)
set "ROOT=%CD%"

rem -----------------------------------------------------------------------
rem  Collegamento "Avvia SubScrivo.lnk": NON e' incluso nel pacchetto
rem  (contiene percorsi assoluti della macchina). Viene creato al primo avvio
rem  e riparato se il pacchetto e' stato spostato o copiato su un altro PC.
rem  Lo script non e' critico: se fallisce l'app parte lo stesso.
rem -----------------------------------------------------------------------
if exist "%ROOT%\scripts\make_shortcut.ps1" (
    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT%\scripts\make_shortcut.ps1" -Root "%ROOT%" >nul 2>&1
)

set "SUBSCRIVO_HOME=%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%ROOT%\app\main.py" (
    echo ERRORE: file dell'applicazione non trovati in:
    echo   %ROOT%\app
    echo.
    echo Il pacchetto sembra incompleto. Estrai di nuovo lo ZIP per intero,
    echo senza spostare singoli file fuori dalla cartella.
    pause
    exit /b 1
)

if exist "%ROOT%\python\pythonw.exe" (
    start "" "%ROOT%\python\pythonw.exe" -m app.main
    exit /b 0
)

if exist "%ROOT%\python\python.exe" (
    "%ROOT%\python\python.exe" -m app.main
    set "EXITCODE=%ERRORLEVEL%"
    if not "%EXITCODE%"=="0" (
        echo.
        echo Il programma e' terminato con codice %EXITCODE%.
        echo Controlla work\logs\subscrivo.log per i dettagli.
        pause
    )
    exit /b %EXITCODE%
)

echo ERRORE: interprete Python non trovato in:
echo   %ROOT%\python
echo.
echo Il pacchetto sembra incompleto. Estrai di nuovo lo ZIP per intero,
echo mantenendo la struttura delle cartelle.
pause
exit /b 1
