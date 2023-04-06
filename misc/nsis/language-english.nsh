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


!insertmacro MUI_LANGUAGE 'English'

; Newlines
LangString 1 ${LANG_ENGLISH} `$\r$\n`
LangString 2 ${LANG_ENGLISH} $(1)$(1)
LangString 3 ${LANG_ENGLISH} $(2)$(1)
LangString 4 ${LANG_ENGLISH} $(3)$(1)

; File and registry texts
LangString DESCRIPTION ${LANG_ENGLISH} `A keyboard-driven, vim-like browser based on Python and Qt.`
LangString HTML_DOCUMENT ${LANG_ENGLISH} `${PRODUCT_NAME} HTML Document`
LangString REG_DEFAULT_ITEM ${LANG_ENGLISH} `(Default)`
LangString REG_EMPTY_VALUE ${LANG_ENGLISH} `(Empty)`

; Section label texts
LangString S_CLEAR_CACHE ${LANG_ENGLISH} `Clear Browser Cache`
LangString S_CLEAR_CONFIG ${LANG_ENGLISH} `Clear Browser Settings`
LangString S_DEFAULT_BROWSER ${LANG_ENGLISH} `Set Default Web Browser`
LangString S_FILES ${LANG_ENGLISH} `Application Files`
LangString S_FILES_UN ${LANG_ENGLISH} `Program Files`
LangString S_ICON_DESKTOP ${LANG_ENGLISH} `Desktop Icon`
LangString S_ICON_STARTMENU ${LANG_ENGLISH} `Start Menu Icon`
LangString S_ICONS ${LANG_ENGLISH} `Shortcut Icons`
LangString S_REGISTRY ${LANG_ENGLISH} `Registry Settings`
LangString S_SYS_INT ${LANG_ENGLISH} `System Integration`

; Section description texts
LangString SD_CLEAR_CACHE ${LANG_ENGLISH} `Clear ${PRODUCT_NAME} cache directory of user $UserName.`
LangString SD_CLEAR_CONFIG ${LANG_ENGLISH} `Clear ${PRODUCT_NAME} configuration data of user $UserName.`
LangString SD_DEFAULT_BROWSER ${LANG_ENGLISH} `Open default apps settings.`
LangString SD_FILES ${LANG_ENGLISH} `Core files required to run ${PRODUCT_NAME}.`
LangString SD_FILES_UN ${LANG_ENGLISH} `Remove ${PRODUCT_NAME} application files:$(1)"$INSTDIR"`
LangString SD_ICON_DESKTOP ${LANG_ENGLISH} `Create ${PRODUCT_NAME} icon on the Desktop.`
LangString SD_ICON_DESKTOP_UN ${LANG_ENGLISH} `Remove ${PRODUCT_NAME} icon from the Desktop:$(1)"$DesktopIconPath"`
LangString SD_ICON_STARTMENU ${LANG_ENGLISH} `Create ${PRODUCT_NAME} icon in the Start Menu.`
LangString SD_ICON_STARTMENU_UN ${LANG_ENGLISH} `Remove ${PRODUCT_NAME} icon from the Start Menu:$(1)"$StartMenuIconPath"`
LangString SD_ICONS ${LANG_ENGLISH} `Create shortcut icons to run ${PRODUCT_NAME}.`
LangString SD_ICONS_UN ${LANG_ENGLISH} `Remove ${PRODUCT_NAME} shortcut icons.`
LangString SD_REGISTRY ${LANG_ENGLISH} `Register protocols and file types with ${PRODUCT_NAME}.`
LangString SD_REGISTRY_UN ${LANG_ENGLISH} `Remove ${PRODUCT_NAME} settings from the registry.`
LangString SD_SYS_INT ${LANG_ENGLISH} `Integrate ${PRODUCT_NAME} with the Operating System.`

