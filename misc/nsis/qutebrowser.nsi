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


### Configure build and run compile time commands.

!addincludedir '${__FILEDIR__}'
!include 'config.nsh'
!insertmacro PREPARE_BUILD_ENVIRONMENT

### Include and configure plugins

; Include WinCore NSIS header and define some missing values
!include 'WinCore.nsh'

!define /ifndef ERROR_DIR_NOT_EMPTY 145

!define /ifndef TVM_SETBKCOLOR 0x111D
!define /ifndef TVM_SETTEXTCOLOR 0x111E

!define /ifndef /math LVM_SETBKCOLOR ${LVM_FIRST} + 1
!define /ifndef /math LVM_SETTEXTCOLOR ${LVM_FIRST} + 36
!define /ifndef /math LVM_SETTEXTBKCOLOR ${LVM_FIRST} + 38

!define /ifndef /math EM_SETCHARFORMAT ${WM_USER} + 68
!define /ifndef ST_SELECTION 2
!define /ifndef CFM_COLOR 0x40000000
!define /ifndef SCF_DEFAULT 0x0000
!define /ifndef SCF_ALL 0x0004

!define /ifndef PP_FILL 5
!define /ifndef PBFS_NORMAL 1

!define /ifndef TMT_FILLCOLORHINT 3821

!define /ifndef DWMWA_USE_IMMERSIVE_DARK_MODE 20

!define /ifndef OPEN_EXISTING 3

!define /ifndef FILE_FLAG_BACKUP_SEMANTICS 0x02000000
!define /ifndef FILE_FLAG_OPEN_REPARSE_POINT 0x00200000

; MUI2
!include 'MUI2.nsh'
!define MUI_BGCOLOR 'SYSCLR:Window'
!define MUI_TEXTCOLOR 'SYSCLR:WindowText'
!define MUI_ICON '${INST_ICON}'
!define MUI_UNICON '${UNINST_ICON}'
!define MUI_WELCOMEFINISHPAGE_BITMAP '${WIZARD_IMAGE}'
!define MUI_UNABORTWARNING
!define MUI_LANGDLL_REGISTRY_ROOT 'SHCTX'
!define MUI_LANGDLL_REGISTRY_KEY '${REG_UNINSTALL}\${SETUP_GUID}'
!define MUI_LANGDLL_REGISTRY_VALUENAME 'Language'
!define MUI_LANGDLL_ALLLANGUAGES ; Show all languages, despite user's codepage

; NsisMultiUser
!include 'NsisMultiUser.nsh' ; FileFunc LogicLib nsDialogs StrFunc UAC WinVer x64

!define MULTIUSER_INSTALLMODE_64_BIT 1
!define MULTIUSER_INSTALLMODE_ALLOW_BOTH_INSTALLATIONS 1
!define MULTIUSER_INSTALLMODE_ALLOW_ELEVATION 1
!define MULTIUSER_INSTALLMODE_ALLOW_ELEVATION_IF_SILENT 1
!define MULTIUSER_INSTALLMODE_DEFAULT_ALLUSERS 1
!define MULTIUSER_INSTALLMODE_DISPLAYNAME '${PRODUCT_NAME} v${VERSION} ${ARCH}'
!define MULTIUSER_INSTALLMODE_UNINSTALL_REGISTRY_KEY '${SETUP_GUID}'
!define MULTIUSER_INSTALLMODE_NO_HELP_DIALOG

; StdUtils Plugin
!include 'StdUtils.nsh'

; Make sure the plugin files are stored at the beginning of the compressed data block
ReserveFile /plugin 'UAC.dll'
ReserveFile /plugin 'StdUtils.dll'
!insertmacro MUI_RESERVEFILE_LANGDLL

### MUI: Insert Pages and define Callbacks

;Installer

!define MUI_CUSTOMFUNCTION_ABORT onUserAbort

!define MUI_CUSTOMFUNCTION_GUIINIT onGUIInitMUI

!define MUI_PAGE_CUSTOMFUNCTION_PRE PageWelcomeLicensePre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageWelcomeShow
!insertmacro MUI_PAGE_WELCOME

!define MUI_PAGE_CUSTOMFUNCTION_PRE PageWelcomeLicensePre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageLicenseShow
!insertmacro MUI_PAGE_LICENSE '${LICENSE_FILE}'

