; CalcStar NSIS 安装包脚本：由 build.ps1 -Pack 调用，VERSION 通过 /DVERSION 传入。
; 输入为 PyInstaller onedir 产物 ..\dist\CalcStar\（含 lib\ 运行时目录）。

!include "MUI2.nsh"

!define APP_NAME "计算之星"
!define EXE_NAME "CalcStar.exe"
!define APP_ID "CalcStar"

Name "${APP_NAME}"
OutFile "..\dist\CalcStar-${VERSION}-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\CalcStar"
InstallDirRegKey HKCU "Software\${APP_ID}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Unicode true

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "安装"
    SetShellVarContext current

    ; 若注册表记录了不同的旧安装目录，先清理旧副本（改安装路径时不会自动搬移）
    ReadRegStr $0 HKCU "Software\${APP_ID}" "InstallDir"
    StrCmp $0 "" no_old_dir
    StrCmp $0 "$INSTDIR" no_old_dir
    IfFileExists "$0\uninstall.exe" 0 no_old_uninstaller
        ExecWait '"$0\uninstall.exe" /S _?=$0'
        Delete "$0\uninstall.exe"
    no_old_uninstaller:
    RMDir /r /REBOOTOK "$0"
    no_old_dir:

    SetOutPath "$INSTDIR"
    File /r "..\dist\CalcStar\*.*"

    WriteUninstaller "$INSTDIR\uninstall.exe"

    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"

    WriteRegStr HKCU "Software\${APP_ID}" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayName" "${APP_NAME} ${VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayIcon" "$INSTDIR\${EXE_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayVersion" "${VERSION}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    SetShellVarContext current
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r /REBOOTOK "$INSTDIR"
    DeleteRegKey HKCU "Software\${APP_ID}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
SectionEnd
