import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def methods(filename, names, **globals_):
    tree = ast.parse((ROOT / 'src/tasks' / filename).read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    selected = [node for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {'re': re, **globals_}
    exec(compile(ast.Module(body=selected, type_ignores=[]), filename, 'exec'), namespace)
    return namespace


class UpstreamFixTest(unittest.TestCase):
    def test_loading_frames_do_not_click_but_dialogs_still_do(self):
        for labels, expected_clicks in [([], 0), (['资源加载中'], 0),
                                        (['加载 53%'], 0), (['剧情正文'], 1)]:
            with self.subTest(labels=labels):
                clock = Mock()
                clock.time.side_effect = [0, 1, 2]
                ns = methods('BaseGfTask.py', {'skip_dialogs', '_is_loading_frame'},
                             time=clock, pop_ups=[])
                task = Mock()
                task.ocr.return_value = [SimpleNamespace(name=name) for name in labels]
                task.find_boxes.return_value = []
                task._is_loading_frame.side_effect = lambda boxes: ns['_is_loading_frame'](task, boxes)
                ns['skip_dialogs'](task, end_match=['完成'], time_out=2, raise_if_not_found=False)
                self.assertEqual(expected_clicks, task.click_relative.call_count)
                task.next_frame.assert_called_once()

    def test_xunlu_missing_entry_returns_home(self):
        ns = methods('DailyTask.py', {'xunlu'})
        task = Mock()
        task.wait_ocr.return_value = []
        ns['xunlu'](task)
        task.wait_click_ocr.assert_not_called()
        task.ensure_main.assert_called_once()

    def test_xunlu_both_entry_forms_allow_missing_rewards(self):
        ns = methods('DailyTask.py', {'xunlu'})
        for preview in [False, True]:
            with self.subTest(preview=preview):
                task = Mock()
                task.wait_ocr.return_value = [Mock()]
                task.wait_click_ocr.side_effect = [preview, False, False]
                ns['xunlu'](task)
                task.ensure_main.assert_called_once()
                self.assertEqual(3, task.wait_click_ocr.call_count)
                for call in task.wait_click_ocr.call_args_list:
                    self.assertFalse(call.kwargs['raise_if_not_found'])


if __name__ == '__main__':
    unittest.main()