!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageInstallModeShow
!insertmacro MULTIUSER_PAGE_INSTALLMODE

!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_PAGE_CUSTOMFUNCTION_PRE PageComponentsPre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageComponentsShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE PageComponentsLeave
!insertmacro MUI_PAGE_COMPONENTS

!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageDirectoryShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE PageDirectoryLeave
!insertmacro MUI_PAGE_DIRECTORY

!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageInstFilesShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE PageInstFilesLeave
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN
!define MUI_PAGE_CUSTOMFUNCTION_SHOW PageFinishShow
!define MUI_FINISHPAGE_RUN_FUNCTION PageFinishRun
!insertmacro MUI_PAGE_FINISH

; Uninstaller

!define MUI_CUSTOMFUNCTION_UNGUIINIT un.onGUIInitMUI

!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.PageInstallModeShow
!insertmacro MULTIUSER_UNPAGE_INSTALLMODE

!define MUI_PAGE_CUSTOMFUNCTION_PRE un.PageComponentsPre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.PageComponentsShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE un.PageComponentsLeave
!insertmacro MUI_UNPAGE_COMPONENTS

!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.PageInstFilesShow
!insertmacro MUI_UNPAGE_INSTFILES

### Languages (all Pages must be set)

!include 'language-english.nsh' ; The first is the default
!insertmacro MULTIUSER_LANGUAGE_INIT ;must be last

### Variables

Var UserName
Var AdminName

Var DarkMode

Var DesktopIconPath
Var StartMenuIconPath

Var CacheDir
Var ConfigDir

!define INSTALLER_PREPARE 0
!define INSTALLER_ACTIVE 1
!define INSTALLER_PAUSE 2
!define INSTALLER_ABORT 3
!define UNINSTALLER_STANDALONE 4
!define UNINSTALLER_UNDER_INSTALLER 5
Var SetupState

; Components: -1 = not set from command line, 0 = disabled, 1 = enabled
Var RegisterBrowser
Var DesktopIcon
Var StartMenuIcon
Var ClearCache
Var ClearConfig

Var LogFile
Var LogHandle

!ifdef DEBUG
    Var DebugLogFile
    Var DebugLogHandle
!endif

Var CancelButtonText

MiscButtonText '' '' $CancelButtonText

### Custom commands

!include '${FILE_MACROS_NSH}'

!include 'commands.nsh'

### Installer Sections

InstType 'Full'
InstType 'Typical'
InstType 'Minimal'

Section '-Installer Uninstall'
    ${Reserve} $R0 ExitCode 0
    ${Reserve} $R1 UninstallDir ''
    ${Reserve} $R2 UninstallDirState ''
    ${Reserve} $R3 UninstallString ''

    ${If} ${FileExists} $LogFile
        ${WriteLog} ''
    ${EndIf}
    ${WriteLog} '$(^SetupCaption): ${MULTIUSER_INSTALLMODE_DISPLAYNAME}'

    ${If} $HasCurrentModeInstallation = 1
        ${If} $MultiUser.InstallMode == 'AllUsers'
            ${Set} UninstallDir $PerMachineInstallationFolder
            ${Set} UninstallString $PerMachineUninstallString
        ${Else}
            ${Set} UninstallDir $PerUserInstallationFolder
            ${Set} UninstallString $PerUserUninstallString
        ${EndIf}

        ${WriteLog} $(M_EXEC)${UninstallString}
        ${CloseLogFile}
        ClearErrors
        ExecWait ${UninstallString} ${ExitCode}
        BringToFront
        ${If} ${Errors}
            ${If} ${UninstallDir} != $INSTDIR
                Push ${UninstallDir}
                Exch $INSTDIR
                ${ClearInstDir}
                Pop $INSTDIR
                !insertmacro MULTIUSER_RegistryRemoveInstallInfo
            ${EndIf}
        ${ElseIf} ${ExitCode} = 0
            ${If} ${UninstallDir} != $INSTDIR
                ${DeleteAnyFile} '${UninstallDir}\${UNINSTALL_FILENAME}'
                ${DirState} ${UninstallDir} ${UninstallDirState}
                ${If} ${UninstallDirState} = 0
                    ${RemoveDir} ${UninstallDir}
                ${EndIf}
            ${EndIf}
        ${Else}
            ${Quit} ExitCode ''
        ${Endif}
    ${EndIf}

    ${If} ${FileExists} '$INSTDIR\*'
        ${ClearInstDir}
    ${EndIf}

    ${If} $RegisterBrowser = 0
        ${ClearRegistry}
    ${EndIf}

    ${Release} UninstallString ''
    ${Release} UninstallDirState ''
    ${Release} UninstallDir ''
    ${Release} ExitCode ''
