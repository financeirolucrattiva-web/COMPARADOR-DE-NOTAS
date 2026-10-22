Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef APP_VERSION
  !error "APP_VERSION obrigatorio"
!endif
!ifndef PAYLOAD
  !error "PAYLOAD obrigatorio"
!endif
!ifndef OUTPUT
  !error "OUTPUT obrigatorio"
!endif

Name "Comparador de Notas Lucrattiva"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Lucrattiva\ComparadorNotas"
InstallDirRegKey HKCU "Software\Lucrattiva\ComparadorNotas" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
BrandingText "Lucrattiva - Comparador de Notas ${APP_VERSION}"
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=1046 "ProductName" "Comparador de Notas Lucrattiva"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador offline do Comparador de Notas"
VIAddVersionKey /LANG=1046 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1046 "LegalCopyright" "Lucrattiva"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Instalar o Comparador de Notas"
!define MUI_WELCOMEPAGE_TEXT "Este instalador inclui o programa, Python e as dependências.$\r$\n$\r$\nNão é preciso instalar Python ou ter acesso de administrador.$\r$\n$\r$\nFeche outras cópias do comparador antes de atualizar."
!define MUI_FINISHPAGE_RUN "$INSTDIR\runtime\python.exe"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenComparator
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o Comparador de Notas"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\LEIA-ME.txt"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Este instalador requer Windows de 64 bits."
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext current
FunctionEnd

Function OpenComparator
  Exec '"$INSTDIR\runtime\python.exe" -E -s "$INSTDIR\desktop.py"'
FunctionEnd

Section "Comparador de Notas"
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}\*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  CreateDirectory "$SMPROGRAMS\Lucrattiva"
  CreateShortcut "$SMPROGRAMS\Lucrattiva\Comparador de Notas.lnk" "$INSTDIR\runtime\python.exe" '-E -s "$INSTDIR\desktop.py"' "$INSTDIR\runtime\python.exe"
  CreateShortcut "$DESKTOP\Comparador de Notas Lucrattiva.lnk" "$INSTDIR\runtime\python.exe" '-E -s "$INSTDIR\desktop.py"' "$INSTDIR\runtime\python.exe"
  CreateShortcut "$SMPROGRAMS\Lucrattiva\Desinstalar Comparador.lnk" "$INSTDIR\Desinstalar.exe"
  WriteRegStr HKCU "Software\Lucrattiva\ComparadorNotas" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "DisplayName" "Comparador de Notas Lucrattiva"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "Publisher" "Lucrattiva"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "QuietUninstallString" '"$INSTDIR\Desinstalar.exe" /S'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext current
  ; Remove only installed code; leave user PDFs/reports or other files alone.
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\templates"
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\exemplos"
  RMDir /r "$INSTDIR\__pycache__"
  Delete "$INSTDIR\desktop.py"
  Delete "$INSTDIR\app.py"
  Delete "$INSTDIR\comparator.py"
  Delete "$INSTDIR\dominio_reader.py"
  Delete "$INSTDIR\sped_reader.py"
  Delete "$INSTDIR\pdf_orientation.py"
  Delete "$INSTDIR\LEIA-ME.txt"
  Delete "$INSTDIR\build-info.json"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Comparador de Notas Lucrattiva.lnk"
  Delete "$SMPROGRAMS\Lucrattiva\Comparador de Notas.lnk"
  Delete "$SMPROGRAMS\Lucrattiva\Desinstalar Comparador.lnk"
  RMDir "$SMPROGRAMS\Lucrattiva"
  DeleteRegKey HKCU "Software\Lucrattiva\ComparadorNotas"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas"
SectionEnd
