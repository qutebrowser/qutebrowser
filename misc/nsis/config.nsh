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


!ifdef VERBOSE
    !verbose 4
!endif

### Defines

; Basic information
!define SETUP_GUID '{D9357122-593C-48F3-B281-01CA55F83947}'
!define PRODUCT_NAME 'qutebrowser'
!define PROGEXE 'qutebrowser.exe'
!define COMPANY_NAME 'qutebrowser.org'
!define CONTACT 'mail@qutebrowser.org'
!define COPYRIGHT 'Copyright 2014-2022 Florian Bruhin (The Compiler)'
!define LICENSE `qutebrowser is free software under the GNU General Public License`
!define URL_INFO_ABOUT 'https://qutebrowser.org/'
!define URL_UPDATE_INFO 'https://qutebrowser.org/doc/install.html'
!define URL_HELP_LINK 'https://qutebrowser.org/doc/help/'

!define MIN_WIN_VER 8

; Dark colors
!define /ifndef DARK_BGCOLOR_0 0x191919
!define /ifndef DARK_BGCOLOR_1 0x202020
!define /ifndef DARK_BGCOLOR_2 0x2B2B2B
!define /ifndef DARK_FGCOLOR 0xFFFFFF

; Registry keys
!define HTML_HANDLE '${PRODUCT_NAME}HTML'
!define REG_CLS 'Software\Classes'
!define REG_SMI 'Software\Clients\StartMenuInternet\${PRODUCT_NAME}'
!define REG_EXT 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts'
!define REG_URL 'Software\Microsoft\Windows\Shell\Associations\UrlAssociations'
!define REG_UNINSTALL 'Software\Microsoft\Windows\CurrentVersion\Uninstall'
!define REG_APPS 'Software\RegisteredApplications'
!define REG_MSI_COMPONENTS 'Software\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Components'

