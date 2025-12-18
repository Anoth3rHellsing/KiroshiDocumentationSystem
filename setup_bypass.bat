@echo off
echo [INFO] Configuring SSL Bypass...

REM NPM is handled by JavaSTools/.npmrc automatically.
echo [INFO] NPM SSL Bypass configured in JavaSTools/.npmrc

REM Configure Pip to use the local pip.ini
set PIP_CONFIG_FILE=%~dp0pip.ini
echo [INFO] PIP_CONFIG_FILE set to: %PIP_CONFIG_FILE%

echo [SUCCESS] SSL verification disabled for this session.
echo You can now run "pip install ..." or "npm install" without SSL errors.
