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
        self.assertFalse(ns['xunlu'](task))
        task.wait_click_ocr.assert_not_called()
        task.ensure_main.assert_called_once()

    def test_xunlu_both_entry_forms_open_actions_before_claiming(self):
        ns = methods('DailyTask.py', {'xunlu'})
        for preview in [False, True]:
            with self.subTest(preview=preview):
                task = Mock()
                task.box_of_screen.side_effect = lambda *coords: coords
                task.wait_ocr.side_effect = [[Mock()], True, True, False]
                task.wait_click_ocr.side_effect = [preview, True, True, True, True, True]
                self.assertTrue(ns['xunlu'](task))
                task.ensure_main.assert_called_once()
                self.assertEqual(6, task.wait_click_ocr.call_count)
                calls = task.wait_click_ocr.call_args_list
                self.assertEqual('^沿途行动$', calls[1].kwargs['match'][0].pattern)
                self.assertEqual(task.box.top, calls[1].kwargs['box'])
                self.assertEqual('^一键领取$', calls[2].kwargs['match'][0].pattern)
                self.assertEqual((0.70, 0.88, 1, 1), calls[2].kwargs['box'])
                self.assertEqual('^远航巡录$', calls[3].kwargs['match'][0].pattern)
                self.assertEqual((0.25, 0, 0.65, 0.12), calls[3].kwargs['box'])
                self.assertEqual('^一键领取$', calls[4].kwargs['match'][0].pattern)
                self.assertEqual('^确认$', calls[5].kwargs['match'][0].pattern)
                self.assertEqual(task.box.bottom_right, calls[5].kwargs['box'])
                self.assertEqual((0, 0, 1, 1), task.wait_ocr.call_args_list[2].kwargs['box'])
                self.assertEqual((0, 0, 1, 1), task.wait_ocr.call_args_list[3].kwargs['box'])
                task.click.assert_called_once_with(0.5, 0.95, after_sleep=1)
                names = [call[0] for call in task.mock_calls]
                self.assertLess(names.index('click'), names.index('ensure_main'))
                for call in task.wait_click_ocr.call_args_list:
                    self.assertFalse(call.kwargs['raise_if_not_found'])

    def test_xunlu_does_not_claim_on_pass_page_when_actions_unavailable(self):
        ns = methods('DailyTask.py', {'xunlu'})
        for tab_found, page_found in [(False, False), (True, False)]:
            with self.subTest(tab_found=tab_found):
                task = Mock()
                task.wait_ocr.side_effect = [[Mock()], page_found]
                task.wait_click_ocr.side_effect = [False, tab_found]
                self.assertFalse(ns['xunlu'](task))
                self.assertEqual(2, task.wait_click_ocr.call_count)
                task.ensure_main.assert_called_once()

    def test_xunlu_missing_claim_reports_incomplete(self):
        ns = methods('DailyTask.py', {'xunlu'})
        task = Mock()
        task.wait_ocr.side_effect = [[Mock()], True, True, False]
        task.wait_click_ocr.side_effect = [False, True, False, True, True, True]
        self.assertFalse(ns['xunlu'](task))
        self.assertEqual(6, task.wait_click_ocr.call_count)
        task.ensure_main.assert_called_once()

    def test_xunlu_selects_bottom_bulk_claim_with_individual_claims_visible(self):
        ns = methods('DailyTask.py', {'xunlu'})
        task = Mock()
        task.box_of_screen.side_effect = lambda *coords: coords
        task.wait_ocr.side_effect = [[Mock()], True, True, False]
        selected = []
        calls = 0

        def click_ocr(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return False
            if calls == 3:
                # 2560x1600 日志中的单项领取 y=970，底部一键领取约 y=1515。
                candidates = [('领取', 2274 / 2560, 970 / 1600),
                              ('一键领取', 2225 / 2560, 1515 / 1600)]
                x1, y1, x2, y2 = kwargs['box']
                found = [name for name, x, y in candidates
                         if x1 <= x <= x2 and y1 <= y <= y2
                         and kwargs['match'][0].fullmatch(name)]
                selected.extend(found[:1])
                return bool(found)
            return True

        task.wait_click_ocr.side_effect = click_ocr
        self.assertTrue(ns['xunlu'](task))
        self.assertEqual(['一键领取'], selected)

    def test_xunlu_pass_reward_failures_never_report_success(self):
        ns = methods('DailyTask.py', {'xunlu'})
        scenarios = [
            ([False, True, True, False], [[Mock()], True]),
            ([False, True, True, True, False], [[Mock()], True]),
            ([False, True, True, True, True], [[Mock()], True, False]),
            ([False, True, True, True, True, False], [[Mock()], True, True]),
            ([False, True, True, True, True, True], [[Mock()], True, True, True]),
        ]
        for clicks, observations in scenarios:
            with self.subTest(clicks=clicks, observations=observations):
                task = Mock()
                task.wait_click_ocr.side_effect = clicks
                task.wait_ocr.side_effect = observations
                self.assertFalse(ns['xunlu'](task))
                task.wait_pop_up.assert_not_called()
                task.click.assert_not_called()
                task.ensure_main.assert_called_once()


if __name__ == '__main__':
    unittest.main()
