import re
import time

import numpy as np

from src.tasks.BaseGfTask import BaseGfTask


def name_pattern(name):
    return re.compile(r'^\s*' + r'\s*'.join(re.escape(c) for c in name) + r'\s*$')


def chef_tab_selected(frame):
    """The chef tab is yellow when selected; other yellow controls are excluded."""
    if frame is None or not frame.size:
        return False
    height, width = frame.shape[:2]
    crop = frame[int(height * .255):int(height * .335),
                 int(width * .133):int(width * .164), :3].astype(np.int16)
    if not crop.size:
        return False
    blue, green, red = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    return float(np.mean((red > 175) & (green > 150) & (blue < 150)
                         & (red - blue > 65))) > .45


class CookingTask(BaseGfTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '自研菜品'
        self.description = '从灶台旁出现“美味烹调”提示处，或选择菜品页面开始；独立循环制作自研菜品'
        self.default_config.update({'菜品名称': '椒香紫薯包', '循环次数': 1})
        self.config_description.update({
            '菜品名称': '填写已解锁自研菜品的完整名称，每轮均核对菜名',
            '循环次数': '成功制作次数（正整数）；使用当前默认选中的人形，失败或材料不足即停止',
        })

    def _read(self, match, bounds, timeout=2):
        return self.wait_ocr(match=match, box=self.box_of_screen(*bounds),
                             time_out=timeout, raise_if_not_found=False)

    def _click_text(self, match, bounds, timeout=5):
        boxes = self._read(match, bounds, timeout)
        if not boxes:
            raise RuntimeError(f'未找到按钮：{match}，已停止制作')
        self.click(boxes[0], after_sleep=1)

    def _selection_page(self):
        return self._read(name_pattern('下一步'), (.63, .83, .86, .94), 2)

    def _enter_cooking(self):
        if self._selection_page():
            return
        entry = self._read(re.compile('美味烹调'), (.35, .25, .98, .88), 15)
        if not entry:
            raise RuntimeError('请先站到灶台旁，显示“美味烹调”，或打开选择菜品页面')
        # The activity layer hides its cursor; F interacts with the visible stove.
        self.send_key('f', after_sleep=1)
        if not self._read(name_pattern('下一步'), (.63, .83, .86, .94), 15):
            raise RuntimeError('未进入选择菜品页面，已停止制作')

    def _select_chef_tab(self):
        self.next_frame()
        if not chef_tab_selected(self.frame):
            self.click(.148, .295, after_sleep=1)
        self.next_frame()
        if not chef_tab_selected(self.frame):
            raise RuntimeError('未确认厨师帽图标变为黄色，已停止制作')
        if not self._read(re.compile('创意烹调|自研菜品'), (.18, .15, .57, .92), 5):
            raise RuntimeError('未确认自研菜品页面，已停止制作')

    def _select_dish(self, dish):
        match = name_pattern(dish)
        self.scroll_relative(.48, .45, 30)
        self.sleep(1)
        for page in range(12):
            cards = self._read(match, (.20, .20, .56, .75))
            if cards:
                self.click(cards[0], after_sleep=1)
                if not self._read(match, (.58, .19, .79, .26), 4):
                    raise RuntimeError(f'未确认选中「{dish}」，已停止制作')
                if self._read(re.compile('未解锁|可解锁|材料不足|食材不足'),
                              (.20, .20, .83, .93), 1):
                    raise RuntimeError('菜品未解锁或材料不足，已停止制作')
                return
            if page < 11:
                self.scroll_relative(.48, .45, -3)
                self.sleep(1)
        raise RuntimeError(f'未找到自研菜品「{dish}」，请检查完整名称和解锁情况')

    def _finish_cooking(self, dish):
        # Both skip controls can appear late or remain disabled briefly. Only a
        # verified reward screen ends this wait; clicking skip is not success.
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            self.next_frame()
            if self._read(re.compile('材料不足|食材不足|次数不足|无法制作'),
                          (.20, .20, .85, .90), 1):
                raise RuntimeError('材料或制作次数不足，已停止制作')
            if self._read(name_pattern('获得道具'), (.30, .10, .70, .35), 1):
                if not self._read(name_pattern(dish), (.41, .27, .82, .45), 3):
                    raise RuntimeError('制作结果的菜名不符，已停止，未计入完成次数')
                self._confirm_cooking_result()
                return
            skip = self._read(re.compile(r'^\s*跳\s*过(?:\s*动\s*画)?\s*$'),
                              (.72, 0, 1, .18), 1)
            if skip:
                self.click(skip[0], after_sleep=.5)
            else:
                # Some recipes display an extra invitation/skip confirmation.
                confirm = self._read(name_pattern('确认'), (.35, .45, .85, .85), 1)
                if confirm:
                    self.click(confirm[0], after_sleep=.5)
            self.sleep(.5)
        raise RuntimeError('等待烹调结果超时（180秒），已停止，未计入完成次数')

    def _confirm_cooking_result(self):
        # A click during the reward animation can be ignored. Re-detect the
        # visible dialog/button until it actually closes, using fresh positions.
        deadline = time.monotonic() + 30
        approached_stove = False
        while time.monotonic() < deadline:
            self.next_frame()
            if self._read(name_pattern('获得道具'), (.30, .10, .70, .35), 1):
                confirm = self._read(name_pattern('确认'), (.55, .55, .90, .88), 2)
                if confirm:
                    self.click(confirm[0], after_sleep=1)
            else:
                # Closing the reward can leave the character just outside the
                # stove's interaction range. Move once, not on every OCR retry.
                if not approached_stove:
                    self.send_key('w', down_time=.1, after_sleep=.5)
                    approached_stove = True
                if self._read(re.compile('美味烹调'), (.35, .25, .98, .88), 2):
                    return
            self.sleep(.5)
        raise RuntimeError('未确认返回灶台（结果页确认重试30秒），已停止，未计入完成次数')

    def run(self):
        dish = re.sub(r'\s+', '', str(self.config.get('菜品名称', '') or ''))
        raw_count = str(self.config.get('循环次数', '')).strip()
        if not dish or not re.fullmatch(r'[1-9]\d*', raw_count):
            raise ValueError('请填写菜品名称，并将循环次数设为正整数')
        count = int(raw_count)
        self.info_set('已完成次数', f'0/{count}')
        for index in range(count):
            self.info_set('当前步骤', f'第 {index + 1}/{count} 次：{dish}')
            self._enter_cooking()
            self._select_chef_tab()
            self._select_dish(dish)
            self._click_text(name_pattern('下一步'), (.63, .83, .86, .94))
            self._click_text(name_pattern('确认邀请'), (.63, .83, .86, .94), 10)
            self._finish_cooking(dish)
            self.info_set('已完成次数', f'{index + 1}/{count}')
        self.info_set('当前步骤', '制作完成')
        self.log_info(f'自研菜品「{dish}」已完成 {count} 次')
