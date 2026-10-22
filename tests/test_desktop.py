import json
import subprocess
import sys
from pathlib import Path

from app import APP_VERSION


def test_desktop_launcher_serves_and_exports_without_current_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    # Exercise the actual launcher/server and native PDF libraries, not mocks.
    result = subprocess.run([sys.executable, str(root / 'desktop.py'), '--self-test'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report == {'versao': APP_VERSION, 'self_test': 'ok', 'documentos': 105,
                      'counts': [100, 95], 'relatorios': ['xlsx', 'pdf']}
