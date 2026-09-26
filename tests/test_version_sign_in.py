import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.image.version_sign_in import find_sign_in_icon, sign_in_layout, claimable_days


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'src/tasks/DailyTask.py'
task_class = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                  if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
methods = [n for n in task_class.body if isinstance(n, ast.FunctionDef)
           and n.name in ('version_sign_in', '_version_sign_in_layout')]
namespace = dict(find_sign_in_icon=find_sign_in_icon, sign_in_layout=sign_in_layout,
                 claimable_days=claimable_days, pop_ups=['点击空白处关闭'])
exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)


class VersionSignInTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = cv2.imread(str(ROOT / 'tests/images/version_sign_in.png'))

    def test_reference_at_multiple_resolutions(self):
        for width in (1280, 1920, 2560):
            with self.subTest(width=width):
                frame = cv2.resize(self.frame, (width, round(width * .625)))
                point = find_sign_in_icon(frame)
                self.assertIsNotNone(point)
                self.assertAlmostEqual(point[0] / width, .0574, delta=.003)
                self.assertAlmostEqual(point[1] / frame.shape[0], .3925, delta=.004)
                k = width / 2560
                result = claimable_days(frame, (985.5*k, 778.5*k, 190.75*k))
                self.assertEqual([4], [r[0] for r in result])

    def test_unselected_icon_and_absent_icon(self):
        frame = self.frame.copy()
        frame[300:330, 60:88] = 255 - frame[300:330, 60:88]
        self.assertIsNotNone(find_sign_in_icon(frame))
        frame[300:330, 60:88] = 0
        self.assertIsNone(find_sign_in_icon(frame))
        self.assertIsNone(find_sign_in_icon(np.zeros_like(frame)))

    def test_no_glow_and_ambiguous_glow(self):
        frame = self.frame.copy()
        layout = (985.5/2, 778.5/2, 190.75/2)
        # Copy the entire future card into today's slot; orange ticket art remains.
        frame[360:610, 738:820] = frame[360:610, 833:915]
        self.assertEqual([], claimable_days(frame, layout))
        frame = self.frame.copy()
        frame[360:610, 833:915] = frame[360:610, 738:820]
        self.assertEqual([4, 5], [r[0] for r in claimable_days(frame, layout)])

    def test_layout_rejects_unrelated_numbers(self):
        boxes = [SimpleNamespace(name=f'{i:02}', x=100+i*90, y=200, width=20, height=30)
                 for i in range(4, 8)]
        self.assertIsNotNone(sign_in_layout(boxes))
        boxes[1].y += 60
        self.assertIsNone(sign_in_layout(boxes))
        self.assertIsNone(sign_in_layout(boxes[:2]))

    def make_task(self):
        task = Mock()
        task.frame = self.frame
        task._version_sign_in_layout.return_value = (492.75, 389.25, 95.375)
        return task

    def test_only_confirmed_popup_and_state_change_succeeds(self):
        for popup, after, expected in ((True, [], True), (False, [], '待核查'),
                                       (True, [(4, 780, 470)], '待核查'),
                                       (True, None, '待核查')):
            with self.subTest(popup=popup, after=after):
                task = self.make_task()
                task.wait_ocr.return_value = popup
                with patch.dict(namespace, claimable_days=Mock(side_effect=[[(4,780,470)], after])):
                    self.assertEqual(expected, namespace['version_sign_in'](task))
                task.click.assert_any_call(780, 470, after_sleep=1)
                task.ensure_main.assert_called_once()

    def test_ambiguous_or_absent_reward_is_not_clicked(self):
        for candidates in ([], None, [(4,780,470), (5,875,470)]):
            task = self.make_task()
            with patch.dict(namespace, claimable_days=Mock(return_value=candidates)):
                namespace['version_sign_in'](task)
            self.assertEqual(1, task.click.call_count)  # menu only
            task.ensure_main.assert_called_once()

    def test_missing_entry_scan_is_bounded(self):
        task = self.make_task()
        with patch.dict(namespace, find_sign_in_icon=Mock(return_value=None)):
            namespace['version_sign_in'](task)
        self.assertEqual(5, task.scroll_relative.call_count)
        task.click.assert_not_called()
        task.ensure_main.assert_called_once()

    def test_unrecognized_page_does_not_claim(self):
        task = self.make_task()
        task._version_sign_in_layout.return_value = None
        self.assertEqual('待核查', namespace['version_sign_in'](task))
        self.assertEqual(1, task.click.call_count)
        task.ensure_main.assert_called_once()


if __name__ == '__main__':
    unittest.main()
