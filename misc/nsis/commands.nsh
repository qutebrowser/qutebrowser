# SPDX-FileCopyrightText: 2023 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

!define /ifndef F

### Command names, macros, installer-only functions

!if '${F}' == ''
    ; Commands using the auto-generated macros imported from FILE_MACROS_NSH
    !define PassFiles '!insertmacro PASS_FILES'
    !define PassFilesAndHash '!insertmacro PASS_FILES_AND_HASH'
    !define PassDirs '!insertmacro PASS_DIRS'
    !define PassDirsReverse '!insertmacro PASS_DIRS_REVERSE'

    ; Macro commands that help with writing and debugging the code

    ; ${Call} FUNCTION_OR_LABEL
    !define Call '!insertmacro CALL'
    !macro CALL DESTINATION
        !searchparse /noerrors '${DESTINATION}' ':' IS_LABEL
        ${WriteDebug} `${DESTINATION}`
        !ifdef IS_LABEL
            Call ${DESTINATION}
            !undef IS_LABEL
        !else
            !ifndef __UNINSTALL__
                Call ${DESTINATION}
            !else
                Call un.${DESTINATION}
            !endif
        !endif
    !macroend

    ; ${CallAsUser} FUNCTION_OR_LABEL
    !define CallAsUser '!insertmacro CALL_U'
    !macro CALL_U DESTINATION
        !searchparse /noerrors '${DESTINATION}' ':' IS_LABEL
        ${WriteDebug} `${DESTINATION}`
        !ifdef IS_LABEL
            !insertmacro UAC_AsUser_Call Label ${IS_LABEL} ${UAC_SYNCREGISTERS}|${UAC_SYNCINSTDIR}
            !undef IS_LABEL
        !else
            !ifndef __UNINSTALL__
                !insertmacro UAC_AsUser_Call Function ${DESTINATION} ${UAC_SYNCREGISTERS}|${UAC_SYNCINSTDIR}
            !else
                !insertmacro UAC_AsUser_Call Function un.${DESTINATION} ${UAC_SYNCREGISTERS}|${UAC_SYNCINSTDIR}
            !endif
        !endif
    !macroend

    ; ${Error} NAME_OF_ERROR_DEFINE
    !define Error '!insertmacro ERROR'
    !macro ERROR ERROR
        ${WriteDebug} '${ERROR}'
        !if ${${ERROR}} <> 0
            SetErrors
        !endif
    !macroend

    ; ${Quit} NAME_OF_ERROR_DEFINE OPT_MESSAGE
    !define Quit '!insertmacro QUIT'
    !macro QUIT EXIT_CODE MESSAGE
        !ifndef ${EXIT_CODE}
            !error `${EXIT_CODE} not defined`
        !endif
        !if '${MESSAGE}' != ''
            !if ${${EXIT_CODE}} = 0
                MessageBox MB_ICONINFORMATION '${MESSAGE}' /SD IDOK
            !else
                MessageBox MB_ICONSTOP '${MESSAGE}' /SD IDOK
            !endif
        !endif
        ${WriteDebug} '${EXIT_CODE}'
        SetErrorLevel ${${EXIT_CODE}}
        Quit
    !macroend

    ; ${Reserve} REGISTER TEMP_NAME INIT_VALUE
    !define Reserve '!insertmacro RESERVE'
    !macro RESERVE REGISTER TEMP_NAME INIT_VALUE
        !ifdef ${TEMP_NAME}
            !error 'Reserve: "${TEMP_NAME}" already defined'
        !endif
        !searchreplace /ignorecase r.${TEMP_NAME} '${REGISTER}' '$R' 'r1'
        !if '${r.${TEMP_NAME}}' == '${REGISTER}'
            !searchreplace 'r.${TEMP_NAME}' '${REGISTER}' '$' 'r'
            !if '${r.${TEMP_NAME}}' == '${REGISTER}'
                !error 'Reserve: invalid register name'
            !endif
            !searchreplace push.${TEMP_NAME} '${REGISTER}' '$' 'p'
            !searchreplace pop.${TEMP_NAME} '${REGISTER}' '$' 'r'
        !else
            !searchreplace /ignorecase push.${TEMP_NAME} '${REGISTER}' '$R' 'P'
            !searchreplace /ignorecase pop.${TEMP_NAME} '${REGISTER}' '$R' 'R'
        !endif
        Push ${REGISTER}
        StrCpy ${REGISTER} '${INIT_VALUE}'
        !define ${TEMP_NAME} ${REGISTER}
    !macroend

    ; ${Release} TEMP_NAME OPT_OUT_VALUE
    !define Release '!insertmacro RELEASE'
    !macro RELEASE TEMP_NAME PASS_VALUE
        !ifndef ${TEMP_NAME}
            !error 'Release: "${TEMP_NAME}" not defined'
        !endif
        !if '${PASS_VALUE}' != ''
            StrCpy ${PASS_VALUE} ${${TEMP_NAME}}
        !endif
        Pop ${${TEMP_NAME}}
    !undef ${TEMP_NAME} r.${TEMP_NAME} push.${TEMP_NAME} pop.${TEMP_NAME}
    !macroend

    ; ${Return}
    !define Return '!insertmacro RETURN'
    !macro RETURN
        ${WriteDebug} ':'
        Return
    !macroend

    ; ${Set} OUT_VARIABLE VALUE
    !define Set '!insertmacro SET'
    !macro SET VAR VAL
        !searchparse /noerrors '${VAR}' '$' IS_VAR
        !ifdef IS_VAR
            StrCpy ${VAR} '${VAL}'
            !undef IS_VAR
        !else
            StrCpy ${${VAR}} '${VAL}'
        !endif
        ${WriteDebug} `${VAR}`
    !macroend

    ; Common installer/uninstaller commands

    ; ${WriteLog} LOG_MESSAGE
    !define WriteLog '!insertmacro CALL_WriteLog'
    !macro CALL_WriteLog IN_MESSAGE
        ${If} $LogFile != ''
            ${Reserve} $9 InOutLogFile $LogFile
            ${Reserve} $8 InOutLogHandle $LogHandle
            ${Reserve} $7 InLogMessage '${IN_MESSAGE}'
            ${Call} WriteLog
            ${Release} InLogMessage ''
            ${Release} InOutLogHandle $LogHandle
            ${Release} InOutLogFile $LogFile
        ${EndIf}
    !macroend

    ; ${WriteDebug} OPT_DEFINE_NAME_OR_VAR
    !define WriteDebug '!insertmacro CALL_WriteDebug "${__MACRO__}"'
    !macro CALL_WriteDebug IN_MACRO IN_MESSAGE
        !ifdef DEBUG
            !define IN_LINE '${__LINE__}'
            ${Reserve} $9 InOutDebugLogFile $DebugLogFile
            ${Reserve} $8 InOutDebugLogHandle $DebugLogHandle
            ${Reserve} $7 InMessage `${__FILE__}$\t@${IN_LINE}`
            StrCpy $7 $7 -2 ; remove the last '.1' from the line
            ${Reserve} $6 HasErrors 0
            ${Reserve} $5 StrLen 0

            ${If} ${Errors}
                StrCpy ${HasErrors} 1
            ${EndIf}

            StrLen ${StrLen} '${IN_LINE}'
            ${If} ${StrLen} < 9
                StrCpy ${InMessage} `${InMessage}$\t$\t`
            ${ElseIf} ${StrLen} < 17
                StrCpy ${InMessage} `${InMessage}$\t`
            ${EndIf}

            !ifdef __FUNCTION__
                StrCpy ${InMessage} `${InMessage}${__FUNCTION__}:$\t$\t`
                StrLen ${StrLen} '${__FUNCTION__}'
                !ifdef __UNINSTALL__
                    ${If} ${StrLen} < 9
                        StrCpy ${InMessage} `${InMessage}$\t$\t`
                    ${ElseIf} ${StrLen} < 16
                        StrCpy ${InMessage} `${InMessage}$\t`
                    ${EndIf}
                !else
                    ${If} ${StrLen} < 16
                        StrCpy ${InMessage} `${InMessage}$\t`
                    ${EndIf}
                !endif
            !else ifdef __SECTION__
                StrCpy ${InMessage} `${InMessage}*${__SECTION__}:$\t`
                StrLen ${StrLen} '${__SECTION__}'
                ${If} ${StrLen} < 14
                    StrCpy ${InMessage} `${InMessage}$\t$\t`
                ${ElseIf} ${StrLen} < 22
                    StrCpy ${InMessage} `${InMessage}$\t`
                ${EndIf}
            !endif

            !if '${IN_MACRO}' == '${__MACRO__}'
                !define /redef IN_MACRO ''
            !else if '${IN_MACRO}' != 'CALL_U'
                !searchparse /noerrors '${IN_MACRO}' 'CALL_' CALL_MACRO
                !ifdef CALL_MACRO
                    !define /redef IN_MACRO ''
                    !undef CALL_MACRO
                !endif
            !endif

            StrCpy ${InMessage} `${InMessage}${IN_MACRO}>$\t`

            !searchparse /noerrors '${IN_MESSAGE}' '$' IS_VAR
            !ifdef IS_VAR
                !if '${IN_MESSAGE}' != '$${IS_VAR}'
                    !undef IS_VAR
                !endif
            !endif
            !ifdef IS_VAR
                StrCpy ${InMessage} `${InMessage}$${IN_MESSAGE} = '${IN_MESSAGE}'`
                !undef IS_VAR
            !else ifdef '${IN_MESSAGE}'
                !searchparse /noerrors '${${IN_MESSAGE}}' '!insertmacro' IS_MACRO
                !ifdef IS_MACRO
                    StrCpy ${InMessage} `${InMessage}${IN_MESSAGE}`
                    !undef IS_MACRO
                !else
                    StrCpy ${InMessage} `${InMessage}${IN_MESSAGE} = '${${IN_MESSAGE}}'`
                !endif
            !else
                StrCpy ${InMessage} `${InMessage}${IN_MESSAGE}`
            !endif

            !ifndef __UNINSTALL__
                Call WriteLog
            !else
                Call un.WriteLog
            !endif
            FileClose ${InOutDebugLogHandle}
            StrCpy ${InOutDebugLogHandle} ''

            ${If} ${HasErrors} = 1
                SetErrors
            ${EndIf}

            ${Release} StrLen ''
            ${Release} HasErrors ''
            ${Release} InMessage ''
            ${Release} InOutDebugLogHandle $DebugLogHandle
            ${Release} InOutDebugLogFile $DebugLogFile
            !undef IN_LINE
        !endif
    !macroend

    ; ${CloseLogFile}
    !define CloseLogFile '!insertmacro CLOSE_LOG_FILE'
    !macro CLOSE_LOG_FILE
        ${If} $LogHandle != ''
            FileClose $LogHandle
            StrCpy $LogHandle ''
        ${EndIf}
    !macroend

    ; ${PushFileExts} OUT_EXT_COUNT
    !define PushFileExts '!insertmacro CALL_PushFileExts'
    !macro CALL_PushFileExts OUT_EXT_COUNT
        ${Call} PushFileExts
        ${Set} ${OUT_EXT_COUNT} 8
    !macroend

    !define CheckCleanInstDir '${Call} CheckCleanInstDir'
    !define CheckInactiveApp '${Call} CheckInactiveApp'
    !define ClearCache '${Call} ClearCache'
    !define ClearConfig '${Call} ClearConfig'
    !define ClearInstDir '${Call} ClearInstDir'
    !define ClearRegistry '${Call} ClearRegistry'
    !define PromptOnDirtyDirs '${Call} PromptOnDirtyDirs'
    !define RemoveUninstaller '${Call} RemoveUninstaller'

    !define ExecShellAsUser '!insertmacro EXEC_SHELL_AS_USER'
    !macro EXEC_SHELL_AS_USER ACTION COMMAND PARAMETERS SHOW
        !define LABEL_ID ${__LINE__}
        ${Reserve} $0 ExecShellResult 0
        ${If} $IsInnerInstance = 1
            DetailPrint `$(^ExecShell)${ACTION} ${COMMAND} ${PARAMETERS}`
        ${EndIf}
        ${CallAsUser} :exec_shell_${LABEL_ID}
        ${If} ${ExecShellResult} <> 0
            SetErrors
        ${EndIf}
        Goto _end_${LABEL_ID}

        exec_shell_${LABEL_ID}:
        ClearErrors
        ExecShell '${ACTION}' '${COMMAND}' '${PARAMETERS}' ${SHOW}
        ${If} ${Errors}
            ${Set} ${ExecShellResult} 1
        ${EndIf}
        ${Return}

        _end_${LABEL_ID}:
        ${Release} ExecShellResult ''
        !undef LABEL_ID
    !macroend

    ; ${Fail} MESSAGE
    !define Fail '!insertmacro FAIL'
    !macro FAIL MESSAGE
        ${WriteDebug} ''
        ${WriteLog} '${MESSAGE}'
        !ifndef __UNINSTALL__
            ${Set} $SetupState ${INSTALLER_ABORT}
            ${If} $RegisterBrowser = 1
                ${ClearRegistry}
            ${EndIf}
            ${ClearInstDir}
        !endif
        ${WriteLog} $(M_ABORTED)${MESSAGE}
        ${CloseLogFile}
        ${RefreshShellIcons}
        Abort $(M_ABORTED)${MESSAGE}
    !macroend

    ; Installer-only (function) commands

    ; ${CheckValidInstDir}
    ;
    ; Set Error if $INSTDIR path isn't valid.
    !define CheckValidInstDir '${Call} CheckValidInstDir'
    Function CheckValidInstDir
        ${Reserve} $R0 InstDirLength 0
        ${Reserve} $R1 WinDirLength 0
        ${Reserve} $R2 InstDirPart ''
        ; Reject path of different install mode.
        StrCmp $MultiUser.InstallMode 'AllUsers' 0 _@
        StrCmpS $HasPerUserInstallation 1 0 _@@
        StrCmp $INSTDIR $PerUserInstallationFolder _reject _@@
        _@:
        StrCmp $MultiUser.InstallMode 'CurrentUser' 0 _@@
        StrCmpS $HasPerMachineInstallation 1 0 _@@
        StrCmp $INSTDIR $PerMachineInstallationFolder _reject
        _@@:
        ; Reject drive root
        StrLen ${InstDirLength} $INSTDIR
        IntCmpU ${InstDirLength} 3 _reject _reject
        ; Reject $PROGRAMFILES root
        StrCmp $INSTDIR $PROGRAMFILES _reject
        StrCmp $INSTDIR $PROGRAMFILES64 _reject
        ; Reject $WINDIR parent
        StrLen ${WinDirLength} $WINDIR
        IntCmpU ${InstDirLength} ${WinDirLength} _equal _end _greater
        _equal:
        StrCmp $INSTDIR $WINDIR _reject _end
        _greater:
        IntOp ${InstDirLength} ${WinDirLength} + 1
        StrCpy ${InstDirPart} $INSTDIR ${InstDirLength}
        StrCmp ${InstDirPart} '$WINDIR\' _reject _end
        _reject:
        ${Error} ERROR_BAD_PATHNAME
        _end:
        ${Release} InstDirPart ''
        ${Release} WinDirLength ''
        ${Release} InstDirLength ''
    FunctionEnd

    ; ${CreateDesktopIcon}
    ; ${CreateStartMenuIcon}
    ;
    ; Shortcut icon creation.
    !define CreateDesktopIcon '!insertmacro CALL_CreateIcon $DesktopIconPath'
    !define CreateStartMenuIcon '!insertmacro CALL_CreateIcon $StartMenuIconPath'
    !macro CALL_CreateIcon ICON_PATH
        ${Reserve} $0 CreateIcon.Target '${ICON_PATH}'
        ${WriteDebug} CreateIcon.Target
        ${Call} CreateIcon
        ${Release} CreateIcon.Target ''
    !macroend
    Function CreateIcon
        ${Reserve} $R0 IconPath $0
        _start:
        ClearErrors
        CreateShortcut ${IconPath} '$INSTDIR\${PROGEXE}'
        IfErrors 0 _ok
        ${Error} ERROR_WRITE_FAULT
        MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONSTOP $(MB_FILE_ERROR) /SD IDABORT IDRETRY _start IDIGNORE _skip
        ${Fail} $(M_ERROR_CREATING_SHORTCUT)${IconPath}
        _skip:
        ${WriteLog} $(M_SKIPPED)$(M_CREATE_SHORTCUT)${IconPath}
        Goto _end
        _ok:
        ${WriteLog} $(M_CREATE_SHORTCUT)${IconPath}
        _end:
        ${Release} IconPath ''
    FunctionEnd
