# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# encoding: iso-8859-1
#
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

# NSIS installer script. Uses NsisMultiUser plugin and contains portions of
# its demo code, copyright 2017 Richard Drizin, Alex Mitev.

# Includes modified graphics from the NSIS distribution.

# Requires:
# - NsisMultiUser plugin        https://github.com/Drizin/NsisMultiUser
# - UAC plugin                  https://nsis.sourceforge.net/UAC_plug-in
# - StdUtils plugin             https://nsis.sourceforge.io/StdUtils_plug-in


; Installer Attributes
Unicode true
XPStyle on
ManifestSupportedOS all
SetDatablockOptimize on
SetCompressor /SOLID /FINAL lzma
SetCompressorDictSize 32
CRCCheck on
AllowSkipFiles off
SetOverwrite on
ShowInstDetails hide
ShowUninstDetails hide

!addplugindir /x86-unicode ".\plugins\x86-unicode"
!addincludedir ".\include"

!include MUI2.nsh
!include NsisMultiUser.nsh
!include StdUtils.nsh

; Installer defines
!define PRODUCT_NAME "qutebrowser" ; name of the application as displayed to the user
!define PROGEXE "qutebrowser.exe" ; main application filename
!define COMPANY_NAME "qutebrowser.org" ; company, used for registry tree hierarchy
!define COPYRIGHT "© 2014-2018 Florian Bruhin (The Compiler)"
!define TM "qutebrowser is free software under the GNU General Public License"
!define URL_ABOUT "https://qutebrowser.org/"
!define URL_UPDATE "https://qutebrowser.org/doc/install.html"
!define HELP_LINK "https://qutebrowser.org/doc/help/"
!define CONTACT "mail@qutebrowser.org"
!define COMMENTS "A keyboard-driven, vim-like browser based on PyQt5."
!define LANGID "1033" ; U.S. English
!define MIN_WIN_VER "8"
!define SETUP_MUTEX "${PRODUCT_NAME} Setup Mutex" ; do not change this between program versions!
!define APP_MUTEX "${PRODUCT_NAME} App Mutex" ; do not change this between program versions!
!define REG_UN "Software\Microsoft\Windows\CurrentVersion\Uninstall"
!define SETTINGS_REG_KEY "${REG_UN}\${PRODUCT_NAME}"
!define CONFIG_DIR "$APPDATA\${PRODUCT_NAME}"
!define CACHE_DIR "$LOCALAPPDATA\${PRODUCT_NAME}"
!define LICENSE_FILE ".\..\..\LICENSE"
!define MUI_ICON ".\graphics\install.ico"
!define MUI_UNICON ".\graphics\uninstall.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP ".\graphics\wizard.bmp"
; The old MSI installers had a different Product Code on every release by mistake
!define MSI_COUNT 24
!define MSI32_010 "{50691080-E51F-4F1A-AEEA-ACA8C64DB98B}"
!define MSI32_011 "{B6FE0FC1-3754-4FF6-A5E5-A305B1EDC8CB}"
!define MSI32_012 "{B1341894-8D82-40C6-B0D0-A5ECEFB997BE}"
!define MSI32_013 "{22EEF3C7-4D72-4F7E-B35B-1F2A22B5E64A}"
!define MSI32_014 "{29C7D770-EBFE-465A-8354-C6A4EA3D8BAF}"
!define MSI32_020 "{061B339B-ABBC-4D89-BE0D-A843FEA48DA7}"
!define MSI32_021 "{0228BB7C-8D7C-4763-A1C6-AAE0B1902AF9}"
!define MSI32_030 "{F514C234-DB31-4158-9D96-53412B431F81}"
!define MSI32_040 "{895E71DC-41D6-4FC3-A0F8-2EC5FE19ACB8}"
!define MSI32_041 "{66F9576D-0DB5-475D-9C25-E0511580C897}"
!define MSI32_050 "{EDB54F4D-7A00-47AE-9808-E59FF5E79136}"
!define MSI32_051 "{EEF03487-BC9F-4EA4-A5A1-E9CF5F9E1FB6}"
!define MSI32_060 "{F9FECA24-95DA-4E46-83E3-A805E5B1CE06}"
!define MSI32_061 "{F1A0F4B9-CCA3-4B07-8ADB-16BC81530440}"
!define MSI32_062 "{43F5E4C5-FF96-4676-B027-5AD63D3871AB}"
!define MSI32_070 "{558FF39C-CA5F-4E2A-87D2-90963FCBC424}"
!define MSI32_080 "{9DF540E2-4F8C-46A4-A27F-43BD0558CC42}"
!define MSI32_081 "{EA0FB6B1-83AF-4F16-8B89-645B587D90FD}"
!define MSI32_082 "{F849A0B2-301C-435D-9CC0-9651938FCA6F}"
!define MSI32_084 "{9331D947-AC86-4542-A755-A833429C6E69}"
!define MSI32_090 "{AD967987-7777-4095-A03A-3F2EE8968D9E}"
!define MSI32_091 "{87F05B8A-2238-4D86-82BB-EC8B4CE97E78}"
!define MSI32_100 "{07B85A0B-D025-4B4B-B46D-BC9B02912835}"
!define MSI32_101 "{9F05D9E4-D049-445E-A489-A7DC0256C774}"
!define MSI64_010 "{A8191862-28A7-4BB0-9532-49AD5CFFFE66}"
!define MSI64_011 "{1C476CC1-A171-48B7-A883-0F00F4D301D3}"
!define MSI64_012 "{ADA727AC-9DDD-4F03-93B7-BAFE950757BE}"
!define MSI64_013 "{64949BFF-287A-4C16-A5F3-84A38A6703F1}"
!define MSI64_014 "{63F22761-D886-4FDD-93F4-7543265E9FF7}"
!define MSI64_020 "{80BE09C6-347F-4121-98D3-1E4363C3CE6B}"
!define MSI64_021 "{2D86F472-DD52-40A1-8FE0-90550D674554}"
!define MSI64_030 "{53DED10D-C609-406F-959E-C1B52A518561}"
!define MSI64_040 "{B9535FDF-7A9E-4AED-BA1E-BEE5FFCBC311}"
!define MSI64_041 "{DAE1309A-FE7D-46E5-B488-B437CC509DF9}"
!define MSI64_050 "{DC9ECE64-F8E5-4BCB-BCFF-BE4ADCEF2655}"
!define MSI64_051 "{26AED286-23BD-49FF-BD9C-7C0DC4467BD7}"
!define MSI64_060 "{3035744D-2390-4D5E-ACAD-905E72B9EBEC}"
!define MSI64_061 "{0223F48F-93A8-4985-BCFF-328E5A9D97D5}"
!define MSI64_062 "{95835A82-A9C2-4924-87DF-E03D910E3400}"
!define MSI64_070 "{61D1AC75-7ECD-45FF-B42B-454C056DB178}"
!define MSI64_080 "{92D1C65C-1338-4B11-B515-6BD5B1FF92D9}"
!define MSI64_081 "{AF7AC009-FB82-48F6-9439-6E46AEB60DBF}"
!define MSI64_082 "{CC316D68-5742-4C2B-98EC-4ADF06A19B84}"
!define MSI64_084 "{633F41F9-FE9B-42D1-9CC4-718CBD01EE11}"
!define MSI64_090 "{5E3E7404-D6D7-4FF1-846A-F9BBFE2F841A}"
!define MSI64_091 "{3190D3F6-7B24-47DC-88E7-99280905FACF}"
!define MSI64_100 "{7AA6530C-3812-4DC5-9A30-E762BBDDF55E}"
!define MSI64_101 "{B0104B85-8229-49FB-8606-275A90ACC024}"

