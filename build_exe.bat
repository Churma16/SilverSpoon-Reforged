@echo off
echo Building SilverSpoon executable...
echo This might take a minute or two.
echo.

pyinstaller --clean SilverSpoon.spec

echo.
echo Build complete! You can find the executable in the 'dist' folder.
pause