SectionEnd

Section $(S_FILES) SectionProgramFiles
    SectionIn 1 2 3 RO
    ${Reserve} $R0 AppDir ''
    ${Reserve} $R1 AppFile ''
    ${Reserve} $R2 FileHash ''
    ${Reserve} $R3 CalcHash ''
    ${Reserve} $0 LangVar ''
    Goto _start

    !macro MKDIR APP_DIR
        ${Set} AppDir '${APP_DIR}'
        ${Call} :create_dir
    !macroend
    create_dir:
    ${Set} LangVar ${AppDir}
    IfFileExists '${AppDir}\*' _check_cancel
    ClearErrors
    CreateDirectory ${AppDir}
    IfErrors _dir_error
    ${WriteLog} $(M_CREATE_FOLDER)${AppDir}
    Goto _check_cancel
    _dir_error:
    ${Error} ERROR_WRITE_FAULT
    DetailPrint '$(M_CANT_CREATE_FOLDER)${AppDir}'
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION $(MB_CANT_CREATE_FOLDER) /SD IDCANCEL IDRETRY create_dir
    ${Fail} '$(M_CANT_CREATE_FOLDER)${AppDir}'

    !macro EXTRACT FILE SHA
        ${Set} AppFile '$INSTDIR\${FILE}'
        ${Set} FileHash '${SHA}'
        !define Start 'EXTRACT_@${__LINE__}'
        _${Start}:
        ClearErrors
        File '/oname=${FILE}' '${DIST_DIR}\${FILE}'
        ${Call} :check_extract
        IfErrors _${Start}
        !undef Start
    !macroend
    check_extract:
    ${Set} LangVar ${AppFile}
    IfErrors _write_error
    ${StdUtils.HashFile} ${CalcHash} 'SHA2-256' ${AppFile}
    ${WriteDebug} CalcHash
    StrCmpS ${CalcHash} ${FileHash} 0 _hash_error
    ${WriteLog} $(M_EXTRACT)${AppFile}
    Goto _check_cancel
    _write_error:
    DetailPrint $(M_EXTRACT_ERROR)${AppFile}
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_FILE_ERROR_NO_IGNORE) /SD IDCANCEL IDRETRY _retry
    ${Fail} $(M_EXTRACT_ERROR)${AppFile}
    _hash_error:
    DetailPrint $(M_CHECKSUM_ERROR)${AppFile}
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_CHECKSUM_ERROR) /SD IDCANCEL IDRETRY _retry
    ${Fail} $(M_CHECKSUM_ERROR)${AppFile}

    _retry:
    ${Error} ERROR_RETRY
    _return:
    ${Return}

    _check_cancel:
    IntCmp $SetupState ${INSTALLER_PAUSE} 0 _return _user_abort
    Sleep 500
    Goto _check_cancel
    _user_abort:
    ${Fail} $(M_USER_CANCEL)

    _start:
    !insertmacro MKDIR $INSTDIR
    SetOutPath $INSTDIR
    ${Set} $SetupState ${INSTALLER_ACTIVE}
    EnableWindow $mui.Button.Cancel ${SW_NORMAL}
    ${PassDirs} '!insertmacro MKDIR'
    ${PassFilesAndHash} '!insertmacro EXTRACT'
    EnableWindow $mui.Button.Cancel ${SW_HIDE}
    !macroundef MKDIR
    !macroundef EXTRACT

    ${Release} LangVar ''
    ${Release} CalcHash ''
    ${Release} FileHash ''
    ${Release} AppFile ''
    ${Release} AppDir ''
SectionEnd

