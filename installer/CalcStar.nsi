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

    ; 升级流程：只要存在旧版本，先静默卸载旧版，再安装新版。
    ; 1) 注册表记录的旧目录与本次目标目录不同：先卸载并清理（改安装路径时不会自动搬移）
    ReadRegStr $0 HKCU "Software\${APP_ID}" "InstallDir"
    StrCmp $0 "" skip_registry_old
    StrCmp $0 "$INSTDIR" skip_registry_old
    IfFileExists "$0\uninstall.exe" 0 registry_no_uninstaller
        ExecWait '"$0\uninstall.exe" /S _?=$0'
        Delete "$0\uninstall.exe"
    registry_no_uninstaller:
    RMDir /r /REBOOTOK "$0"
    skip_registry_old:

    ; 2) 目标目录已有旧版（注册表缺失或路径相同）：同样先卸载再清理，避免覆盖式升级残留旧文件
    IfFileExists "$INSTDIR\uninstall.exe" 0 skip_target_old
        ExecWait '"$INSTDIR\uninstall.exe" /S _?=$INSTDIR'
        Delete "$INSTDIR\uninstall.exe"
        RMDir /r /REBOOTOK "$INSTDIR"
    skip_target_old:

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