!endif

### Common installer/uninstaller functions

; Set Error if $INSTDIR containts files, excluding $CacheDir.
Function ${F}CheckCleanInstDir
    ${Reserve} $R0 FileHandle 0
    ${Reserve} $R1 FileName ''
    ClearErrors
    FindFirst ${FileHandle} ${FileName} '$INSTDIR\*' ; FileName = "."
    IfErrors _end
    ${WriteDebug} FileName
    FindNext ${FileHandle} ${FileName} ; FileName = ".."
    IfErrors _end
    ${WriteDebug} FileName
    StrCmp $CacheDir '$INSTDIR\cache' 0 _@
    IfFileExists '$CacheDir\*' 0 _@
    FindNext ${FileHandle} ${FileName}
    IfErrors _end
    ${WriteDebug} FileName
    _@:
    FindNext ${FileHandle} ${FileName}
    IfErrors _end
    ${WriteDebug} FileName
    ${Error} ERROR_DIR_NOT_EMPTY
    _end:
    FindClose ${FileHandle}
    ${Release} FileName ''
    ${Release} FileHandle ''
FunctionEnd

; Prompt user if the installed application is running.
; Set Error if user selects Abort, or on silent mode.
Function ${F}CheckInactiveApp
    ${Reserve} $R0 WindowHandle ''
    ${Reserve} $R1 ProcessId ''
    ${Reserve} $R2 ProcessHandle ''
    ${Reserve} $R3 ProcessPath ''
    ${Reserve} $R4 AppExePath '$INSTDIR\${PROGEXE}'
    ${Reserve} $R5 AppExeUnPath ''
    ${Reserve} $R6 AppRunning 0
    ${Reserve} $R7 Result 0

    _start:
    ${Set} AppRunning 0

    !if '${F}' == ''
        StrCmp $MultiUser.InstallMode 'AllUsers' 0 _@
        StrCmpS $HasPerMachineInstallation 1 0 _@@
        StrCmp $PerMachineInstallationFolder $INSTDIR _@@
        IfFileExists '$PerMachineInstallationFolder\${PROGEXE}' 0 _@@
        ${Set} AppExeUnPath '$PerMachineInstallationFolder\${PROGEXE}'
        Goto _start_scan
        _@:
        StrCmp $MultiUser.InstallMode 'CurrentUser' 0 _@@
        StrCmpS $HasPerUserInstallation 1 0 _@@
        StrCmp $PerUserInstallationFolder $INSTDIR _@@
        IfFileExists '$PerUserInstallationFolder\${PROGEXE}' 0 _@@
        ${Set} AppExeUnPath '$PerUserInstallationFolder\${PROGEXE}'
        Goto _start_scan
        _@@:
    !endif
    IfFileExists ${AppExePath} _start_scan _end
    _start_scan:
    ${Call} :scan_windows
    StrCmp $AdminName '' _check_flag
    StrCmp $AdminName $UserName _check_flag
    ${CallAsUser} :scan_windows
    Goto _check_flag

    scan_windows:
    FindWindow ${WindowHandle} '' '' '' ${WindowHandle}
    StrCmpS ${WindowHandle} 0 _ret
    System::Call 'user32::GetWindowThreadProcessId(p${r.WindowHandle}, *p.${r.ProcessId}) i.${r.Result}'
    StrCmpS ${Result} 0 scan_windows
    System::Call 'kernel32::OpenProcess(i${PROCESS_ALL_ACCESS}, i0, p${r.ProcessId}) p.${r.ProcessHandle}'
    StrCmpS ${ProcessHandle} 0 scan_windows
    System::Call 'psapi::GetModuleFileNameExW(p${r.ProcessHandle}, n, w.${r.ProcessPath}, i${NSIS_MAX_STRLEN}) i.${r.Result}'
    System::Call 'kernel32::CloseHandle(p${r.ProcessHandle})'
    StrCmpS ${Result} 0 scan_windows
    !if '${F}' == ''
        StrCmpS ${AppExeUnPath} '' +2
        StrCmp ${ProcessPath} ${AppExeUnPath} _process_detected
    !endif
    StrCmp ${ProcessPath} ${AppExePath} _process_detected scan_windows
    _process_detected:
    ${Set} AppRunning 1
    _ret:
    ${Return}

    _check_flag:
    StrCmpS ${AppRunning} 0 _end
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION $(MB_APPLICATION_RUNNING) /SD IDCANCEL IDRETRY _start
    ${Error} ERROR_LOCK_VIOLATION

    _end:
    ${Release} Result ''
    ${Release} AppRunning ''
    ${Release} AppExeUnPath ''
    ${Release} AppExePath ''
    ${Release} ProcessPath ''
    ${Release} ProcessHandle ''
    ${Release} ProcessId ''
    ${Release} WindowHandle ''
