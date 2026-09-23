import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


source = Path(__file__).resolve().parents[1] / 'src/tasks/DailyTask.py'
task_class = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                  if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
methods = [n for n in task_class.body if isinstance(n, ast.FunctionDef)
           and n.name in ('select_food', 'do_food_flow')]
namespace = {'re': re}
exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)


class SelectFoodTest(unittest.TestCase):
    def make_task(self, dish='九转大肠', found_page=0, locked=False, detail='九转大肠',
                  label='九 转 大 肠'):
        task = Mock()
        task.config = {'指定菜品': dish}
        task.width, task.height = 2560, 1600
        task.box_of_screen.side_effect = lambda *args: args
        state = {'page': 0}

        def scroll(x, y, count):
            state['page'] = 0 if count > 0 else state['page'] + 1

        def ocr(*, match, box, **kwargs):
            if box[0] == 0.20:
                if state['page'] == found_page and match.search(label):
                    return [SimpleNamespace(x=710, y=475, width=160, height=30)]
                return []
            if box[0] == 0.58:
                return [detail] if match.search(detail) else []
            return ['可解锁'] if locked else []

        task.scroll_relative.side_effect = scroll
        task.wait_ocr.side_effect = ocr
        return task

    def test_blank_preserves_default_without_navigation(self):
        task = self.make_task(dish='  ')
        self.assertTrue(namespace['select_food'](task))
        task.scroll_relative.assert_not_called()
        task.click.assert_not_called()

    def test_finds_spaced_name_after_scrolling_and_checks_detail(self):
        task = self.make_task(found_page=2)
        self.assertTrue(namespace['select_food'](task))
        self.assertEqual(3, task.scroll_relative.call_count)
        task.click.assert_called_once()

    def test_partial_name_is_accepted(self):
        task = self.make_task(dish='大肠')
        self.assertTrue(namespace['select_food'](task))
        task.click.assert_called_once()

    def test_icon_noise_in_card_and_detail_is_accepted(self):
        task = self.make_task(label='上★九 转 大 肠图', detail='※ 九转大肠 •')
        self.assertTrue(namespace['select_food'](task))
        task.click.assert_called_once()

    def test_unrelated_name_is_not_selected(self):
        task = self.make_task(dish='芝士烤土豆')
        self.assertFalse(namespace['select_food'](task))
        task.click.assert_not_called()
        self.assertEqual(12, task.scroll_relative.call_count)

    def test_locked_dish_is_not_clicked(self):
        task = self.make_task(locked=True)
        self.assertFalse(namespace['select_food'](task))
        task.click.assert_not_called()

    def test_unchanged_detail_is_failure(self):
        task = self.make_task(detail='糖醋狮子头')
        self.assertFalse(namespace['select_food'](task))

    def test_failed_selection_blocks_next_step_and_invitation(self):
        task = Mock()
        task.wait_ocr.return_value = True
        selector = Mock(return_value=False)
        result = namespace['do_food_flow'](
            task, enter_func=Mock(), entry_match='美味烹调', main_btn='下一步',
            second_btn='确认邀请', skip_end_match=[], before_main=selector)
        self.assertFalse(result)
        selector.assert_called_once()
        task.wait_click_ocr.assert_not_called()

    def run_drink_flow(self, task, fallback=True):
        return namespace['do_food_flow'](
            task, enter_func=Mock(), entry_match='茶歇一刻', main_btn='制作',
            second_btn='确认', skip_end_match=['饮品加成'],
            fallback_page_match=re.compile('茶歇一刻|饮品') if fallback else None)

    def test_fallback_enters_drink_page_and_continues(self):
        task = Mock()
        task.wait_ocr.side_effect = [False, True, True]
        self.assertTrue(self.run_drink_flow(task))
        task.send_key.assert_called_once_with('f', after_sleep=1)
        task.click_with_key.assert_not_called()
        task.back.assert_not_called()
        self.assertEqual('制作', task.wait_click_ocr.call_args_list[0].kwargs['match'])

    def test_fallback_wrong_page_exits_without_making_anything(self):
        task = Mock()
        task.wait_ocr.side_effect = [False, False]
        self.assertFalse(self.run_drink_flow(task))
        task.send_key.assert_called_once_with('f', after_sleep=1)
        task.back.assert_called_once_with(after_sleep=2)
        task.wait_click_ocr.assert_not_called()

    def test_fallback_drink_page_without_make_button_exits(self):
        task = Mock()
        task.wait_ocr.side_effect = [False, True, False]
        self.assertFalse(self.run_drink_flow(task))
        task.back.assert_called_once_with(after_sleep=2)
        task.wait_click_ocr.assert_not_called()

    def test_recognized_entry_does_not_press_f(self):
        task = Mock()
        task.wait_ocr.side_effect = [True, True]
        self.assertTrue(self.run_drink_flow(task))
        task.send_key.assert_not_called()
        task.click_with_key.assert_called_once()

    def test_other_food_flow_does_not_use_drink_fallback(self):
        task = Mock()
        task.wait_ocr.return_value = False
        self.assertFalse(self.run_drink_flow(task, fallback=False))
        task.send_key.assert_not_called()


if __name__ == '__main__':
    unittest.main()
