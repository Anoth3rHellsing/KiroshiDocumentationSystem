@echo off
REM ======================================================================
REM Uninstall_Kiroshi_Minimal.bat
REM Elimina SOLO la carpeta de datos del programa:
REM C:\ProgramData\Kiroshi Documentation
REM No toca otras rutas ni el PATH del sistema.
REM ======================================================================


:: Requiere privilegios de administrador para borrar en C:\ProgramData
net session >nul 2>&1
if %errorlevel% neq 0 (
echo Solicitando privilegios de administrador...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b
)


setlocal EnableExtensions
set "TARGET=C:\ProgramData\Kiroshi Documentation"


if not exist "%TARGET%" (
echo No existe: "%TARGET%". Nada que desinstalar.
exit /b 0
)


echo Esto BORRARA permanentemente la carpeta:
echo "%TARGET%"
choice /M "Continuar?" >nul
if errorlevel 2 (
echo Cancelado por el usuario.
exit /b 0
)


:: Intento best-effort de cerrar Streamlit si mantiene archivos bloqueados
echo Intentando cerrar Streamlit si esta en ejecucion...
taskkill /IM streamlit.exe /F >nul 2>&1


:: Borrado
echo Eliminando archivos...
rmdir /S /Q "%TARGET%"


if exist "%TARGET%" (
echo No se pudo borrar completamente. Asegurate de cerrar Kiroshi y vuelve a intentar.
exit /b 1
) else (
echo Listo. "%TARGET%" ha sido eliminado.
)


exit /b 0