; Old MSI Product Codes / Registry keys
;32-Bit
!define MSI32_010_GUID '50691080-E51F-4F1A-AEEA-ACA8C64DB98B'
!define MSI32_010_PATH_KEY '1FAA6D98863076E42B98F3172CEEAD3F'
!define MSI32_010_PATH_STR '08019605F15EA1F4EAAECA8A6CD49BB8'
!define MSI32_011_GUID 'B6FE0FC1-3754-4FF6-A5E5-A305B1EDC8CB'
!define MSI32_011_PATH_KEY '0B5AD7D36557BF74B96BC2E38744E255'
!define MSI32_011_PATH_STR '1CF0EF6B45736FF45A5E3A501BDE8CBC'
!define MSI32_012_GUID 'B1341894-8D82-40C6-B0D0-A5ECEFB997BE'
!define MSI32_012_PATH_KEY '8ED11B2C057338A45906F47AE99857DF'
!define MSI32_012_PATH_STR '4981431B28D86C040B0D5ACEFE9B79EB'
!define MSI32_013_GUID '22EEF3C7-4D72-4F7E-B35B-1F2A22B5E64A'
!define MSI32_013_PATH_KEY '36A89139A17BD4E4FAA5FA521304FA52'
!define MSI32_013_PATH_STR '7C3FEE2227D4E7F43BB5F1A2225B6EA4'
!define MSI32_014_GUID '29C7D770-EBFE-465A-8354-C6A4EA3D8BAF'
!define MSI32_014_PATH_KEY '81EB639AA5A79284DB14B909CFF46E38'
!define MSI32_014_PATH_STR '077D7C92EFBEA56438456C4AAED3B8FA'
!define MSI32_020_GUID '061B339B-ABBC-4D89-BE0D-A843FEA48DA7'
!define MSI32_020_PATH_KEY 'ED5A4BE170008BC4A8F764C5F6C1A501'
!define MSI32_020_PATH_STR 'B933B160CBBA98D4EBD08A34EF4AD87A'
!define MSI32_021_GUID '0228BB7C-8D7C-4763-A1C6-AAE0B1902AF9'
!define MSI32_021_PATH_KEY '8877BC675FCC0A940A5A421F8EB2895F'
!define MSI32_021_PATH_STR 'C7BB8220C7D836741A6CAA0E1B09A29F'
!define MSI32_030_GUID 'F514C234-DB31-4158-9D96-53412B431F81'
!define MSI32_030_PATH_KEY '960D9BC5DB5A7EC4EBF86FBE2D24F8E2'
!define MSI32_030_PATH_STR '432C415F13BD8514D9693514B234F118'
!define MSI32_040_GUID '895E71DC-41D6-4FC3-A0F8-2EC5FE19ACB8'
!define MSI32_040_PATH_KEY 'E3BFECC7FB6926C418480EC1D995297E'
!define MSI32_040_PATH_STR 'CD17E5986D143CF40A8FE25CEF91CA8B'
!define MSI32_041_GUID '66F9576D-0DB5-475D-9C25-E0511580C897'
!define MSI32_041_PATH_KEY '2788C6B6710E26A48B4186ABAE014F53'
!define MSI32_041_PATH_STR 'D6759F665BD0D574C9520E1551088C79'
!define MSI32_050_GUID 'EDB54F4D-7A00-47AE-9808-E59FF5E79136'
!define MSI32_050_PATH_KEY '432F2806E44312240AF02987439A3323'
!define MSI32_050_PATH_STR 'D4F45BDE00A7EA7489805EF95F7E1963'
!define MSI32_051_GUID 'EEF03487-BC9F-4EA4-A5A1-E9CF5F9E1FB6'
!define MSI32_051_PATH_KEY '66AEC89BAF2EADC4EB3B2FAC7CFA905A'
!define MSI32_051_PATH_STR '78430FEEF9CB4AE45A1A9EFCF5E9F16B'
!define MSI32_060_GUID 'F9FECA24-95DA-4E46-83E3-A805E5B1CE06'
!define MSI32_060_PATH_KEY '56B5CF1DEE839624F98B6B6157D0DCF2'
!define MSI32_060_PATH_STR '42ACEF9FAD5964E4383E8A505E1BEC60'
!define MSI32_061_GUID 'F1A0F4B9-CCA3-4B07-8ADB-16BC81530440'
!define MSI32_061_PATH_KEY 'F52DC941CA5202146A91F7416F6A1C17'
!define MSI32_061_PATH_STR '9B4F0A1F3ACC70B4A8BD61CB18354004'
!define MSI32_062_GUID '43F5E4C5-FF96-4676-B027-5AD63D3871AB'
!define MSI32_062_PATH_KEY 'A7FFD7CA0B2751D4B94EA902812308FE'
!define MSI32_062_PATH_STR '5C4E5F3469FF67640B72A56DD38317BA'
!define MSI32_070_GUID '558FF39C-CA5F-4E2A-87D2-90963FCBC424'
!define MSI32_070_PATH_KEY '282848F0F17D1BE47BC558CC6A52298E'
!define MSI32_070_PATH_STR 'C93FF855F5ACA2E4782D0969F3BC4C42'
!define MSI32_080_GUID '9DF540E2-4F8C-46A4-A27F-43BD0558CC42'
!define MSI32_080_PATH_KEY 'DED12D34A7986C847BCF99D76E488D1F'
!define MSI32_080_PATH_STR '2E045FD9C8F44A642AF734DB5085CC24'
!define MSI32_081_GUID 'EA0FB6B1-83AF-4F16-8B89-645B587D90FD'
!define MSI32_081_PATH_KEY 'D600001DAE0F77847803C4A940DFAE52'
!define MSI32_081_PATH_STR '1B6BF0AEFA3861F4B89846B585D709DF'
!define MSI32_082_GUID 'F849A0B2-301C-435D-9CC0-9651938FCA6F'
!define MSI32_082_PATH_KEY '7600031B36E5B644A8BC12F91B922E29'
!define MSI32_082_PATH_STR '2B0A948FC103D534C90C691539F8ACF6'
!define MSI32_084_GUID '9331D947-AC86-4542-A755-A833429C6E69'
!define MSI32_084_PATH_KEY '9CCAE40D4467FEF4AAE71E512F542CAB'
!define MSI32_084_PATH_STR '749D133968CA24547A558A3324C9E696'
!define MSI32_090_GUID 'AD967987-7777-4095-A03A-3F2EE8968D9E'
!define MSI32_090_PATH_KEY '58BD217699835FC45A0EF93AE4776CF8'
!define MSI32_090_PATH_STR '789769DA777759040AA3F3E28E69D8E9'
!define MSI32_091_GUID '87F05B8A-2238-4D86-82BB-EC8B4CE97E78'
!define MSI32_091_PATH_KEY '13FD54EBE0D66264391D932822E85DC1'
!define MSI32_091_PATH_STR 'A8B50F78832268D428BBCEB8C49EE787'
!define MSI32_100_GUID '07B85A0B-D025-4B4B-B46D-BC9B02912835'
!define MSI32_100_PATH_KEY '7D3F6C619E7243C41A3D313F1D527127'
!define MSI32_100_PATH_STR 'B0A58B70520DB4B44BD6CBB920198253'
!define MSI32_101_GUID '9F05D9E4-D049-445E-A489-A7DC0256C774'
!define MSI32_101_PATH_KEY 'A3B9AA82AC33AE44E9575D3C34F26222'
!define MSI32_101_PATH_STR '4E9D50F9940DE5444A987ACD20657C47'
; 64-Bit
!define MSI64_010_GUID 'A8191862-28A7-4BB0-9532-49AD5CFFFE66'
!define MSI64_010_PATH_KEY '0201C34ADF4D72C438DCE190679E0688'
!define MSI64_010_PATH_STR '2681918A7A820BB4592394DAC5FFEF66'
!define MSI64_011_GUID '1C476CC1-A171-48B7-A883-0F00F4D301D3'
!define MSI64_011_PATH_KEY '6112026ECEFF8B749B956E60C9DFBB83'
!define MSI64_011_PATH_STR '1CC674C1171A7B848A38F0004F3D103D'
!define MSI64_012_GUID 'ADA727AC-9DDD-4F03-93B7-BAFE950757BE'
!define MSI64_012_PATH_KEY '41F734ED8759DF041A1E1C3D8CB25CBD'
!define MSI64_012_PATH_STR 'CA727ADADDD930F4397BABEF597075EB'
!define MSI64_013_GUID '64949BFF-287A-4C16-A5F3-84A38A6703F1'
!define MSI64_013_PATH_KEY 'BDED843E2F82F0D4C9D5B44DECD09615'
!define MSI64_013_PATH_STR 'FFB94946A78261C45A3F483AA876301F'
!define MSI64_014_GUID '63F22761-D886-4FDD-93F4-7543265E9FF7'
!define MSI64_014_PATH_KEY 'AE32CEF9331C5F74A9EC09D0F09A3A8D'
!define MSI64_014_PATH_STR '16722F36688DDDF4394F573462E5F97F'
!define MSI64_020_GUID '80BE09C6-347F-4121-98D3-1E4363C3CE6B'
!define MSI64_020_PATH_KEY '32EE6F0D0D78954419FA1B4E96102BD4'
!define MSI64_020_PATH_STR '6C90EB08F7431214893DE134363CECB6'
!define MSI64_021_GUID '2D86F472-DD52-40A1-8FE0-90550D674554'
!define MSI64_021_PATH_KEY '676C5F930985867468B79CA167D7674F'
!define MSI64_021_PATH_STR '274F68D225DD1A04F80E0955D0765445'
!define MSI64_030_GUID '53DED10D-C609-406F-959E-C1B52A518561'
!define MSI64_030_PATH_KEY '6509CE9AB4D293B4DA4FAA8E160EF483'
!define MSI64_030_PATH_STR 'D01DED35906CF60459E91C5BA2155816'
!define MSI64_040_GUID 'B9535FDF-7A9E-4AED-BA1E-BEE5FFCBC311'
!define MSI64_040_PATH_KEY 'EFA601D9A5C4749498BD9CB4659B4C64'
!define MSI64_040_PATH_STR 'FDF5359BE9A7DEA4ABE1EB5EFFBC3C11'
!define MSI64_041_GUID 'DAE1309A-FE7D-46E5-B488-B437CC509DF9'
!define MSI64_041_PATH_KEY 'E7082D5AFADF1074E86FDE1D59CA504D'
!define MSI64_041_PATH_STR 'A9031EADD7EF5E644B884B73CC05D99F'
!define MSI64_050_GUID 'DC9ECE64-F8E5-4BCB-BCFF-BE4ADCEF2655'
!define MSI64_050_PATH_KEY 'D78867B89E7588A4992055CC26EF8245'
!define MSI64_050_PATH_STR '46ECE9CD5E8FBCB4CBFFEBA4CDFE6255'
!define MSI64_051_GUID '26AED286-23BD-49FF-BD9C-7C0DC4467BD7'
!define MSI64_051_PATH_KEY '27EF38A5E49F1184FAA8F81C574C19CC'
!define MSI64_051_PATH_STR '682DEA62DB32FF94DBC9C7D04C64B77D'
!define MSI64_060_GUID '3035744D-2390-4D5E-ACAD-905E72B9EBEC'
!define MSI64_060_PATH_KEY '581F37CF6C977134E963BFB9764CC660'
!define MSI64_060_PATH_STR 'D44753030932E5D4CADA09E5279BBECE'
!define MSI64_061_GUID '0223F48F-93A8-4985-BCFF-328E5A9D97D5'
!define MSI64_061_PATH_KEY 'F26B8AD31FB1C614684226314583509F'
!define MSI64_061_PATH_STR 'F84F32208A395894CBFF23E8A5D9795D'
!define MSI64_062_GUID '95835A82-A9C2-4924-87DF-E03D910E3400'
!define MSI64_062_PATH_KEY '0B0E85358E720C84D827BD7261221E4E'
!define MSI64_062_PATH_STR '28A538592C9A429478FD0ED319E04300'
!define MSI64_070_GUID '61D1AC75-7ECD-45FF-B42B-454C056DB178'
!define MSI64_070_PATH_KEY '2999E31DAC300104AB919C5E719BA08D'
!define MSI64_070_PATH_STR '57CA1D16DCE7FF544BB254C450D61B87'
!define MSI64_080_GUID '92D1C65C-1338-4B11-B515-6BD5B1FF92D9'
!define MSI64_080_PATH_KEY '76D1A06F371D11A4C93042BB8A8E4036'
!define MSI64_080_PATH_STR 'C56C1D29833111B45B51B65D1BFF299D'
!define MSI64_081_GUID 'AF7AC009-FB82-48F6-9439-6E46AEB60DBF'
!define MSI64_081_PATH_KEY '1C2D21096C7508F4592F2A76C3A56FC1'
!define MSI64_081_PATH_STR '900CA7FA28BF6F844993E664EA6BD0FB'
!define MSI64_082_GUID 'CC316D68-5742-4C2B-98EC-4ADF06A19B84'
!define MSI64_082_PATH_KEY 'A3E836CE390215A448E5D694136F8B3C'
!define MSI64_082_PATH_STR '86D613CC2475B2C489CEA4FD601AB948'
!define MSI64_084_GUID '633F41F9-FE9B-42D1-9CC4-718CBD01EE11'
!define MSI64_084_PATH_KEY 'F42DEC26B920F0E4581924AD4F44BF13'
!define MSI64_084_PATH_STR '9F14F336B9EF1D24C94C17C8DB10EE11'
!define MSI64_090_GUID '5E3E7404-D6D7-4FF1-846A-F9BBFE2F841A'
!define MSI64_090_PATH_KEY '859F4CE731C663141A34A2905A27FC83'
!define MSI64_090_PATH_STR '4047E3E57D6D1FF448A69FBBEFF248A1'
!define MSI64_091_GUID '3190D3F6-7B24-47DC-88E7-99280905FACF'
!define MSI64_091_PATH_KEY '17BBF14B1FA2A114499C3C105171EAC5'
!define MSI64_091_PATH_STR '6F3D091342B7CD74887E99829050AFFC'
!define MSI64_100_GUID '7AA6530C-3812-4DC5-9A30-E762BBDDF55E'
!define MSI64_100_PATH_KEY 'F3F51DED90F46D34DB9793D7ADC13D4E'
!define MSI64_100_PATH_STR 'C0356AA721835CD4A9037E26BBDD5FE5'
!define MSI64_101_GUID 'B0104B85-8229-49FB-8606-275A90ACC024'
!define MSI64_101_PATH_KEY '905C17AEE1023BD48AD248A079A03039'
!define MSI64_101_PATH_STR '58B4010B9228BF94686072A509CA0C42'

