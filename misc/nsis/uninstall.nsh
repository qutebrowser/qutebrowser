# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# NSIS uninstaller header. Uses NsisMultiUser plugin and contains portions of
# its demo code, copyright 2017 Richard Drizin, Alex Mitev.


; Variables
Var SemiSilentMode ; installer started uninstaller in semi-silent mode using /SS parameter
Var RunningFromInstaller ; installer started uninstaller using /uninstall parameter
Var RunningAsUser ; uninstaller restarted itself using the user of the running shell
Var UserName

!insertmacro DeleteRetryAbortFunc "un."
!insertmacro CheckSingleInstanceFunc "un."

Function un.GetUserName
  System::Call "advapi32::GetUserName(t .r0, *i ${NSIS_MAX_STRLEN} r1) i.r2"
FunctionEnd

Function un.GetConfigDir
  SetShellVarContext current
  StrCpy $0 ${CONFIG_DIR}
  SetShellVarContext all
FunctionEnd

Function un.GetCacheDir
  SetShellVarContext current
  StrCpy $0 ${CACHE_DIR}
  SetShellVarContext all
FunctionEnd

Section "un.Program Files" SectionUninstallProgram
  SectionIn RO

  ; Call shell script to generate an uninstall-list nsh file
  !tempfile UNLIST
  !ifdef NSIS_WIN32_MAKENSIS
    !execute 'cmd.exe /c .\mkunlist.cmd "${DIST_DIR}" "${UNLIST}"'
  !else
    !error "POSIX script for uninstall list generation is not yet available."
  !endif

  ; Try to delete the EXE as the first step - if it's in use, don't remove anything else
  !insertmacro DeleteRetryAbort "$INSTDIR\${PROGEXE}"

  ; Clean up "Desktop Icon"
  !insertmacro MULTIUSER_GetCurrentUserString $0
  !insertmacro DeleteRetryAbort "$DESKTOP\${PRODUCT_NAME}$0.lnk"

  ; Clean up "Start Menu Icon"
  !insertmacro MULTIUSER_GetCurrentUserString $0
  !insertmacro DeleteRetryAbort "$STARTMENU\${PRODUCT_NAME}$0.lnk"

  ; Clean up Windows Registry
  ${if} $KeepReg = 0
    ${if} $MultiUser.InstallMode == "AllUsers"
    ${orif} ${AtLeastWin8}
      DeleteRegValue SHCTX "SOFTWARE\RegisteredApplications" "${PRODUCT_NAME}"
      DeleteRegKey SHCTX "SOFTWARE\Clients\StartMenuInternet\${PRODUCT_NAME}"
      DeleteRegKey SHCTX "SOFTWARE\Classes\${PRODUCT_NAME}HTML"
      DeleteRegKey SHCTX "SOFTWARE\Classes\${PRODUCT_NAME}URL"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.htm\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.html\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.pdf\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.shtml\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.svg\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.xht\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.xhtml\OpenWithProgids" "${PRODUCT_NAME}HTML"
      DeleteRegValue SHCTX "SOFTWARE\Classes\.webp\OpenWithProgids" "${PRODUCT_NAME}HTML"
    ${endif}
  ${endif}

  ; Include and then delete the uninstall nsh file
  !include "${UNLIST}"
  !delfile "${UNLIST}"
SectionEnd

SectionGroup /e "un.$UserName's Files" SectionGroupRemoveUserFiles

Section /o "!un.Program Settings" SectionRemoveSettings
  ; this section is executed only explicitly and shouldn't be placed in SectionUninstallProgram
  ${if} $MultiUser.InstallMode == "CurrentUser"
    !insertmacro UAC_AsUser_GetGlobal $0 ${CONFIG_DIR}
  ${else}
    !insertmacro UAC_AsUser_Call Function un.GetConfigDir ${UAC_SYNCREGISTERS}
  ${endif}
  RMDIR /r "$0\data"
  RMDIR /r "$0\config"
  RMDIR "$0"
SectionEnd

Section /o "un.Program Cache" SectionRemoveCache
  ; this section is executed only explicitly and shouldn't be placed in SectionUninstallProgram
  ${if} $MultiUser.InstallMode == "CurrentUser"
    !insertmacro UAC_AsUser_GetGlobal $0 ${CACHE_DIR}
  ${else}
    !insertmacro UAC_AsUser_Call Function un.GetCacheDir ${UAC_SYNCREGISTERS}
  ${endif}
  RMDIR /r "$0\cache"
  RMDIR "$0"
SectionEnd

SectionGroupEnd

