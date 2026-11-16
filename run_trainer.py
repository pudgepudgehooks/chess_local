"""Launch the trainer using local dependencies when available."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if (ROOT / '.deps').is_dir():
    sys.path.insert(0, str(ROOT / '.deps'))

if __name__ == '__main__':
    try:
        from streamlit.web import cli
    except ImportError:
        raise SystemExit('Install dependencies first: python -m pip install -r requirements.txt')
    sys.argv = [
        'streamlit', 'run', str(ROOT / 'visualization_all.py'),
        '--global.developmentMode=false', '--server.address=127.0.0.1',
        '--server.port=8501', '--server.headless=true',
    ]
    cli.main()
