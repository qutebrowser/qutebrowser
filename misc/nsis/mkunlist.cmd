@echo off

rem This is called from qutebrowser NSIS script at compile time.
rem It enumerates the files of the release and generates a nsh file with the
rem commands to remove them.

setlocal EnableDelayedExpansion

if [%2]==[] exit 1

set "DIST=%~f1"
set "ULIST=%2"
set "DLIST=%TEMP%\%~n2%RANDOM%.tmp"

if not exist "%DIST%" exit 2

if exist "%ULIST%" del "%ULIST%" || exit 3
if exist "%DLIST%" del "%DLIST%" || exit 3

for /r "%DIST%" %%i in (*) do call:AddToNSH "%%i" Delete "%ULIST%"

rem '*' doesn't catch hidden files and there are a couple files starting with
rem a '.', which will appear as hidden if mapped from a linux file system.
for /f "tokens=*" %%i in ('dir "%DIST%" /a:h-d /b /s') do call:AddToNSH "%%i" Delete "%ULIST%"

for /r "%DIST%" %%i in (.) do call:AddToNSH "%%i" RMDir "%DLIST%"

sort /r "%DLIST%" >> "%ULIST%"
del "%DLIST%"
goto:eof

:AddToNSH
set "FN=%~1"
set "FN=!FN:%DIST%=!"
set "FN=!FN:$=$$!"
(echo:%2 "$INSTDIR!FN!") >> %3
