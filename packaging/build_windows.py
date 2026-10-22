"""Build a Windows x64 NSIS installer on Windows or Linux, with offline runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.12.10'
PYTHON_SHA256 = '0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8'
APP_FILES = ('desktop.py', 'updater.py', 'app.py', 'comparator.py', 'dominio_reader.py',
             'sped_reader.py', 'pdf_orientation.py', 'templates/index.html',
             'static/app.js', 'static/style.css', 'exemplos/sped_simulado.pdf',
             'exemplos/dominio_simulado.pdf', 'exemplos/gabarito.json')


def app_version():
    text = (ROOT / 'app.py').read_text(encoding='utf-8')
    match = re.search(r"^APP_VERSION = '(\d+\.\d+\.\d+)'$", text, re.MULTILINE)
    if not match:
        raise ValueError('APP_VERSION precisa ter formato x.y.z.')
    return match[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_payload(payload, cache):
    package = cache / f'python.{PYTHON_VERSION}.nupkg'
    if not package.exists():
        url = f'https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSION}/{package.name}'
        print('Baixando o runtime oficial Python Windows...', flush=True)
        urllib.request.urlretrieve(url, package)
    if sha256(package) != PYTHON_SHA256:
        raise ValueError('Checksum do runtime Python não confere; remova o arquivo do cache e tente novamente.')
    runtime = payload / 'runtime'
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(package) as archive:
        for item in archive.infolist():
            name = Path(item.filename)
            if not name.parts or name.parts[0] != 'tools' or len(name.parts) < 2:
                continue
            if '..' in name.parts or name.is_absolute():
                raise ValueError('Caminho inválido no pacote Python.')
            target = runtime.joinpath(*name.parts[1:])
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
    site_packages = runtime / 'Lib' / 'site-packages'
    shutil.rmtree(site_packages, ignore_errors=True)
    shutil.rmtree(runtime / 'Scripts', ignore_errors=True)
    wheels = cache / 'wheels-win-amd64-cp312'
    wheels.mkdir(exist_ok=True)
    target = ['--platform', 'win_amd64', '--python-version', '3.12', '--implementation', 'cp',
              '--abi', 'cp312', '--only-binary=:all:', '-r', str(ROOT / 'packaging/requirements-windows.txt')]
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--disable-pip-version-check',
                    '--dest', str(wheels), *target], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                    '--no-index', '--find-links', str(wheels), '--no-compile',
                    '--target', str(site_packages), *target], check=True)
    for filename in APP_FILES:
        source = ROOT / filename
        destination = payload / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(ROOT / 'packaging/LEIA-ME.txt', payload / 'LEIA-ME.txt')
    manifest = {'app_version': app_version(), 'python_version': PYTHON_VERSION,
                'python_sha256': PYTHON_SHA256, 'architecture': 'win-amd64',
                'files': {str(path.relative_to(payload)).replace(os.sep, '/'): sha256(path)
                          for path in sorted(payload.rglob('*')) if path.is_file()}}
    (payload / 'build-info.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--makensis', default=shutil.which('makensis'))
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--cache', type=Path, default=ROOT / '.build-cache')
    args = parser.parse_args()
    if not args.makensis:
        parser.error('Informe --makensis com o caminho do compilador NSIS.')
    output, cache = args.output.resolve(), args.cache.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    payload = output / 'payload-windows-x64'
    # Do not delete an existing user-selected directory; use a fresh build path.
    if payload.exists():
        parser.error(f'A pasta {payload} já existe. Escolha outra pasta --output para reconstruir.')
    prepare_payload(payload, cache)
    installer = output / f'ComparadorNotas-{app_version()}-Windows-x64.exe'
    prefix = '/' if os.name == 'nt' else '-'
    command = [args.makensis, f'{prefix}DAPP_VERSION={app_version()}', f'{prefix}DPAYLOAD={payload}',
               f'{prefix}DOUTPUT={installer}', str(ROOT / 'packaging/installer.nsi')]
    subprocess.run(command, check=True)
    if installer.read_bytes()[:2] != b'MZ':
        raise ValueError('O compilador não produziu um executável Windows válido.')
    checksum = sha256(installer)
    (output / (installer.name + '.sha256')).write_text(checksum + '  ' + installer.name + '\n', encoding='ascii')
    stable = output / 'ComparadorNotas-Windows-x64.exe'
    shutil.copy2(installer, stable)
    (output / 'atualizacao.json').write_text(json.dumps(dict(version=app_version(),
        url=f'https://github.com/financeirolucrattiva-web/COMPARADOR-DE-NOTAS/releases/download/v{app_version()}/{installer.name}',
        sha256=checksum)), encoding='utf-8')
    print(json.dumps({'installer': str(installer), 'bytes': installer.stat().st_size, 'sha256': checksum}), flush=True)


if __name__ == '__main__':
    main()
