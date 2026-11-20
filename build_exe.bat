@echo off
echo Building SilverSpoon executable...
echo This might take a minute or two.
echo.

pyinstaller --clean SilverSpoon.spec
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed with exit code %ERRORLEVEL%!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Build complete! You can find the executable in the 'dist' folder.
pause