FunctionEnd

; Remove browser cache files.
Function ${F}ClearCache
    ${Reserve} $R0 CacheParentDir ''
    ${Reserve} $R1 CacheParentState 0

    ${StdUtils.NormalizePath} ${CacheParentDir} '$CacheDir\..'
    goto _start

    remove_cache_dir:
    ClearErrors
    ${If} ${FileExists} '$CacheDir\*'
        RMDir /r $CacheDir
        ClearErrors
    ${Else}
        ${Error} ERROR_PATH_NOT_FOUND
    ${EndIf}
    ${Return}

    check_cache_parent:
    ${DirState} ${CacheParentDir} ${CacheParentState}
    ${WriteDebug} CacheParentState
    ${Return}

    remove_cache_parent:
    ClearErrors
    RMDir ${CacheParentDir}
    ${Return}

    _start:
    DetailPrint $(M_DELETE_FOLDER)$CacheDir
    ${CallAsUser} :remove_cache_dir
    ${IfNot} ${Errors}
        ${WriteLog} $(M_DELETE_FOLDER)$CacheDir
    ${EndIf}

    ${CallAsUser} :check_cache_parent
    ${If} ${CacheParentState} = 0
        DetailPrint $(M_DELETE_FOLDER)${CacheParentDir}
        ${CallAsUser} :remove_cache_parent
        ${IfNot} ${Errors}
            ${WriteLog} $(M_DELETE_FOLDER)${CacheParentDir}
        ${EndIf}
    ${EndIf}

    ${Release} CacheParentState ''
    ${Release} CacheParentDir ''
