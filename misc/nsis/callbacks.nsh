# Copyright 2014-2022 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.


### Callback Functions

; The function prefix. First is defined with an empty value to import the
; installer functions. At the end is set with the uninstaller prefix and the
; file includes itself to import the uninstaller functions.
!define /ifndef F

### Functions for both Installer and Uninstaler

; Init: single instance, command line options, plugins
Function ${F}.onInit
    ${Reserve} $R0 Parameters ''
    ${Reserve} $R1 Option ''
    ${Reserve} $R2 Handle ''
    ${Reserve} $R3 SetupCaption ''
    ${Reserve} $R4 WindowCaption ''
    ${Reserve} $R5 MsiGuid ''
    ${Reserve} $R6 MsiPathKey ''
    ${Reserve} $R7 MsiPathStr ''
    ${Reserve} $R8 Value ''
    ${Reserve} $R9 Result ''
    Goto _start

    get_user_name:
    System::Call 'advapi32::GetUserNameW(w.${r.Value}, *i${NSIS_MAX_STRLEN}) i.${r.Result}'
    ${If} ${Result} = 0
        ${Quit} ERROR_BAD_USERNAME $(MB_GETUSERNAME_FAIL)
    ${EndIf}
    ${Return}
    !macro GET_USER_NAME USER_NAME
        ${Call} :get_user_name
        ${Set} ${USER_NAME} ${Value}
    !macroend
    !define GetUserName '!insertmacro GET_USER_NAME'

    get_option_state:
    ClearErrors
    ${GetOptions} ${Parameters} ${Option} ${Result}
    ${If} ${Errors}
        ${Set} Result -1
    ${Else}
        ${If} ${Result} == ''
        ${OrIf} ${Result} == '=on'
            ${Set} Result 1
        ${ElseIf} ${Result} == '=off'
            ${Set} Result 0
        ${Else}
            ${Quit} MULTIUSER_ERROR_INVALID_PARAMETERS $(MULTIUSER_INVALID_PARAMS)
        ${EndIf}
    ${EndIf}
    ${Return}
    !macro GET_OPTION_STATE OPTION_NAME OPTION_VAR
        ${Set} Option '/${OPTION_NAME}'
        ${Call} :get_option_state
        !if '${OPTION_VAR}' S!= ''
            ${Set} ${OPTION_VAR} ${Result}
        !endif
    !macroend
    !define GetOptionState '!insertmacro GET_OPTION_STATE'

    set_log_file:
    ClearErrors
    ${GetOptions} ${Parameters} '/Log=' $LogFile
    ${If} ${Errors}
        ${GetOptions} ${Parameters} '/Log' $LogFile
    ${EndIf}
    ${IfNot} ${Errors}
        ${If} $LogFile == ''
            !if '${F}' == ''
                ${StdUtils.NormalizePath} $LogFile '$EXEDIR\${DEFAULT_LOG_FILENAME}'
            !else
                ${StdUtils.NormalizePath} $LogFile '$INSTDIR\${DEFAULT_LOG_FILENAME}'
            !endif
        ${Else}
            ${StdUtils.NormalizePath} $LogFile $LogFile
            ${If} ${FileExists} "$LogFile\*"
                ${Set} $LogFile "$LogFile\${DEFAULT_LOG_FILENAME}"
            ${EndIf}
        ${EndIf}
        ${WriteDebug} $LogFile
    ${EndIf}
    ${Return}

    set_single_instance:
    !macro CREATE_MUTEX IN_MUTEX_NAME OUT_LAST_ERROR
        System::Call 'kernel32::CreateMutexW(n, i1, w"${IN_MUTEX_NAME}") p.${r.Handle} ?e'
        Pop ${OUT_LAST_ERROR}
        ${WriteDebug} OUT_LAST_ERROR
    !macroend
    ${If} ${Silent}
        !insertmacro CREATE_MUTEX "${SILENT_SETUP_GUID}" ${Result}
        ${If} ${Result} = ${ERROR_ALREADY_EXISTS}
            ${Quit} ERROR_SINGLE_INSTANCE_APP ''
        ${EndIf}
    ${Else}
        System::Call 'kernel32::OpenMutexW(i${SYNCHRONIZE}, i0, w"${SILENT_SETUP_GUID}") p.${r.Handle}'
        ${If} ${Handle} <> 0
            System::Call 'kernel32::CloseHandle(p${r.Handle})'
            MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION $(MB_ACTIVE_SILENT) /SD IDCANCEL IDRETRY set_single_instance
            ${Quit} ERROR_SINGLE_INSTANCE_APP ''
        ${EndIf}
    ${EndIf}
    !insertmacro CREATE_MUTEX "${SETUP_GUID}" ${Result}
    ${If} ${Result} = ${ERROR_ALREADY_EXISTS}
        ${Set} SetupCaption $(^SetupCaption)
        ${Set} Handle 0
        Sleep 500
        ClearErrors
        ${Call} :set_foreground_window
        ${If} ${Errors}
            ${Set} SetupCaption $(^UninstallCaption)
            ${Set} Handle 0
            ${Call} :set_foreground_window
            ${If} ${Errors}
                ${Quit} ERROR_INSTALL_ALREADY_RUNNING $(MB_ACTIVE_NO_WINDOW)
            ${EndIf}
        ${EndIf}
        ${Quit} ERROR_SINGLE_INSTANCE_APP ''
    ${EndIf}
    ${Return}
    set_foreground_window:
    FindWindow ${Handle} '#32770' '' '' ${Handle}
    ${If} ${Handle} <> 0
        StrLen ${Value} ${SetupCaption}
        IntOp ${Value} ${Value} + 1 ; include null character
        System::Call 'user32::GetWindowTextW(p${r.Handle}, w.${r.WindowCaption}, i${r.Value}) i.${r.Result}'
        ${If} ${Result} > 0
            StrCmpS ${WindowCaption} ${SetupCaption} 0 set_foreground_window
            SendMessage ${Handle} ${WM_SYSCOMMAND} ${SC_RESTORE} 0 /TIMEOUT=2000 ; restore if minimized
            System::Call 'user32::SetForegroundWindow(p${r.Handle}) i.${r.Result}'
            ${If} ${Result} = 0
                MessageBox MB_OK|MB_ICONSTOP $(MB_ACTIVE_SETUP)
                ${Quit} ERROR_SINGLE_INSTANCE_APP ''
            ${EndIf}
        ${EndIf}
    ${Else}
        ${Error} ERROR_NOT_FOUND
    ${EndIf}
    ${Return}
    !macroundef CREATE_MUTEX

    restart_as_user:
    !if '${F}' == ''
        ${StdUtils.ExecShellAsUser} ${Result} '$EXEPATH' 'open' '/NCRC /${SETUP_GUID} ${Parameters}'
    !else
        ${StdUtils.ExecShellAsUser} ${Result} '$INSTDIR\${UNINSTALL_FILENAME}' 'open' '/NCRC /${SETUP_GUID} ${Parameters}'
    !endif
    ${WriteDebug} Result
    ${If} ${Result} != 'ok'
        ${Quit} ERROR_GEN_FAILURE $(MB_RESTART_FAILED)
    ${EndIf}
    !if '${F}' == ''
        ${Do}
            Sleep 2000
            System::Call 'kernel32::OpenMutexW(i${SYNCHRONIZE}, i0, w"${SETUP_GUID}") p.${r.Handle}'
            ${WriteDebug} Handle
            ${If} ${Handle} <> 0
                System::Call 'kernel32::CloseHandle(p${r.Handle})'
            ${EndIf}
        ${LoopUntil} ${Handle} = 0
    !endif
    ${Quit} ERROR_SUCCESS ''

    !if '${F}' == ''
        check_win_ver:
        GetWinVer ${Result} Major
        IntCmpU ${Result} 10 0 _unsupported_os _os_ok
        ${If} ${IsNativeAMD64}
            GetWinVer ${Result} Build
            IntCmpU ${Result} 19044 _os_ok 0 _os_ok
        ${EndIf}
        _unsupported_os:
        ${Quit} ERROR_INSTALL_PLATFORM_UNSUPPORTED $(MB_UNSUPPORTED_OS)
        _os_ok:
        ${Return}

        detect_nsis_v2:
        !macro DETECT_NSIS_V2 HKEY CONTEXT MODE
            ${If} $HasPer${CONTEXT}Installation = 0
                ReadRegStr ${Value} ${HKEY} '${REG_UNINSTALL}\${PRODUCT_NAME}' 'InstallLocation'
                ${If} ${Value} S!= ''
                    ${Set} $Per${CONTEXT}InstallationFolder ${Value}
                    ${Set} $Per${CONTEXT}UninstallString '"${Value}\uninstall.exe" /${MODE} /SS _?=${Value}'
                    ${If} ${Silent}
                        ${Set} $Per${CONTEXT}UninstallString '$Per${CONTEXT}UninstallString /S _?=${Value}'
                    ${Else}
                        ${Set} $Per${CONTEXT}UninstallString '$Per${CONTEXT}UninstallString _?=${Value}'
                    ${EndIf}
                    ${Set} $HasPer${CONTEXT}Installation 1
                    ${If} $MultiUser.InstallMode == '${MODE}'
                        ${Set} $HasCurrentModeInstallation 1
                    ${EndIf}
                    ClearErrors
                    ReadRegStr ${Value} ${HKEY} '${REG_UNINSTALL}\${PRODUCT_NAME}' 'DisplayVersion'
                    ${IfNot} ${Errors}
                        ${Set} $Per${CONTEXT}InstallationVersion ${Value}
                    ${EndIf}
                ${EndIf}
            ${EndIf}
        !macroend
        !insertmacro DETECT_NSIS_V2 'HKLM' 'Machine' 'AllUsers'
        !insertmacro DETECT_NSIS_V2 'HKCU' 'User' 'CurrentUser'
        !macroundef DETECT_NSIS_V2
        ${Return}

        detect_nsis_v1:
        SetRegView 32
        ReadRegStr $PerMachineUninstallString HKLM '${REG_UNINSTALL}\${PRODUCT_NAME}' 'UninstallString'
        SetRegView 64
        StrCmpS $PerMachineUninstallString '' _detect_nsis_v1_end
        System::Call 'shlwapi::PathUnquoteSpacesW(w$PerMachineUninstallString ${r.Result})'
        ${StdUtils.GetParentPath} $PerMachineInstallationFolder ${Result}
        ${Set} $PerMachineUninstallString '$PerMachineUninstallString /S _?=$PerMachineInstallationFolder'
        ${Set} $HasPerMachineInstallation 1
        ${If} $MultiUser.InstallMode == 'AllUsers'
            ${Set} $HasCurrentModeInstallation 1
        ${EndIf}
        IfFileExists '$PerMachineInstallationFolder\git-commit-id' 0 _file_not_found
        ClearErrors
        FileOpen ${Handle} '$PerMachineInstallationFolder\git-commit-id' r
        IfErrors _file_open_error
        FileSeek ${Handle} -26 END
        IfErrors _file_seek_error
        FileRead ${Handle} ${Result} 10
        IfErrors _file_read_error
        FileClose ${Handle}
        ${WriteDebug} Result
        !macro GET_VERSION VER
            ${If} ${Result} S== '${GIT_DATE_${VER}}'
                ${Set} $PerMachineInstallationVersion '${GIT_VER_${VER}}'
                Goto _detect_nsis_v1_end
            ${EndIf}
        !macroend
        !insertmacro GET_VERSION 163
        !insertmacro GET_VERSION 162
        !insertmacro GET_VERSION 161
        !insertmacro GET_VERSION 160
        !insertmacro GET_VERSION 152
        !insertmacro GET_VERSION 151
        !insertmacro GET_VERSION 150
        !insertmacro GET_VERSION 142
        !insertmacro GET_VERSION 141
        !insertmacro GET_VERSION 140
        !insertmacro GET_VERSION 133
        !insertmacro GET_VERSION 132
        !insertmacro GET_VERSION 131
        !insertmacro GET_VERSION 130
        !insertmacro GET_VERSION 121
        !insertmacro GET_VERSION 120
        !insertmacro GET_VERSION 112
        !insertmacro GET_VERSION 111
        !insertmacro GET_VERSION 110
        !insertmacro GET_VERSION 104
        !insertmacro GET_VERSION 103
        !insertmacro GET_VERSION 102
        !insertmacro GET_VERSION 101
        !insertmacro GET_VERSION 100
        !insertmacro GET_VERSION 0111
        !insertmacro GET_VERSION 0110
        !macroundef GET_VERSION
        Goto _detect_nsis_v1_end
        _file_not_found:
        ${Error} ERROR_FILE_NOT_FOUND
        Goto _detect_nsis_v1_end
        _file_open_error:
        ${Error} ERROR_ACCESS_DENIED
        Goto _detect_nsis_v1_end
        _file_seek_error:
        FileClose ${Handle}
        ${Error} ERROR_SEEK
        Goto _detect_nsis_v1_end
        _file_read_error:
        FileClose ${Handle}
        ${Error} ERROR_READ_FAULT
        _detect_nsis_v1_end:
        ${Return}

        detect_msi:
        !macro CHECK_MSI BITS VER
            ${Set} MsiGuid '{${MSI${BITS}_${VER}_GUID}}'
            ${Set} MsiPathKey '${MSI${BITS}_${VER}_PATH_KEY}'
            ${Set} MsiPathStr '${MSI${BITS}_${VER}_PATH_STR}'
            ${Call} :check_msi_ver
            StrCmpS $HasPerMachineInstallation 1 _detect_msi_end
        !macroend
        !macro CHECK_MSI_ARCH BITS
            !insertmacro CHECK_MSI ${BITS} 101
            !insertmacro CHECK_MSI ${BITS} 100
            !insertmacro CHECK_MSI ${BITS} 091
            !insertmacro CHECK_MSI ${BITS} 090
            !insertmacro CHECK_MSI ${BITS} 084
            !insertmacro CHECK_MSI ${BITS} 082
            !insertmacro CHECK_MSI ${BITS} 081
            !insertmacro CHECK_MSI ${BITS} 080
            !insertmacro CHECK_MSI ${BITS} 070
            !insertmacro CHECK_MSI ${BITS} 062
            !insertmacro CHECK_MSI ${BITS} 061
            !insertmacro CHECK_MSI ${BITS} 060
            !insertmacro CHECK_MSI ${BITS} 051
            !insertmacro CHECK_MSI ${BITS} 050
            !insertmacro CHECK_MSI ${BITS} 041
            !insertmacro CHECK_MSI ${BITS} 040
            !insertmacro CHECK_MSI ${BITS} 030
            !insertmacro CHECK_MSI ${BITS} 021
            !insertmacro CHECK_MSI ${BITS} 020
            !insertmacro CHECK_MSI ${BITS} 014
            !insertmacro CHECK_MSI ${BITS} 013
            !insertmacro CHECK_MSI ${BITS} 012
            !insertmacro CHECK_MSI ${BITS} 011
            !insertmacro CHECK_MSI ${BITS} 010
        !macroend
        !insertmacro CHECK_MSI_ARCH 64
        SetRegView 32
        !insertmacro CHECK_MSI_ARCH 32
        !macroundef CHECK_MSI_ARCH
        !macroundef CHECK_MSI
        _detect_msi_end:
        SetRegView 64
        ${Return}
        check_msi_ver:
        ReadRegStr ${Value} HKLM '${REG_UNINSTALL}\${MsiGuid}' 'DisplayName'
        ${If} ${Value} == '${PRODUCT_NAME}'
            SetRegView 64
            ReadRegStr $PerMachineInstallationFolder HKLM '${REG_MSI_COMPONENTS}\${MsiPathKey}' '${MsiPathStr}'
            SetRegView lastused
            ${StdUtils.NormalizePath} $PerMachineInstallationFolder $PerMachineInstallationFolder
            ${WriteDebug} $PerMachineInstallationFolder
            ${If} $PerMachineInstallationFolder S!= ''
            ${AndIf} ${FileExists} '$PerMachineInstallationFolder\*'
                ${Set} $PerMachineUninstallString '"$SYSDIR\msiexec.exe" /x ${MsiGuid} /passive /norestart'
                ReadRegStr $PerMachineInstallationVersion HKLM '${REG_UNINSTALL}\${MsiGuid}' 'DisplayVersion'
                ${Set} $HasPerMachineInstallation 1
                ${If} $MultiUser.InstallMode == 'AllUsers'
                    ${Set} $HasCurrentModeInstallation 1
                ${EndIf}
            ${EndIf}
        ${EndIf}
        ${Return}
    !endif

    init_outer:
    ${Set} $SetupState 0
    !if '${F}' == ''
        ${Call} :check_win_ver
    !endif
    ; Internal switch: check if restarted by '/user',
    ; or the uninstaller is started from the installer
    ${GetOptionState} '${SETUP_GUID}' ''
    !if '${F}' != ''
        ${If} ${Result} = 0
            ${Set} $SetupState 1
            SetAutoClose true
        ${EndIf}
    !endif
    ; /User
    ${If} ${Result} = -1
        ${GetOptionState} 'User' ''
        ${If} ${Result} = 1
            ${Call} :restart_as_user
        ${EndIf}
    ${EndIf}
    ; User/Admin name
    ${GetUserName} $UserName
    ${If} ${UAC_IsAdmin}
        ${Set} $AdminName $UserName
    ${Else}
        ${Set} $AdminName ''
    ${EndIf}
    ; Config/Cache dirs
    SetShellVarContext current
    ${Set} $CacheDir '$LOCALAPPDATA\${PRODUCT_NAME}\cache'
    ${Set} $ConfigDir '$APPDATA\${PRODUCT_NAME}'
    ; Command line options
    ${GetOptionState} 'Help' ''
    ${If} ${Result} = -1
        ${GetOptionState} '?' ''
    ${EndIf}
    ${If} ${Result} = 1
        !ifdef __UNINSTALL__
            ${Quit} ERROR_SUCCESS $(MB_HELP_UNINSTALL)$(MB_HELP_EXIT_CODES)
        !else
            ${Quit} ERROR_SUCCESS $(MB_HELP_INSTALL)$(MB_HELP_EXIT_CODES)
        !endif
    ${EndIf}
    ${GetOptionState} 'ClearCache' $ClearCache
    ${GetOptionState} 'ClearConfig' $ClearConfig
    !if '${F}' == ''
        ${GetOptionState} 'RegisterBrowser' $RegisterBrowser
        ${GetOptionState} 'DesktopIcon' $DesktopIcon
        ${GetOptionState} 'StartMenuIcon' $StartMenuIcon
        ClearErrors
        ${GetOptions} ${Parameters} '/InstallDir=' ${Result}
        ${IfNot} ${Errors}
            ${StdUtils.NormalizePath} ${Result} ${Result}
            ${Set} $INSTDIR ${Result}
            ClearErrors
            ${CheckValidInstDir}
            ${If} ${Errors}
            ${AndIf} ${Silent}
                ${Quit} ERROR_BAD_PATHNAME ''
            ${EndIf}
        ${EndIf}
    !endif
    ${Call} :set_log_file
    ; Single instance
    !if '${F}' == ''
        ${GetOptionState} 'uninstall' ''
        ${If} ${Result} = -1
            ${Call} :set_single_instance
        ${EndIf}
    !else
        ${If} $SetupState = 0
            ${Call} :set_single_instance
        ${EndIf}
    !endif
    ; Init MultiUser
    ${Call} :init_multiuser
    ; MUI language selection
    !insertmacro MUI_LANGDLL_DISPLAY
    ${Return}

    init_inner:
    !macro SYNC IN_OUT_VAR
        !if '${F}' == ''
            !insertmacro UAC_AsUser_GetGlobalVar ${IN_OUT_VAR}
        !else
            !define start 'L${__LINE__}'
            !define sync_var 'L${__LINE__}'
            ${Reserve} $0 OutVar ''
            Goto _${start}

            ${sync_var}:
            StrCpy ${OutVar} ${IN_OUT_VAR}
            ${Return}

            _${start}:
            ${CallAsUser} :${sync_var}
            ${Release} OutVar ${IN_OUT_VAR}
            !undef start sync_var
        !endif
        ${WriteDebug} ${IN_OUT_VAR}
    !macroend
    ${GetUserName} $AdminName
    !insertmacro SYNC $UserName
    !insertmacro SYNC $LogFile
    !insertmacro SYNC $ClearCache
    !insertmacro SYNC $ClearConfig
    !insertmacro SYNC $CacheDir
    !insertmacro SYNC $ConfigDir
    !if '${F}' == ''
        !insertmacro SYNC $RegisterBrowser
        !insertmacro SYNC $DesktopIcon
        !insertmacro SYNC $StartMenuIcon
        !insertmacro SYNC $INSTDIR
    !endif
    !insertmacro SYNC $SetupState
    ${Call} :init_multiuser
    ${Return}

    init_multiuser:
    !if '${F}' == ''
        !insertmacro MULTIUSER_INIT
    !else
        !insertmacro MULTIUSER_UNINIT
    !endif
    ${WriteDebug} $MultiUser.Privileges ; Current user level: "Admin", "Power" (up to Windows XP), or else regular user.
    ${WriteDebug} $MultiUser.InstallMode ; Current Install Mode ("AllUsers" or "CurrentUser")
    ${WriteDebug} $IsAdmin ; 0 or 1, initialized via UserInfo::GetAccountType
    ${WriteDebug} $IsInnerInstance ; 0 or 1, initialized via UAC_IsInnerInstance
    ${WriteDebug} $HasPerMachineInstallation ; 0 or 1
    ${WriteDebug} $HasPerUserInstallation ; 0 or 1
    ${WriteDebug} $HasCurrentModeInstallation ; 0 or 1
    ${WriteDebug} $PerMachineInstallationVersion ; contains version number of empty string ""
    ${WriteDebug} $PerUserInstallationVersion ; contains version number of empty string ""
    ${WriteDebug} $PerMachineInstallationFolder
    ${WriteDebug} $PerUserInstallationFolder
    ${WriteDebug} $PerMachineUninstallString
    ${WriteDebug} $PerUserUninstallString
    ${WriteDebug} $PerMachineOptionAvailable ; 0 or 1: 0 means only per-user radio button is enabled on page, 1 means both; will be 0 only when MULTIUSER_INSTALLMODE_ALLOW_ELEVATION = 0 and user is not admin
    ${WriteDebug} $InstallShowPagesBeforeComponents ; 0 or 1, when 0, use it to hide all pages before Components inside the installer when running as inner instance
    ${WriteDebug} $CmdLineInstallMode ; contains command-line install mode set via /allusers and /currentusers parameters
    ${WriteDebug} $CmdLineDir ; contains command-line directory set via /D parameter

    ${If} $HasPerMachineInstallation = 1
        ${Set} $PerMachineUninstallString '"$PerMachineInstallationFolder\${UNINSTALL_FILENAME}" /${SETUP_GUID}=off /AllUsers'
        ${If} $LogFile != ''
            ${Set} $PerMachineUninstallString '$PerMachineUninstallString /Log="$LogFile"'
        ${EndIf}
        ${If} ${Silent}
            ${Set} $PerMachineUninstallString '$PerMachineUninstallString /S _?=$PerMachineInstallationFolder'
        ${Else}
            ${Set} $PerMachineUninstallString '$PerMachineUninstallString _?=$PerMachineInstallationFolder'
        ${EndIf}
    ${EndIf}
    ${If} $HasPerUserInstallation = 1
        ${Set} $PerUserUninstallString '"$PerUserInstallationFolder\${UNINSTALL_FILENAME}" /${SETUP_GUID}=off /CurrentUser'
        ${If} $LogFile != ''
            ${Set} $PerUserUninstallString '$PerUserUninstallString /Log="$LogFile"'
        ${EndIf}
        ${If} ${Silent}
            ${Set} $PerUserUninstallString '$PerUserUninstallString /S _?=$PerUserInstallationFolder'
        ${Else}
            ${Set} $PerUserUninstallString '$PerUserUninstallString _?=$PerUserInstallationFolder'
        ${EndIf}
    ${EndIf}

    !if '${F}' == ''
        ${If} $HasPerMachineInstallation = 0
        ${OrIf} $HasPerUserInstallation = 0
            ${Call} :detect_nsis_v2
        ${EndIf}
        ${If} $HasPerMachineInstallation = 0
            ${Call} :detect_nsis_v1
            ${If} $HasPerMachineInstallation = 0
                ${Call} :detect_msi
            ${EndIf}
        ${EndIf}
    !endif

    ${If} $HasPerMachineInstallation = 1
    ${AndIf} $PerMachineInstallationVersion S== ''
        ${Set} $PerMachineInstallationVersion '<UNKOWN>'
    ${EndIf}
    ${If} $HasPerUserInstallation = 1
    ${AndIf} $PerUserInstallationVersion S== ''
        ${Set} $PerUserInstallationVersion '<UNKOWN>'
    ${EndIf}

    ${Return}

    _start:
    StrCpy $CancelButtonText $(B_CANCEL)
    ${GetParameters} ${Parameters}

    ; /Silent
    ${GetOptionState} 'Silent' ''
    ${If} ${Result} = 1
        SetSilent silent
    ${EndIf}

    ${If} ${UAC_IsInnerInstance}
        !ifdef DEBUG
            !insertmacro SYNC $DebugLogFile
        !endif
        ${Call} :init_inner
    ${Else}
        !ifdef DEBUG
            ${If} $DebugLogFile == ''
                Sleep 1000
                ${StdUtils.Time} ${Result}
                !if '${F}' == ''
                    StrCpy $DebugLogFile '${DEBUG}\${INSTALLER_NAME}-installer-debug-${Result}.log'
                !else
                    StrCpy $DebugLogFile '${DEBUG}\${INSTALLER_NAME}-uninstaller-debug-${Result}.log'
                !endif
                ${WriteDebug} $CMDLINE
                MessageBox MB_OK|MB_ICONEXCLAMATION `* * *  DEBUG BUILD  * * *   ${MULTIUSER_INSTALLMODE_DISPLAYNAME} Setup$(3)Log:$(2)$DebugLogFile`
            ${EndIf}
        !endif
        ${Call} :init_outer
    ${EndIf}

    ${If} ${Silent}
        ClearErrors
        ${CheckInactiveApp}
        ${If} ${Errors}
            ${Quit} ERROR_LOCK_VIOLATION ''
        ${EndIf}
        ${Call} PageComponentsPre
    ${EndIf}

    !undef GetUserName GetOptionState
    !macroundef GET_USER_NAME
    !macroundef GET_OPTION_STATE
    !macroundef SYNC
    ${Release} Result ''
    ${Release} Value ''
    ${Release} MsiPathStr ''
    ${Release} MsiPathKey ''
    ${Release} MsiGuid ''
    ${Release} WindowCaption ''
    ${Release} SetupCaption ''
    ${Release} Handle ''
    ${Release} Option ''
    ${Release} Parameters ''
