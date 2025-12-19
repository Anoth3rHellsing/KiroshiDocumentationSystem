@echo off
echo ========================================================
echo Kiroshi Dependency Installer (SSL Bypass Mode)
echo ========================================================
echo.
echo This script sets aggressive SSL bypass variables to handle
echo corporate proxies and firewall inspection.
echo.

set NODE_TLS_REJECT_UNAUTHORIZED=0
set npm_config_strict_ssl=false

echo Environment variables set:
echo NODE_TLS_REJECT_UNAUTHORIZED=%NODE_TLS_REJECT_UNAUTHORIZED%
echo npm_config_strict_ssl=%npm_config_strict_ssl%
echo.

echo Running npm install...
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] npm install failed. Please check the logs above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] Dependencies installed successfully.
echo.
echo You can now run the application using:
echo   npm start
echo.
echo Or build the installer using:
echo   npm run build
echo.
pause
