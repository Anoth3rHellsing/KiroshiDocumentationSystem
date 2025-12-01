@echo off
cd /d "C:\ProgramData\Kiroshi Documentation"
echo ------------------------------------------
echo     Lanzador Kiroshi Cloud Console
echo ------------------------------------------
echo.
echo ¿Cómo quieres ejecutar Kiroshi?
echo 1. Browser (navegador)
echo 2. Desktop App (ventana propia)
echo.
set /p opcion="Elige una opción (1 o 2): "

if "%opcion%"=="1" (
    streamlit run kiroshi_cloud_client.py
    goto :eof
)
if "%opcion%"=="2" (
    streamlit-desktop-app run kiroshi_cloud_client.py
    goto :eof
)

echo Opción no válida. Por favor, ejecuta de nuevo el lanzador.
pause
