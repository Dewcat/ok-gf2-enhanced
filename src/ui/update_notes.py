"""Read commit titles locally instead of displaying flattened launcher messages."""

import logging
from pathlib import Path
import re
import subprocess


logger = logging.getLogger(__name__)
UNAVAILABLE = '暂时无法读取本地提交标题，请查看 GitHub 发布说明。'


def repository_path():
    root = Path(__file__).resolve().parents[2]
    # Installed source lives in working; the launcher keeps Git data in repo.
    return root.parent / 'repo' if root.name == 'working' else root


def version_ref(version):
    value = str(version or '')
    if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-.](?:alpha|beta|rc)(?:\.\d+)?)?', value):
        raise ValueError('Unsupported version reference')
    return 'refs/tags/' + (value if value.startswith('v') else 'v' + value)


def commit_titles(repo, current, target):
    old, new = version_ref(current), version_ref(target)
    if old == new:
        return []
    repo = Path(repo).resolve()

    def git(*args):
        return subprocess.run(
            ['git', '-c', f'safe.directory={repo.as_posix()}', '-C', str(repo), *args],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=10, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        ).stdout

    old_sha = git('rev-parse', '--verify', old + '^{commit}').strip()
    new_sha = git('rev-parse', '--verify', new + '^{commit}').strip()
    base = git('merge-base', old_sha, new_sha).strip()
    # On downgrade show the changes removed; on upgrade show those introduced.
    revision = f'{new_sha}..{old_sha}' if base == new_sha else f'{old_sha}..{new_sha}'
    messages = git('log', '--encoding=UTF-8', '--no-merges', '--topo-order', '--max-count=10',
                   '--format=%B%x00', revision, '--')
    return [message.strip().splitlines()[0].strip()
            for message in messages.split('\0') if message.strip()]


def install_update_notes(module=None):
    if module is None:
        import pyappify as module
    if getattr(module, '_gf2_title_notes_installed', False):
        return

    def read(current, target):
        try:
            return commit_titles(repository_path(), current, target)
        except (OSError, ValueError, subprocess.SubprocessError):
            logger.warning('无法读取本地版本间的提交标题', exc_info=True)
            # Flattened launcher notes cannot reliably distinguish titles from bodies.
            return [UNAVAILABLE]

    def startup_notes():
        return read(module.app_starting_version, module.app_version)

    def selected_notes(update_notes, current_version, target_version):
        return read(current_version, target_version)

    module.get_update_notes = startup_notes
    module.get_update_note = startup_notes
    module.calculate_update_notes = selected_notes
    module._gf2_title_notes_installed = True