SectionGroup /e $(S_SYS_INT) SectionGroupIntegration
    Section $(S_REGISTRY) SectionRegistry
        SectionIn 1 2
        ${Reserve} $R0 RegKey ''
        ${Reserve} $R1 RegName ''
        ${Reserve} $R2 RegValue ''
        ${Reserve} $R3 CurrentRegValue ''
        ${Reserve} $R4 RegLogText ''
        ${Reserve} $R5 HKey ''
        ${Reserve} $R6 FileExtCount 0
        ${Reserve} $R7 FileExt ''
        ${Reserve} $R8 CurrentUserId ''
        ${Reserve} $R9 CurrentUserString ''
        ${Reserve} $0 LangVar ''
        ${Reserve} $1 ExePath '$INSTDIR\${PROGEXE}'

        !insertmacro MULTIUSER_GetCurrentUserString ${CurrentUserString}
        ${If} $MultiUser.InstallMode == 'AllUsers'
            ${Set} HKey 'HKLM'
        ${Else}
            ${Set} CurrentUserId '-U'
            ${Set} HKey 'HKCU'
        ${EndIf}
        Goto _start

        !define UpdateRegStr '!insertmacro CALL_UpdateRegValue Str'
        !define UpdateRegDWORD '!insertmacro CALL_UpdateRegValue DWORD'

        !macro CALL_UpdateRegValue VALUE_TYPE REG_KEY VALUE_NAME VALUE_CONTENT
            !if '${REG_KEY}' != ''
                ${Set} RegKey '${REG_KEY}'
            !endif
            ${Set} RegName '${VALUE_NAME}'
            ${Set} RegValue '${VALUE_CONTENT}'
            ${Call} :update_reg_${VALUE_TYPE}
            IfErrors _error
        !macroend

        !macro UPDATE_REG_VALUE VALUE_TYPE
            !if '${VALUE_TYPE}' == 'str'
                !define EMPTY_VALUE ''
                !define EMPTY_VALUE_TEXT $(REG_EMPTY_VALUE)
                !define Is '=='
                !define IsNot '!='
            !else if '${VALUE_TYPE}' == 'dword'
                !define EMPTY_VALUE 0
                !define EMPTY_VALUE_TEXT '0'
                !define Is '='
                !define IsNot '<>'
            !else
                !error 'UPDATE_REG_VALUE: invalid "VALUE_TYPE"'
            !endif
            ClearErrors
            ReadReg${VALUE_TYPE} ${CurrentRegValue} SHCTX ${RegKey} ${RegName}
            ${If} ${Errors}
            ${OrIf} ${CurrentRegValue} ${IsNot} ${RegValue}

                ${Set} RegLogText '${HKey}\${RegKey}>'

                ${If} ${RegName} == ''
                    ${Set} RegLogText '${RegLogText}$(REG_DEFAULT_ITEM)'
                ${Else}
                    ${Set} RegLogText '${RegLogText}${RegName}'
                ${EndIf}
                ${If} ${RegValue} ${Is} '${EMPTY_VALUE}'
                    ${Set} RegLogText '${RegLogText}=${VALUE_TYPE}:${EMPTY_VALUE_TEXT}'
                ${Else}
                    ${Set} RegLogText '${RegLogText}=${VALUE_TYPE}:${RegValue}'
                ${EndIf}
                DetailPrint $(M_UPDATE_REG)${RegLogText}
                ClearErrors
                WriteReg${VALUE_TYPE} SHCTX ${RegKey} ${RegName} ${RegValue}
                ${If} ${Errors}
                    DetailPrint $(M_CANT_WRITE_REG)${RegLogText}
                    ${Error} ERROR_ACCESS_DENIED
                ${Else}
                    ${WriteLog} $(M_UPDATE_REG)${RegLogText}
                ${EndIf}
            ${Else}
                ${Error} ERROR_ALREADY_EXISTS
                ClearErrors
            ${EndIf}
            ${Return}
            !undef EMPTY_VALUE EMPTY_VALUE_TEXT IS ISNOT
        !macroend

        update_reg_str:
        !insertmacro UPDATE_REG_VALUE 'str'

        update_reg_dword:
        !insertmacro UPDATE_REG_VALUE 'dword'

        _start:
        ; StartMenuInternet
        ${UpdateRegStr} '${REG_SMI}${CurrentUserId}' '' '${PRODUCT_NAME}'
        ; StartMenuInternet\Capabilities
        ${UpdateRegStr} '${REG_SMI}${CurrentUserId}\Capabilities' 'ApplicationDescription' $(DESCRIPTION)
        ${UpdateRegStr} '' 'ApplicationIcon' '${ExePath},0'
        ${UpdateRegStr} '' 'ApplicationName' '${PRODUCT_NAME}${CurrentUserString}'

        ; StartMenuInternet\Capabilities\FileAssociations
        ${Set} RegKey '${REG_SMI}${CurrentUserId}\Capabilities\FileAssociations'
        ${Set} RegValue '${HTML_HANDLE}${CurrentUserId}'
        ${PushFileExts} FileExtCount
        _file_assoc_loop:
        Pop ${FileExt}
        ${Set} RegName ${FileExt}
        ${Call} :update_reg_str
        IntOp ${FileExtCount} ${FileExtCount} - 1
        IntCmp ${FileExtCount} 0 0 0 _file_assoc_loop

        ; StartMenuInternet\Capabilities\StartMenu
        ${UpdateRegStr} '${REG_SMI}${CurrentUserId}\Capabilities\StartMenu' 'StartMenuInternet' '${PRODUCT_NAME}${CurrentUserString}'
        ; StartMenuInternet\Capabilities\URLAssociations
        ${Set} RegKey '${REG_SMI}${CurrentUserId}\Capabilities\URLAssociations'
        ${Set} RegValue '${HTML_HANDLE}${CurrentUserId}'
        ${Set} RegName 'http'
        ${Call} :update_reg_str
        ${Set} RegName 'https'
        ${Call} :update_reg_str
        ; StartMenuInternet\DefaultIcon
        ${UpdateRegStr} '${REG_SMI}${CurrentUserId}\DefaultIcon' '' '${ExePath},0'
        ; StartMenuInternet\InstallInfo
        ${UpdateRegDWORD} '${REG_SMI}${CurrentUserId}\InstallInfo' 'IconsVisible' 1
        ; StartMenuInternet\shell\open\command
        ${UpdateRegStr} '${REG_SMI}${CurrentUserId}\shell\open\command' '' '"${ExePath}"'

        ; Software\Classes
        ${UpdateRegStr} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}' '' $(HTML_DOCUMENT)
        ${UpdateRegStr} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\Application' 'ApplicationCompany' '${COMPANY_NAME}'
        ${UpdateRegStr} '' 'ApplicationDescription' $(DESCRIPTION)
        ${UpdateRegStr} '' 'ApplicationIcon' '${ExePath},0'
        ${UpdateRegStr} '' 'ApplicationName' '${PRODUCT_NAME}${CurrentUserString}'
        ${UpdateRegStr} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\DefaultIcon' '' '${ExePath},0'
        ${UpdateRegStr} '${REG_CLS}\${HTML_HANDLE}${CurrentUserId}\shell\open\command' '' '"${ExePath}" --untrusted-args "%1"'

        ${Set} RegName '${HTML_HANDLE}${CurrentUserId}'
        ${Set} RegValue ''
        ${PushFileExts} FileExtCount
        _open_with_loop:
        Pop ${FileExt}
        ${Set} RegKey '${REG_CLS}\${FileExt}\OpenWithProgids'
        ${Call} :update_reg_str
        IntOp ${FileExtCount} ${FileExtCount} - 1
        IntCmp ${FileExtCount} 0 0 0 _open_with_loop

        ; Software\RegisteredApplications
        ${UpdateRegStr} '${REG_APPS}' '${PRODUCT_NAME}${CurrentUserId}' '${REG_SMI}${CurrentUserId}\Capabilities'

        Goto _end

        _error:
        IntCmp ${FileExtCount} 0 _prompt _prompt 0
        Pop ${FileExt}
        IntOp ${FileExtCount} ${FileExtCount} - 1
        Goto _error
        _prompt:
        ${Set} LangVar '${HKey}\${RegKey}'
        MessageBox MB_ABORTRETRYIGNORE|MB_DEFBUTTON2|MB_ICONSTOP $(MB_CANT_WRITE_REG) /SD IDABORT IDRETRY _start IDIGNORE _skip
        ${Fail} $(M_CANT_WRITE_REG)${RegLogText}
        _skip:
        ${Set} $RegisterBrowser 0
        ${WriteLog} $(M_CANT_WRITE_REG)${RegLogText}
        ${ClearRegistry}
        DetailPrint $(M_SKIPPED)$(S_REGISTRY)
        ${WriteLog} $(M_SKIPPED)$(S_REGISTRY)

        _end:
        ${Release} ExePath ''
        ${Release} LangVar ''
        ${Release} CurrentUserString ''
        ${Release} CurrentUserId ''
        ${Release} FileExt ''
        ${Release} FileExtCount ''
        ${Release} HKey ''
        ${Release} RegLogText ''
        ${Release} CurrentRegValue ''
        ${Release} RegValue ''
        ${Release} RegName ''
        ${Release} RegKey ''
    SectionEnd

    Section /o $(S_DEFAULT_BROWSER) SectionDefaultBrowser
        SectionIn 1
        StrCmpS $RegisterBrowser 0 _end
        ClearErrors
        ${ExecShellAsUser} open 'ms-settings:defaultapps' '' SW_SHOWNORMAL
        IfErrors 0 _end
        MessageBox MB_OK|MB_ICONSTOP $(MB_OPEN_DEFAULT_APPS_FAIL) /SD IDOK
        _end:
    SectionEnd