FunctionEnd

; The following shared functions don't start with '.',
; so add it to the uninstaller prefix.
!if '${F}' != ''
    !define /redef F 'un.'
!endif

; Called by .onGUIInit, which is used by MUI.
; Detect if Windows dark mode theme is enabled, and apply dark colors to the
; setup window, set $DarkMode value. Each page must change the colors of its
; controls using its 'Show'.callback.
Function ${F}onGUIInitMUI
    ${Reserve} $R0 Result 0
    ${If} ${IsHighContrastModeActive}
        ${Set} $DarkMode 0
    ${Else}
        System::Call 'uxtheme::#132() i.${r.Result}' ; ShouldAppsUseDarkMode
        ${Set} $DarkMode ${Result}
    ${EndIf}
    StrCmpS $DarkMode 0 _end

    System::Call 'dwmapi::DwmSetWindowAttribute(p$HWNDPARENT, i${DWMWA_USE_IMMERSIVE_DARK_MODE}, *i1, i4) i.${r.Result}'
    ${If} ${Result} = ${S_OK}
        System::Call 'uxtheme::#135(i1)' ; SetPreferredAppMode
    ${Else}
        ${Set} $DarkMode 0
        Goto _end
    ${EndIf}

    SetCtlColors $HWNDPARENT ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.Header.Image ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
    SetCtlColors $mui.Header.Background ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
    SetCtlColors $mui.Header.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
    SetCtlColors $mui.Header.SubText ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
    SetCtlColors $mui.Button.Next '' ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$mui.Button.Next, w"DarkMode_Explorer", n)'
    SetCtlColors $mui.Button.Back '' ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$mui.Button.Back, w"DarkMode_Explorer", n)'
    SetCtlColors $mui.Button.Cancel '' ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$mui.Button.Cancel, w"DarkMode_Explorer", n)'
    SetCtlColors $mui.Branding.Text /BRANDING '' transparent

    _end:
    ${Release} Result ''
