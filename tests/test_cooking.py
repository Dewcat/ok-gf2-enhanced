import ast
from pathlib import Path
import re
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np


# Exercise the workflow without launching the Qt/capture runtime.
SOURCE = Path(__file__).resolve().parents[1] / 'src/tasks/CookingTask.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
tree.body = [node for node in tree.body
             if not isinstance(node, (ast.Import, ast.ImportFrom))]
scope = {'re': re, 'time': time, 'np': np, 'BaseGfTask': object}
exec(compile(tree, str(SOURCE), 'exec'), scope)
CookingTask = scope['CookingTask']


class CookingTest(unittest.TestCase):
    def task(self):
        task = object.__new__(CookingTask)
        task.config = {'菜品名称': '椒香紫薯包', '循环次数': 2}
        for name in ('info_set', 'log_info', 'click', 'sleep', 'send_key',
                     'next_frame', 'scroll_relative'):
            setattr(task, name, Mock())
        task._read = Mock(return_value=[])
        return task

    def test_color_only_accepts_yellow_chef_tab(self):
        frame = np.zeros((1600, 2560, 3), dtype=np.uint8)
        frame[1200:, :500] = (60, 225, 250)  # unrelated yellow control
        self.assertFalse(scope['chef_tab_selected'](frame))
        frame[408:536, 340:420] = (60, 225, 250)
        self.assertTrue(scope['chef_tab_selected'](frame))

    def test_name_is_exact_but_allows_ocr_spaces(self):
        pattern = scope['name_pattern']('椒香紫薯包')
        self.assertTrue(pattern.fullmatch(' 椒 香紫薯包 '))
        self.assertFalse(pattern.fullmatch('椒香紫薯包子'))

    def test_already_selected_tab_is_not_clicked(self):
        task = self.task()
        task.frame = None
        task._read.return_value = [object()]
        with patch.dict(scope, chef_tab_selected=Mock(return_value=True)):
            task._select_chef_tab()
        task.click.assert_not_called()

    def test_black_tab_clicked_once_and_verified(self):
        task = self.task()
        task.frame = None
        task._read.return_value = [object()]
        with patch.dict(scope, chef_tab_selected=Mock(side_effect=[False, True])):
            task._select_chef_tab()
        task.click.assert_called_once_with(.148, .295, after_sleep=1)

    def test_scrolls_to_dish_and_verifies_detail(self):
        task = self.task()
        card = object()
        task._read.side_effect = [[], [card], [object()], []]
        task._select_dish('椒香紫薯包')
        self.assertEqual(task.scroll_relative.call_count, 2)
        task.click.assert_called_once_with(card, after_sleep=1)

    def test_wrong_detail_stops_before_invitation(self):
        task = self.task()
        task._read.side_effect = [[object()], []]
        with self.assertRaisesRegex(RuntimeError, '未确认选中'):
            task._select_dish('椒香紫薯包')

    def test_delayed_skip_and_result(self):
        task = self.task()
        animation, skip, confirm = object(), object(), object()
        # iteration 1: animation skip; 2: skip not ready; 3: skip ready;
        # iteration 4: reward heading, matching dish, confirmation, stove.
        task._read.side_effect = [[], [], [animation], [], [], [], [],
                                 [], [], [skip], [], [object()], [object()],
                                 [object()], [confirm], [], [object()]]
        task._finish_cooking('椒香紫薯包')
        self.assertEqual([call.args[0] for call in task.click.call_args_list],
                         [animation, skip, confirm])

    def test_missing_return_does_not_succeed(self):
        task = self.task()
        with patch.object(time, 'monotonic', side_effect=[0, 1, 31]):
            with self.assertRaisesRegex(RuntimeError, '未确认返回灶台'):
                task._confirm_cooking_result()

    def test_ignored_confirmation_is_retried_at_fresh_position(self):
        task = self.task()
        first, second = object(), object()
        task._read.side_effect = [[object()], [first], [object()], [second],
                                 [], [object()]]
        task._confirm_cooking_result()
        self.assertEqual([call.args[0] for call in task.click.call_args_list],
                         [first, second])

    def test_waits_for_confirmation_button_and_never_clicks_other_actions(self):
        task = self.task()
        confirm = object()
        task._read.side_effect = [[object()], [], [object()], [confirm],
                                 [], [], [], [object()]]
        task._confirm_cooking_result()
        task.click.assert_called_once_with(confirm, after_sleep=1)
        for call in task._read.call_args_list:
            if call.args[0].search('确认'):
                self.assertFalse(call.args[0].search('前往自主循环'))
                self.assertFalse(call.args[0].search('前往战役'))

    def test_approaches_stove_once_after_reward_closes(self):
        task = self.task()
        events = []
        task.click.side_effect = lambda *a, **kw: events.append('confirm')
        task.send_key.side_effect = lambda *a, **kw: events.append('move')
        # First confirm is ignored; after the second one, the label takes two
        # checks to reappear. Neither condition should cause extra movement.
        task._read.side_effect = [[object()], [object()], [object()], [object()],
                                 [], [], [], [object()]]
        task._confirm_cooking_result()
        self.assertEqual(events, ['confirm', 'confirm', 'move'])
        task.send_key.assert_called_once_with('w', down_time=.1, after_sleep=.5)

    def test_confirmation_bounds_cover_both_screenshot_layouts(self):
        task = self.task()
        task._read.side_effect = [[object()], [object()], [], [object()]]
        task._confirm_cooking_result()
        bounds = task._read.call_args_list[1].args[1]
        # Actual text rectangles in the original 2560x1600 capture and the
        # user's wider 2297x1183 screenshot, expressed as screen fractions.
        for left, top, right, bottom in ((.675, .660, .706, .685),
                                         (.706, .735, .738, .763)):
            self.assertLessEqual(bounds[0], left)
            self.assertLessEqual(bounds[1], top)
            self.assertGreaterEqual(bounds[2], right)
            self.assertGreaterEqual(bounds[3], bottom)

    def test_material_shortage_stops(self):
        task = self.task()
        task._read.return_value = [object()]
        with self.assertRaisesRegex(RuntimeError, '不足'):
            task._finish_cooking('椒香紫薯包')
        task.click.assert_not_called()

    def test_wait_timeout_is_bounded(self):
        task = self.task()
        with patch.object(time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, '超时'):
                task._finish_cooking('椒香紫薯包')

    def test_only_completed_rounds_count(self):
        task = self.task()
        for name in ('_enter_cooking', '_select_chef_tab', '_select_dish',
                     '_click_text', '_finish_cooking'):
            setattr(task, name, Mock())
        task.run()
        self.assertEqual(task._enter_cooking.call_count, 2)
        self.assertEqual(task._finish_cooking.call_count, 2)
        task.info_set.assert_any_call('已完成次数', '2/2')
        task._finish_cooking.side_effect = RuntimeError('failure')
        task.info_set.reset_mock()
        with self.assertRaises(RuntimeError):
            task.run()
        self.assertNotIn(('已完成次数', '1/2'),
                         [call.args for call in task.info_set.call_args_list])

    def test_invalid_count_rejected_before_interaction(self):
        for value in (0, -1, 1.5, '', True):
            task = self.task()
            task.config['循环次数'] = value
            with self.assertRaises(ValueError):
                task.run()
            task._read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
