@echo off
title Drone Flight Simulator Builder

echo ==========================================
echo    DRONE FLIGHT TRAINING SIMULATOR
echo          Windows EXE Builder
echo ==========================================
echo.

echo Installing dependencies...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Cleaning previous build...

if exist "C:\drone_build" rmdir /s /q "C:\drone_build"
if exist "C:\drone_dist" rmdir /s /q "C:\drone_dist"
if exist "C:\drone_spec" rmdir /s /q "C:\drone_spec"

mkdir "C:\drone_build"
mkdir "C:\drone_dist"
mkdir "C:\drone_spec"

echo.
echo Building DroneFlightSimulator.exe...
echo.

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name DroneFlightSimulator ^
    --workpath "C:\drone_build" ^
    --distpath "C:\drone_dist" ^
    --specpath "C:\drone_spec" ^
    main.py

if errorlevel 1 (
    echo.
    echo ==========================================
    echo BUILD FAILED
    echo ==========================================
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD SUCCESSFUL!
echo ==========================================
echo.
echo Your EXE is:
echo C:\drone_dist\DroneFlightSimulator.exe
echo.

pause