; Set PLATFORM - default x64
!ifdef X86
  !define PLATFORM "Win32"
  !define ARCH "x86"
  !define SUFFIX "win32"
!else
  !define PLATFORM "Win64"
  !define ARCH "x64"
  !define SUFFIX "amd64"
!endif

; If not defined, get VERSION from PROGEXE. Set DIST_DIR accordingly.
!ifndef VERSION
  !define /ifndef DIST_DIR ".\..\..\dist\${PRODUCT_NAME}-${ARCH}"
  !getdllversion "${DIST_DIR}\${PROGEXE}" expv_
  !define VERSION "${expv_1}.${expv_2}.${expv_3}"
!else
  !define /ifndef DIST_DIR ".\..\..\dist\${PRODUCT_NAME}-${VERSION}-${ARCH}"
!endif

; Pack the exe header with upx if UPX is defined.
!ifdef UPX
  !packhdr "$%TEMP%\exehead.tmp" '"upx" "--ultra-brute" "$%TEMP%\exehead.tmp"'
!endif

!define MULTIUSER_INSTALLMODE_ALLOW_ELEVATION_IF_SILENT 1

; Version Information
VIFileVersion "${VERSION}.0"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=${LANGID} "Comments" "Built with NSIS ${NSIS_VERSION}"
VIAddVersionKey /LANG=${LANGID} "CompanyName" "${COMPANY_NAME}"
VIAddVersionKey /LANG=${LANGID} "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=${LANGID} "InternalName" "${PRODUCT_NAME}-${VERSION}-${SUFFIX}"
VIAddVersionKey /LANG=${LANGID} "LegalTrademarks" "${TM}"
VIAddVersionKey /LANG=${LANGID} "LegalCopyright" "${COPYRIGHT}"
VIAddVersionKey /LANG=${LANGID} "FileDescription" "${PRODUCT_NAME} ${ARCH} Setup"
VIAddVersionKey /LANG=${LANGID} "OriginalFilename" "${PRODUCT_NAME}-${VERSION}-${SUFFIX}.exe"
VIAddVersionKey /LANG=${LANGID} "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=${LANGID} "ProductVersion" "${VERSION}"

; Final Attributes
Name "${PRODUCT_NAME}"
BrandingText "${PRODUCT_NAME} v${VERSION} Installer (${ARCH})"
OutFile "${DIST_DIR}\..\${PRODUCT_NAME}-${VERSION}-${SUFFIX}.exe"

; installer/uninstaller pages and actions
!include "Utils.nsh"
!include "install_pages.nsh"
; remove next line if you're using signing after the uninstaller is extracted from the initially compiled setup
!include "uninstall_pages.nsh"
!include "install.nsh"
; remove next line if you're using signing after the uninstaller is extracted from the initially compiled setup
!include "uninstall.nsh"
