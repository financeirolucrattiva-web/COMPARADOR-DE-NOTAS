param([Parameter(Mandatory=$true)][string]$Installer, [Parameter(Mandatory=$true)][string]$Version)
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:RUNNER_TEMP 'Comparador Teste Instalado'
$old = Join-Path $env:RUNNER_TEMP 'ComparadorNotas-0.7.1.exe'
Invoke-WebRequest 'https://github.com/financeirolucrattiva-web/COMPARADOR-DE-NOTAS/releases/download/v0.7.1/ComparadorNotas-0.7.1-Windows-x64.exe' -OutFile $old
if ((Get-FileHash $old -Algorithm SHA256).Hash.ToLower() -ne 'ae3c84133f866213cd8b7cdcbeef9dd10b21614f1ab16976d47a977ee5a78c16') { throw 'Checksum do instalador antigo incorreto' }
$process = Start-Process -FilePath $old -ArgumentList "/S /D=$target" -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Falha ao instalar 0.7.1 para testar atualizacao' }
& "$target/runtime/python.exe" -E -s "$target/desktop.py" --self-test
if ($LASTEXITCODE -ne 0) { throw 'A instalacao antiga nao ficou funcional' }
Set-Content -Path "$target/meu-relatorio.pdf" -Value 'Dado ficticio para testar preservacao de arquivos'

# Upgrade exactly the installer already sent to the colleague, in the same path.
$process = Start-Process -FilePath $Installer -ArgumentList "/S /D=$target" -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Falha na atualizacao da instalacao existente' }
if (!(Test-Path "$target/updater.py")) { throw 'Atualizador nao instalado' }
& "$target/runtime/python.exe" -E -s "$target/desktop.py" --self-test
if ($LASTEXITCODE -ne 0) { throw 'A versao atualizada nao passou na validacao offline' }
if (!(Test-Path "$target/meu-relatorio.pdf")) { throw 'A atualizacao apagou um arquivo do usuario' }
$shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Comparador de Notas Lucrattiva.lnk'
if (!(Test-Path $shortcut)) { throw 'Atalho da area de trabalho ausente' }
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LucrattivaComparadorNotas'
$installed = Get-ItemProperty $registry
if ($installed.DisplayVersion -ne $Version) { throw 'A instalacao continua na versao antiga' }
if ($installed.UninstallString -ne ('"' + $target + '\Desinstalar.exe"')) { throw 'Comando de desinstalacao incorreto' }
$feed = (Resolve-Path dist/atualizacao.json).Path
& "$target/runtime/python.exe" -E -s -c "import sys,json;sys.path.insert(0,sys.argv[1]);import updater;data=json.load(open(sys.argv[2],encoding='utf-8'));assert updater.validate_update(data,'0.7.1')['version']==sys.argv[3]" $target $feed $Version
if ($LASTEXITCODE -ne 0) { throw 'Metadados de atualizacao invalidos' }
$meta = Get-Content dist/atualizacao.json -Raw | ConvertFrom-Json
if ($meta.sha256 -ne (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLower()) { throw 'Feed aponta para um instalador de outro checksum' }

$process = Start-Process -FilePath "$target/Desinstalar.exe" -ArgumentList "/S _?=$target" -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Falha na desinstalacao' }
if (Test-Path "$target/runtime") { throw 'Runtime nao removido' }
if (Test-Path $registry) { throw 'Registro do programa nao removido' }
if (Test-Path $shortcut) { throw 'Atalho nao removido' }
if (!(Test-Path "$target/meu-relatorio.pdf")) { throw 'Arquivo do usuario removido indevidamente' }
"Windows x64: atualizacao real de 0.7.1 para $Version aprovada. Atalhos, reconciliacao de documentos, comparacao, Excel, PDF, feed de atualizacao, desinstalacao e preservacao de arquivos aprovados." | Set-Content dist/VALIDACAO-WINDOWS.txt
