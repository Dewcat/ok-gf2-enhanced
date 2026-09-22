import re
import time
from ok import Logger, find_boxes_by_name, Box
from src.tasks.BaseGfTask import BaseGfTask, pop_ups, stamina_re, map_re, parse_time_option
from src.tasks.CommunityClient import CommunityMixin
from src.image.hsv_config import HSVRange as hR

logger = Logger.get_logger(__name__)

activity_time_re = re.compile(r'^(\d+)\s*(?:天|days?)\s*(\d+)\s*(?:小时|hours?)', re.I)


class DailyTask(CommunityMixin, BaseGfTask):
    def wait_ocr_until_count(self, match, box=None, min_count=2, timeout=5, interval=0.5, **kwargs):
        """
        固定时间内循环OCR，检测到对象数>=min_count立即返回，否则超时。
        """
        start_time = time.time()
        while True:
            results = self.wait_ocr(match=match, box=box, raise_if_not_found=False, time_out=interval, **kwargs)
            if results and len(results) >= min_count:
                return results
            if time.time() - start_time >= timeout:
                return results  # 可能为None或不足min_count

    def __init__(self, *args, **kwargs):
        """
            该模块总启动配置
        """
        super().__init__(*args, **kwargs)
        self.name = "一键日常"
        self.description = "收菜"
        self.support_schedule_task = True
        self._init_default_config()
        self._init_stamina_options()
        self._init_default_config_group()
        self.add_exit_after_config()

    def _init_default_config(self):
        """

            输入框和选择框配置

        """
        auto_loop_skip_list = ['体力本', '自动刷体力', '刷钱本', '竞技场']
        auto_loop_skip_dict = {i: "开启自主循环后会跳过该项" for i in auto_loop_skip_list}
        self.config_description.update(auto_loop_skip_dict | {
            '已确认启用游戏内全局自动功能': (
                '运行前必须先在游戏内开启全局自动战斗\n'
                '（设置 → 其他 → 自动战斗设置），开启后勾选本项'
            ),
            '当前物资关卡名称': (
                '活动自律中当前大活动的名称\n'
                '例：铸碑者的黎明'
            ),
            '用户名': '使用账户密码方式登录网页社区时(不是直接的手机号或邮箱)\n account 请求负载中的 account_name 的值',
            '密码': '使用账户密码方式登录网页社区时(不是直接的密码)\n account 请求负载中的 passwd 的值',
            '喝水': (
                '活动层喝水动作的按键时长，格式：a键时长-w键时长-d键时长\n'
                '例：1.087-1.4-0.5'
            ),
            '吃饭': (
                '活动层吃饭动作的按键时长，格式：时长（秒）\n'
                '例：1.0'
            ),
            '社区每日': '自动完成社区每日任务（需填写用户名和密码）',
            '邮件': '自动领取邮件中的所有奖励',
            '情报/战前补给': '自动领取活动页面中的情报补给奖励',
            '战前补给': '自动领取活动页面中的战前补给奖励',
            '闪耀星愿': '自动完成活动页面中的闪耀星愿关卡',
            '活动自律': (
                '自动进入限时开启活动并挑战物资关卡\n'
                '关卡名称在"当前物资关卡名称"中配置'
            ),
            '活动层': '活动层总开关；按下方独立开关执行喝水、吃饭、浇花，并领取奖励',
            '活动层喝水': '独立控制喝水任务，关闭后跳过喝水',
            '活动层吃饭': '独立控制吃饭任务，关闭后跳过吃饭',
            '指定菜品': '填写常规菜品完整名称，如九转大肠；留空使用默认菜品。自动翻找，未找到或未解锁则跳过吃饭',
            '活动层浇花': '独立控制栽培浇灌任务，关闭后跳过浇花；不施肥',
            '公共区/调度室': '自动完成公共区委托的派遣与领取',
            '自主循环': (
                '开启后公共区将启动游戏内自主循环模式\n'
                '同时跳过：体力本、自动刷体力、刷钱本、竞技场'
            ),
            '购买免费礼包': '自动购买商城中的免费礼包',
            '商店心愿单购买': (
                '自动在各商店（家具/班组/调度/讯段/心智/人形堆栈）中\n'
                '一键购买心愿单商品'
            ),
            "尘烟": '需开启班组项',
            '领任务': '自动领取委托中的每日任务奖励',
            '大月卡': '先领取沿途行动奖励，再领取远航巡录奖励并确认；支持新一期巡录开启入口',
            '拂晓之光补给包奖励': '远航巡录领取时自动选择的补给包奖励，默认数据链路',
            '探索领取': '自动领取边界推进探索区域的采集与派遣奖励'
        })
        self.default_config.update({
            '已确认启用游戏内全局自动功能': False,
            '当前物资关卡名称': '铸碑者的黎明',
            '体力本': "军备解析",
            '用户名': "",
            '密码': "",
            '喝水': '1.087-1.4-0.5',
            '吃饭': '1.0',
            '指定菜品': '',
            "社区每日": False,
            '邮件': True,
            '情报和战前补给': True,
            '闪耀星愿': False,
            '活动自律': True,
            '活动层': True,
            '活动层喝水': True,
            '活动层吃饭': True,
            '活动层浇花': True,
            '公共区/调度室': True,
            '自主循环': False,
            '购买免费礼包': True,
            '商店心愿单购买': True,
            '自动刷体力': True,
            '刷钱本': False,
            '竞技场': True,
            '班组': True,
            '尘烟': True,
            '领任务': True,
            '大月卡': True,
            '拂晓之光补给包奖励': '数据链路',
            '探索领取': True
        })

    def _init_stamina_options(self):
        """

            下拉框配置

        """
        self.config_type['拂晓之光补给包奖励'] = {
            'type': 'drop_down',
            'options': ['数据链路', '坍塌晶条', '增域存量条T2', '大容量内存条', '转录导体·序三', '萨狄斯金'],
        }
        self.stamina_options = ['军备解析', '深度搜索', '决策构象', '定向']
        self.config_type["体力本"] = {'type': "drop_down", 'options': self.stamina_options}

    def _init_default_config_group(self):
        """
            配置组，开启自主循环后会跳过的项目

        """
        self.default_config_group.update({
            "社区每日": ["用户名", "密码"],
            "大月卡": ["拂晓之光补给包奖励"],
            "活动自律": ["当前物资关卡名称"],
            "活动层": ["活动层喝水", "活动层吃饭", "活动层浇花"],
            "活动层喝水": ["喝水"],
            "活动层吃饭": ["吃饭", "指定菜品"],
            "公共区/调度室": ["自主循环"],
            "自主循环跳过项": ["自动刷体力", "刷钱本", "竞技场"],
            "购买免费礼包": ["商店心愿单购买"],
            "自动刷体力": ["体力本"],
            "班组": ["尘烟"],
        })
        for group, keys in self.default_config_group.items():
            self.config_type.update({group: {'sub_configs': {True: keys}}})

    def run(self):
        if not self.config.get('已确认启用游戏内全局自动功能'):
            self.confirm_auto_battle_up()
        tasks = [
            ("社区每日", self.community_daily),
            ("ensure_main", lambda: self.ensure_main(
                recheck_time=2,
                time_out=90
            )),
            ('邮件', self.mail),
            ('情报和战前补给', self.activities),
            ('活动自律', self.activity),
            ('活动层', self.free_time_layer),
            ('公共区/调度室', self.gongongqu),
            ('购买免费礼包', self.shopping),
            ('自动刷体力', self.battle),
            ('竞技场', self.arena),
            ('班组', self.guild),
            ('探索领取', self.explore_claim),
            ('闪耀星愿', self.star_wish),
            # 完成其他任务后统一领取订单，随后领取依赖日活跃度的巡录奖励。
            ('领任务', self.claim_quest),
            ('大月卡', self.xunlu),
        ]

        failed_tasks = []
        uncertain_tasks = []
        for key, func in tasks:
            # -------- 关键逻辑开始 --------
            if key != "ensure_main":
                # 统一转为列表
                keys = [key] if isinstance(key, str) else list(key)

                # or 规则：任一为 True 即执行
                if not any(self.config.get(k) for k in keys):
                    continue
            self.ensure_main(recheck_time=2, time_out=90)
            result = func()  # 不捕获异常，异常自然向上传递
            if result is False:
                self.log_info(f"任务 {key} 执行失败或未完成")
                failed_tasks.append(key)
            elif result == '待核查':
                uncertain_tasks.append(key)

        if failed_tasks:
            self.log_info(f"以下任务未完成或失败: {failed_tasks}", notify=True)
        if uncertain_tasks:
            self.log_info(f"以下任务结果待核查（未计为失败或成功）: {uncertain_tasks}", notify=True)
        if not failed_tasks and not uncertain_tasks:
            self.log_info("日常完成!", notify=True)

    def explore_claim(self):
        self.info_set('current_task', 'explore_claim')
        if not self.wait_click_ocr(match='限时开启', box=self.box.top_right, after_sleep=2, time_out=2,
                                   raise_if_not_found=True, log=True):
            return
        if not self.wait_click_ocr(match=re.compile('边界推进'), box=self.box.top_right, after_sleep=6, time_out=2,
                                   raise_if_not_found=True, log=True):
            return
        if not self.wait_click_ocr(match=re.compile('采集'), box=self.box.bottom_right, after_sleep=2, time_out=2,
                                   raise_if_not_found=True, log=True):
            return
        if not self.wait_click_ocr(match=re.compile('领取'), box=self.box.bottom_right, time_out=2,
                                   raise_if_not_found=True, after_sleep=2, log=True):
            return
        self.wait_pop_up(count=1)
        if not self.wait_click_ocr(match=re.compile('派遣'), box=self.box.bottom_right, after_sleep=2, time_out=2,
                                   raise_if_not_found=False, log=True):
            return

    def community_daily(self):
        user = self.config.get('用户名')
        pwd = self.config.get('密码')
        self.info_set('current_task', 'community_daily')
        self.run_community_flow(user, pwd)

    def confirm_auto_battle_up(self):
        """
        确认启用游戏内的全局自动战斗
        如果未启用，抛出异常提醒用户
        """
        raise Exception(
            "请先确认启用游戏内的全局自动战斗(设置->其他->自动战斗设置),"
            "然后勾选本软件内一键日常内的确认项"
        )

    def go_drink(self, after_sleep=None):
        down_times = parse_time_option((self.config.get('喝水')))
        self.press_keys_sequence(['a', 'w', 'd'], down_times, sleep_between=0.5)
        if after_sleep and after_sleep > 0:
            self.sleep(after_sleep)

    def go_eat(self, after_sleep=None):
        down_time = float(self.config.get('吃饭'))
        self.press_keys_sequence(['s', 'd'], [down_time, 0], sleep_between=1)
        if after_sleep and after_sleep > 0:
            self.sleep(after_sleep)

    def do_food_flow(
            self,
            *,
            enter_func,
            entry_match,
            main_btn,
            second_btn,
            skip_end_match,
            need_extra_confirm=False,
            need_again_test=False,
            before_main=None
    ):
        enter_func(after_sleep=1)
        times = 1
        if need_again_test:
            times = 2
        for attempt in range(times):
            if result := self.wait_ocr(match=entry_match, time_out=3):
                self.click_with_key('alt', result)
            else:
                return False
            if self.wait_ocr(match=main_btn, box=self.box.bottom_right, time_out=10):
                if before_main is not None and not before_main():
                    return False
                if not self.wait_click_ocr(match=main_btn, box=self.box.bottom_right, time_out=3):
                    return False
                if self.wait_click_ocr(match=second_btn, time_out=3, after_sleep=2):
                    if need_extra_confirm:
                        self.wait_click_ocr(match='确认', time_out=3, after_sleep=1)
                    self.skip_dialogs(end_match=skip_end_match, time_out=60)
                    self.wait_click_ocr(match="确认", time_out=3, box = self.box.bottom, after_sleep=1)
                    self.wait_pop_up(count=1)
                return True
            else:
                if need_again_test and attempt == 0:
                    continue
                else:
                    self.back(after_sleep=2)
                    return False
        return False

    def select_food(self):
        dish = re.sub(r'\s+', '', self.config.get('指定菜品', '') or '')
        if not dish:
            return True
        # 包含匹配：允许菜名前后混入图标字符，以及文字之间的空格。
        dish_match = re.compile(r'\s*'.join(re.escape(c) for c in dish))
        grid = self.box_of_screen(0.20, 0.20, 0.56, 0.75)
        detail = self.box_of_screen(0.58, 0.19, 0.72, 0.26)
        self.scroll_relative(0.48, 0.45, 30)
        self.sleep(1)
        for page in range(12):
            boxes = self.wait_ocr(match=dish_match, box=grid, time_out=2,
                                  raise_if_not_found=False, log=True)
            if boxes:
                card = boxes[0]
                center_x = (card.x + card.width / 2) / self.width
                name_bottom = (card.y + card.height) / self.height
                status = self.box_of_screen(center_x - 0.033, name_bottom,
                                             center_x + 0.033, min(name_bottom + 0.04, 0.755))
                if self.wait_ocr(match=re.compile('可解锁|未解锁'), box=status, time_out=1,
                                 raise_if_not_found=False):
                    self.log_error(f'指定菜品「{dish}」未解锁，跳过吃饭')
                    return False
                self.click(card, after_sleep=1)
                if self.wait_ocr(match=dish_match, box=detail, time_out=3,
                                 raise_if_not_found=False, log=True):
                    self.log_info(f'已选择菜品：{dish}')
                    return True
                self.log_error(f'未确认选中菜品「{dish}」，跳过吃饭')
                return False
            if page < 11:
                self.scroll_relative(0.48, 0.45, -3)
                self.sleep(1)
        self.log_error(f'未找到指定菜品「{dish}」，跳过吃饭；请检查完整名称及是否已解锁')
        return False

    def free_time_layer(self):
        self.info_set('current_task', 'free_time_layer')
        completed = True
        enabled_steps = [i for i, key in enumerate(('活动层喝水', '活动层吃饭', '活动层浇花'))
                         if self.config.get(key, True)] + [3]
        reuse_layer = False
        for position, i in enumerate(enabled_steps):
            if not reuse_layer:
                self.wait_click_ocr(match='活动层', box=self.box.right, time_out=2, raise_if_not_found=True)
            reuse_layer = False
            food_completed = False
            if self.is_free_layer():
                if i == 0:
                    food_completed = self.do_food_flow(
                        enter_func=self.go_drink,
                        entry_match=re.compile('茶歇一刻'),
                        main_btn='制作',
                        second_btn='确认',
                        skip_end_match=['饮品加成'],
                        need_extra_confirm=False
                    )

                elif i == 1:
                    food_completed = self.do_food_flow(
                        enter_func=self.go_eat,
                        entry_match=re.compile('美味烹调'),
                        main_btn='下一步',
                        second_btn='确认邀请',
                        skip_end_match=['前往战役'],
                        need_extra_confirm=True,
                        need_again_test=True,
                        before_main=self.select_food
                    )
                elif i == 2:
                    if not self.water_flowers():
                        completed = False
                else:
                    self.send_key("f2", after_sleep=2)
                    self.wait_click_ocr(match=re.compile('领取'), box=self.box_of_screen(0.151, 0.772, 0.385, 0.883),
                                        time_out=10, raise_if_not_found=False, log=True)
                    self.wait_pop_up(count=1)
            else:
                self.log_error('没检测到活动层页面')
                completed = False
            if i in (0, 1) and not food_completed:
                completed = False
            next_step = enabled_steps[position + 1] if position + 1 < len(enabled_steps) else None
            # 走路任务之间仍需重置起点；只有紧接浇花时才复用当前活动层。
            if i in (0, 1) and food_completed and next_step == 2:
                reuse_layer = self.is_free_layer(time_out=3)
                if reuse_layer:
                    self.log_info('留在活动层，继续执行浇花')
            if not reuse_layer:
                self.ensure_main(time_out=60)
        return completed

    def _ensure_activity_panel(self):
        panel_match = re.compile(
            r'逸\s*趣\s*事\s*件|宜\s*居\s*值|栽\s*培|生\s*长\s*阶\s*段|浇\s*灌')
        panel_box = self.box_of_screen(0.13, 0.16, 0.87, 0.82)

        def is_open(timeout):
            return bool(self.wait_ocr(match=panel_match, box=panel_box,
                                      time_out=timeout, raise_if_not_found=False, log=True))

        # 已打开时不要再次按 F2，以免把面板关闭。
        if is_open(1):
            self.log_info('活动层面板已打开')
            return True
        for attempt in range(2):
            self.log_info(f'尝试打开活动层面板：发送 F2（第 {attempt + 1}/2 次）')
            self.send_key('f2', down_time=0.15, after_sleep=1)
            if is_open(4):
                self.log_info('已确认 F2 面板打开')
                return True
        self.log_info('F2 后未检测到面板，尝试点击顶部 F2 入口')
        if self.wait_click_ocr(match=re.compile(r'^F\s*2$'),
                               box=self.box_of_screen(0.65, 0, 0.74, 0.12),
                               time_out=2, raise_if_not_found=False, after_sleep=1, log=True):
            if is_open(4):
                self.log_info('点击入口后已确认活动层面板打开')
                return True
        self.log_error('活动层 F2 面板未打开：按键重试及入口点击未成功，跳过浇花')
        return False

    def water_flowers(self):
        self.info_set('current_task', 'water_flowers')
        if not self._ensure_activity_panel():
            return False
        watering_match = re.compile(r'浇\s*灌')
        # F2 可能直接选中栽培页；优先识别内容，避免依赖选中页签的黑字。
        on_watering_page = self.wait_ocr(match=watering_match, box=self.box.right,
                                         time_out=2, raise_if_not_found=False)
        on_overview = False
        if not on_watering_page:
            on_overview = self.wait_ocr(match=re.compile(r'栽\s*培\s*天\s*数|生\s*长\s*阶\s*段'),
                                        box=self.box_of_screen(0.36, 0.43, 0.85, 0.59),
                                        time_out=2, raise_if_not_found=False, log=True)
        if on_overview:
            self.log_info('F2 已打开栽培概览，直接前往浇灌')
        if not on_watering_page and not on_overview:
            # 未进入栽培页时才切换页签，允许文字前带图标。
            if not self.wait_click_ocr(match=re.compile(r'栽\s*培'),
                                       box=self.box_of_screen(0.30, 0.15, 0.42, 0.25),
                                       time_out=10, raise_if_not_found=False, after_sleep=2, log=True):
                self.log_error('未找到栽培入口，跳过浇花')
                return False
        if not self.wait_ocr(match=watering_match, box=self.box.right, time_out=3,
                             raise_if_not_found=False):
            # 部分界面先显示栽培概览，需点击“前往”才进入花盆页面。
            if not self.wait_click_ocr(match=re.compile('前往'), box=self.box.bottom_right,
                                       time_out=5, raise_if_not_found=False, after_sleep=3, log=True):
                self.log_error('栽培页面未找到浇灌或前往入口')
                return False
        if not self.wait_ocr(match=watering_match, box=self.box.right, time_out=10,
                             raise_if_not_found=False):
            self.log_error('未进入浇灌页面，跳过浇花')
            return False
        # 仅检查浇灌按钮下方次数，避免把施肥的 1/1 当成浇水完成。
        count_box = self.box_of_screen(0.75, 0.51, 0.87, 0.59)
        done_match = re.compile(r'^\s*1\s*[/／]\s*1\s*$')
        if self.wait_ocr(match=done_match, box=count_box, time_out=1, raise_if_not_found=False):
            self.log_info('今日已浇灌，跳过重复浇花')
            self.back(after_sleep=2)
            return True
        if not self.wait_click_ocr(match=watering_match, box=self.box.right, time_out=5,
                                   raise_if_not_found=False, after_sleep=2, log=True):
            self.log_error('未找到浇灌按钮，跳过浇花')
            return False
        self.wait_pop_up(count=1, time_out=5)
        completed = bool(self.wait_ocr(match=done_match, box=count_box, time_out=10,
                                       raise_if_not_found=False, log=True))
        if not completed:
            self.log_error('点击浇灌后未检测到次数 1/1，浇花未确认完成')
        # 关闭栽培页面后，由活动层共用的 ensure_main 处理退出确认。
        self.back(after_sleep=2)
        return completed

    def activities(self):
        self.info_set('current_task', 'activity_stamina')
        self.wait_click_ocr(match=['活动'], box=self.box._activities, after_sleep=0.5, raise_if_not_found=True)
        reward_activities = ['情报补给', '战前补给']
        for reward_activity in reward_activities:
            if self.wait_click_ocr(match=reward_activity, box=self.box.left, time_out=3, raise_if_not_found=False):
                while self.wait_click_ocr(match=['领取'], box=self.box.right, time_out=3,
                                        raise_if_not_found=False,
                                        after_sleep=0.2):
                    self.wait_pop_up(time_out=6, count=1)
        self.ensure_main()

    def star_wish(self):
        self.info_set('current_task', 'star_wish')
        if not self.wait_click_ocr(match=[re.compile("闪耀星愿")], box=self.box_of_screen(0.036, 0.185, 0.229, 0.819), time_out=3, settle_time=0.5):
            self.ensure_main()
            return

        if not self.wait_click_ocr(match=['开始作战'], box=self.box.bottom_right, time_out=3, settle_time=0.5,
                                   after_sleep=0.5):
            if self.wait_click_ocr(match=re.compile("一{0,1}键领取"), box=self.box.bottom_right, time_out=3, settle_time=0.5,
                                   after_sleep=0.5):
                self.wait_pop_up(count=1)
                self.ensure_main()
                return
            self.log_info('闪耀星愿未找到开始作战和一键领取，尝试跳过对话框后重试', notify=True)
            result = self.skip_dialogs(end_match=['开始作战'], end_box=self.box.bottom_right, time_out=30,
                                       has_dialog=True, raise_if_not_found=False)
            if not result:
                self.ensure_main()
                return
            self.click_box(result, after_sleep=1)
        if self.wait_click_ocr(match=['取消'], time_out=1, after_sleep=0.5):
            self.ensure_main()
            return
        self.auto_battle(need_click_auto=True)
        self.wait_click_ocr(match=['自律'], box=self.box.bottom_right, after_sleep=0.5, settle_time=0.5)
        self.fast_combat(click_all=True, set_cost=1)
        self.ensure_main()

    def claim_quest(self):
        self.info_set('current_task', 'claim_quest')
        if result := self.wait_ocr(match=re.compile('委托'), box=self.box._claim, raise_if_not_found=True):
            self.click_box_by_match_position(result, "委托", after_sleep=2)
            self.wait_click_ocr(match=[re.compile('领取')], box=self.box_of_screen(1423/1920,939/1080,1,1), time_out=6,
                                log=True,raise_if_not_found=False, after_sleep=2)
            results = self.wait_ocr(match=['领取全部', '已全部领取'], box=self.box.left, time_out=15, log=True)
            # if results and results[0].name == '一键领取':
            if results:
                if results[0].name == '领取全部':
                    self.click(results[0])
                    self.wait_pop_up(time_out=4, count=1)
                elif results[0].name == '已全部领取':
                    pass
                else:
                    self.log_error("未知的领取状态")
            else:
                self.log_error("委托未领取")
        self.ensure_main()

    def mail(self):
        self.info_set('current_task', 'mail')
        if self.is_adb():
            self.click(0.07, 0.63)
        else:
            self.click(0.06, 0.7)
        self.wait_click_ocr(match=['领取全部'], box=self.box.bottom_left, time_out=4, after_sleep=2,
                            raise_if_not_found=False)
        self.ensure_main()

    def xunlu(self):
        self.info_set('current_task', 'xunlu')
        self.info_set('每日行动', '未检查')
        self.info_set('巡录奖励', '未检查')
        box = self.wait_ocr(match=[re.compile(r'^巡录$')], box=self.box._xunlun, time_out=3, raise_if_not_found=False)
        if not box:
            self.log_info('未找到「巡录」入口，跳过')
            self.ensure_main()
            return False
        self.click_box_by_match_position(box, '巡录', after_sleep=2)
        # 预览页入口是可选的；通行证奖励页并不是每日行动页。
        if self.wait_click_ocr(match=[re.compile(r'^开启远航巡录$')], box=self.box.bottom_left,
                               time_out=3, raise_if_not_found=False, after_sleep=2):
            self.log_info('已通过「开启远航巡录」进入大月卡主页')
        # 必须切换到沿途行动；两个页面都有“一键领取”，不能仅凭按钮判断。
        if not self.wait_click_ocr(match=[re.compile(r'^沿途行动$')], box=self.box.top,
                                   time_out=4, raise_if_not_found=False, after_sleep=1):
            self.log_info('未找到「沿途行动」页签，巡录每日奖励未完成')
            self.ensure_main()
            return False
        if not self.wait_ocr(match=[re.compile(r'^每日行动$')], box=self.box.left,
                             time_out=4, raise_if_not_found=False):
            self.log_info('未确认进入每日行动页面，跳过领取')
            self.ensure_main()
            return False
        # 分别确认行动里程和巡录道具，不能用行动按钮是否存在决定整项成败。
        action_box = self.box_of_screen(0.70, 0.88, 1, 1)
        claim_match = re.compile(r'^一\s*键\s*领\s*取$')
        clicked = self.wait_click_ocr(match=[claim_match], box=action_box, time_out=4,
                                      raise_if_not_found=False, after_sleep=1)
        if clicked:
            # 行动里程直接入账：确认仍在行动页，且原先可见的领取按钮消失。
            if not self.wait_ocr(match=[re.compile(r'^每日行动$')], box=self.box.left,
                                 time_out=3, raise_if_not_found=False):
                action_result = '待核查'
            elif self.wait_ocr(match=[claim_match], box=action_box,
                               time_out=2, raise_if_not_found=False):
                self.log_error('每日行动点击领取后按钮仍在，未确认领取完成')
                action_result = False
            else:
                action_result = True
        else:
            action_result = self._xunlu_no_reward_status()
        self._record_xunlu_result('每日行动', action_result)
        # 先收集行动里程，再回到远航巡录页领取等级/盈余奖励。
        if not self.wait_click_ocr(match=[re.compile(r'^远航巡录$')],
                                   box=self.box_of_screen(0.25, 0, 0.65, 0.12),
                                   time_out=4, raise_if_not_found=False, after_sleep=1):
            self.log_error('未能切换到远航巡录，奖励领取未完成')
            self.ensure_main()
            return False
        if self.wait_click_ocr(match=[claim_match], box=self.box.bottom_right, time_out=4,
                               raise_if_not_found=False, after_sleep=1):
            reward_result = self._claim_xunlu_rewards()
        else:
            # 必须仍在巡录页；不能把错误页面上的按钮缺失当作已领取。
            if not self.wait_ocr(match=[re.compile(r'^大奖预览$|^通行证$')],
                                 box=self.box_of_screen(0, 0, 1, 1),
                                 time_out=3, raise_if_not_found=False):
                self.log_error('未确认巡录奖励页面，无法检查领取状态')
                reward_result = False
            else:
                reward_result = self._xunlu_no_reward_status()
        self._record_xunlu_result('巡录奖励', reward_result)
        self.ensure_main()
        if action_result is False or reward_result is False:
            return False
        if action_result == '待核查' or reward_result == '待核查':
            return '待核查'
        return True

    def _xunlu_no_reward_status(self):
        # 仅接受明确的整体状态；单条任务的“已领取”不能证明全部领完。
        if self.wait_ocr(match=[re.compile(r'^\s*(?:已全部领取|全部已领取|暂无可领取奖励|无可领取奖励)\s*$')],
                         box=self.box.bottom_right, time_out=2, raise_if_not_found=False, log=True):
            return True
        return '待核查'

    def _record_xunlu_result(self, name, result):
        status = ('领取已确认／已无可领取奖励' if result is True else
                  '执行失败' if result is False else '待核查：缺少领取结果证据')
        self.info_set(name, status)
        self.log_info(f'{name}：{status}')

    def _claim_xunlu_rewards(self):
        # 自选补给包可能直接出现，也可能跟在普通奖励确认之后。
        pack_title = re.compile(r'^拂晓之光补给包$')
        reward_title = re.compile(r'^领取奖励$')
        obtained_title = re.compile(r'^获得道具$')
        obtained = False
        for _ in range(8):
            titles = self.wait_ocr(match=[pack_title, reward_title, obtained_title],
                                   box=self.box_of_screen(0, 0, 1, 1),
                                   time_out=4, raise_if_not_found=False, log=True)
            if not titles:
                if obtained:
                    return True
                self.log_info('未看到获得道具，巡录领取结果待核查')
                return '待核查'
            if any(obtained_title.search(title.name) for title in titles):
                obtained = True
                self.log_info('巡录已显示获得道具，确认奖励到账')
                self.click(0.5, 0.95, after_sleep=1)
                continue
            if any(pack_title.search(title.name) for title in titles):
                reward = self.config.get('拂晓之光补给包奖励', '数据链路')
                if not reward:
                    self.log_error('未配置拂晓之光补给包奖励，请手动选择')
                    return False
                reward_match = re.compile(r'^\s*' + r'\s*'.join(re.escape(c) for c in reward) + r'\s*$')
                if not self.wait_click_ocr(match=[reward_match],
                                           box=self.box_of_screen(0.20, 0.34, 0.80, 0.53),
                                           time_out=4, raise_if_not_found=False, after_sleep=0.5):
                    self.log_error(f'补给包未找到配置奖励「{reward}」，请手动选择')
                    return False
                button = re.compile(r'^开启$')
                # 仅匹配选择弹窗底部右侧的“开启”。
                button_box = self.box_of_screen(0.51, 0.67, 0.71, 0.76)
            else:
                button = re.compile(r'^确认$')
                button_box = self.box.bottom_right
            if not self.wait_click_ocr(match=[button], box=button_box,
                                       time_out=4, raise_if_not_found=False, after_sleep=1, log=True):
                self.log_error('未找到巡录奖励弹窗操作按钮，领取未完成')
                return False
        self.log_error('巡录奖励弹窗连续出现或未关闭，请手动检查')
        return False

    def _box_center_ratio(self, box):
        return (
            (box.x + box.width / 2) / self.width,
            (box.y + box.height / 2) / self.height,
        )

    def _filter_boxes_near_candidates(
            self, row_boxes, candidate_boxes, max_x_distance=0.15, max_y_distance=0.06
    ):
        filtered = []
        for row_box in row_boxes:
            row_x, row_y = self._box_center_ratio(row_box)
            for candidate in candidate_boxes:
                candidate_x, candidate_y = self._box_center_ratio(candidate)
                x_distance = abs(row_x - candidate_x)
                y_distance = abs(row_y - candidate_y)
                if x_distance <= max_x_distance and y_distance <= max_y_distance:
                    filtered.append(row_box)
                    break

        return filtered

    def _chapter_click_order(self, box):
        if re.search("下[篇筒]", box.name):
            return 0
        if re.search("中[篇筒]", box.name):
            return 1
        if re.search("上[篇筒]", box.name):
            return 2
        return 3

    def activity(self):
        activity_wuzi_names = [name.strip() for name in str(self.config.get('当前物资关卡名称')).split("-")]
        self.info_set('current_task', 'activity')
        if to_activity_page := self.wait_click_ocr(match=['限时开启'], box=self.box.top_right, after_sleep=2,
                                                   raise_if_not_found=False,
                                                   time_out=4):
            if activities := self.wait_ocr(match=['开启中'], box=self.box.bottom_left, time_out=4):
                activity_count = 0
                for activity in activities:
                    self.ensure_main()
                    self.click(to_activity_page, after_sleep=2)
                    self.click(activity)
                    if activity_count >= len(activity_wuzi_names):
                        activity_count -= 1
                    name_re = activity_wuzi_names[activity_count]
                    chapter_re = re.compile(rf"{re.escape(name_re)}[·・：][上下中][篇筒]")
                    to_clicks = self.wait_ocr_until_count(
                        match=[chapter_re],
                        box=None,
                        min_count=2,
                        timeout=5,
                        settle_time=2,
                        log=True
                    )
                    if to_clicks:
                        up = None
                        middle = None
                        down = None
                        for click in to_clicks:
                            if re.search("上[篇筒]", click.name):
                                up = click
                            elif re.search("中[篇筒]", click.name):
                                middle = click
                            elif re.search("下[篇筒]", click.name):
                                down = click

                        chapter_boxes = [box for box in (up, middle, down) if box]
                        wuzi_boxes = self.wait_ocr(
                            match=re.compile('物资'), box=None, time_out=4, settle_time=2, log=True
                        )
                        click_boxes = self._filter_boxes_near_candidates(chapter_boxes, wuzi_boxes) if wuzi_boxes else []

                        if not click_boxes:
                            click_boxes = chapter_boxes

                        click_boxes = sorted(click_boxes, key=self._chapter_click_order)

                        for chapter in click_boxes:
                            self.click(chapter, after_sleep=0.2)
                    elif to_clicks := self.wait_ocr(match=['活动战役', re.compile('物资')], box=self.box.bottom,
                                                    raise_if_not_found=False, time_out=4, settle_time=2, log=True):
                        self.click(to_clicks, after_sleep=2)
                    if to_clicks:
                        self.sleep(2)
                        if wu_zi := self.ocr(match=re.compile('物资'), box=self.box.bottom_right):
                            self.click(wu_zi, after_sleep=0.5)
                        battles = self.wait_ocr(match=map_re, time_out=4)
                        if battles:
                            self.click(battles[-1])
                            self.fast_combat(set_cost=1, battle_max=6, activity=True)
            else:
                self.log_info("找不到开启的活动")
        self.ensure_main()

    def find_activities(self):
        return self.wait_ocr(match=[activity_time_re], box=self.box.bottom_left,
                             raise_if_not_found=False, time_out=4)

    def find_latest_activity(self):
        boxs = self.find_activities()

        def parse_time(name):
            match = activity_time_re.match(name)
            if match:
                days = int(match.group(1))
                hours = int(match.group(2))
                return days * 24 + hours
            return 0

        if not boxs:
            return None
        longest = max(boxs, key=lambda b: parse_time(b.name))
        return longest

    def gongongqu(self):
        self.info_set('current_task', 'gongongqu')
        if result := self.wait_ocr(match=re.compile('委托'), box=self.box._claim, raise_if_not_found=True, log=True):
            self.click_box_by_match_position(result, "委托", after_sleep=2)
            start_time = time.time()
            while True:
                if time.time() - start_time > 10:
                    self.log_info("公共区委托界面停留过久，返回")
                    break
                buttons = self.find_feature(feature_name='ggq_can_button', box=self.box.left)
                if buttons and len(buttons) >= 2:
                    break            
            if not self.config.get('自主循环'):
                if buttons:
                    self.click(buttons[0])
                if self.wait_ocr(match=['最小'], time_out=4, settle_time=2, log=True):
                    self.wait_click_ocr(match=['确认'], after_sleep=2.5, raise_if_not_found=True)
                self.back(after_sleep=2)

            if buttons and len(buttons) >= 2:
                self.click(buttons[1], after_sleep=2)
            if self.wait_ocr(match='获得道具', box=self.box.top, time_out=2, log=True):
                self.back(after_sleep=2)
            else:
                self.wait_pop_up(count=1)
            if buttons and len(buttons) > 2:
                self.click(buttons[2], after_sleep=2)
                self.wait_click_ocr(match=[re.compile('再次派[遣造]')], box=self.box.bottom, after_sleep=2, raise_if_not_found=False)
            if self.config.get("自主循环"):
                self.auto_loop()

    def _auto_loop_step_with_retry(self, step_num, match, need_confirm=False, box=None, time_out=5, after_sleep=2, **kwargs):
        """
        点击OCR匹配元素，等待点击特征在 3s 内消失。
        若特征未消失则重试，最多尝试 3 次。
        Args:
            step_num (int): 步骤编号
            match (str or list): OCR匹配内容
            box (Box): OCR匹配范围
            time_out (int): OCR匹配超时时间
            after_sleep (int): 点击后等待时间
            **kwargs: 其他参数，传递给 wait_click_ocr
        Returns:
            bool: 是否成功点击
        """
        for attempt in range(3):
            result = self.wait_click_ocr(
                match=match, box=box, time_out=time_out, after_sleep=0, log=True, **kwargs
            )
            if not result:
                self.log_info(f"自主循环步骤{step_num}未完成，退出循环", notify=True)
                return False
            # 等待最多 3s，检测点击特征是否消失
            start = time.time()
            while time.time() - start < 3:
                self.next_frame()
                if not self.ocr(box=box, match=match):
                    self.sleep(after_sleep)
                    return result
                if need_confirm and self.ocr(box=self.box.center, match='确认'):
                    return result

                self.sleep(0.3)
            if attempt < 2:
                self.log_info(f"自主循环步骤{step_num}点击后特征未消失，重试 ({attempt + 2}/3)", notify=True)
        self.log_info(f"自主循环步骤{step_num}未完成，退出循环", notify=True)
        return False

    def auto_loop(self):
        # 步骤 1: 点击"自主循环"，带重试
        if not self._auto_loop_step_with_retry(
            step_num=1,
            match=[re.compile("自主循环")],
            box=self.box.bottom_left,
            time_out=5,
            after_sleep=2,
        ):
            return

        # 步骤 2: 点击"开始循环"，带重试
        if not self._auto_loop_step_with_retry(
            step_num=2,
            match="开始循环",
            box=self.box.bottom_left,
            need_confirm=True,
            time_out=5,
            after_sleep=2,
        ):
            return

        # 步骤 3: 部分情况下直接开始循环，仅在出现确认弹窗时处理。
        if self.wait_ocr(match=["确认"], box=self.box.center, time_out=3,
                         raise_if_not_found=False):
            if not self._auto_loop_step_with_retry(
                step_num=3,
                match=["确认"],
                box=self.box.center,
                after_sleep=2,
            ):
                return
        # 步骤 4: 等待"循环结束"出现并点击（仅作为一次识别完成的角色，不需要重试）
        if not self.wait_click_ocr(
            match=re.compile("循环结束"), time_out=600, box=self.box.top, after_sleep=2, log=True
        ):
            self.log_info("自主循环步骤4未完成，退出循环", notify=True)
            return

        # 步骤 5: 点击"确认"，带重试
        if not self._auto_loop_step_with_retry(
            step_num=5,
            match=["确认"],
            settle_time=2,
            after_sleep=2,
            box=self.box.bottom
        ):
            return

    def close_gift_dialog(self):
        # Top-right black X of the gift detail panel (2124, 408 at 2560x1600).
        self.click(0.83, 0.255, after_sleep=1)
        self.next_frame()
        if self.ocr(box=self.box_of_screen(0.34, 0.275, 0.70, 0.315),
                    match=re.compile(r'礼包|补给箱'), log=True):
            raise RuntimeError('礼包详情未关闭，停止购物以避免误购')

    def confirm_free_gift(self):
        # Read the modal again after opening it. Background "免费" labels do
        # not establish that the selected gift is free.
        self.next_frame()
        boxes = self.ocr(box=self.box_of_screen(0.15, 0.23, 0.85, 0.80), log=True)
        controls = self.box_of_screen(0.28, 0.71, 0.72, 0.78)
        price = self.box_of_screen(0.73, 0.275, 0.82, 0.32)
        free = self.find_boxes(boxes, match=re.compile(r'^\s*免费\s*$'), boundary=price)
        cancel = self.find_boxes(boxes, match=re.compile(r'^取消$'), boundary=controls)
        buy = self.find_boxes(boxes, match=re.compile(r'^(购买|确认)$'), boundary=controls)
        sold_out = self.find_boxes(boxes, match=re.compile(r'.*(已售罄|售罄|已购买|已领取).*'))
        title = self.find_boxes(boxes, match=re.compile(r'.*晶条.*'),
                                boundary=self.box_of_screen(0.34, 0.275, 0.70, 0.315))
        if sold_out or title or not (free and cancel and len(buy) == 1):
            self.log_info('无法确认礼包弹窗价格为免费，跳过购买')
            self.close_gift_dialog()
            return False
        self.click(buy[0], after_sleep=1.5)
        self.wait_pop_up(time_out=5, count=1)
        # A successful free purchase can switch directly to a paid gift.
        # Close that detail panel without searching for another purchase button.
        self.close_gift_dialog()
        return True

    def shopping(self):
        self.info_set('current_task', 'shopping')
        self.wait_click_ocr(match=['商城'], box=self.box.bottom_right, after_sleep=1.5, raise_if_not_found=True)
        self.wait_click_ocr(match=['品质甄选'], box=self.box.top_left, after_sleep=1, raise_if_not_found=True)
        self.wait_click_ocr(match=['周期礼包', '常驻礼包'], box=self.box.top, after_sleep=1, raise_if_not_found=True)
        if self.wait_click_ocr(match=['免费'], after_sleep=0.5, raise_if_not_found=False, time_out=1):
            self.log_info('found free item to buy')
            if not self.confirm_free_gift():
                self.ensure_main()
                return
        self.wait_click_ocr(match=["臻品礼包", "限时礼包"], box=self.box.top, after_sleep=0.5,
                            raise_if_not_found=True, time_out=2)
        if self.wait_click_ocr(match=['免费'], after_sleep=0.5, raise_if_not_found=False, time_out=1):
            self.log_info('found free item to buy')
            if not self.confirm_free_gift():
                self.ensure_main()
                return
        if self.config.get('商店心愿单购买'):
            self.buy_others()
        self.ensure_main()

    def buy_others(self):
        self.info_set('current_task', '心愿单购买')
        self.click(0.055, 0.946, after_sleep=1)
        others_list = ['家具商店', '班组商店', '调度商店', '讯段交易', '心智统合', '人形堆栈']
        for other in others_list:
            if not self.wait_click_ocr(match=other, after_sleep=1, raise_if_not_found=False):
                continue  # 找不到商店就跳过
            if not self.wait_click_ocr(match=re.compile("购买"), box=self.box.bottom_right, time_out=1,
                                       raise_if_not_found=False):
                continue  # 找不到一键购买按钮就跳过
            if self.wait_click_ocr(match='购买', after_sleep=1, raise_if_not_found=False):
                self.wait_pop_up(time_out=5, count=1)

    def arena(self):
        if self.config.get('自主循环'):
            self.ensure_main()
            return
        self.info_set('current_task', 'arena')
        self.wait_click_ocr(match=re.compile('战役推进'), box=self.box.top_right, after_sleep=1,
                            raise_if_not_found=True)
        self.wait_ocr(match=re.compile('补给作战'), box=self.box.top_right, raise_if_not_found=True)
        self.sleep(1)
        self.click_relative(0.89, 0.05)  # 模拟战斗
        self.wait_click_ocr(match=['实兵演习'], box=self.box.bottom, after_sleep=0.5, raise_if_not_found=True)
        self.wait_pop_up(time_out=15, count=1)
        remaining_count = self.arena_remaining()
        if remaining_count > 1:
            self.wait_click_ocr_with_pop_up("进攻", box=self.box.bottom_right)
            self.sleep(2)
            self.challenge_arena_opponent()
            self.back()
            self.sleep(1)
        # if count > 0:
        #     self.click_relative(0.34 if self.is_adb() else 0.26, 0.89, after_sleep=0.5)
        #     if not self.wait_ocr(match=['演习补给'], box=self.box.top, time_out=4):
        #         self.wait_pop_up(time_out=4)
        if self.wait_click_ocr(match=['周期奖励'], box=self.box.left, after_sleep=1, raise_if_not_found=True):
            self.wait_click_ocr(match=[re.compile('键领取')], after_sleep=1, raise_if_not_found=False)
        self.ensure_main()

    def bingqi(self):
        if self.config.get('自主循环'):
            self.ensure_main()
            return
        self.info_set('current_task', 'bingqi')
        self.wait_click_ocr(match=re.compile('战役推进'), box=self.box.top_right, after_sleep=1,
                            raise_if_not_found=True)
        self.wait_ocr(match=re.compile('补给作战'), box=self.box.top_right, raise_if_not_found=True)
        self.sleep(1)
        self.click_relative(0.90, 0.05, after_sleep=0.95)  # 补给
        self.click_relative(0.98, 0.49, after_sleep=0.52)
        self.wait_ocr(match='防御阵容', box=self.box.right, time_out=30,
                      post_action=lambda: self.click_relative(0.5, 0.5, after_sleep=2))
        while self.find_top_right_count():
            self.info_incr('bingqi')
            self.wait_click_ocr(match=['匹配'], box=self.box.bottom, after_sleep=0.5, raise_if_not_found=True)
            self.auto_battle(end_match='匹配')
            self.sleep(2)
        self.ensure_main()

    def guild(self):
        self.info_set('current_task', 'guild')
        if result := self.wait_ocr(match=['班组'], box=self.box._group, raise_if_not_found=True):
            self.click_box_by_match_position(result, "班组", after_sleep=2)
            self.wait_click_ocr(match=['要务'], box=self.box.bottom_right, after_sleep=0.5, settle_time=2)
            result = self.wait_ocr(match=['开始作战', '每日要务已完成'], box=self.box.bottom_right, raise_if_not_found=True, log=True)
            if result[0].name == '开始作战':
                self.click(result)
                self.auto_battle()
                self.wait_ocr(match=['开始作战', '每日要务已完成', '要务'], box=self.box.bottom_right,
                              raise_if_not_found=True)
            else:
                self.log_info('每日要务已完成')
            self.back()
            self.sleep(1)
            self.chenyan()

            self.wait_click_ocr(match=['补给'], box=self.box.bottom_right, after_sleep=0.5)
            if result := self.wait_ocr(match=['领取全部'], box=self.box.bottom_right, time_out=4,
                                       raise_if_not_found=False):
                self.click_box(result)
                self.wait_pop_up(count=1)
            self.back()
            self.sleep(1)
        self.ensure_main()

    def chenyan(self):
        if not self.config.get('尘烟'):
            return
        end = self.ocr(match=re.compile('前线'), box=self.box.bottom_right, log=True)
        if not end:
            return
        self.click(end, after_sleep=1)
        result = self.ocr(0.89, 0.01, 0.99, 0.1, match=stamina_re, box=self.box.top_right)
        if not result:
            return
        while True:
            tickets = int(result[0].name.split('/')[0])
            self.log_info(f'chenyan tickets {tickets}')
            self.info_set('chenyan tickets', tickets)
            if tickets == 0:
                break
            self.wait_click_ocr(match='攻坚战', box=self.box.top_right, after_sleep=0.5, raise_if_not_found=True)
            self.wait_click_ocr(match='开始作战', box=self.box.bottom_right, after_sleep=2, raise_if_not_found=True)
            self.choose_chenyan(tickets)
            self.sleep(2)
            result = self.ocr(0.89, 0.01, 0.99, 0.1, match=stamina_re, box=self.box.top_right)
        self.back(after_sleep=2)

    def choose_chenyan(self, tickets):
        existing = self.ocr(box=self.box_of_screen(0.61, 0.69, 0.88, 0.83), match=re.compile(r"^\d+$"))
        for exist in existing:
            self.click_box(exist, after_sleep=0.1)
        self.click_relative(0.28, 0.35, after_sleep=0.2)
        self.click_relative(0.21, 0.64, after_sleep=0.2)
        self.click_relative(0.28, 0.35, after_sleep=0.2)
        if tickets == 2:
            self.click_relative(0.16, 0.47, after_sleep=0.2)  # 编队1
        else:
            self.click_relative(0.16, 0.56, after_sleep=0.2)  # 编队2
        x_start = 0.06
        step = (0.24 - 0.03) / 3
        for i in range(4):
            self.click_relative(x_start + step * i, 0.45, after_sleep=0.2)

        self.wait_click_ocr(match='助战', box=self.box.bottom_right, settle_time=1, after_sleep=1,
                            raise_if_not_found=True)
        priority = ['威玛西娜', '可露凯', '夏安', '罗蕾莱', '春田', '莱妮', '妮基塔', '玛绮朵', '洛贝拉', '托洛洛',
                    '琼玖']
        selected = False
        my_chars = []

        for name, m in [(i, self.get_role_by_name(i)) for i in priority]:
            self.wait_click_ocr(match=m, time_out=2, after_sleep=2)

            chars = self.ocr(0.18, 0.27, 0.82, 0.79, match=re.compile(r'^\D*$'))
            solved_chars = [char for char in chars if char.name == name]

            if not solved_chars:
                continue

            self.click(solved_chars[0], after_sleep=1)

            join = self.ocr(match='入队', box=self.box.bottom_right)
            if not join:
                continue

            self.click_box(join, after_sleep=1)

            if self.ocr(box=self.box.bottom_right, match="确认"):
                my_chars.append(name)
                self.back(after_sleep=1)
                self.log_info(f'duplicate char {my_chars}')
            else:
                selected = True
                break
        if not selected:
            self.log_info('no priority char joined, fallback start')

            attr_order = ['物理', '酸蚀', '浊刻', '燃烧', '冷凝', '电导']

            for attr in attr_order:
                self.wait_click_ocr(match=attr, time_out=2, after_sleep=2)

                chars = self.ocr(
                    0.18, 0.27, 0.82, 0.79,
                    match=re.compile(r'^\D*$')
                )

                for char in chars:
                    if char.name in my_chars:
                        continue

                    self.click(char, after_sleep=1)

                    join = self.ocr(match='入队', box=self.box.bottom_right)
                    if not join:
                        continue

                    self.click_box(join, after_sleep=1)

                    if self.ocr(box=self.box.bottom_right, match="确认"):
                        my_chars.append(char.name)
                        self.back(after_sleep=1)
                        self.log_info(f'duplicate char {char.name}')
                    else:
                        self.log_info(f'fallback joined char: {char.name}')
                        selected = True
                        break

                if selected:
                    break

        self.wait_click_ocr(match='确定', box=self.box.bottom_right)
        self.auto_battle('开始作战', self.box.bottom_right)

    def wait_click_ocr_with_pop_up(self, match, box=None):
        if self.wait_until(lambda: self.do_wait_pop_up_and_click(match, box), time_out=10, raise_if_not_found=True):
            self.sleep(0.5)
            return True
        return None

    def do_wait_pop_up_and_click(self, match, box):
        boxes = self.ocr()
        if find_boxes_by_name(boxes, pop_ups):
            self.back(after_sleep=2)
            return False
        elif click := find_boxes_by_name(boxes, match):
            if click := find_boxes_within_boundary(click, self.get_box_by_name(box)):
                self.click(click)
                return True
            return None
        return None

    def wait_ocr_with_possible_pop_up(self, match, box=None, raise_if_not_found=True,
                                      time_out=30):
        if self.wait_until(lambda: self.do_wait_pop_up_and_click(match, box), time_out=time_out,
                           raise_if_not_found=raise_if_not_found):
            self.sleep(0.5)
            return True
        return None

    def do_wait_ocr_with_possible_pop_up(self, match, box):
        boxes = self.ocr()
        if find_boxes_by_name(boxes, pop_ups):
            self.back(after_sleep=2)
            return False
        elif click := find_boxes_by_name(boxes, match):
            if box:
                return find_boxes_within_boundary(click, self.get_box_by_name(box))
            else:
                return click
        return None

    def arena_remaining(self):
        return int(self.ocr(0.89, 0.01, 0.99, 0.1, match=stamina_re)[0].name.split('/')[0])

    def challenge_arena_opponent(self):
        challenged = 0
        waited_pop_up = False
        while True:
            remaining_count = self.arena_remaining()
            self.log_info(f'challenge_arena_opponent remaining_count {remaining_count}')
            if remaining_count <= 1:
                self.log_info(f'challenge arena complete {remaining_count}')
                break
            boxes = self.ocr(0, 0.51, 0.94, 0.59, match=re.compile(r"^[1-9]\d*$"))
            if len(boxes) < 3:
                if not waited_pop_up:
                    waited_pop_up = True
                    self.wait_pop_up(time_out=15) and self.wait_pop_up(time_out=15) and self.wait_pop_up(time_out=15)
                    continue
                else:
                    raise Exception("找不到五个演习对手")
            self.log_info(f'arena opponents {boxes}')
            for box in boxes:
                if remaining_count - challenged <= 1:
                    self.log_info(f'challenged enough return {remaining_count} {challenged}')
                    return challenged
                if int(box.name) < 5000:
                    search_success = box.copy()
                    search_success.width = self.width_of_screen(0.17)
                    search_success.height = self.height_of_screen(0.15)
                    search_success.y -= search_success.height
                    if not self.ocr(match=re.compile('挑战'), box=search_success, log=True):
                        self.log_info(f'challenge opponent {box.name}')
                        self.click(box)
                        self.wait_click_ocr(match=['进攻'], box=self.box.bottom_right, after_sleep=0.5,
                                            raise_if_not_found=True)
                        self.auto_battle(end_match='刷新')
                        self.sleep(3)
                        challenged += 1
                        continue
            if self.ocr(match=['刷新消耗'], box=self.box.bottom_right):
                self.log_info(f'no refresh count remains')
                return challenged
            self.wait_click_ocr(match='刷新', box=self.box.bottom_right, after_sleep=2, raise_if_not_found=True)
        return challenged

    def battle(self):
        if self.config.get('自主循环'):
            self.ensure_main()
            return
        self.info_set('current_task', 'battle')
        self.wait_click_ocr(match=re.compile('战役推进'), box=self.box.top_right, after_sleep=0.5,
                            raise_if_not_found=True)
        self.wait_ocr(match=re.compile('补给作战'), box=self.box.top_right, raise_if_not_found=True)
        self.click_relative(0.78, 0.05)
        if self.is_adb():
            self.swipe_relative(0.8, 0.6, 0.5, 0.6, duration=1)
        self.sleep(1)
        remaining = 10000
        if self.config.get('刷钱本'):
            self.wait_click_ocr(match=['标准同调'], box=self.box.right, after_sleep=0.5, raise_if_not_found=True)
            remaining = self.fast_combat(battle_max=4, set_cost=20)
            self.back(after_sleep=1)
        target = self.config.get('体力本')
        cost_dict = {"深度搜索": 10, "军备解析": 10, "决策构象": 20, "定向精研": 30}
        min_stamina = cost_dict.get(target, 30)
        if remaining >= min_stamina:
            ding_xiang = self.stamina_options.index(target) >= 3
            if ding_xiang:
                target = '定向精研'
            self.wait_click_ocr(match=target, settle_time=1, after_sleep=0.5, raise_if_not_found=True, log=True)
            # if ding_xiang:
            #     self.wait_click_ocr(match=re.compile(self.config.get('体力本')),
            #                         box=self.box_of_screen(0.01, 0.21, 0.73, 0.31),
            #                         settle_time=0.5,
            #                         after_sleep=0.5, log=True,
            #                         raise_if_not_found=True)
            while remaining >= min_stamina:
                if ding_xiang:
                    remaining = self.fast_combat(plus_x=0.69, plus_y=0.59, set_cost=cost_dict[target])
                else:
                    remaining = self.fast_combat(set_cost=cost_dict.get(target, None))
        self.ensure_main()