FunctionEnd

; Remove browser configuration files.
Function ${F}ClearConfig
    Goto _start

    remove_config_dir:
    ClearErrors
    ${If} ${FileExists} '$ConfigDir\*'
        RMDir /r $ConfigDir
        ClearErrors
    ${Else}
        ${Error} ERROR_PATH_NOT_FOUND
    ${EndIf}
    ${Return}

    _start:
    DetailPrint $(M_DELETE_FOLDER)$ConfigDir
    ${CallAsUser} :remove_config_dir
    ${IfNot} ${Errors}
        ${WriteLog} $(M_DELETE_FOLDER)$ConfigDir
    ${EndIf}
FunctionEnd

; Remove installation files and folders.
Function ${F}ClearInstDir
    ${Reserve} $0 TargetPath ''
    ${Reserve} $R0 FileHandle ''
    ${Reserve} $R1 FileCount 0
    ${Reserve} $R2 ErrorMessage ''
    ${Reserve} $R3 State ''
    !if '${F}' == ''
        ${Reserve} $R4 IsDistDir 0
    !endif
    Goto _start

    ; Sub-function: lock_and_stack
    ; Open file for exclusive access, requsting DELETE rights, and push its path
    ; and handle onto the stack.

    !macro CALL_LOCK_AND_STACK BASEDIR FILE
        !if '${BASEDIR}' == ''
            ${Set} TargetPath '${FILE}'
        !else
            ${Set} TargetPath '${BASEDIR}\${FILE}'
        !endif
        ${Call} :lock_and_stack
        StrCmpS ${ErrorMessage} '' +2
        Goto _unstack
    !macroend
    lock_and_stack:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_PREPARE} 0 _check_file
        ; First check if a folder with the same name exists.
        StrCmpS ${IsDistDir} 0 +2
        IfFileExists '${TargetPath}\*' _ret _check_file
        IfFileExists '${TargetPath}\*' 0 _check_file
        DetailPrint $(M_INCOMPATIBLE_FOLDER)${TargetPath}
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION $(MB_DELETE_INCOMPATIBLE_FOLDER) /SD IDOK IDOK _rmdir
        ${Set} ErrorMessage $(M_USER_CANCEL)
        ${Return}
        _check_file:
    !else
        IfFileExists '${TargetPath}\*' _ret
    !endif
    IfFileExists ${TargetPath} _lock
    ${Error} ERROR_FILE_NOT_FOUND
    _ret:
    ${Return}

    _lock:
    DetailPrint $(M_LOCK_FILE)${TargetPath}
    System::Call 'kernel32::CreateFileW(w${r.TargetPath}, i${DELETE}, i0, n, i${OPEN_EXISTING}, i${FILE_ATTRIBUTE_NORMAL}, n) p.${r.FileHandle}'
    StrCmpS ${FileHandle} ${INVALID_HANDLE_VALUE} 0 _stack
    ${Error} ERROR_LOCK_FAILED
    DetailPrint $(M_CANT_LOCK_FILE)${TargetPath}
    StrCmpS $SetupState ${INSTALLER_ABORT} _ret_lock_fail
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_CANT_LOCK_FILE) /SD IDCANCEL IDRETRY lock_and_stack
    ${Set} ErrorMessage $(M_CANT_LOCK_FILE)${TargetPath}
    _ret_lock_fail:
    ${WriteLog} $(M_CANT_LOCK_FILE)${TargetPath}
    ${Return}

    _stack:
    Push ${TargetPath}
    Push ${FileHandle}
    IntOp ${FileCount} ${FileCount} + 1
    ${Return}

    ; Sub-function: remove_dir

    !macro CALL_REMOVE_DIR DIR
        !if '${DIR}' == ''
            ${Set} TargetPath $INSTDIR
        !else
            ${Set} TargetPath '$INSTDIR\${DIR}'
        !endif
        ${Call} :remove_dir
    !macroend
    remove_dir:
    ${DirState} ${TargetPath} ${State}
    ${WriteDebug} State
    IntCmp ${State} 0 _rmdir _ret 0
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} _skip_dir
    !else
        SendMessage $mui.InstFilesPage.ProgressBar ${PBM_STEPIT} 0 0
    !endif
    StrCmp ${TargetPath} $INSTDIR _skip_dir
    MessageBox MB_YESNOCANCEL|MB_DEFBUTTON2|MB_ICONEXCLAMATION $(MB_NON_EMPTY_SUBDIR) /SD IDNO IDYES _rmdir IDNO _skip_dir
    ${Error} ERROR_CANCELLED
    DetailPrint $(M_USER_CANCEL)
    ${WriteLog} $(M_ABORTED)$(M_USER_CANCEL)
    Abort $(M_ABORTED)$(M_USER_CANCEL)

    _rmdir:
    ClearErrors
    RMDir /r ${TargetPath}
    IfErrors _rmdir_error
    ${WriteLog} $(M_DELETE_FOLDER)${TargetPath}
    ${Return}

    _rmdir_error:
    ${Error} ERROR_ACCESS_DENIED
    DetailPrint $(M_CANT_DELETE_FOLDER)${TargetPath}
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} _skip_fail
        StrCmpS ${IsDistDir} 1 _@
        MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_CANT_DELETE_FOLDER_NO_IGNORE) /SD IDCANCEL IDRETRY _rmdir
        ${Set} ErrorMessage $(M_CANT_DELETE_FOLDER)${TargetPath}
        ${WriteLog} $(M_CANT_DELETE_FOLDER)${TargetPath}
        ${Return}
        _@:
    !endif
    MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONEXCLAMATION $(MB_CANT_DELETE_FOLDER) /SD IDIGNORE IDRETRY _rmdir IDIGNORE _skip_fail
    ${Error} ERROR_CANCELLED
    ${WriteLog} $(M_CANT_DELETE_FOLDER)${TargetPath}
    ${WriteLog} $(M_ABORTED)$(M_CANT_DELETE_FOLDER)${TargetPath}
    Abort $(M_ABORTED)$(M_CANT_DELETE_FOLDER)${TargetPath}

    _skip_fail:
    ${WriteLog} $(M_CANT_DELETE_FOLDER)${TargetPath}
    _skip_dir:
    DetailPrint $(M_SKIPPED)$(M_DELETE_FOLDER)${TargetPath}
    ${WriteLog} $(M_SKIPPED)$(M_DELETE_FOLDER)${TargetPath}
    ${Return}

    ; Entry point

    _start:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} 0 +2
        SetOutPath $EXEDIR
    !else
        SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETPOS} 0 0
    !endif

    ${DirState} $INSTDIR ${State}
    IntCmp ${State} 0 _rm_instdir _end

    ${PassFiles} '!insertmacro CALL_LOCK_AND_STACK $INSTDIR'
    !insertmacro CALL_LOCK_AND_STACK '' $DesktopIconPath
    !insertmacro CALL_LOCK_AND_STACK '' $StartMenuIconPath
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_PREPARE} 0 _unstack
        !insertmacro CALL_LOCK_AND_STACK $INSTDIR '${UNINSTALL_FILENAME}'
        ${Set} IsDistDir 1
        ${PassDirs} '!insertmacro CALL_LOCK_AND_STACK $INSTDIR'
    !endif

    _unstack:
    IntCmp ${FileCount} 0 _unstack_done _unstack_done
    Pop ${FileHandle}
    ${WriteDebug} FileHandle
    Pop ${TargetPath}
    ${WriteDebug} TargetPath
    IntOp ${FileCount} ${FileCount} - 1
    System::Call 'kernel32::CloseHandle(p${r.FileHandle})'
    StrCmpS ${ErrorMessage} '' _delete
    DetailPrint $(M_UNLOCK_FILE)${TargetPath}
    Goto _unstack

    _delete:
    IfFileExists ${TargetPath} 0 _unstack
    ClearErrors
    Delete ${TargetPath}
    IfErrors _delete_error
    !if '${F}' != ''
        SendMessage $mui.InstFilesPage.ProgressBar ${PBM_STEPIT} 0 0
    !endif
    ${WriteLog} $(M_DELETE_FILE)${TargetPath}
    Goto _unstack

    _delete_error:
    ${Error} ERROR_UNABLE_TO_REMOVE_REPLACED
    DetailPrint $(M_CANT_DELETE_FILE)${TargetPath}
    StrCmpS $SetupState ${INSTALLER_ABORT} _@@
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_CANT_DELETE_FILE) /SD IDCANCEL IDRETRY _delete
    ${Set} ErrorMessage $(M_CANT_DELETE_FILE)${TargetPath}
    _@@:
    ${WriteLog} $(M_CANT_DELETE_FILE)${TargetPath}
    Goto _unstack

    _unstack_done:
    StrCmpS ${ErrorMessage} '' _rm_subdirs
    ${WriteLog} $(M_ABORTED)${ErrorMessage}
    Abort $(M_ABORTED)${ErrorMessage}

    _rm_subdirs:
    ${PassDirsReverse} '!insertmacro CALL_REMOVE_DIR'

    _rm_instdir:
    StrCmpS $SetupState ${INSTALLER_ABORT} 0 _end
    !insertmacro CALL_REMOVE_DIR ''

    _end:
    !if '${F}' == ''
        ${Release} IsDistDir ''
    !endif
    ${Release} State ''
    ${Release} ErrorMessage ''
    ${Release} FileCount ''
    ${Release} FileHandle ''
    ${Release} TargetPath ''
    !macroundef CALL_LOCK_AND_STACK
    !macroundef CALL_REMOVE_DIR