; NSIS v1 git-commit-id version dates
!define GIT_DATE_0110 '2017-07-04'
!define GIT_VER_0110 '0.11.0'
!define GIT_DATE_0111 '2017-10-09'
!define GIT_VER_0111 '0.11.1'
!define GIT_DATE_100 '2017-10-12'
!define GIT_VER_100 '1.0.0'
!define GIT_DATE_101 '2017-10-12'
!define GIT_VER_101 '1.0.1'
!define GIT_DATE_102 '2017-10-17'
!define GIT_VER_102 '1.0.2'
!define GIT_DATE_103 '2017-11-04'
!define GIT_VER_103 '1.0.3'
!define GIT_DATE_104 '2017-11-04'
!define GIT_VER_104 '1.0.4'
!define GIT_DATE_110 '2018-01-15'
!define GIT_VER_110 '1.1.0'
!define GIT_DATE_111 '2018-01-20'
!define GIT_VER_111 '1.1.1'
!define GIT_DATE_112 '2018-03-01'
!define GIT_VER_112 '1.1.2'
!define GIT_DATE_120 '2018-03-09'
!define GIT_VER_120 '1.2.0'
!define GIT_DATE_121 '2018-03-14'
!define GIT_VER_121 '1.2.1'
!define GIT_DATE_130 '2018-05-03'
!define GIT_VER_130 '1.3.0'
!define GIT_DATE_131 '2018-05-29'
!define GIT_VER_131 '1.3.1'
!define GIT_DATE_132 '2018-06-10'
!define GIT_VER_132 '1.3.2'
!define GIT_DATE_133 '2018-06-21'
!define GIT_VER_133 '1.3.3'
!define GIT_DATE_140 '2018-07-03'
!define GIT_VER_140 '1.4.0'
!define GIT_DATE_141 '2018-07-11'
!define GIT_VER_141 '1.4.1'
!define GIT_DATE_142 '2018-09-02'
!define GIT_VER_142 '1.4.2'
!define GIT_DATE_150 '2018-10-03'
!define GIT_VER_150 '1.5.0'
!define GIT_DATE_151 '2018-10-10'
!define GIT_VER_151 '1.5.1'
!define GIT_DATE_152 '2018-10-26'
!define GIT_VER_152 '1.5.2'
!define GIT_DATE_160 '2019-02-25'
!define GIT_VER_160 '1.6.0'
!define GIT_DATE_161 '2019-03-20'
!define GIT_VER_161 '1.6.1'
!define GIT_DATE_162 '2019-05-06'
!define GIT_VER_162 '1.6.2'
!define GIT_DATE_163 '2019-06-18'
!define GIT_VER_163 '1.6.3'

