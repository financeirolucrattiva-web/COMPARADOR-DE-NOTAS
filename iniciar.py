"""Execute com Python 3.12 para instalar e abrir o comparador localmente."""
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent

def open_when_ready(process):
    import time
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(40):
        if process.poll() is not None:
            return
        try:
            with opener.open('http://127.0.0.1:5000', timeout=1) as response:
                if response.status == 200:
                    webbrowser.open('http://127.0.0.1:5000')
                    return
        except OSError:
            pass
        time.sleep(.5)

def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Instale Python 3.12 ou superior para iniciar.')
    folder = ROOT / '.venv-local'
    executable = folder / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not executable.exists():
        print('Preparando o ambiente local…', flush=True)
        venv.EnvBuilder(with_pip=True).create(folder)
    subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], check=True, cwd=ROOT)
    process = subprocess.Popen([str(executable), 'app.py'], cwd=ROOT)
    threading.Thread(target=open_when_ready, args=(process,), daemon=True).start()
    print('O navegador será aberto. Mantenha esta janela aberta; Ctrl+C encerra o servidor.', flush=True)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 0

if __name__ == '__main__':
    sys.exit(main())