SectionGroupEnd

SectionGroup /e $(S_ICONS) SectionGroupShortcuts
    Section $(S_ICON_DESKTOP) SectionDesktopIcon
        SectionIn 1 2
        ${CreateDesktopIcon}
    SectionEnd

    Section $(S_ICON_STARTMENU) SectionStartMenuIcon
        SectionIn 1 2
        ${CreateStartMenuIcon}
    SectionEnd
SectionGroupEnd

Section /o $(S_CLEAR_CACHE) SectionClearCache
    ${ClearCache}
SectionEnd

Section /o $(S_CLEAR_CONFIG) SectionClearConfig
    ${ClearConfig}
SectionEnd

Section '-Write Install Info'
    ${Reserve} $R0 CurrentUserString ''
    ${Reserve} $R1 RegKey ''
    ${Reserve} $R2 RegValue ''
    ${Reserve} $0 LangVar ''

    _write_reg:
    !insertmacro MULTIUSER_RegistryAddInstallInfo
    !insertmacro MULTIUSER_RegistryAddInstallSizeInfo
    !insertmacro MULTIUSER_GetCurrentUserString ${CurrentUserString}
    ${Set} RegKey '${MULTIUSER_INSTALLMODE_UNINSTALL_REGISTRY_KEY_PATH}${CurrentUserString}'
    ClearErrors
    ReadRegStr ${RegValue} SHCTX ${RegKey} 'UninstallString'
    IfErrors _reg_error
    WriteRegStr SHCTX ${RegKey} 'UninstallString' '${RegValue} /User'
    IfErrors _reg_error
    WriteRegStr '${MUI_LANGDLL_REGISTRY_ROOT}' '${MUI_LANGDLL_REGISTRY_KEY}' '${MUI_LANGDLL_REGISTRY_VALUENAME}' $LANGUAGE
    IfErrors _reg_error

    _write_file:
    ClearErrors
    WriteUninstaller '${UNINSTALL_FILENAME}'
    IfErrors _file_error
    ${WriteLog} '$(M_CREATED_UNINSTALLER)$INSTDIR\${UNINSTALL_FILENAME}'
    Goto _end

    _file_error:
    ${Set} LangVar '$INSTDIR\${UNINSTALL_FILENAME}'
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_FILE_ERROR_NO_IGNORE) /SD IDCANCEL IDRETRY _write_file
    !insertmacro MULTIUSER_RegistryRemoveInstallInfo
    ${Fail} $(M_ERROR_CREATING)${LangVar}

    _reg_error:
    ${Set} LangVar ${RegKey}
    MessageBox MB_RETRYCANCEL|MB_ICONSTOP $(MB_CANT_WRITE_REG) /SD IDCANCEL IDRETRY _write_reg
    ${Fail} $(M_CANT_WRITE_REG)${LangVar}

    _end:
    ${WriteLog} $(M_COMPLETED)
    ${WriteLog} ''
    ${CloseLogFile}
    ${RefreshShellIcons}

    ${ClearDataDirsCheck}

    ${Release} LangVar ''
    ${Release} RegValue ''
    ${Release} RegKey ''
    ${Release} CurrentUserString ''
