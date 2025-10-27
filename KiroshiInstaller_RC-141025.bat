@echo off
REM ======================================================================
REM  Kiroshi Documentation System — Simple .BAT Installer & Launcher (v5)
REM  PLAN C: Creates plain .CMD launchers instead of .LNK shortcuts.
REM  - Copies to C:\ProgramData\Kiroshi Documentation
REM  - Creates venv, installs requirements (with pip SSL bypass)
REM  - Writes launcher CMD files to Desktop(s) and Start Menu folders
REM  - Launches with: streamlit-desktop-app run case_documentation_app.py
REM  NOTE: .CMD files don't support custom icons.
REM ======================================================================

:: ---------------------------- Elevate to Admin ----------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

setlocal EnableExtensions EnableDelayedExpansion

:: ------------------------------- Variables --------------------------------
set "SRC=%~dp0"
set "DEST=C:\ProgramData\Kiroshi Documentation"
set "VENV=%DEST%\.venv"
set "PYTHON_EXE=%VENV%\Scripts\python.exe"
set "STREAMLIT_EXE=%VENV%\Scripts\streamlit.exe"
set "STREAMLIT_DESKTOP_EXE=%VENV%\Scripts\streamlit-desktop-app.exe"
set "DESKTOP_USER=%USERPROFILE%\Desktop"
set "DESKTOP_PUBLIC=%Public%\Desktop"
set "START_MENU_USER=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "START_MENU_ALL=%ProgramData%\Microsoft\Windows\Start Menu\Programs"
set "LAUNCH_BASE=Kiroshi Documentation System"

for /f "tokens=2 delims==" %%A in ('wmic os get LocalDateTime /value ^| find "LocalDateTime"') do set LDT=%%A
set "LOG=%TEMP%\Kiroshi_Installer_!LDT:~0,8!.log"

echo SRC  = "%SRC%"
echo DEST = "%DEST%"

:: ----------------------- Ensure destination folder ------------------------
if not exist "%DEST%" (
    mkdir "%DEST%" || (echo Failed to create "%DEST%" & exit /b 1)
)

:: --------------------------- Copy project files ---------------------------
echo Copying files via PowerShell... (log: %LOG%)
set "PSCMD=$src=[IO.Path]::GetFullPath('%SRC%'); $dest='%DEST%'; if(-not (Test-Path $dest)){New-Item -ItemType Directory -Path $dest^|Out-Null}; Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force"

powershell -NoProfile -ExecutionPolicy Bypass -Command "%PSCMD%" 1>>"%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo PowerShell copy failed, falling back to XCOPY...>>"%LOG%"
    xcopy "%SRC%*" "%DEST%\" /E /I /Y >>"%LOG%" 2>&1
    if %errorlevel% GEQ 1 (
        echo Copy failed. See log: %LOG%
        exit /b 1
    )
)

:: -------------------------- Python launcher pick --------------------------
set "PY3=python"
where py >nul 2>&1 && set "PY3=py -3"

:: ------------------------------ Create venv -------------------------------
if not exist "%VENV%\Scripts\python.exe" (
    echo Creating virtual environment at "%VENV%" ...
    %PY3% -m venv "%VENV%" 2>>"%LOG%"
    if not exist "%VENV%\Scripts\python.exe" (
        echo Failed to create virtual environment. See log: %LOG%
        exit /b 1
    )
)

:: ------------------- Configure pip SSL bypass (risky) ---------------------
set "PIPDIR=%APPDATA%\pip"
if not exist "%PIPDIR%" mkdir "%PIPDIR%" >nul 2>&1
(
  echo [global]
  echo trusted-host = pypi.org
  echo 	files.pythonhosted.org
  echo 	pypi.python.org
  echo disable-pip-version-check = true
  echo timeout = 60
) > "%PIPDIR%\pip.ini"
set PIP_TRUSTED_HOST=pypi.org files.pythonhosted.org pypi.python.org

:: ----------------------- Pip upgrade & requirements -----------------------
"%PYTHON_EXE%" -m pip install --upgrade pip 1>>"%LOG%" 2>&1
if exist "%DEST%\requirements.txt" (
    echo Installing requirements.txt (this can take a few minutes)...
    "%PYTHON_EXE%" -m pip install ^
        --trusted-host pypi.org ^
        --trusted-host files.pythonhosted.org ^
        --trusted-host pypi.python.org ^
        -r "%DEST%\requirements.txt" 1>>"%LOG%" 2>&1
) else (
    echo requirements.txt not found, installing streamlit only...
)
"%PYTHON_EXE%" -m pip show streamlit >nul 2>&1 || (
    "%PYTHON_EXE%" -m pip install ^
        --trusted-host pypi.org ^
        --trusted-host files.pythonhosted.org ^
        --trusted-host pypi.python.org ^
        streamlit 1>>"%LOG%" 2>&1
)
REM Install desktop wrapper used for packaged Streamlit experience.
"%PYTHON_EXE%" -m pip install ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --trusted-host pypi.python.org ^
    streamlit-desktop-app 1>>"%LOG%" 2>&1

:: ------------------------- Create .CMD launchers --------------------------
for %%D in ("%DESKTOP_USER%","%DESKTOP_PUBLIC%","%START_MENU_USER%","%START_MENU_ALL%") do (
    if not exist "%%~D" mkdir "%%~D" >nul 2>&1
)