### Configurable defines

; The makensis parameters for the second build
!define MAKENSIS_D

; Project root path
!ifdef PRJ_ROOT
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"PRJ_ROOT=${PRJ_ROOT}"'
    !if '${PRJ_ROOT}' == ''
        !define /redef PRJ_ROOT '.'
    !endif
!else
    !define PRJ_ROOT '${__FILEDIR__}\..\..'
!endif

; Parent directory of releases
!ifdef DIST_PARENT
    !ifdef DIST_DIR
        !error `Both "DIST_PARENT" and "DIST_DIR" cannot be defined.`
    !endif
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"DIST_PARENT=${DIST_PARENT}"'
    !if '${DIST_PARENT}' == ''
        !define /redef DIST_PARENT '.'
    !endif
!else
    !define DIST_PARENT '${PRJ_ROOT}\dist'
!endif

!ifdef ARCH ; set the targeted architecture defined in ARCH
    !if '${ARCH}' == 'x64'
        !define /redef ARCH 'x64' ; make sure "x64" is in lowercase
        !define SUFFIX 'amd64'
    !else if '${ARCH}' == 'x86'
        !define /redef ARCH 'x86' ; make sure "x86" is in lowercase
        !define SUFFIX 'win32'
    !else
        !error '"ARCH" must be either "x86" or "x64".'
    !endif
