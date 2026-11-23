@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem SPDX-License-Identifier: GPL-3.0-or-later
rem No downloads, administrator privileges, or security setting changes.
set "APP_DIR=%~dp0"
set "ENGINE="
if defined CMYK_GIMP_ROOT call :try_root "%CMYK_GIMP_ROOT%"
if not defined ENGINE call :try_root "%APP_DIR%runtime"
if not defined ENGINE if exist "%APP_DIR%data\gimp-runtime\READY" call :try_root "%APP_DIR%data\gimp-runtime"
if not defined ENGINE call :try_root "%LOCALAPPDATA%\Programs\GIMP 3"
if not defined ENGINE call :try_root "%USERPROFILE%\AppData\Local\Programs\GIMP 3"
if not defined ENGINE call :try_root "%ProgramFiles%\GIMP 3"
if not defined ENGINE call :try_root "%ProgramFiles%\GIMP 3.2"
if not defined ENGINE call :try_root "%ProgramFiles%\GIMP 3.0"
if not defined ENGINE for /f "delims=" %%K in ('reg query "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages" 2^>nul ^| findstr /i /l /c:"GIMP."') do call :store_root "%%K"
if not defined ENGINE (
  echo GIMP 3 was not found. Install the official Windows version first:
  echo https://www.gimp.org/downloads/
  echo You can also set CMYK_GIMP_ROOT to the GIMP installation directory.
  pause
  exit /b 1
)
set "CMYK_GIMP_ROOT=%ENGINE%"
if /i "%~1"=="--check" (
  echo GIMP engine: %ENGINE%
  exit /b 0
)
if /i "%~1"=="--console" (
  "%ENGINE%\bin\python.exe" "%APP_DIR%app.py"
  exit /b
)
start "" "%ENGINE%\bin\pythonw.exe" "%APP_DIR%app.py"
exit /b 0

:try_root
if exist "%~1\bin\pythonw.exe" if exist "%~1\bin\gimp-console-3.exe" set "ENGINE=%~1"
exit /b

:store_root
if defined ENGINE exit /b
set "STORE_ROOT="
for /f "tokens=2,*" %%A in ('reg query "%~1" /v PackageRootFolder 2^>nul ^| findstr /i /l /c:"PackageRootFolder"') do set "STORE_ROOT=%%B\VFS\ProgramFilesX64\GIMP"
if not defined STORE_ROOT exit /b
if not exist "%STORE_ROOT%\bin\pythonw.exe" exit /b
echo Preparing the installed Microsoft Store GIMP for local use...
echo This one-time copy can require about 700 MB. No files are downloaded.
if not exist "%APP_DIR%data" mkdir "%APP_DIR%data"
robocopy "%STORE_ROOT%" "%APP_DIR%data\gimp-runtime" /E /XJ /R:1 /W:1 /NP /NFL /NDL /NJH /NJS > "%APP_DIR%data\runtime-setup.log" 2>&1
if errorlevel 8 (
  echo GIMP preparation failed. See data\runtime-setup.log.
  exit /b
)
> "%APP_DIR%data\gimp-runtime\READY" echo Prepared from the user's installed Microsoft Store GIMP.
call :try_root "%APP_DIR%data\gimp-runtime"
exit /b