set "PS1_FILE=%TEMP%\mk_kiroshi_cmd_launchers.ps1"
>"%PS1_FILE%" echo param(^[string]$Dest,^ [string]$Venv,^ [string[]]$Paths^)
>>"%PS1_FILE%" echo $content = @"
>>"%PS1_FILE%" echo @echo off
>>"%PS1_FILE%" echo cd /d ""$Dest""
>>"%PS1_FILE%" echo if exist ".venv\Scripts\streamlit-desktop-app.exe" ^(
>>"%PS1_FILE%" echo ^  start "" ".venv\Scripts\streamlit-desktop-app.exe" run case_documentation_app.py
>>"%PS1_FILE%" echo ^) else ^(
>>"%PS1_FILE%" echo ^  start "" ".venv\Scripts\python.exe" -m streamlit_desktop_app run case_documentation_app.py
>>"%PS1_FILE%" echo ^  REM Legacy Streamlit CLI fallback retained for older installs.
>>"%PS1_FILE%" echo ^  if exist ".venv\Scripts\streamlit.exe" start "" ".venv\Scripts\streamlit.exe" run case_documentation_app.py
>>"%PS1_FILE%" echo ^)
>>"%PS1_FILE%" echo "@
>>"%PS1_FILE%" echo foreach($p in $Paths){
>>"%PS1_FILE%" echo ^  try{
>>"%PS1_FILE%" echo ^    New-Item -ItemType Directory -Path (Split-Path $p) -Force ^| Out-Null
>>"%PS1_FILE%" echo ^    Set-Content -Path $p -Value $content -Encoding ASCII
>>"%PS1_FILE%" echo ^    Write-Output "Created CMD: $p"
>>"%PS1_FILE%" echo ^  } catch {
>>"%PS1_FILE%" echo ^    Write-Output "Failed to create CMD: $p - $($_.Exception.Message)"
>>"%PS1_FILE%" echo ^  }
>>"%PS1_FILE%" echo }
>>"%PS1_FILE%" echo 
>>"%PS1_FILE%" echo # Also generate Kiroshi Chat launchers if kiroshi_chat.py exists
>>"%PS1_FILE%" echo if(Test-Path (Join-Path $Dest 'kiroshi_chat.py')){
>>"%PS1_FILE%" echo ^  $content2 = @"
>>"%PS1_FILE%" echo @echo off
>>"%PS1_FILE%" echo cd /d ""$Dest""
>>"%PS1_FILE%" echo if exist ".venv\Scripts\streamlit-desktop-app.exe" ^(
>>"%PS1_FILE%" echo ^  start "" ".venv\Scripts\streamlit-desktop-app.exe" run kiroshi_chat.py
>>"%PS1_FILE%" echo ^) else ^(
>>"%PS1_FILE%" echo ^  start "" ".venv\Scripts\python.exe" -m streamlit_desktop_app run kiroshi_chat.py
>>"%PS1_FILE%" echo ^  REM Legacy Streamlit CLI fallback retained for older installs.
>>"%PS1_FILE%" echo ^  if exist ".venv\Scripts\streamlit.exe" start "" ".venv\Scripts\streamlit.exe" run kiroshi_chat.py
>>"%PS1_FILE%" echo ^)
>>"%PS1_FILE%" echo "@
>>"%PS1_FILE%" echo ^  foreach($p in $Paths){
>>"%PS1_FILE%" echo ^    $p2 = [IO.Path]::Combine([IO.Path]::GetDirectoryName($p), 'Kiroshi Chat.cmd')
>>"%PS1_FILE%" echo ^    Set-Content -Path $p2 -Value $content2 -Encoding ASCII
>>"%PS1_FILE%" echo ^    Write-Output "Created CMD: $p2"
>>"%PS1_FILE%" echo ^  }
>>"%PS1_FILE%" echo }

set "P1=%DESKTOP_USER%\%LAUNCH_BASE%.cmd"
set "P2=%DESKTOP_PUBLIC%\%LAUNCH_BASE%.cmd"
set "P3=%START_MENU_USER%\%LAUNCH_BASE%.cmd"
set "P4=%START_MENU_ALL%\%LAUNCH_BASE%.cmd"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" ^
  -Dest "%DEST%" ^
  -Venv "%VENV%" ^
  -Paths "%P1%","%P2%","%P3%","%P4%"

if exist "%PS1_FILE%" del "%PS1_FILE%" >nul 2>&1

:: ------------------------------- Launch App -------------------------------
echo Launching Kiroshi with Streamlit Desktop runner...
if exist "%STREAMLIT_DESKTOP_EXE%" (
    start "" "%STREAMLIT_DESKTOP_EXE%" run case_documentation_app.py
) else (
    start "" "%PYTHON_EXE%" -m streamlit_desktop_app run case_documentation_app.py
    REM Legacy Streamlit CLI fallback retained for older installs lacking the desktop package.
    if exist "%STREAMLIT_EXE%" start "" "%STREAMLIT_EXE%" run case_documentation_app.py
)

echo.
echo CMD launchers created (check these paths):
echo   %DESKTOP_USER%\%LAUNCH_BASE%.cmd
echo   %DESKTOP_PUBLIC%\%LAUNCH_BASE%.cmd
echo   %START_MENU_USER%\%LAUNCH_BASE%.cmd
echo   %START_MENU_ALL%\%LAUNCH_BASE%.cmd

echo Log: %LOG%
echo Done.
exit /b 0