SectionEnd

; Installer Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SectionProgramFiles} $(SD_FILES)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionGroupIntegration} $(SD_SYS_INT)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionRegistry} $(SD_REGISTRY)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionDefaultBrowser} $(SD_DEFAULT_BROWSER)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionGroupShortcuts} $(SD_ICONS)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionDesktopIcon} $(SD_ICON_DESKTOP)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionStartMenuIcon} $(SD_ICON_STARTMENU)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionClearCache} $(SD_CLEAR_CACHE)
!insertmacro MUI_DESCRIPTION_TEXT ${SectionClearConfig} $(SD_CLEAR_CONFIG)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

### Uninstaller Sections

Section un.$(S_FILES) un.SectionProgramFiles
    SectionIn RO
    ${If} $SetupState = ${UNINSTALLER_STANDALONE}
    ${AndIf} ${FileExists} $LogFile
        ${WriteLog} ''
    ${EndIf}
    ${WriteLog} '$(^UninstallCaption): ${MULTIUSER_INSTALLMODE_DISPLAYNAME}'
    ${DeleteFile} '${PROGEXE}'
SectionEnd

Section un.$(S_REGISTRY) un.SectionRegistry
    SectionIn RO
    ${If} $SetupState = ${UNINSTALLER_STANDALONE}
        ${ClearRegistry}
    ${EndIf}