!else ; if ARCH isn't defined, set to build both architectures
    !ifdef DIST_DIR
        !error 'DIST_DIR requires ARCH to be set.'
    !endif
    !define ARCH 'x64'
    !define SUFFIX 'amd64'
    !define DUAL_BUILD
    !define /redef MAKENSIS_D `/D"ARCH=x86" /D"NO_DOWNLOADS" /D"KEEP_SCRATCHDIR" ${MAKENSIS_D}`
!endif

; Version number and source path of release
!ifdef VERSION
    !if '${VERSION}' == ''
        !error '"VERSION" cannot be empty.'
    !endif
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"VERSION=${VERSION}"'
!else ifndef DIST_DIR
    !searchparse /file '${PRJ_ROOT}\qutebrowser\__init__.py' `__version__ = "` VER_MAJOR `.` VER_MINOR `.` VER_PATCH `"`
    !define VERSION '${VER_MAJOR}.${VER_MINOR}.${VER_PATCH}'
!endif
!define /ifndef DIST_DIR '${DIST_PARENT}\${PRODUCT_NAME}-${VERSION}-${ARCH}'

!getdllversion '${DIST_DIR}\${PROGEXE}' expv_ ; get the version from executable
!ifdef VERSION ; check if VERSION matches the value from the executable
    !if '${VERSION}' != '${expv_1}.${expv_2}.${expv_3}'
        !error 'The file version does not match the defined value.'
    !endif
!else ; if not set, define VERSION with the value from the executable
    !define VERSION '${expv_1}.${expv_2}.${expv_3}'
!endif

; Installer output directory
!ifdef OUTDIR
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"OUTDIR=${OUTDIR}"'
    !if '${OUTDIR}' == ''
        !define /redef OUTDIR '.'
    !endif
!else
    !define OUTDIR '${DIST_PARENT}'
!endif

; Scratch directory
!ifdef SCRATCHDIR
    !if '${SCRATCHDIR}' == ''
        !error '"SCRATCHDIR" cannot be empty.'
    !endif
!else
    !tempfile SCRATCHDIR
    !delfile '${SCRATCHDIR}'
!endif
!define /redef MAKENSIS_D '${MAKENSIS_D} /D"SCRATCHDIR=${SCRATCHDIR}"'

; Exe headers packer tool and parameters
!ifdef PACK
    !searchreplace DPACK `${PACK}` `"` `"""`
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"PACK=${DPACK}"'
    !undef DPACK
    !if '${PACK}' == ''
        !define /redef PACK 'upx --ultra-brute "%1"'
    !endif
!endif

; Installer signing command and parameters
!ifdef SIGN
    !searchreplace DSIGN `${SIGN}` `"` `"""`
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"SIGN=${DSIGN}"'
    !undef DSIGN
    !if '${SIGN}' == ''
        !define /redef SIGN 'signtool.exe sign /a /tr http://timestamp.digicert.com /td sha256 /fd sha256 "%1"'
    !endif
!endif

; WiX binaries
!ifdef MSI
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"MSI=${MSI}"'
    !if '${MSI}' == ''
        !define CANDLE 'candle.exe'
        !define LIGHT 'light.exe'
    !else
        !searchparse /noerrors '${MSI}' 'http://' DOWNLOAD_WIX
        !searchparse /noerrors '${MSI}' 'https://' DOWNLOAD_WIX
        !ifdef DOWNLOAD_WIX
            !if '${DOWNLOAD_WIX}' == ''
                !define /redef MSI 'https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311-binaries.zip'
            !endif
            !ifdef NSIS_WIN32_MAKENSIS
                !define CANDLE '"${SCRATCHDIR}\wix3\candle.exe"'
                !define LIGHT '"${SCRATCHDIR}\wix3\light.exe"'
            !else
                !define CANDLE 'wine "${SCRATCHDIR}/wix3/candle.exe"'
                !define LIGHT 'wine "${SCRATCHDIR}/wix3/light.exe"'
            !endif
        !else
            !ifdef NSIS_WIN32_MAKENSIS
                !define CANDLE '"${MSI}\candle.exe"'
                !define LIGHT '"${MSI}\light.exe"'
            !else
                !define CANDLE 'wine "${MSI}\candle.exe"'
                !define LIGHT 'wine "${MSI}\light.exe"'
            !endif
        !endif
    !endif
!endif

; Installer icon
!ifdef INST_ICON
    !if '${INST_ICON}' == ''
        !error `"INST_ICON" cannot be empty.`
    !endif
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"INST_ICON=${INST_ICON}"'
!else
    !define INST_ICON '${PRJ_ROOT}\qutebrowser\icons\qutebrowser.ico'
!endif

; Uninstaler icon
!ifdef UNINST_ICON
    !if '${UNINST_ICON}' == ''
        !error `"UNINST_ICON" cannot be empty.`
    !endif
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"UNINST_ICON=${UNINST_ICON}"'
!else
    !define UNINST_ICON '${NSISDIR}\Contrib\Graphics\Icons\nsis3-uninstall.ico'
!endif

; Setup Welcome/Finish image
!ifdef WIZARD_IMAGE
    !if '${WIZARD_IMAGE}' == ''
        !error `"WIZARD_IMAGE" cannot be empty.`
    !endif
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"WIZARD_IMAGE=${WIZARD_IMAGE}"'
!else
    !define WIZARD_IMAGE '${__FILEDIR__}\setup.bmp'
!endif

