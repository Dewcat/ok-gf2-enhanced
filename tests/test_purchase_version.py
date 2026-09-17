import ast
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('app_version', ROOT / 'src/app_version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)
tree = ast.parse((ROOT / 'src/tasks/DailyTask.py').read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'confirm_free_gift')
namespace = {'re': re}
exec(compile(ast.Module(body=[method], type_ignores=[]), '<gift>', 'exec'), namespace)
close_method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'close_gift_dialog')
exec(compile(ast.Module(body=[close_method], type_ignores=[]), '<gift>', 'exec'), namespace)


class PurchaseTest(unittest.TestCase):
    def check_gift(self, labels, expected):
        task = Mock()
        task.box_of_screen.side_effect = lambda *coords: coords
        task.ocr.return_value = labels
        def find(boxes, match, boundary=None):
            x1, y1, x2, y2 = boundary or (0, 0, 1, 1)
            return [b for b in boxes if match.fullmatch(b.name)
                    and x1 <= b.x <= x2 and y1 <= b.y <= y2]
        task.find_boxes.side_effect = find
        self.assertEqual(expected, namespace['confirm_free_gift'](task))
        task.close_gift_dialog.assert_called_once()
        task.back.assert_not_called()
        if expected:
            task.click.assert_called_once()
            task.wait_pop_up.assert_called_once()
            calls = [call[0] for call in task.mock_calls]
            self.assertLess(calls.index('click'), calls.index('wait_pop_up'))
            self.assertLess(calls.index('wait_pop_up'), calls.index('close_gift_dialog'))
        else:
            task.click.assert_not_called()
            task.wait_pop_up.assert_not_called()

    def test_free_paid_unknown_and_background_free(self):
        from types import SimpleNamespace as Box
        controls = [Box(name='取消', x=.35, y=.74), Box(name='购买', x=.63, y=.74)]
        for price in ['免费', '0', '60', '晶条', '']:
            with self.subTest(price=price):
                self.check_gift(controls + [Box(name=price, x=.79, y=.30)], price == '免费')
        self.check_gift(controls + [Box(name='免费', x=.30, y=.40)], False)
        self.check_gift([Box(name='免费', x=.58, y=.71)], False)
        self.check_gift([], False)
        free = Box(name='免费', x=.79, y=.30)
        for label, x, y in [('已售罄', .63, .74), ('每日晶条礼包', .40, .30)]:
            self.check_gift(controls + [free, Box(name=label, x=x, y=y)], False)

    def test_black_x_closes_detail_and_stops_if_still_open(self):
        task = Mock()
        task.ocr.return_value = []
        namespace['close_gift_dialog'](task)
        task.click.assert_called_once_with(0.83, 0.255, after_sleep=1)
        task.back.assert_not_called()
        task.ocr.return_value = [Mock(name='每日晶条礼包')]
        with self.assertRaises(RuntimeError):
            namespace['close_gift_dialog'](task)


class VersionTest(unittest.TestCase):
    def test_launcher_takes_priority(self):
        with patch.dict(version.os.environ, {'PYAPPIFY_APP_VERSION': 'v9.0'}):
            self.assertEqual('v9.0', version.get_app_version())

    def test_install_fallback_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'working/src/app_version.py'
            with patch.object(version, '__file__', str(source)), patch.dict(version.os.environ, {'PYAPPIFY_APP_VERSION': ''}):
                self.assertEqual('dev', version.get_app_version())
                metadata = root / 'app.json'
                metadata.write_text(json.dumps({'name': 'ok-gf2', 'current_version': 'v1.2.75'}))
                self.assertEqual('v1.2.75', version.get_app_version())
                metadata.write_text('{broken')
                self.assertEqual('dev', version.get_app_version())
                metadata.write_text('[]')
                self.assertEqual('dev', version.get_app_version())


if __name__ == '__main__':
    unittest.main()
