"""Optional startup update check. Only metadata/installer bytes leave the app flow."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

BASE = 'https://github.com/financeirolucrattiva-web/COMPARADOR-DE-NOTAS/releases/'
FEED = BASE + 'latest/download/atualizacao.json'
MAX_INSTALLER = 100 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Versão de atualização inválida.')
    return tuple(map(int, value.split('.')))


def validate_update(data, current):
    version = data.get('version')
    if version_tuple(version) <= version_tuple(current):
        return None
    expected = BASE + f'download/v{version}/ComparadorNotas-{version}-Windows-x64.exe'
    if data.get('url') != expected or not re.fullmatch(r'[a-f0-9]{64}', data.get('sha256', '')):
        raise ValueError('Endereço ou checksum de atualização inválido.')
    return dict(version=version, url=expected, sha256=data['sha256'])


def check_update(current):
    with urllib.request.urlopen(FEED, timeout=4) as response:
        raw = response.read(32769)
    if len(raw) > 32768:
        raise ValueError('Metadados de atualização excedem o limite.')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Metadados de atualização inválidos.')
    return validate_update(data, current)


def download_update(info, folder):
    # Revalidate the fixed repository/asset path before any download or execution.
    if validate_update(info, '0.0.0') is None:
        raise ValueError('Versão do instalador inválida.')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"ComparadorNotas-{info['version']}-Windows-x64.exe"
    partial = target.with_suffix('.part')
    digest, size, signature = hashlib.sha256(), 0, b''
    try:
        with urllib.request.urlopen(info['url'], timeout=30) as response, partial.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                if not signature:
                    signature = chunk[:2]
                size += len(chunk)
                if size > MAX_INSTALLER:
                    raise ValueError('Instalador excede o limite.')
                digest.update(chunk)
                stream.write(chunk)
        if signature != b'MZ' or digest.hexdigest() != info['sha256']:
            raise ValueError('Integridade do instalador não confere. A atualização não será executada.')
        partial.replace(target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def offer_update(current):
    """Ask before replacing an installation; network failures never block use."""
    if os.name != 'nt':
        return False
    import ctypes
    message = ctypes.windll.user32.MessageBoxW
    print('Verificando atualizações (sem envio de PDFs)...', flush=True)
    try:
        info = check_update(current)
    except Exception:
        print('Verificação de atualização indisponível. O comparador pode ser usado normalmente, inclusive offline.', flush=True)
        return False
    if not info:
        return False
    answer = message(None, f"A versão {info['version']} está disponível.\n\nDeseja baixar e instalar agora?\nO instalador abrirá e esta cópia será encerrada antes da instalação.", 'Atualização do Comparador de Notas', 0x24)
    if answer != 6:
        return False
    try:
        folder = Path(os.environ['LOCALAPPDATA']) / 'Lucrattiva' / 'AtualizacoesComparador'
        print('Baixando e verificando a nova versão...', flush=True)
        installer = download_update(info, folder)
        subprocess.Popen([str(installer)], close_fds=True)
        return True
    except Exception as exc:
        message(None, f'Não foi possível atualizar: {exc}\n\nO comparador atual será aberto normalmente.', 'Comparador de Notas', 0x10)
        return False