; Application mutex object name
!ifdef APP_MUTEX
    !if '${APP_MUTEX}' == ''
        !error '"APP_MUTEX" cannot be empty.'
    !else
        !define /redef MAKENSIS_D '${MAKENSIS_D} /D"APP_MUTEX=${APP_MUTEX}"'
    !endif
!endif

!ifdef DEBUG
    !define /redef MAKENSIS_D '${MAKENSIS_D} /D"DEBUG=${DEBUG}"'
    !if '${DEBUG}' == ''
        !define /redef DEBUG '${OUTDIR}'
    !endif
!endif

; License file
!define LICENSE_FILE '${PRJ_ROOT}\LICENSE'

; Installer name
!define INSTALLER_NAME '${PRODUCT_NAME}-${VERSION}-${SUFFIX}'

; Uninstaller file name
!define UNINSTALL_FILENAME 'uninstall.exe'

!define FILE_MACROS_NSH '${INSTALLER_NAME}.nsh'

!define DEFAULT_LOG_FILENAME '${INSTALLER_NAME}.log'


### Attributes

Unicode true
XPStyle on
ManifestSupportedOS all
SetDatablockOptimize on
SetCompressor /SOLID /FINAL lzma
SetCompressorDictSize 32
CRCCheck on
AllowSkipFiles off
SetOverwrite try
ShowInstDetails hide
ShowUninstDetails hide
RequestExecutionLevel user
Name '${PRODUCT_NAME}'
BrandingText '${PRODUCT_NAME} v${VERSION} ${ARCH} Setup'
VIFileVersion '${VERSION}.0'
VIProductVersion '${VERSION}.0'
OutFile '${OUTDIR}\${INSTALLER_NAME}.exe'

### Prepare build macro

!macro PREPARE_BUILD_ENVIRONMENT
    !if ${NSIS_PACKEDVERSION} < 0x3008000
        !error 'NSIS v3.08 or higher is required.'
    !endif

    !system `${SHELL_PREPARE_SCRATCHDIR}` = 0
    !addincludedir '${SCRATCHDIR}'
    !addplugindir /x86-unicode '${SCRATCHDIR}'

    !ifdef DUAL_BUILD
        !makensis `${MAKENSIS_D} "${__FILE__}"` = 0
    !endif

    ; Pack the exe header if PACK is defined
    !ifdef PACK
        !searchreplace PACK '${PACK}' '%1' '${SCRATCHDIR}\exehead.tmp'
        !packhdr '${SCRATCHDIR}\exehead.tmp' '${PACK}'
    !endif

    !ifdef SIGN
        !finalize `${SIGN}` = 0
        !uninstfinalize '${SIGN}' = 0
    !endif

    !ifdef MSI
        !finalize `${SHELL_BUILD_MSI}` = 0
        !ifdef SIGN
            !searchreplace SIGN_MSI '${SIGN}' '%1' '${OUTDIR}\${INSTALLER_NAME}.msi'
            !finalize `${SIGN_MSI}` = 0
        !endif
    !endif

    !ifndef KEEP_SCRATCHDIR
        !finalize `${SHELL_CLEAR_SCRATCHDIR}` = 0
    !endif
!macroend

; WiX source
!define WXS `\
<?xml version="1.0" encoding="utf-8"?>\
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">\
<Product Name="${PRODUCT_NAME} ${VERSION} ${ARCH}" \
    Manufacturer="${COMPANY_NAME}" Language="1033" Codepage="1252" \
    Version="${VERSION}" Id="7B844E14-DED3-4D7A-BD48-CEB882A0DE43" \
    UpgradeCode="92FC827F-798D-471E-92F7-1FD538606448" >\
    <Package Id="*" InstallerVersion="200" Compressed="yes" Platform="${ARCH}" InstallScope="perMachine" />\
    <Media Id="1" />\
    <Directory Id="TARGETDIR" Name="SourceDir">\
        <Directory Id="${PRODUCT_NAME}">\
            <Component Id="${PRODUCT_NAME}" Guid="6FD262AE-31C4-4DBB-B38F-0099BE3D4CD4">\
                <CreateFolder />\
            </Component>\
        </Directory>\
    </Directory>\
    <Feature Id="${PRODUCT_NAME}" Level="0">\
        <ComponentRef Id="${PRODUCT_NAME}" />\
    </Feature>\
    <Binary Id="Installer" SourceFile="${OUTDIR}\${INSTALLER_NAME}.exe" />\
    <Property Id="INSTALL_PATH" Value="__DEFAULT__" />\
    <Property Id="REGISTER_BROWSER" Value="on" />\
    <Property Id="DESKTOP_ICON" Value="on" />\
    <Property Id="START_MENU_ICON" Value="on" />\
    <Property Id="LOG" Value="\\.\nul" />\
    <CustomAction Id="InstallDefaultPath" Return="check" Execute="deferred" \
        HideTarget="no" Impersonate="no" BinaryKey="Installer" \
        ExeCommand="/AllUsers /Silent /RegiserBrowser=[REGISTER_BROWSER] \
            /DesktopIcon=[DESKTOP_ICON] /StartMenuIcon=[START_MENU_ICON] \
            /Log=[LOG]" />\
    <CustomAction Id="InstallCustomPath" Return="check" Execute="deferred" \
        HideTarget="no" Impersonate="no" BinaryKey="Installer" \
        ExeCommand="/AllUsers /Silent /RegisterBrowser=[REGISTER_BROWSER] \
            /DesktopIcon=[DESKTOP_ICON] /StartMenuIcon=[START_MENU_ICON] \
            /Log=[LOG] /InstallDir=[INSTALL_PATH]" />\
    <InstallExecuteSequence>\
        <Custom Action="InstallDefaultPath" After="ProcessComponents">\
            <![CDATA[(INSTALL_PATH = "__DEFAULT__")]]>\
        </Custom>\
        <Custom Action="InstallCustomPath" After="ProcessComponents">\
            <![CDATA[(INSTALL_PATH <> "__DEFAULT__")]]>\
        </Custom>\
    </InstallExecuteSequence>\
</Product>\
</Wix>`

