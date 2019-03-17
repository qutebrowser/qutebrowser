Name "qutebrowser"

Unicode true
RequestExecutionLevel admin
SetCompressor /solid lzma

!ifdef X64
  OutFile "..\dist\qutebrowser-${VERSION}-amd64.exe"
  InstallDir "$ProgramFiles64\qutebrowser"
!else
  OutFile "..\dist\qutebrowser-${VERSION}-win32.exe"
  InstallDir "$ProgramFiles\qutebrowser"
!endif

;Default installation folder
  
!include "MUI2.nsh"
;!include "MultiUser.nsh"

!define MUI_ABORTWARNING
;!define MULTIUSER_MUI
;!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MUI_ICON "../icons/qutebrowser.ico"
!define MUI_UNICON "../icons/qutebrowser.ico"

!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; depends on admin status
;SetShellVarContext current


Section "Install"

  ; Uninstall old versions
  ExecWait 'MsiExec.exe /quiet /qn /norestart /X{633F41F9-FE9B-42D1-9CC4-718CBD01EE11}'
  ExecWait 'MsiExec.exe /quiet /qn /norestart /X{9331D947-AC86-4542-A755-A833429C6E69}'
  IfFileExists "$INSTDIR\uninst.exe" 0 +2
  ExecWait "$INSTDIR\uninst.exe /S _?=$INSTDIR"
  CreateDirectory "$INSTDIR"

  SetOutPath "$INSTDIR"
  
  !ifdef X64
	file /r "..\dist\qutebrowser-${VERSION}-x64\*.*"
  !else
	file /r "..\dist\qutebrowser-${VERSION}-x86\*.*"
  !endif

  SetShellVarContext all
  CreateShortCut "$SMPROGRAMS\qutebrowser.lnk" "$INSTDIR\qutebrowser.exe"
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\uninst.exe"

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\qutebrowser" "DisplayName" "qutebrowser"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\qutebrowser" "UninstallString" '"$INSTDIR\uninst.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\qutebrowser" "QuietUninstallString" '"$INSTDIR\uninst.exe" /S'

SectionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  SetShellVarContext all
  Delete "$SMPROGRAMS\qutebrowser.lnk"

  RMDir /r "$INSTDIR\*.*"
  RMDir "$INSTDIR"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\qutebrowser"

SectionEnd