FunctionEnd

; Page callbacks

; Dark mode for InstallMode page.
Function ${F}PageInstallModeShow
    StrCmpS $DarkMode 0 _end
    SetCtlColors $MultiUser.InstallModePage ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $MultiUser.InstallModePage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $MultiUser.InstallModePage.Description ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$MultiUser.InstallModePage.AllUsers, w"", w"")'
    SetCtlColors $MultiUser.InstallModePage.AllUsers ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$MultiUser.InstallModePage.CurrentUser, w"", w"")'
    SetCtlColors $MultiUser.InstallModePage.CurrentUser ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    _end:
FunctionEnd

; Prepare the Components page, update component variables and set shortcut paths.
; This is an essential function and is called by .onInit when silent mode is on
; (and page callbacks are skipped).
Function ${F}PageComponentsPre
    ${Reserve} $R0 SectionId ''
    ${Reserve} $R1 SectionVar 0
    ${Reserve} $R2 IconPath ''
    ${Reserve} $R3 Flag 0
    ${Reserve} $R4 RegValue ''
    ${Reserve} $R5 CurrentUserId ''
    ${Reserve} $R6 CurrentUserString ''

    !insertmacro MULTIUSER_GetCurrentUserString ${CurrentUserString}
    StrCmp $MultiUser.InstallMode 'AllUsers' _start
    ${Set} CurrentUserId '-U'
    Goto _start

    set_icon_selection:
    SectionGetFlags ${SectionId} ${Flag}
    !if '${F}' == ''
        IntCmp ${SectionVar} 0 _unselect_section 0 _select_section
        IntCmp $HasCurrentModeInstallation 1 _check_existing
        ${Return}
        _check_existing:
    !endif
    IfFileExists ${IconPath} _select_section _unselect_section

    _unselect_section:
    IntOp ${Flag} ${Flag} & 0xFFFFFFFE
    !if '${F}' != ''
        SectionSetText ${SectionId} ''
    !endif
    Goto _set_flag
    _select_section:
    IntOp ${Flag} ${Flag} | 1
    _set_flag:
    ${WriteDebug} Flag
    SectionSetFlags ${SectionId} ${Flag}
    ${Return}

    _start:
    ${Set} $DesktopIconPath '$DESKTOP\${PRODUCT_NAME}${CurrentUserString}.lnk'
    ${Set} $StartMenuIconPath '$SMPROGRAMS\${PRODUCT_NAME}${CurrentUserString}.lnk'

    !if '${F}' == ''
        IntCmp $RegisterBrowser 0 _unselect_reg 0 _@
        StrCmpS $HasCurrentModeInstallation 1 _read_reg
        ${Set} $RegisterBrowser 1
        Goto _@
        _read_reg:
    !endif
    ClearErrors
    ReadRegStr ${RegValue} SHCTX '${REG_APPS}' '${PRODUCT_NAME}${CurrentUserId}'
    IfErrors 0 _@
    ReadRegStr ${RegValue} SHCTX '${REG_SMI}${CurrentUserId}' ''
    IfErrors 0 _@
    ReadRegStr ${RegValue} SHCTX '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}' ''
    IfErrors _unselect_reg _@
    _unselect_reg:
    ${Set} $RegisterBrowser 0
    ${Set} SectionId ${${F}SectionRegistry}
    SectionGetFlags ${SectionId} ${Flag}
    ${Call} :_unselect_section

    _@:
    ${Set} SectionId ${${F}SectionDesktopIcon}
    ${Set} SectionVar $DesktopIcon
    ${Set} IconPath $DesktopIconPath
    ${Call} :set_icon_selection

    ${Set} SectionId ${${F}SectionStartMenuIcon}
    ${Set} SectionVar $StartMenuIcon
    ${Set} IconPath $StartMenuIconPath
    ${Call} :set_icon_selection

    !if '${F}' != ''
        SectionGetFlags ${un.SectionGroupShortcuts} ${Flag}
        IntOp ${Flag} ${Flag} | 16
        SectionSetFlags ${un.SectionGroupShortcuts} ${Flag}

        SectionGetFlags ${un.SectionDesktopIcon} ${Flag}
        IntCmp ${Flag} 17 +4
        SectionGetFlags ${un.SectionStartMenuIcon} ${Flag}
        IntCmp ${Flag} 17 +2
        SectionSetText ${un.SectionGroupShortcuts} ''
    !endif

    !macro INIT_DATA_SECTION DATA_DIR DATA_VAR DATA_SEC
        ${IfNot} ${FileExists} '${DATA_DIR}\*'
            ${Set} ${DATA_VAR} 0
            SectionSetText ${DATA_SEC} ''
        ${ElseIf} ${DATA_VAR} = 1
            SectionGetFlags ${DATA_SEC} ${Flag}
            IntOp ${Flag} ${Flag} | 1
            SectionSetFlags ${DATA_SEC} ${Flag}
        ${EndIf}
    !macroend
    !insertmacro INIT_DATA_SECTION $CacheDir $ClearCache ${${F}SectionClearCache}
    !insertmacro INIT_DATA_SECTION $ConfigDir $ClearConfig ${${F}SectionClearConfig}
    !macroundef INIT_DATA_SECTION

    ${Release} CurrentUserString ''
    ${Release} CurrentUserId ''
    ${Release} RegValue ''
    ${Release} Flag ''
    ${Release} IconPath ''
    ${Release} SectionVar ''
    ${Release} SectionId ''
    !if '${F}' != ''
        IfSilent +3
        StrCmpS $SetupState 0 +2
        Abort
    !endif