;Powershell commands
!define PS_INIT `\
if ($PSVersionTable.PSVersion.Major -lt 5) {\
    Write-Error -Message 'PowerShell version 5 or greater is required.' -ErrorAction 'Stop'\
};\
$InformationPreference = 'Continue';\
$NL = [System.Environment]::NewLine;`

!define PS_CHECK_NSIS `\
$ErrorActionPreference = 'SilentlyContinue';\
Write-Information -MessageData "${NL}Checking NSIS version.";\
[Net.ServicePointManager]::SecurityProtocol = (\
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls12\
);\
$nsis = (Invoke-RestMethod -Uri 'https://sourceforge.net/projects/nsis/rss' -UseBasicParsing).title[0].'#cdata-section'.Split('/');\
Write-Debug $nsis[2];\
if ($nsis[1] -match 'NSIS\s\d{1,}' -and $nsis[2] -match '\d{1,}\.\d{1,}') {\
    if (('v' + $nsis[2]) -ne '${NSIS_VERSION}') {\
        Write-Warning -Message "NSIS version $($nsis[2]) is available."\
    }\
} else {\
    Write-Warning -Message 'NSIS version check failed.'\
};`

!define PS_SCRATCHDIR `\
$ErrorActionPreference = 'Stop';\
Write-Information -MessageData "${NL}Using: ${SCRATCHDIR}";\
$ScratchDir = New-Item -ItemType 'Directory' -Path '${SCRATCHDIR}' -Force;`

!define PS_DOWNLOAD_PLUGINS `\
$NsisMultiUser = 'https://raw.githubusercontent.com/Drizin/NsisMultiUser/master';\
[System.Uri[]]$PluginUris = @(\
    "$NsisMultiUser/Include/NsisMultiUser.nsh",\
    "$NsisMultiUser/Include/NsisMultiUserLang.nsh",\
    "$NsisMultiUser/Include/StdUtils.nsh",\
    "$NsisMultiUser/Plugins/x86-unicode/StdUtils.dll",\
    "$NsisMultiUser/Include/UAC.nsh",\
    "$NsisMultiUser/Plugins/x86-unicode/UAC.dll"\
);\
foreach ($uri in $PluginUris) {\
    $path = Join-Path -Path $ScratchDir -ChildPath $uri.Segments[-1];\
    Write-Information -MessageData "Downloading: $($uri.Segments[-1])";\
    Write-Debug $uri;\
    (New-Object System.Net.WebClient).DownloadFile($uri, $path)\
}`

!define PS_DOWNLOAD_WIX `\
[System.Uri]$WixUri = '${MSI}';\
$WixZip = $WixUri.Segments[-1];\
$WixZipPath = Join-Path -Path $ScratchDir -ChildPath $WixZip;\
$WixDirPath = Join-Path -Path $ScratchDir -ChildPath 'wix3';\
Write-Information -MessageData "Downloading: $WixZip";\
Write-Debug $WixUri;\
(New-Object System.Net.WebClient).DownloadFile($WixUri, $WixZipPath);`

!define PS_EXTRACT_WIX `\
Write-Information -MessageData "Extracting: $WixZip";\
Remove-Item -Path $WixDirPath -Recurse -Force -ErrorAction 'SilentlyContinue';\
Add-Type -AssemblyName 'System.IO.Compression.FileSystem';\
[System.IO.Compression.ZipFile]::ExtractToDirectory($WixZipPath, $WixDirPath);\
Remove-Item -Path $WixZipPath -Force;`

!define PS_CREATE_WXS `\
Write-Information -MessageData "Writing: ${INSTALLER_NAME}.wxs"; \
Set-Content -Value '${WXS}' -Path (Join-Path -Path $ScratchDir -ChildPath '${INSTALLER_NAME}.wxs') -Encoding 'UTF8';`