SectionEnd

SectionGroup /e un.$(S_ICONS) un.SectionGroupShortcuts
    Section un.$(S_ICON_DESKTOP) un.SectionDesktopIcon
        SectionIn RO
        ${RemoveDesktopIcon}
    SectionEnd

    Section un.$(S_ICON_STARTMENU) un.SectionStartMenuIcon
        SectionIn RO
        ${RemoveStartMenuIcon}
    SectionEnd
SectionGroupEnd

Section /o un.$(S_CLEAR_CACHE) un.SectionClearCache
    ${ClearCache}
SectionEnd

Section /o un.$(S_CLEAR_CONFIG) un.SectionClearConfig
    ${ClearConfig}
SectionEnd

Section '-Uninstall'
    ${Reserve} $R0 InstDirState 0

    ${PassFiles} '${DeleteFile}'
    ${PassDirsReverse} '${RemoveDir}'
    !insertmacro MULTIUSER_RegistryRemoveInstallInfo
    ${If} $EXEPATH != '$INSTDIR\${UNINSTALL_FILENAME}'
        ${DeleteFile} '${UNINSTALL_FILENAME}'
        ${DirState} $INSTDIR ${InstDirState}
        ${If} ${InstDirState} = 0
            ${RemoveDir} $INSTDIR
        ${EndIf}
    ${EndIf}

    ${If} $SetupState = ${UNINSTALLER_STANDALONE}
        ${WriteLog} $(M_COMPLETED)
        ${WriteLog} ''
    ${EndIf}
    ${CloseLogFile}
    ${RefreshShellIcons}

    ${If} $SetupState = ${UNINSTALLER_STANDALONE}
    ${AndIf} ${InstDirState} = 1
        ClearErrors
        ${CheckCleanInstDir}
        ${If} ${Errors}
            MessageBox MB_YESNO|MB_ICONEXCLAMATION $(MB_OPEN_INSTDIR) /SD IDNO IDNO _@
            ClearErrors
            ExecShell 'open' $INSTDIR
            IfErrors 0 _@
            MessageBox MB_OK|MB_ICONSTOP $(MB_OPEN_DIR_FAIL)$INSTDIR /SD IDOK
            _@:
        ${EndIf}
    ${EndIf}
    ${ClearDataDirsCheck}

    ${Release} InstDirState ''
SectionEnd

; Uninstaller Section Descriptions
!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionProgramFiles} $(SD_FILES_UN)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionRegistry} $(SD_REGISTRY_UN)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionGroupShortcuts} $(SD_ICONS_UN)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionDesktopIcon} $(SD_ICON_DESKTOP_UN)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionStartMenuIcon} $(SD_ICON_STARTMENU_UN)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionClearCache} $(SD_CLEAR_CACHE)
!insertmacro MUI_DESCRIPTION_TEXT ${un.SectionClearConfig} $(SD_CLEAR_CONFIG)
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END

### Callback functions - must be included after Sections

!include 'callbacks.nsh'
