import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

source = Path(__file__).resolve().parents[1] / 'src/tasks/DailyTask.py'
cls = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
           if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == '_claim_xunlu_rewards')
namespace = {'re': re}
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in
           ('_claim_xunlu_rewards', 'xunlu', '_switch_xunlu_rewards_page', '_xunlu_no_reward_status', '_record_xunlu_result', 'run')]
exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)
claim = namespace['_claim_xunlu_rewards']


class XunluRewardsTest(unittest.TestCase):
    def task(self, pages, reward='数据链路', missing=False, stuck=False, show_obtained=True,
             next_buttons=0, missing_after=None):
        task = Mock()
        task.config = {}
        task.box_of_screen.side_effect = lambda *bounds: bounds
        pages = list(pages)
        if pages and show_obtained:
            pages.append('获得道具')
        clicks = []
        def ocr(**kwargs):
            return [SimpleNamespace(name=pages[0])] if pages else []
        def click(**kwargs):
            nonlocal next_buttons
            pattern = kwargs['match'][0]
            if pattern.search(reward):
                if missing or (missing_after is not None and clicks.count(reward) >= missing_after):
                    return False
                clicks.append(reward)
                return True
            expected = ('下一个' if next_buttons else '开启') if pages[0] == '拂晓之光补给包' else '确认'
            if not pattern.search(expected):
                return False
            clicks.append(expected)
            if not stuck:
                if expected == '下一个':
                    next_buttons -= 1
                else:
                    pages.pop(0)
            return True
        task.click.side_effect = lambda *args, **kwargs: pages.pop(0)
        task.wait_ocr.side_effect = ocr
        task.wait_click_ocr.side_effect = click
        return task, clicks

    def test_popup_orders_and_repeated_packs(self):
        for pages in (['领取奖励'], ['拂晓之光补给包'],
                      ['领取奖励', '拂晓之光补给包'],
                      ['拂晓之光补给包', '领取奖励'],
                      ['拂晓之光补给包', '拂晓之光补给包']):
            with self.subTest(pages=pages):
                task, clicks = self.task(pages)
                self.assertIs(True, claim(task))
                expected = []
                for page in pages:
                    expected.extend(['数据链路', '开启'] if page == '拂晓之光补给包' else ['确认'])
                self.assertEqual(expected, clicks)

    def test_missing_reward_never_opens(self):
        task, clicks = self.task(['拂晓之光补给包'], missing=True)
        self.assertFalse(claim(task))
        self.assertEqual([], clicks)

    def test_next_pages_reselect_reward_before_opening(self):
        for count in (1, 3):
            with self.subTest(next_buttons=count):
                task, clicks = self.task(['拂晓之光补给包'], next_buttons=count)
                self.assertIs(True, claim(task))
                self.assertEqual(['数据链路', '下一个'] * count + ['数据链路', '开启'], clicks)

    def test_missing_reward_on_next_page_does_not_open(self):
        task, clicks = self.task(['拂晓之光补给包'], next_buttons=1, missing_after=1)
        self.assertFalse(claim(task))
        self.assertEqual(['数据链路', '下一个'], clicks)

    def test_next_button_without_obtained_does_not_report_success(self):
        task, clicks = self.task(['拂晓之光补给包'], next_buttons=1, show_obtained=False)
        self.assertEqual('待核查', claim(task))
        self.assertEqual(['数据链路', '下一个', '数据链路', '开启'], clicks)

    def test_stuck_next_button_is_bounded(self):
        task, clicks = self.task(['拂晓之光补给包'], next_buttons=1, stuck=True)
        self.assertFalse(claim(task))
        self.assertEqual(['数据链路', '下一个'] * 8, clicks)

    def test_custom_reward(self):
        task, clicks = self.task(['拂晓之光补给包'], reward='大容量内存条')
        task.config = {'拂晓之光补给包奖励': '大容量内存条'}
        self.assertIs(True, claim(task))
        self.assertEqual(['大容量内存条', '开启'], clicks)

    def test_no_popup_is_not_success(self):
        task, clicks = self.task([])
        self.assertEqual('待核查', claim(task))
        self.assertEqual([], clicks)

    def test_confirmation_without_obtained_is_uncertain(self):
        task, clicks = self.task(['领取奖励'], show_obtained=False)
        self.assertEqual('待核查', claim(task))
        self.assertEqual(['确认'], clicks)

    def test_missing_confirmation_is_failure(self):
        task, _ = self.task(['领取奖励'])
        task.wait_click_ocr.side_effect = None
        task.wait_click_ocr.return_value = False
        self.assertIs(False, claim(task))

    def test_stuck_dialog_is_bounded_failure(self):
        task, clicks = self.task(['领取奖励'], stuck=True)
        self.assertFalse(claim(task))
        self.assertEqual(8, len(clicks))