; Log texts
LangString M_ABORTED ${LANG_ENGLISH} `Aborted: `
LangString M_CANT_CREATE_FOLDER ${LANG_ENGLISH} `Can't create folder: `
LangString M_CANT_DELETE_FILE ${LANG_ENGLISH} `Can't delete file: `
LangString M_CANT_DELETE_FOLDER ${LANG_ENGLISH} `Can't remove folder: `
LangString M_CANT_DELETE_REG_ITEM ${LANG_ENGLISH} `Can't delete registry item: `
LangString M_CANT_DELETE_REG_KEY ${LANG_ENGLISH} `Can't remove registry key: `
LangString M_CANT_WRITE ${LANG_ENGLISH} $(^CantWrite)
LangString M_CANT_WRITE_REG ${LANG_ENGLISH} `Can't write registry: `
LangString M_CHECKSUM_ERROR ${LANG_ENGLISH} `File checksum error: `
LangString M_COMPLETED ${LANG_ENGLISH} $(^Completed)
LangString M_CREATE_FOLDER ${LANG_ENGLISH} $(^CreateFolder)
LangString M_CREATE_SHORTCUT ${LANG_ENGLISH} $(^CreateShortcut)
LangString M_CREATED_UNINSTALLER ${LANG_ENGLISH} $(^CreatedUninstaller)
LangString M_DELETE_FILE ${LANG_ENGLISH} $(^Delete)
LangString M_DELETE_FOLDER ${LANG_ENGLISH} $(^RemoveFolder)
LangString M_DELETE_REG_KEY ${LANG_ENGLISH} `Remove registry key: `
LangString M_DELETE_REG_ITEM ${LANG_ENGLISH} `Delete registry item: `
LangString M_EXEC ${LANG_ENGLISH} $(^Exec)
LangString M_EXTRACT ${LANG_ENGLISH} $(^Extract)
LangString M_EXTRACT_ERROR ${LANG_ENGLISH} $(^ErrorWriting)
LangString M_ERROR_CREATING ${LANG_ENGLISH} $(^ErrorCreating)
LangString M_ERROR_CREATING_SHORTCUT ${LANG_ENGLISH} $(^ErrorCreatingShortcut)
LangString M_SKIPPED ${LANG_ENGLISH} $(^Skipped)
LangString M_UPDATE_REG ${LANG_ENGLISH} `Update registry: `
LangString M_USER_CANCEL ${LANG_ENGLISH} `Canceled by user`

; MessageBox action texts
LangString A_RETRY_CANCEL ${LANG_ENGLISH} `$(2)Click Retry to try again, or$(1)Cancel quit.`
LangString A_ABORT_RETRY_IGNORE ${LANG_ENGLISH} `$(2)Click Abort to quit,$(1)Retry to try again, or$(1)Ignore to skip `