def sort_characters_by_priority(chars, priority):
    """
    Sorts a list of character objects based on their 'char_name' attribute,
    according to a priority list.

    Characters whose 'char_name' attribute appears in the priority list are
    placed at the front, sorted by their order within the priority list.
    Characters not in the priority list retain their original order.

    Args:
        chars: A list of character objects, where each object has a 'char_name' attribute (string).
        priority: A list of character names (strings) representing the priority order.

    Returns:
        A new list of character objects, sorted according to the priority.  The
        original `chars` list is not modified.
    """

    priority_map = {name: index for index, name in enumerate(priority)}
    sorted_chars = []

    for i, the_char in enumerate(chars):  # Use enumerating to get the original index
        char_name = the_char.name.lower()
        if char_name in priority_map:
            sorted_chars.append((priority_map[char_name], i, the_char))  # (priority_index, original_index, char_object)
        else:
            sorted_chars.append((len(priority), i, the_char))  # (lowest_priority, original_index, char_object)

    sorted_chars.sort()  # Sort the list of tuples

    return [char_object for _, _, char_object in sorted_chars]  # Extract the character objects


def find_boxes_within_boundary(
        boxes: list["Box"],
        boundary_box: "Box",
        sort: bool = False
) -> list["Box"]:
    """
    查找完全包含在边界框内的框。
    """

    if not boxes or not boundary_box:
        return []

    # 计算边界框四个边
    bx1 = boundary_box.x
    by1 = boundary_box.y
    bx2 = boundary_box.x + boundary_box.width
    by2 = boundary_box.y + boundary_box.height

    result = []

    for box in boxes:
        x1 = box.x
        y1 = box.y
        x2 = box.x + box.width
        y2 = box.y + box.height

        # 完全包含判断
        if x1 >= bx1 and y1 >= by1 and x2 <= bx2 and y2 <= by2:
            result.append(box)

    if sort:
        # 从上到下，再从左到右
        result.sort(key=lambda b: (b.y, b.x))

    return result