FunctionEnd

; Dark mode for Components page.
; Also hide the back button for the uninstaller, if there are not both
; per-user and per-machine installations on the system.
Function ${F}PageComponentsShow
    StrCmpS $DarkMode 0 _end
    !if '${F}' == ''
        ${Reserve} $R0 hwndCombo $mui.ComponentsPage.InstTypes
        ${Reserve} $R1 pcbi 0 ; pointer for COMBOBOXINFO structure
        System::Call '*(i52, i, i, i, i, i, i, i, i, i, p, p, p0) p.${r.pcbi}'
        System::Call 'user32::GetComboBoxInfo(i${r.hwndCombo}, p${r.pcbi})'
        System::Call '*${pcbi}(i, i, i, i, i, i, i, i, i, i, p, p, p.${r.hwndCombo})'
        System::Free ${pcbi}
        SetCtlColors ${hwndCombo} ${DARK_FGCOLOR} ${DARK_BGCOLOR_2}
        System::Call 'uxtheme::SetWindowTheme(p$mui.ComponentsPage.InstTypes, w"DarkMode_CFD", n)'
        ${Release} pcbi ''
        ${Release} hwndCombo ''
    !else
        ShowWindow $mui.Button.Back $UninstallShowBackButton
    !endif
    SetCtlColors $mui.ComponentsPage ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SendMessage $mui.ComponentsPage.Components ${TVM_SETBKCOLOR} 0 ${DARK_BGCOLOR_2}
    SendMessage $mui.ComponentsPage.Components ${TVM_SETTEXTCOLOR} 0 ${DARK_FGCOLOR}
    System::Call 'uxtheme::SetWindowTheme(p$mui.ComponentsPage.Components, w"DarkMode_Explorer", n)'
    SetCtlColors $mui.ComponentsPage.ComponentsText ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.ComponentsPage.DescriptionText ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.ComponentsPage.DescriptionText.Info ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$mui.ComponentsPage.DescriptionTitle, w"", w"")'
    SetCtlColors $mui.ComponentsPage.DescriptionTitle ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.ComponentsPage.InstTypesText ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.ComponentsPage.SpaceRequired ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.ComponentsPage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    _end:
FunctionEnd

; Update component variables, based on user selection. Show warning for ClearConfig.
Function ${F}PageComponentsLeave
    !macro S_VAR IN_SECTION OUT_VAR
        SectionGetFlags ${IN_SECTION} ${OUT_VAR}
        IntOp ${OUT_VAR} ${OUT_VAR} & 1
        ${WriteDebug} ${OUT_VAR}
    !macroend
    !if '${F}' == ''
        !insertmacro S_VAR ${SectionRegistry} $RegisterBrowser
        !insertmacro S_VAR ${SectionDesktopIcon} $DesktopIcon
        !insertmacro S_VAR ${SectionStartMenuIcon} $StartMenuIcon
    !endif
    !insertmacro S_VAR ${${F}SectionClearCache} $ClearCache
    !insertmacro S_VAR ${${F}SectionClearConfig} $ClearConfig
    !macroundef S_VAR

    StrCmpS $ClearConfig 1 0 _@
    MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONEXCLAMATION $(MB_CONFIRM_CLEAR_CONFIG) /SD IDYES IDYES _@ IDNO _abort
    _abort:
    Abort

    _@:
    !if '${F}' != ''
        ClearErrors
        ${CheckInactiveApp}
        IfErrors _abort
    !endif
FunctionEnd

; Dark mode for InstFiles page.
Function ${F}PageInstFilesShow
    StrCmpS $DarkMode 0 _end

    ; Dark color for progress bar background
    ${Reserve} $R0 HResult ''
    ${Reserve} $R1 ThemeData ''
    ${Reserve} $0 FillColor '' ; NSIS system plugin bug: Direct register memory access works correctly only with $0-$1
    System::Call 'uxtheme::OpenThemeData(p$mui.InstFilesPage.ProgressBar, w"PROGRESS") p.${r.ThemeData}'
    StrCmpS ${ThemeData} 0 _@
    System::Call 'uxtheme::GetThemeColor(p${r.ThemeData}, i${PP_FILL}, i${PBFS_NORMAL}, i${TMT_FILLCOLOR}, @${r.FillColor}) i.${r.HResult}'
    StrCmpS ${HResult} ${S_OK} 0 _@@
    System::Call 'uxtheme::SetWindowTheme(p$mui.InstFilesPage.ProgressBar, w" ", w" ")'
    SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBKCOLOR} 0 ${DARK_BGCOLOR_2}
    SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBARCOLOR} 0 ${FillColor}
    _@@:
    System::Call 'uxtheme::CloseThemeData(p${r.ThemeData})'
    _@:
    ${Release} FillColor ''
    ${Release} ThemeData ''
    ${Release} Hresult ''

    SetCtlColors $mui.InstFilesPage ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    SetCtlColors $mui.InstFilesPage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
    System::Call 'uxtheme::SetWindowTheme(p$mui.InstFilesPage.ShowLogButton, w"DarkMode_Explorer", n)'
    SetCtlColors $mui.InstFilesPage.ShowLogButton ${DARK_FGCOLOR} ${DARK_BGCOLOR_2}
    System::Call 'uxtheme::SetWindowTheme(p$mui.InstFilesPage.Log, w"DarkMode_Explorer", n)'
    SendMessage $mui.InstFilesPage.Log ${LVM_SETBKCOLOR} 0 ${DARK_BGCOLOR_2}
    SendMessage $mui.InstFilesPage.Log ${LVM_SETTEXTCOLOR} 0 ${DARK_FGCOLOR}
    SendMessage $mui.InstFilesPage.Log ${LVM_SETTEXTBKCOLOR} 0 ${DARK_BGCOLOR_2}
    _end:
FunctionEnd

### Seperate Installer / Uninstaller functions

!if '${F}' == '' ; installer only
    ; Make Default Browser selection depend on Registry Settings.
    Function .onSelChange
        ${Reserve} $R0 Flag 0
        SectionGetFlags ${SectionDefaultBrowser} ${Flag}
        IntOp ${Flag} ${Flag} & 1
        StrCmpS ${Flag} 1 _lock_reg
        SectionGetFlags ${SectionRegistry} ${Flag}
        IntOp ${Flag} ${Flag} & -17 ; not readonly (~16)
        Goto _set_flag
        _lock_reg:
        ${Set} Flag 17 ; selected and readonly (1 | 16)
        _set_flag:
        SectionSetFlags ${SectionRegistry} ${Flag}
        ${Release} Flag ''
    FunctionEnd

    ; Verify $INSTDIR every time the user modifies its value in Directory page.
    Function .onVerifyInstDir
        ${Reserve} $R0 InText ''
        ${Reserve} $R1 OutText ''
        ${Reserve} $R2 LastChar ''
        ${Reserve} $R3 CursorPos 0
        ${Reserve} $R4 TextLength 0
        ${Reserve} $R6 Result 0

        System::Call 'user32::GetWindowTextW(p$mui.DirectoryPage.Directory, w.${r.InText}, i${NSIS_MAX_STRLEN}) i.${r.Result}'
        StrCmpS ${Result} 0 _end
        StrCpy ${LastChar} ${InText} '' -1

        ${If} ${InText} S!= ''
        ${AndIf} ${LastChar} S!= '.'
            ${StdUtils.NormalizePath} ${OutText} ${InText}
            ${Set} $INSTDIR ${OutText}

            ${If} ${LastChar} S== '\'
            ${AndIf} ${FileExists} '$INSTDIR\*'
                System::Call 'kernel32::GetLongPathNameW(w$INSTDIR, w.${r.OutText}, i${NSIS_MAX_STRLEN}) i.${r.TextLength}'
                ${If} ${TextLength} U> 0
                ${Andif} ${TextLength} U< ${NSIS_MAX_STRLEN}
                    ${Set} $INSTDIR ${OutText}
                ${EndIf}
            ${EndIf}

            ${If} ${InText} != $INSTDIR
            ${AndIf} ${InText} != '$INSTDIR\'
                SendMessage $mui.DirectoryPage.Directory ${EM_GETSEL} '' '' ${CursorPos}
                IntOp ${CursorPos} ${CursorPos} >> 16
                IntOp ${CursorPos} ${CursorPos} & 0xffff
                StrLen ${TextLength} $INSTDIR
                IntOp ${CursorPos} ${CursorPos} + ${TextLength}
                StrLen ${TextLength} ${InText}
                IntOp ${CursorPos} ${CursorPos} - ${TextLength}
                ${If} ${LastChar} S== '\'
                    SendMessage $mui.DirectoryPage.Directory ${WM_SETTEXT} 0 'STR:$INSTDIR\'
                    IntOp ${CursorPos} ${CursorPos} + 1
                ${Else}
                    SendMessage $mui.DirectoryPage.Directory ${WM_SETTEXT} 0 STR:$INSTDIR
                ${EndIf}
                SendMessage $mui.DirectoryPage.Directory ${EM_SETSEL} ${CursorPos} ${CursorPos}
            ${EndIf}
        ${EndIf}

        ${StdUtils.NormalizePath} $INSTDIR $INSTDIR
        ClearErrors
        ${CheckValidInstDir}
        ${If} ${Errors}
            Abort
        ${EndIf}

        _end:
        ${Release} Result ''
        ${Release} TextLength ''
        ${Release} CursorPos ''
        ${Release} LastChar ''
        ${Release} OutText ''
        ${Release} InText ''
    FunctionEnd

    Function .onInstFailed
        StrCmpS $SetupState 3 +2
        MessageBox MB_ICONSTOP $(MB_FAIL_INSTALL) /SD IDOK IDOK +2
        MessageBox MB_ICONSTOP $(MB_USER_ABORT) /SD IDOK
    FunctionEnd

    ; Confirm user abort. Called by .onUserAbort which is used by MUI.
    Function onUserAbort
        ${WriteDebug} $SetupState
        StrCmpS $SetupState 1 _confirm
        MessageBox MB_YESNO|MB_ICONQUESTION $(MB_CONFIRM_QUIT) IDYES _end IDNO _resume
        _confirm:
        EnableWindow $mui.Button.Cancel ${SW_HIDE}
        LockWindow on
        ${Set} $SetupState 2
        MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONEXCLAMATION|MB_TOPMOST $(MB_CONFIRM_ABORT) IDYES _abort
        ${Set} $SetupState 1
        LockWindow off
        EnableWindow $mui.Button.Cancel ${SW_NORMAL}
        _resume:
        Abort ; Aborts the abort!
        _abort:
        ${Set} $SetupState 3
        LockWindow off
        Abort
        _end:
    FunctionEnd

    ; Page callbacks

    ; Dark mode for Welcome page.
    Function PageWelcomeShow
        StrCmpS $DarkMode 0 _end
        SetCtlColors $mui.WelcomePage ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        SetCtlColors $mui.WelcomePage.Title ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        SetCtlColors $mui.WelcomePage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        _end:
    FunctionEnd

    ; Hide Welcome and License pages for inner instance.
    Function PageWelcomeLicensePre
        StrCmpS $InstallShowPagesBeforeComponents 1 +2
        Abort
    FunctionEnd

    ; Dark mode for License page.
    Function PageLicenseShow
        StrCmpS $DarkMode 0 _end
        ${Reserve} $R0 CharFormat 0
        SetCtlColors $mui.LicensePage ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SetCtlColors $mui.Licensepage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SetCtlColors $mui.Licensepage.TopText ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SendMessage $mui.Licensepage.LicenseText ${EM_SETBKGNDCOLOR} 0 ${DARK_BGCOLOR_2}
        System::Call '*(i92, i${CFM_COLOR}, i0, i0, i0, i${DARK_FGCOLOR}, i, &w32) p.${r.CharFormat}'
        SendMessage $mui.Licensepage.LicenseText ${EM_SETCHARFORMAT} ${SCF_ALL} ${CharFormat}
        System::Free ${CharFormat}
        System::Call 'uxtheme::SetWindowTheme(p$mui.Licensepage.LicenseText, w"DarkMode_Explorer", n)'
        ${Release} CharFormat ''
        _end:
    FunctionEnd

    ; Dark mode for Directory page.
    Function PageDirectoryShow
        StrCmpS $DarkMode 0 _end
        SetCtlColors $mui.DirectoryPage ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SetCtlColors $mui.DirectoryPage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        System::Call 'uxtheme::SetWindowTheme(p$mui.DirectoryPage.DirectoryBox, w"", w"")'
        SetCtlColors $mui.DirectoryPage.DirectoryBox ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        System::Call 'uxtheme::SetWindowTheme(p$mui.DirectoryPage.Directory, w"DarkMode_CFD", n)'
        SetCtlColors $mui.DirectoryPage.Directory ${DARK_FGCOLOR} ${DARK_BGCOLOR_2}
        System::Call 'uxtheme::SetWindowTheme(p$mui.DirectoryPage.BrowseButton, w"DarkMode_Explorer", n)'
        SetCtlColors $mui.DirectoryPage.BrowseButton ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SetCtlColors $mui.DirectoryPage.SpaceRequired ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        SetCtlColors $mui.DirectoryPage.SpaceAvailable ${DARK_FGCOLOR} ${DARK_BGCOLOR_0}
        _end:
    FunctionEnd

    ; Prompt user if install dir is not empty, not writable, or if the application is running.
    Function PageDirectoryLeave
        !define /math SHARED_MODE ${FILE_SHARE_READ} | ${FILE_SHARE_WRITE}
        !define /math FILE_FLAGS ${FILE_FLAG_BACKUP_SEMANTICS} | ${FILE_FLAG_OPEN_REPARSE_POINT}
        ${Reserve} $R0 Handle ''

        StrCmpS $HasCurrentModeInstallation 0 _check_instdir
        StrCmp $MultiUser.InstallMode 'AllUsers' 0 +2
        StrCmp $INSTDIR $PerMachineInstallationFolder _check_app_running _check_instdir
        StrCmp $iNSTDIR $PerUserInstallationFolder _check_app_running _check_instdir

        _check_instdir:
        IfFileExists '$INSTDIR\*' _check_contents
        ClearErrors
        CreateDirectory $INSTDIR
        IfErrors 0 _end
        MessageBox MB_OK|MB_ICONSTOP $(MB_CANT_CREATE_INSTDIR)
        Abort

        _check_contents:
        ClearErrors
        ${CheckCleanInstDir}
        IfErrors 0 _check_write_access
        MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONEXCLAMATION $(MB_NON_EMPTY_INSTDIR) /SD IDYES IDYES _check_write_access
        Abort

        _check_write_access:
        System::Call 'kernel32::CreateFileW(w"$INSTDIR", i${GENERIC_WRITE}, i${SHARED_MODE}, n, i${OPEN_EXISTING}, i${FILE_FLAGS}, n) p.${r.Handle}'
        StrCmpS ${Handle} ${INVALID_HANDLE_VALUE} 0 _close_handle
        MessageBox MB_OK|MB_ICONSTOP $(MB_CANT_WRITE_INSTDIR)
        Abort
        _close_handle:
        System::Call 'kernel32::CloseHandle(p${r.Handle})'

        _check_app_running:
        ClearErrors
        ${CheckInactiveApp}
        IfErrors 0 _end
        Abort

        _end:
        ${Release} Handle ''
        !undef SHARED_MODE FILE_FLAGS
    FunctionEnd

    ; Reset progress bar for aborted installations.
    Function PageInstFilesLeave
        IfAbort 0 +3
        SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETPOS} 0 0
        StrCpy $CancelButtonText $(B_CLOSE)
    FunctionEnd

    ; Dark mode for Finish page.
    Function PageFinishShow
        StrCmpS $DarkMode 0 _end
        SetCtlColors $mui.FinishPage ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        SetCtlColors $mui.FinishPage.Title ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        SetCtlColors $mui.FinishPage.Text ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        System::Call 'uxtheme::SetWindowTheme(p$mui.FinishPage.Run, w"", w"")'
        SetCtlColors $mui.FinishPage.Run ${DARK_FGCOLOR} ${DARK_BGCOLOR_1}
        _end:
    FunctionEnd

    ; Run installed application.
    Function PageFinishRun
        ShowWindow $HWNDPARENT ${SW_MINIMIZE}
        HideWindow
        ${RunAsUser} '$INSTDIR\${PROGEXE}' ''
    FunctionEnd

    ; Import the uninstaller functions
    !define /redef F 'un'
    !include '${__FILEDIR__}\${__FILE__}'
!else ; uninstaller only
    Function un.onUninstFailed
        StrCmpS $SetupState 1 +2
        MessageBox MB_ICONSTOP $(MB_FAIL_UNINSTALL) /SD IDOK IDOK +2
        MessageBox MB_ICONSTOP $(MB_FAIL_INSTALL) /SD IDOK
    FunctionEnd
    !undef F
!endif
