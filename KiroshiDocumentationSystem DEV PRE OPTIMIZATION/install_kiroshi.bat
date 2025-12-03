@echo off
REM ---- Variables: Cambia los paths según tu entorno ----
set INSTALLDIR=C:\ProgramFiles\KiroshiDocumentation
set SRCDIR=%USERPROFILE%\kiroshi_nueva_version
set REQFILE=%SRCDIR%\requirements.txt

echo --------- Instalador Kiroshi (Windows .bat) ---------

REM Borra contenido previo (archivos y carpetas)
if exist "%INSTALLDIR%" (
    echo Borrando archivos previos en "%INSTALLDIR%"...
    del /Q "%INSTALLDIR%\*" 2>nul
    for /d %%i in ("%INSTALLDIR%\*") do rd /s /q "%%i"
) else (
    mkdir "%INSTALLDIR%"
)

REM Copia archivos y carpetas nuevos
echo Copiando archivos nuevos desde "%SRCDIR%"...
xcopy "%SRCDIR%\*" "%INSTALLDIR%\" /E /H /C /Y

REM Instala requisitos de Python
if exist "%REQFILE%" (
    echo Instalando dependencias desde requirements.txt...
    python -m pip install -r "%REQFILE%"
    echo Dependencias instaladas correctamente.
) else (
    echo No se encontró requirements.txt en "%SRCDIR%", saltando instalación de dependencias.
)

echo Instalación terminada. Kiroshi listo para usar.
pause

