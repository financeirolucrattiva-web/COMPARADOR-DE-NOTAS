"""Execute com Python 3.12 para instalar e abrir o comparador localmente."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import venv
import webbrowser
import uuid

ROOT = Path(__file__).resolve().parent

def choose_port(preferred=5000):
    with socket.socket() as candidate:
        try:
            candidate.bind(('127.0.0.1', preferred))
        except OSError:
            candidate.bind(('127.0.0.1', 0))
        return candidate.getsockname()[1]


def open_when_ready(process, address, instance_id):
    import time
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(40):
        if process.poll() is not None:
            return
        try:
            with opener.open(address + '/versao', timeout=1) as response:
                data = json.load(response)
            if data.get('instancia') == instance_id and process.poll() is None:
                webbrowser.open(address)
                return True
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    print('O navegador não foi aberto automaticamente. Confira o erro e o endereço nesta janela.', flush=True)
    return False


def start_application(executable):
    port = choose_port()
    instance_id = uuid.uuid4().hex
    address = f'http://127.0.0.1:{port}'
    child_env = os.environ.copy()
    child_env.update(COMPARADOR_PORT=str(port), COMPARADOR_HOST='127.0.0.1',
                     COMPARADOR_INSTANCE_ID=instance_id)
    if port != 5000:
        print('A porta padrão está ocupada. Esta cópia será aberta em outra porta.', flush=True)
    process = subprocess.Popen([str(executable), 'app.py'], cwd=ROOT, env=child_env)
    print('Endereço desta cópia: ' + address, flush=True)
    threading.Thread(target=open_when_ready, args=(process, address, instance_id), daemon=True).start()
    return process

def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Instale Python 3.12 ou superior para iniciar.')
    folder = ROOT / '.venv-local'
    executable = folder / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not executable.exists():
        print('Preparando o ambiente local…', flush=True)
        venv.EnvBuilder(with_pip=True).create(folder)
    subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], check=True, cwd=ROOT)
    process = start_application(executable)
    print('O navegador será aberto. Mantenha esta janela aberta; Ctrl+C encerra o servidor.', flush=True)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 0

if __name__ == '__main__':
    sys.exit(main())
