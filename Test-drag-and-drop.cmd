@echo off
rem  Test isolato drag-and-drop: apre una finestra minimale e stampa
rem  a console ogni drop ricevuto. Chiudi la finestra per terminare.
rem  Funziona sia dalla cartella launcher\ sia dalla root del pacchetto.
setlocal EnableExtensions
if exist "%~dp0python\python.exe" (
    set "BASE=%~dp0"
) else (
    set "BASE=%~dp0..\"
)
pushd "%BASE%"
set "SUBSCRIVO_HOME=%CD%"
set "PYTHONUTF8=1"
if not exist "scripts\test_dnd.py" (
    echo ERRORE: scripts\test_dnd.py non trovato in %CD%
    pause
    popd
    endlocal
    exit /b 1
)
"python\python.exe" scripts\test_dnd.py
pause
popd
endlocal