!define PS_CREATE_NSH `\
$i =0;\
Write-Information -MessageData "Writing: ${FILE_MACROS_NSH}${NL}";\
$dist = Resolve-Path -Path '${DIST_DIR}';\
$DistLength = $dist.Path.Length + 1;\
$DistFiles = Get-ChildItem -Path $dist -File -Recurse -Force;\
[string[]]$nsh = @('!macro PASS_FILES FILE_CMD');\
Write-Debug $nsh[$i++];\
foreach ($file in $DistFiles) {\
    $nsh += '${FILE_CMD} "' + $file.FullName.Remove(0, $DistLength).Replace('$', '$$') + '"';\
    Write-Debug $nsh[$i++];\
};\
$nsh += "!macroend${NL}";\
Write-Debug $nsh[$i++];\
$nsh += '!macro PASS_FILES_AND_HASH FILE_CMD';\
Write-Debug $nsh[$i++];\
foreach ($file in $DistFiles) {\
    $sha = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash;\
    $nsh += '${FILE_CMD} "' + $file.FullName.Remove(0, $DistLength).Replace('$', '$$') + '" "' + $sha + '"';\
    Write-Debug $nsh[$i++];\
};\
$nsh += "!macroend${NL}";\
Write-Debug $nsh[$i++];\
$dirs = @(Get-ChildItem -Path $dist -Directory -Recurse -Force);\
$nsh += '!macro PASS_DIRS DIR_CMD';\
Write-Debug $nsh[$i++];\
foreach ($dir in ($dirs | Sort-Object -Property 'FullName')) {\
    $nsh += '${DIR_CMD} "$' + $dir.FullName.Replace("$dist", 'INSTDIR').Replace('$', '$$') + '"';\
    Write-Debug $nsh[$i++];\
};\
$nsh += "!macroend${NL}";\
Write-Debug $nsh[$i++];\
$nsh += '!macro PASS_DIRS_REVERSE DIR_CMD';\
Write-Debug $nsh[$i++];\
foreach ($dir in ($dirs | Sort-Object -Property 'FullName' -Descending)) {\
    $nsh += '${DIR_CMD} "$' + $dir.FullName.Replace("$dist", 'INSTDIR').Replace('$', '$$') + '"';\
    Write-Debug $nsh[$i++];\
};\
$nsh += '!macroend';\
Write-Debug $nsh[$i++];\
Set-Content -Value $nsh -Path (Join-Path -Path '${SCRATCHDIR}' -ChildPath '${FILE_MACROS_NSH}');`

!ifdef NO_DOWNLOADS
    !define PS `${PS_INIT}${PS_SCRATCHDIR}`
!else
    !define PS `${PS_INIT}${PS_CHECK_NSIS}${PS_SCRATCHDIR}${PS_DOWNLOAD_PLUGINS}`
    !ifdef DOWNLOAD_WIX
        !define /redef PS `${PS}${PS_DOWNLOAD_WIX}${PS_EXTRACT_WIX}`
    !endif
!endif
!ifdef MSI
    !define /redef PS `${PS}${PS_CREATE_WXS}`
!endif
!define /redef PS `${PS}${PS_CREATE_NSH}`

!ifdef DEBUG
    !define /redef PS `$DebugPreference = 'Continue'; ${PS}`
!else
    !define /redef PS `& { ${PS} }`
!endif

!ifdef NSIS_WIN32_MAKENSIS
    !searchreplace PS `${PS}` `"` `\"`
    !define SHELL_PREPARE_SCRATCHDIR `powershell.exe -noprofile -command "${PS}"`
!else
    !searchreplace PS `${PS}` `'` `'"'"'`
    !define SHELL_PREPARE_SCRATCHDIR `pwsh -noprofile -command '${PS}'`
!endif
!undef PS PS_INIT PS_CHECK_NSIS PS_SCRATCHDIR PS_DOWNLOAD_PLUGINS PS_CREATE_WXS PS_CREATE_NSH

!define SHELL_BUILD_MSI `\
${CANDLE} -arch ${ARCH} -nologo -out "${SCRATCHDIR}\${INSTALLER_NAME}.wxsobj" \
    "${SCRATCHDIR}\${INSTALLER_NAME}.wxs" && \
${LIGHT} -spdb -nologo -out "${OUTDIR}\${INSTALLER_NAME}.msi" \
    "${SCRATCHDIR}\${INSTALLER_NAME}.wxsobj"\
`

; Clear scratch directory
!ifdef NSIS_WIN32_MAKENSIS
    !define SHELL_CLEAR_SCRATCHDIR `\
(echo: & echo:Removing: ${SCRATCHDIR}) \
& (for %i in (NsisMultiUser.nsh, NsisMultiUserLang.nsh, StdUtils.nsh, StdUtils.dll, UAC.nsh, UAC.dll\
    ) do @del /f "${SCRATCHDIR}\%~i" 2> nul) \
& (del "${SCRATCHDIR}\${PRODUCT_NAME}-${VERSION}*" 2> nul) \
& (rmdir /s /q "${SCRATCHDIR}\wix3" 2> nul) \
& (rmdir "${SCRATCHDIR}" 2> nul \
    || echo:The directory was not completely removed.)\
`
!else
    !define SHELL_CLEAR_SCRATCHDIR `\
echo "Removing: ${SCRATCHDIR}"; \
for i in NsisMultiUser.nsh NsisMultiUserLang.nsh StdUtils.nsh StdUtils.dll UAC.nsh UAC.dll; \
do rm "${SCRATCHDIR}/$i"; \
done; \
rm "${SCRATCHDIR}/${PRODUCT_NAME}-${VERSION}*" 2>null; \
rm -rf "${SCRATCHDIR}/wix3" 2>null; \
rmdir "${SCRATCHDIR}" 2>null || echo "The directory was not completely removed."\
`
!endif
