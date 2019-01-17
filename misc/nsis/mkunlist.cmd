@echo off

rem This is called from qutebrowser NSIS script at compile time.
rem It enumerates the files/directories of the release and generates an nsh
rem file with the commands to remove them.

rem Usage: mkunlist <release_dir> <nsh_file>

setlocal EnableDelayedExpansion

if [%2]==[] exit 1

rem The full path of the release
set "DIST=%~f1"
rem The generated nsh file
set "ULIST=%~2"
rem Temporary file to keep the directories list
set "DLIST=%TEMP%\%~n2%RANDOM%.tmp"

if not exist "%DIST%" exit 2

if exist "%ULIST%" del "%ULIST%" || exit 3
if exist "%DLIST%" del "%DLIST%" || exit 3

rem Add release files deletion commands
for /r "%DIST%" %%i in (*) do call:AddToNSH f "%%i" "%ULIST%"

rem '*' doesn't catch hidden files and there are a couple of files starting with
rem a '.', which will appear as hidden if mapped from a linux file system.
for /f "tokens=*" %%i in ('dir "%DIST%" /a:h-d /b /s') do call:AddToNSH f "%%i" "%ULIST%"

rem Add to the temporary file the directories removal commands
for /r "%DIST%" %%i in (.) do call:AddToNSH d "%%i" "%DLIST%"

rem Reverse dir-list items (so each child will get deleted first)
rem and append them to the nsh.
sort /r "%DLIST%" >> "%ULIST%"
del "%DLIST%"
goto:eof

rem AddToNSH <f|d> <name> <out_file>
:AddToNSH
rem Strip quotes from file/dir name
set "FN=%~2"
rem Strip leading path
set "FN=!FN:%DIST%=!"
rem If the name contains a '$', escape it by adding another '$'
set "FN=!FN:$=$$!"
rem Writing to out_file. EnableDelayedExpansion is weird with '!'
if %1==f (
  (echo:^^!insertmacro DeleteRetryAbort "$INSTDIR!FN!") >> %3
) else (
  (echo:RMDir "$INSTDIR!FN!") >> %3
)
