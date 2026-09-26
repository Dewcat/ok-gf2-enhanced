import ast
from pathlib import Path
import re
import unittest
from unittest.mock import Mock


source = Path(__file__).resolve().parents[1] / 'src/tasks/DailyTask.py'
cls = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
           if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == 'claim_activity_progress')
namespace = {'re': re, 'pop_ups': ['点击空白处关闭']}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
claim = namespace['claim_activity_progress']


class ActivityProgressTest(unittest.TestCase):
    def make_task(self, panel=True, tab=True, page=True, button=True, popup=True,
                  restored=True, empty=False):
        task = Mock()
        task.box_of_screen.side_effect = lambda *bounds: bounds
        task._ensure_activity_panel.return_value = panel
        task.wait_click_ocr.side_effect = [tab, button]
        calls = {'page': 0}

        def ocr(*, match, **kwargs):
            if isinstance(match, list):
                return popup
            if match.search('逸趣导算进度'):
                calls['page'] += 1
                return page if calls['page'] == 1 else restored
            return empty

        task.wait_ocr.side_effect = ocr
        return task

    def test_switches_tab_before_claim_and_confirms_popup(self):
        task = self.make_task()
        self.assertTrue(claim(task))
        calls = task.wait_click_ocr.call_args_list
        self.assertTrue(calls[0].kwargs['match'].search('逸趣事件'))
        self.assertTrue(calls[1].kwargs['match'].search('一键领取'))
        self.assertTrue(calls[1].kwargs['match'].search('键领取'))  # 1280px OCR omits the horizontal stroke.
        self.assertFalse(calls[1].kwargs['match'].search('前往'))
        self.assertEqual((.151, .735, .39, .83), calls[1].kwargs['box'])
        task.wait_pop_up.assert_called_once()

    def test_panel_failure_stops(self):
        task = self.make_task(panel=False)
        self.assertFalse(claim(task))
        task.wait_click_ocr.assert_not_called()

    def test_tab_failure_never_clicks_claim(self):
        task = self.make_task(tab=False)
        self.assertFalse(claim(task))
        self.assertEqual(1, task.wait_click_ocr.call_count)

    def test_wrong_page_never_clicks_claim(self):
        task = self.make_task(page=False)
        self.assertEqual('待核查', claim(task))
        self.assertEqual(1, task.wait_click_ocr.call_count)

    def test_absent_button_skips_without_success_claim(self):
        task = self.make_task(button=False)
        self.assertIsNone(claim(task))
        task.wait_pop_up.assert_not_called()

    def test_no_popup_is_uncertain(self):
        self.assertEqual('待核查', claim(self.make_task(popup=False)))

    def test_popup_without_restored_page_is_uncertain(self):
        self.assertEqual('待核查', claim(self.make_task(restored=False)))

    def test_explicit_empty_state_is_accepted(self):
        self.assertTrue(claim(self.make_task(popup=False, empty=True)))


if __name__ == '__main__':
    unittest.main()
