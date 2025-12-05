@echo off
REM ======================================================================
REM  Update_Kiroshi_Minimal.bat
REM  Actualiza Kiroshi borrando la carpeta en ProgramData y copiando los
REM  archivos de la carpeta actual (donde está este .bat).
REM  No instala dependencias ni lanza la app. Es solo “borrar y reemplazar”.
REM ======================================================================

:: Requiere admin para tocar C:\ProgramData
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando privilegios de administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

setlocal EnableExtensions
set "SRC=%~dp0"
set "DEST=C:\ProgramData\Kiroshi Documentation"

:: Comprobacion rapida de que estamos en la carpeta correcta
if not exist "%SRC%case_documentation_app.py" (
    echo [AVISO] No encontre case_documentation_app.py en: "%SRC%"
    echo Asegurate de ejecutar este .bat en la carpeta raiz del ZIP nuevo.
)

echo.
echo Esto BORRARA y reemplazara:
echo   "%DEST%"
echo con los archivos desde:
echo   "%SRC%"
choice /M "Continuar?" >nul
if errorlevel 2 (
    echo Cancelado por el usuario.
    exit /b 0
)

:: Cerrar Streamlit si esta corriendo para liberar archivos
echo Cerrando Streamlit si esta en ejecucion...
taskkill /IM streamlit.exe /F >nul 2>&1

:: Borrar carpeta destino
if exist "%DEST%" (
    echo Eliminando "%DEST%" ...
    rmdir /S /Q "%DEST%"
)

:: Recrear destino
mkdir "%DEST%" || (echo [ERROR] No se pudo crear "%DEST%" & exit /b 1)

:: Copiar (simple y robusto con XCOPY)
echo Copiando archivos...
xcopy "%SRC%*" "%DEST%\" /E /I /Y >nul
if %errorlevel% GEQ 1 (
    echo [AVISO] XCOPY devolvio codigo %errorlevel%. Si hubo archivos en uso, reintenta.
)

echo.
echo Listo. Contenido actualizado en: "%DEST%"
echo Sugerencia: usa tu launcher minimal para abrir Kiroshi:
echo   Run_Kiroshi_Minimal.bat

echo.
exit /b 0