FunctionEnd

; Remove registry values and keys.
Function ${F}ClearRegistry
    ${Reserve} $R0 RegKey ''
    ${Reserve} $R1 RegItem ''
    ${Reserve} $R2 RegValue ''
    ${Reserve} $R3 ExtCount 0
    ${Reserve} $R4 FileExt ''
    ${Reserve} $R5 CurrentUserId ''
    ${Reserve} $R6 HKey ''
    ${Reserve} $R7 Enum ''
    ${Reserve} $R8 Index ''
    ${Reserve} $0 LangVar ''

    ${If} $MultiUser.InstallMode == 'AllUsers'
        ${Set} HKey 'HKLM'
    ${Else}
        ${Set} CurrentUserId '-U'
        ${Set} HKey 'HKCU'
    ${EndIf}
    Goto _start

    !define RemoveKey '!insertmacro CALL_REMOVE_KEY'
    !macro CALL_REMOVE_KEY REG_KEY
        ${Set} RegKey '${REG_KEY}'
        ${Call} :remove_key
    !macroend
    remove_key:
    ${Set} LangVar '${HKey}\${RegKey}'
    ClearErrors
    EnumRegKey ${Enum} SHCTX ${RegKey} ${Index}
    IfErrors _return
    DetailPrint $(M_DELETE_REG_KEY)${LangVar}
    DeleteRegKey SHCTX ${RegKey}
    IfErrors _remove_key_error
    ${WriteLog} $(M_DELETE_REG_KEY)${LangVar}
    _return:
    ${Return}
    _remove_key_error:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} _skip_key
    !endif
    DetailPrint $(M_CANT_DELETE_REG_KEY)${LangVar}
    MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONSTOP $(MB_CANT_DELETE_REG_KEY) /SD IDIGNORE IDRETRY remove_key IDIGNORE _skip_key
    ${WriteLog} $(M_ABORTED)$(M_CANT_DELETE_REG_KEY)${LangVar}
    Abort $(M_ABORTED)$(M_CANT_DELETE_REG_KEY)${LangVar}
    _skip_key:
    DetailPrint $(M_SKIPPED)$(M_DELETE_REG_KEY)${LangVar}
    ${WriteLog} $(M_CANT_DELETE_REG_KEY)${LangVar}
    ${WriteLog} $(M_SKIPPED)$(M_DELETE_REG_KEY)${LangVar}
    ${Return}

    remove_item:
    ${If} ${RegItem} S== ''
        ${Set} LangVar '${HKey}\${RegKey}>$(REG_DEFAULT_ITEM)'
    ${Else}
        ${Set} LangVar '${HKey}\${RegKey}>${RegItem}'
    ${EndIf}
    ${Set} RegValue ''
    ClearErrors
    ReadRegStr ${RegValue} SHCTX ${RegKey} ${RegItem}
    ${If} ${Errors}
    ${AndIf} ${RegValue} == '' ; it's not a dword value
        ${Return}
    ${EndIf}
    DetailPrint $(M_DELETE_REG_ITEM)${LangVar}
    DeleteRegValue SHCTX ${RegKey} ${RegItem}
    IfErrors _remove_item_error
    ${WriteLog} $(M_DELETE_REG_ITEM)${LangVar}
    ${Return}
    _remove_item_error:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} _skip_item
    !endif
    DetailPrint $(M_CANT_DELETE_REG_KEY)${LangVar}
    MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONSTOP $(MB_CANT_DELETE_REG_ITEM) /SD IDIGNORE IDRETRY remove_item IDIGNORE _skip_item
    ${WriteLog} $(M_ABORTED)$(M_CANT_DELETE_REG_ITEM)${LangVar}
    Abort $(M_ABORTED)$(M_CANT_DELETE_REG_ITEM)${LangVar}
    _skip_item:
    DetailPrint $(M_SKIPPED)$(M_DELETE_REG_ITEM)${LangVar}
    ${WriteLog} $(M_CANT_DELETE_REG_ITEM)${LangVar}
    ${WriteLog} $(M_SKIPPED)$(M_DELETE_REG_ITEM)${LangVar}
    ${Return}

    _start:
    ${Set} RegKey '${REG_APPS}'
    ${Set} RegItem '${PRODUCT_NAME}${CurrentUserId}'
    ${Call} :remove_item

    ${PushFileExts} ExtCount
    ${Set} RegItem '${HTML_HANDLE}${CurrentUserId}'
    _open_with_loop:
    Pop ${FileExt}
    ${Set} RegKey '${REG_CLS}\${FileExt}\OpenWithProgids'
    ${Call} :remove_item
    ${Set} RegKey '${REG_CLS}\${FileExt}'
    DeleteRegKey /ifnovalues SHCTX ${RegKey}
    ${IfNot} ${Errors}
        DetailPrint $(M_DELETE_REG_KEY)${RegKey}
        ${WriteLog} $(M_DELETE_REG_KEY)${RegKey}
    ${EndIf}
    IntOp ${ExtCount} ${ExtCount} - 1
    IntCmp ${ExtCount} 0 0 0 _open_with_loop

    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\Application'
    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\DefaultIcon'
    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\shell\open\command'
    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\shell\open'
    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\shell'
    ${RemoveKey} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}'

    ${RemoveKey} '${REG_SMI}${CurrentUserId}\Capabilities\FileAssociations'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\Capabilities\StartMenu'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\Capabilities\URLAssociations'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\Capabilities'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\DefaultIcon'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\InstallInfo'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\shell\open\command'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\shell\open'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}\shell'
    ${RemoveKey} '${REG_SMI}${CurrentUserId}'

    ${Release} LangVar ''
    ${Release} Index ''
    ${Release} Enum ''
    ${Release} HKey ''
    ${Release} CurrentUserId ''
    ${Release} FileExt ''
    ${Release} ExtCount ''
    ${Release} RegValue ''
    ${Release} Regitem ''
    ${Release} RegKey ''
    !macroundef CALL_REMOVE_KEY
    !undef RemoveKey