class XunluPageSwitchTest(unittest.TestCase):
    def task(self, results):
        task = Mock()
        task.box_of_screen.side_effect = lambda *bounds: bounds
        task.wait_ocr.side_effect = results
        return task

    def test_retries_when_click_does_not_switch_page(self):
        task = self.task([False, True, False])
        self.assertTrue(namespace['_switch_xunlu_rewards_page'](task))
        self.assertEqual(2, task.wait_click_ocr.call_count)

    def test_still_on_action_page_does_not_count_as_success(self):
        task = self.task([True, True, True, False])
        self.assertTrue(namespace['_switch_xunlu_rewards_page'](task))
        self.assertEqual(2, task.wait_click_ocr.call_count)

    def test_stuck_page_stops_after_three_attempts(self):
        task = self.task([False, False, False])
        self.assertFalse(namespace['_switch_xunlu_rewards_page'](task))
        self.assertEqual(3, task.wait_click_ocr.call_count)

    def test_success_does_not_repeat_click(self):
        task = self.task([True, False])
        self.assertTrue(namespace['_switch_xunlu_rewards_page'](task))
        task.wait_click_ocr.assert_called_once()


class XunluOutcomeTest(unittest.TestCase):
    def task(self, action=True, reward=True, page_ok=True):
        task = Mock()
        task.box_of_screen.side_effect = lambda *bounds: bounds
        # optional new-season entry, daily tab, daily claim, reward claim
        task.wait_click_ocr.side_effect = [False, True, False, True]
        task._switch_xunlu_rewards_page.return_value = page_ok
        task.wait_ocr.return_value = True
        task._xunlu_no_reward_status.return_value = action
        task._claim_xunlu_rewards.return_value = reward
        task._record_xunlu_result.side_effect = lambda name, result: namespace['_record_xunlu_result'](task, name, result)
        return task

    def test_reward_success_not_overwritten_by_absent_daily_button(self):
        task = self.task(action='待核查', reward=True)
        self.assertEqual('待核查', namespace['xunlu'](task))
        task._record_xunlu_result.assert_any_call('巡录奖励', True)
        self.assertFalse(any('执行失败' in call.args[0] for call in task.log_info.call_args_list))

    def test_confirmed_no_rewards_is_success(self):
        task = self.task()
        self.assertIs(True, namespace['xunlu'](task))

    def test_failed_switch_never_claims_rewards(self):
        task = self.task(page_ok=False)
        self.assertIs(False, namespace['xunlu'](task))
        task._claim_xunlu_rewards.assert_not_called()
        self.assertEqual(3, task.wait_click_ocr.call_count)
        task._record_xunlu_result.assert_any_call('巡录奖励', False)
        task.ensure_main.assert_called_once()

    def test_real_failure_takes_precedence(self):
        for action, reward in [(False, True), (True, False), ('待核查', False)]:
            task = self.task(action=action, reward=reward)
            self.assertIs(False, namespace['xunlu'](task))

    def test_daily_click_verified_by_page_and_button_transition(self):
        task = self.task()
        task.wait_click_ocr.side_effect = [False, True, True, True, True]
        task.wait_ocr.side_effect = [True, True, True, False]
        self.assertIs(True, namespace['xunlu'](task))
        task._record_xunlu_result.assert_any_call('每日行动', True)

    def test_daily_button_persists_after_click_is_failure(self):
        task = self.task()
        task.wait_click_ocr.side_effect = [False, True, True, True, True]
        self.assertIs(False, namespace['xunlu'](task))
        task._record_xunlu_result.assert_any_call('巡录奖励', True)

    def test_unrecognized_daily_result_is_not_success(self):
        task = self.task()
        task.wait_click_ocr.side_effect = [False, True, True, True, True]
        task.wait_ocr.side_effect = [True, True, False]
        self.assertEqual('待核查', namespace['xunlu'](task))

    def test_absent_reward_button_is_uncertain_without_evidence(self):
        task = self.task(action='待核查')
        task.wait_click_ocr.side_effect = [False, True, False, False]
        self.assertEqual('待核查', namespace['xunlu'](task))
        task._claim_xunlu_rewards.assert_not_called()

    def test_wrong_reward_page_is_failure(self):
        task = self.task()
        task.wait_click_ocr.side_effect = [False, True, False, False]
        task.wait_ocr.side_effect = [True, True, False]
        self.assertIs(False, namespace['xunlu'](task))

    def test_no_reward_requires_explicit_whole_page_notice(self):
        for label, expected in [('已全部领取', True), ('暂无可领取奖励', True),
                                ('已领取', '待核查'), ('每日行动', '待核查'), ('', '待核查')]:
            task = Mock()
            task.wait_ocr.side_effect = lambda label=label, **kw: bool(kw['match'][0].search(label))
            self.assertEqual(expected, namespace['_xunlu_no_reward_status'](task))

    def test_runner_does_not_announce_success_for_unknown(self):
        for result, expected in [('待核查', '结果待核查'), (False, '未完成或失败'), (True, '日常完成!')]:
            task = Mock()
            task.config = {'已确认启用游戏内全局自动功能': True, '大月卡': True}
            task.xunlu.return_value = result
            namespace['run'](task)
            messages = [call.args[0] for call in task.log_info.call_args_list]
            self.assertTrue(any(expected in message for message in messages))
            if result != True:
                self.assertNotIn('日常完成!', messages)
            if result == '待核查':
                self.assertFalse(any('未完成或失败' in message for message in messages))


if __name__ == '__main__':
    unittest.main()
