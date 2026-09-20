from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.ui.update_notes import commit_titles, install_update_notes, UNAVAILABLE


class UpdateNotesTest(unittest.TestCase):
    def test_real_git_upgrade_downgrade_and_no_body(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(['git', '-C', directory, *args], check=True,
                                      capture_output=True)
            git('init')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            git('commit', '--allow-empty', '-m', 'baseline')
            git('tag', 'v1.0.0')
            git('commit', '--allow-empty', '-m', 'A plain title\n\nfix: this is BODY, not a title\nmore details')
            git('commit', '--allow-empty', '-m', 'fix: 中文标题\n\nLong body')
            git('tag', 'v1.0.1')
            git('commit', '--allow-empty', '-m', 'must not leak from newer HEAD')
            git('config', 'i18n.logOutputEncoding', 'GBK')
            expected = ['fix: 中文标题', 'A plain title']
            self.assertEqual(expected, commit_titles(directory, 'v1.0.0', 'v1.0.1'))
            self.assertEqual(expected, commit_titles(directory, 'v1.0.1', 'v1.0.0'))
            self.assertEqual([], commit_titles(directory, '1.0.1', 'v1.0.1'))

    def test_both_ui_paths_use_titles_and_install_is_idempotent(self):
        module = SimpleNamespace(app_starting_version='v1.0.0', app_version='v1.0.1')
        install_update_notes(module)
        original = module.get_update_notes
        install_update_notes(module)
        self.assertIs(original, module.get_update_notes)
        with patch('src.ui.update_notes.commit_titles', return_value=['title']) as read:
            self.assertEqual(['title'], module.get_update_notes())
            self.assertEqual(['title'], module.calculate_update_notes(
                [{'update_note': ['title', 'BODY']}], 'v1.0.1', 'v1.0.2'))
            self.assertEqual(('v1.0.1', 'v1.0.2'), read.call_args.args[1:])

    def test_missing_git_never_falls_back_to_body(self):
        module = SimpleNamespace(app_starting_version='v1.0.0', app_version='v1.0.1')
        install_update_notes(module)
        with patch('src.ui.update_notes.commit_titles', side_effect=FileNotFoundError), \
                self.assertLogs('src.ui.update_notes', level='WARNING'):
            self.assertEqual([UNAVAILABLE], module.get_update_notes())


if __name__ == '__main__':
    unittest.main()