; MessageBox texts
LangString MB_APPLICATION_RUNNING ${LANG_ENGLISH} `\
${PRODUCT_NAME} is currently running.$(2)\
Please close all of its windows and click$(1)\
Retry to continue, or$(1)\
Cancel to abort.\
`
LangString MB_CANT_CREATE_FOLDER ${LANG_ENGLISH} $(M_CANT_CREATE_FOLDER)$(2)$0$(A_RETRY_CANCEL)
LangString MB_CANT_DELETE_FILE ${LANG_ENGLISH} $(M_CANT_DELETE_FILE)$(2)$0$(A_RETRY_CANCEL)
LangString MB_CANT_DELETE_FOLDER ${LANG_ENGLISH} `$(M_CANT_DELETE_FOLDER)$(2)$0$(A_ABORT_RETRY_IGNORE)this folder.`
LangString MB_CANT_DELETE_REG_ITEM ${LANG_ENGLISH} `$(M_CANT_DELETE_REG_ITEM)$(2)$0$(A_ABORT_RETRY_IGNORE)this registry item.`
LangString MB_CANT_DELETE_REG_KEY ${LANG_ENGLISH} `$(M_CANT_DELETE_REG_KEY)$(2)$0$(A_ABORT_RETRY_IGNORE)this registry key.`
LangString MB_CANT_WRITE_REG ${LANG_ENGLISH} `$(M_CANT_WRITE_REG)$(2)$0$(A_ABORT_RETRY_IGNORE)$(S_SYS_INT).`
LangString MB_CHECKSUM_ERROR ${LANG_ENGLISH} $(M_CHECKSUM_ERROR)$(2)$0$(A_RETRY_CANCEL)
LangString MB_CONFIRM_ABORT ${LANG_ENGLISH} `Are you sure you want to abort the installation?`
LangString MB_CONFIRM_CLEAR_CONFIG ${LANG_ENGLISH} `\
ATTENTION: All settings from the default$(1)\
configuration directory of user:$(2)$UserName$(2)\
located in:$(2)$ConfigDir$(2)\
are set to be erased!$(2)\
Continue?\
`
LangString MB_CONFIRM_QUIT ${LANG_ENGLISH} `Are you sure you want to quit $(^Name) Setup?`
LangString MB_FAIL_INSTALL ${LANG_ENGLISH} `\
${PRODUCT_NAME} ${VERSION}installation failed.$(1)\
Please restart Windows and run the setup again.\
`
LangString MB_FAIL_UNINSTALL ${LANG_ENGLISH} `\
${PRODUCT_NAME} ${VERSION} could not be fully uninstalled.$(1)\
Please restart Windows and run the uninstaller again.\
`
LangString MB_FILE_ERROR ${LANG_ENGLISH} $(^FileError)
LangString MB_FILE_ERROR_NO_IGNORE ${LANG_ENGLISH} $(^FileError_NoIgnore)
LangString MB_HELP_INSTALL ${LANG_ENGLISH} `\
Usage:$(2)\
$EXEFILE [</AllUsers | /CurrentUser> [/Silent]] \
[/User] [/DesktopIcon[=off]] [/StartMenuIcon[=off]] \
[/RegisterBrowser[=off]] [/ClearCache] [/ClearConfig] \
[/InstallDir=<{directory}>] [/Log[={file}]]$(2)\
$EXEFILE </Uninstall> </AllUsers | /CurrentUser> \
[/User] [/ClearCache] [/ClearConfig] [/Silent] [/Log[={file}]]\
`
LangString MB_HELP_EXIT_CODES ${LANG_ENGLISH} `\
$(3)Return codes (decimal):$(2)\
0$\t- normal execution (no error)$(1)\
1$\t- (un)installation aborted by user (Cancel button)$(1)\
2$\t- (un)installation aborted by script$(1)\
666660$\t- invalid command-line parameters$(1)\
666661$\t- elevation is not allowed by defines$(1)\
666662$\t- uninstaller detected there is no installed version$(1)\
666663$\t- executing uninstaller from the installer failed$(1)\
666666$\t- cannot start elevated instance$(1)\
other$\t- Windows error code when trying to start elevated instance\
`
LangString MB_HELP_UNINSTALL ${LANG_ENGLISH} `\
Usage:$(2)\
${UNINSTALL_FILENAME} [</AllUsers | /CurrentUser> [/Silent]] \
[/User] [/ClearCache] [/ClearConfig] [/Log[={file}]]\
`
LangString MB_NON_EMPTY_INSTDIR ${LANG_ENGLISH} `\
The directory:$(2)$INSTDIR$(2)\
already exists and contains files!$(2)\
Continue anyway?\
`
LangString MB_NON_EMPTY_SUBDIR ${LANG_ENGLISH} `\
The directory:$(2)$0$(2)\
Contains files that don't belong to the installation.$(2)\
Remove extra files?\
`
LangString MB_NOWINDOW_ERROR ${LANG_ENGLISH} `\
An instance of $(^Name) Setup is already running,$(1)\
but without having a visible window.$(2)\
Please restart Windows and run the Setup again.\
`
LangString MB_OPEN_INSTDIR ${LANG_ENGLISH} `\
The installation directory still contains files.$(2)\
Do you want to view its contents?\
`
LangString MB_RESTART_FAILED ${LANG_ENGLISH} `\
${PRODUCT_NAME} Setuo failed to restart unelevated.$(2)\
Click OK to exit.\
`
LangString MB_UNSUPPORTED_OS ${LANG_ENGLISH} `\
This version of ${PRODUCT_NAME} requires a 64-bit$(1)\
version of Windows 10 21H2 or later.\
`
LangString MB_USER_ABORT ${LANG_ENGLISH} `\
The installation of ${PRODUCT_NAME} was aborted.$(2)\
Click OK to exit Setup.\
`

### File Version Information - Should not translate the first strings

VIAddVersionKey /LANG=${LANG_ENGLISH} 'Comments' `Built with NSIS ${NSIS_VERSION}`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'CompanyName' `${COMPANY_NAME}`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'FileDescription' `${PRODUCT_NAME} ${ARCH} Setup`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'FileVersion' `${VERSION}`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'InternalName' `${INSTALLER_NAME}`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'LegalCopyright' '${COPYRIGHT}'
VIAddVersionKey /LANG=${LANG_ENGLISH} 'LegalTrademarks' '${LICENSE}'
VIAddVersionKey /LANG=${LANG_ENGLISH} 'OriginalFilename' `${INSTALLER_NAME}.exe`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'ProductName' `${PRODUCT_NAME}`
VIAddVersionKey /LANG=${LANG_ENGLISH} 'ProductVersion' `${VERSION}`