FunctionEnd

Function ${F}PromptOnDirtyDirs
    ${Reserve} $R0 DirStatePath ''
    ${Reserve} $R1 DirStateResult ''
    ${Reserve} $R2 MsgBoxText ''
    Goto _start

    check_dir:
    ${CallAsUser} :get_dir_state
    StrCmpS ${DirStateResult} 1 0 _ret
    MessageBox MB_YESNO|MB_ICONEXCLAMATION ${MsgBoxText} /SD IDNO IDNO _ret
    ClearErrors
    ${ExecShellAsUser} open ${DirStatePath} '' SW_SHOWNORMAL
    IfErrors 0 _ret
    MessageBox MB_OK|MB_ICONSTOP $(MB_OPEN_DIR_FAIL)${DirStatePath} /SD IDOK
    _ret:
    ${Return}

    get_dir_state:
    ${DirState} ${DirStatePath} ${DirStateResult}
    ${WriteDebug} DirStateResult
    ${Return}

    _start:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} 0 _@
    !else
        StrCmpS $SetupState ${UNINSTALLER_STANDALONE} 0 _end
    !endif
    ClearErrors
    ${CheckCleanInstDir}
    IfErrors 0 _@
    MessageBox MB_YESNO|MB_ICONEXCLAMATION $(MB_OPEN_INSTDIR) /SD IDNO IDNO _@
    ClearErrors
    ExecShell 'open' $INSTDIR
    IfErrors 0 _@
    MessageBox MB_OK|MB_ICONSTOP $(MB_OPEN_DIR_FAIL)$INSTDIR /SD IDOK
    _@:
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} _end
    !endif

    ${If} $ClearConfig = 1
        ${Set} DirStatePath $ConfigDir
        StrCpy ${MsgBoxText} $(MB_OPEN_CONFIG_DIR)
        ${Call} :check_dir
    ${EndIf}

    ${If} $ClearCache = 1
        ${Set} DirStatePath $CacheDir
        StrCpy ${MsgBoxText} $(MB_OPEN_CACHE_DIR)
        ${Call} :check_dir
    ${EndIf}

    _end:
    ${Release} MsgBoxText ''
    ${Release} DirStateResult ''
    ${Release} DirStatePath ''
