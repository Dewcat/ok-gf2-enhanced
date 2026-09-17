import json
import os
from pathlib import Path


def get_app_version():
    launcher_version = os.environ.get('PYAPPIFY_APP_VERSION')
    if launcher_version and launcher_version.strip():
        return launcher_version.strip()
    # Only consult the installation containing this working tree.
    root = Path(__file__).resolve().parents[1]
    if root.name == 'working':
        try:
            metadata = json.loads((root.parent / 'app.json').read_text(encoding='utf-8'))
            version = metadata.get('current_version')
            if metadata.get('name') == 'ok-gf2' and isinstance(version, str) and version.strip():
                return version.strip()
        except (OSError, ValueError, AttributeError):
            pass
    return 'dev'
