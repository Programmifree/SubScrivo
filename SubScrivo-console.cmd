@echo off
rem ===========================================================================
rem  SubScrivo - launcher diagnostico (con console)
rem  Mostra eventuali errori a video. Utile se la finestra non si apre.
rem ===========================================================================
setlocal EnableExtensions

cd /d "%~dp0"
if errorlevel 1 (
    echo ERRORE: impossibile aprire la cartella del programma:
    echo   %~dp0
    pause
    exit /b 1
)
set "ROOT=%CD%"
set "SUBSCRIVO_HOME=%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%ROOT%\app\main.py" (
    echo ERRORE: file dell'applicazione non trovati in:
    echo   %ROOT%\app
    echo.
    echo Il pacchetto sembra incompleto. Estrai di nuovo lo ZIP per intero.
    pause
    exit /b 1
)

if not exist "%ROOT%\python\python.exe" (
    echo ERRORE: interprete Python non trovato in:
    echo   %ROOT%\python
    echo.
    echo Il pacchetto sembra incompleto. Estrai di nuovo lo ZIP per intero.
    pause
    exit /b 1
)

"%ROOT%\python\python.exe" -m app.main
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo Il programma e' terminato con codice %EXITCODE%.
    echo Controlla work\logs\subscrivo.log per i dettagli.
    pause
)
exit /b %EXITCODE%