FunctionEnd

Function ${F}PushFileExts
    Push '.xhtml'
    Push '.xht'
    Push '.webp'
    Push '.svg'
    Push '.shtml'
    Push '.pdf'
    Push '.html'
    Push '.htm'
FunctionEnd

Function ${F}RemoveUninstaller
    ${Reserve} $R0 UninstallerPath '$INSTDIR\${UNINSTALL_FILENAME}'
    ${Reserve} $R1 InstDirState ''
    !insertmacro MULTIUSER_RegistryRemoveInstallInfo
    !if '${F}' != ''
        StrCmpS $SetupState ${UNINSTALLER_UNDER_INSTALLER} _end
    !endif
    IfFileExists ${UninstallerPath} 0 _rmdir
    ClearErrors
    Delete ${UninstallerPath}
    IfErrors _delete_error
    ${WriteLog} $(M_DELETE_FILE)${UninstallerPath}
    _rmdir:
    ${DirState} $INSTDIR ${InstDirState}
    IntCmp ${InstDirState} 0 0 _end _skip_dir
    ClearErrors
    RMDir $INSTDIR
    IfErrors _rmdir_error
    ${WriteLog} $(M_DELETE_FOLDER)$INSTDIR
    Goto _end
    _delete_error:
    ${WriteLog} $(M_CANT_DELETE_FILE)${UninstallerPath}
    Goto _skip_dir
    _rmdir_error:
    ${WriteLog} $(M_CANT_DELETE_FOLDER)$INSTDIR
    _skip_dir:
    DetailPrint $(M_SKIPPED)$(M_DELETE_FOLDER)$INSTDIR
    ${WriteLog} $(M_SKIPPED)$(M_DELETE_FOLDER)$INSTDIR
    _end:
    ${Release} InstDirState ''
    ${Release} UninstallerPath ''