Section "-Uninstall" ; hidden section, must always be the last one!
  ; we cannot use DeleteRetryAbort here - when using the _? parameter the
  ; uninstaller cannot delete itself and Delete fails, which is OK
  Delete "$INSTDIR\${UNINSTALL_FILENAME}"
  ; remove the directory only if it is empty - the user might have saved some files in it
  RMDir "$INSTDIR"

  ; Remove the uninstaller from registry as the very last step
  ; if something goes wrong, let the user run it again
  !insertmacro MULTIUSER_RegistryRemoveInstallInfo ; Remove registry keys

  ${RefreshShellIcons}

  ; If the uninstaller still exists, use cmd.exe on exit to remove it (along with $INSTDIR if it's empty)
  ${if} ${FileExists} "$INSTDIR\${UNINSTALL_FILENAME}"
    Exec '"$SYSDIR\cmd.exe" /c (del /f /q "$INSTDIR\${UNINSTALL_FILENAME}") & (rmdir "$INSTDIR")'
  ${endif}
SectionEnd

; Modern install component descriptions
!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionGroupRemoveUserFiles} \
    "Remove quterbowser files of user $UserName."
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionUninstallProgram} \
    "Remove ${PRODUCT_NAME} application files."
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionRemoveSettings} \
    "Remove ${PRODUCT_NAME} user files \
    (configuration, bookmarks, history, sessions, scripts, cookies, etc.)."
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionRemoveCache} \
    "Remove ${PRODUCT_NAME} cache files."
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END

; Callbacks
Function un.onInit
  !insertmacro UAC_AsUser_Call Function un.GetUserName ${UAC_SYNCREGISTERS}
  StrCpy $UserName $0

  ${GetParameters} $R0

  ${GetOptions} $R0 "/user" $R1
  ${ifnot} ${errors}
    StrCpy $RunningAsUser 1
  ${else}
    StrCpy $RunningAsUser 0
  ${endif}

  ${GetOptions} $R0 "/uninstall" $R1
  ${ifnot} ${errors}
    StrCpy $RunningFromInstaller 1
  ${else}
    StrCpy $RunningFromInstaller 0
  ${endif}

  ${GetOptions} $R0 "/upgrade" $R1
  ${ifnot} ${errors}
    StrCpy $KeepReg 1
  ${else}
    StrCpy $KeepReg 0
  ${endif}

  ${GetOptions} $R0 "/SS" $R1
  ${ifnot} ${errors}
    StrCpy $SemiSilentMode 1
    StrCpy $RunningFromInstaller 1
    ; auto close (if no errors) if we are called from the installer
    ; if there are errors, will be automatically set to false
    SetAutoClose true
  ${else}
    StrCpy $SemiSilentMode 0
  ${endif}

  ; Windows stars the uninstallers elevated when called from 'Cotrol Panel' or
  ; from 'Apps & features' (where it elevates even for per user installations).
  ; This causes the uninstaller to run for the account used for elevation, which
  ; may be different than the user doing the uninstall. As a workaround, the
  ; uninstaller is restarted using the non-elevated user.
  ${ifnot} ${UAC_IsInnerInstance}
  ${andif} $RunningFromInstaller = 0
    ${if} ${UAC_IsAdmin}
    ${andif} $RunningAsUser = 0
      ${StdUtils.ExecShellAsUser} $0 "$INSTDIR\${UNINSTALL_FILENAME}" "open" "/user $R0"
      Quit
    ${endif}
    !insertmacro CheckSingleInstance "Setup" "Global" "${SETUP_MUTEX}"
    !insertmacro CheckSingleInstance "Application" "Local" "${APP_MUTEX}"
  ${endif}

  !insertmacro MULTIUSER_UNINIT

  !insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Function un.PageInstallModeChangeMode
FunctionEnd

Function un.PageComponentsPre
  ${if} $SemiSilentMode = 1
    ; if user is installing, no use to remove program settings anyway
    ; (should be compatible with all versions)
    Abort
  ${endif}
FunctionEnd

Function un.PageComponentsShow
  ; Show/hide the Back button
  GetDlgItem $0 $HWNDPARENT 3
  ShowWindow $0 $UninstallShowBackButton
FunctionEnd

Function un.onUninstFailed
  ${if} $SemiSilentMode = 0
    MessageBox MB_ICONSTOP \
      "${PRODUCT_NAME} ${VERSION} could not be fully uninstalled.$\r$\n\
      Please restart Windows and run the uninstaller again." \
      /SD IDOK
  ${else}
    MessageBox MB_ICONSTOP \
      "${PRODUCT_NAME} could not be fully installed.$\r$\n\
      Please, restart Windows and run the setup program again." \
      /SD IDOK
  ${endif}
FunctionEnd