FunctionEnd

Function ${F}WriteLog
    ${Reserve} $R0 FileName $9
    ${Reserve} $R1 FileHandle $8
    ${Reserve} $R2 LogMessage $7
    ${Reserve} $R3 Time 0
    ${Reserve} $0 LangVar ${FileName}
    StrCmpS ${FileName} '' _end
    StrCmpS ${FileHandle} '' 0 _set_message
    _start:
    ClearErrors
    FileOpen ${FileHandle} ${FileName} a
    IfErrors _error
    FileSeek ${FileHandle} 0 END
    _set_message:
    StrCmpS ${LogMessage} '' _write
    ${StdUtils.Time} ${Time}
    StrCpy ${LogMessage} '[${Time}] ${LogMessage}'
    _write:
    ClearErrors
    FileWriteUTF16LE /BOM ${FileHandle} '${LogMessage}$(1)'
    IfErrors 0 _end
    FileClose ${FileHandle}
    _error:
    DetailPrint $(M_CANT_WRITE)${LangVar}
    !if '${F}' == ''
        StrCmpS $SetupState ${INSTALLER_ABORT} 0 +2
        MessageBox MB_RETRYCANCEL|MB_DEFBUTTON2|MB_ICONSTOP $(MB_FILE_ERROR_NO_ABORT) /SD IDCANCEL IDRETRY _start IDCANCEL _skip
    !endif
    MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONSTOP $(MB_FILE_ERROR) /SD IDABORT IDRETRY _start IDIGNORE _skip
    ${CloseLogFile}
    ${Set} $LogFile ''
    ${Fail} $(M_ABORTED)$(M_CANT_WRITE)${LangVar}
    _skip:
    StrCpy ${FileName} ''
    StrCpy ${FileHandle} ''
    _end:
    ${Release} LangVar ''
    ${Release} Time ''
    ${Release} LogMessage ''
    ${Release} FileHandle $8
    ${Release} FileName $9
FunctionEnd

; Import uninstaller functions
!if '${F}' == ''
    !define /redef F 'un.'
    !include '${__FILEDIR__}\${__FILE__}'
    !undef F
!endif
