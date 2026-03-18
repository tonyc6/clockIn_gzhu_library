import datetime
import json
import os
import platform
import time
import traceback

import requests
import selenium.webdriver
from func_timeout import func_set_timeout
from loguru import logger
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class clockIn():
    def __init__(self):

        self.xuhao = str(os.environ['XUHAO'])
        self.mima = str(os.environ['MIMA'])
        self.SEATNO = str(os.environ['SEATNO'])
        self.pushplus = str(os.environ['PUSHPLUS'])

        if self.SEATNO == '':
            exit('请在Github Secrets中设置SEATNO')
        if self.xuhao == '':
            exit('请在Github Secrets中设置XUHAO')
        if self.mima == '':
            exit('请在Github Secrets中设置MIMA')

        # 加载配置
        options = Options()
        optionsList = [
            "--headless",
            # "--disable-gpu",
            "--lang=zh-CN",
            "--enable-javascript",
            "start-maximized",
            "--disable-extensions",
            "--no-sandbox",
            "--disable-browser-side-navigation",
            "--disable-dev-shm-usage"
        ]

        for option in optionsList:
            options.add_argument(option)

        options.page_load_strategy = 'none'
        options.add_experimental_option(
            "excludeSwitches",
            ["ignore-certificate-errors", "enable-automation"])
        options.keep_alive = True


        self.driver = selenium.webdriver.Chrome(options=options)

        self.wdwait = WebDriverWait(self.driver, 30)
        self.titlewait = WebDriverWait(self.driver, 20)

        # self.page用来表示当前页面标题，0表示初始页面
        self.page = 0

        # self.fail表示打卡失败与否
        self.fail = False

    def __call__(self):
        for retries in range(4):
            try:
                logger.info(f"第{retries + 1}次运行")
                if retries:
                    # 恢复状态，让它重来
                    self.page = 0
                    self.fail = False

                self.step0()
                self.step1()
                self.step2()
                self.step3()

            except Exception:
                logger.error(traceback.format_exc())
                try:
                    if not self.driver.title:
                        logger.error(f'第{retries + 1}次运行失败，当前页面标题为空')
                    else:
                        logger.error(
                            f'第{retries + 1}次运行失败，当前页面标题为：{self.driver.title}')
                except Exception:
                    logger.error(f'第{retries + 1}次运行失败，获取当前页面标题失败')

                if retries == 3:
                    self.fail = True
                    logger.error("图书馆预定失败")

        self.driver.quit()

    def step0(self):
        """转到图书馆界面
        """
        logger.info('step0 正在转到转到图书馆界面')

        self.driver.get('''
                https://newcas.gzhu.edu.cn/cas/login?service=http://libbooking.gzhu.edu.cn/#/ic/home
                ''')

        if self.driver.title == 'Information Commons':
            # 说明验证通过，直接进入了界面
            return

        logger.info('标题1: ' + self.driver.title)

        # 计算时间

        start = datetime.datetime.now()

        # 获取当前的操作系统
        system = platform.system()
        # 如果是Ubuntu
        if system == 'Linux':
            logger.info("当前操作系统为Linux")
            self.titlewait.until(EC.title_contains("Unified Identity Authentication"))
        else:
            logger.info("当前操作系统为非Linux")
            self.titlewait.until(EC.title_contains("统一身份认证"))


        # time.sleep(10)

        end = datetime.datetime.now()
        logger.info('等待时间: ' + str((end - start).seconds))



        logger.info('标题2: ' + self.driver.title)

    def step1(self):
        """登录融合门户
        """

        self.wdwait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//div[@class='robot-mag-win small-big-small']")))

        logger.info('step1 正在尝试登陆统一身份认证')
        logger.info('标题: ' + self.driver.title)

        for script in [
            f"document.getElementById('un').value='{self.xuhao}'",
            f"document.getElementById('pd').value='{self.mima}'",
            "document.getElementById('index_login_btn').click()"
        ]:
            self.driver.execute_script(script)

    def step2(self):
        """正在转到图书馆界面
        """
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.title_contains("Information Commons"))

        logger.info('step2 正在转到图书馆界面')
        logger.info('标题: ' + self.driver.title)

    def step3(self):
        logger.info('step3 准备进行图书馆预定座位操作')
        logger.info('标题: ' + self.driver.title)

        # 确保在正确的域名下获取cookie
        if 'libbooking.gzhu.edu.cn' not in self.driver.current_url:
            logger.info('正在跳转到图书馆域名...')
            self.driver.get("http://libbooking.gzhu.edu.cn/#/ic/home")
            time.sleep(3)

        # 最多尝试3次获取cookie
        for attempt in range(3):
            cookie = self.get_cookie()

            if cookie != '':
                break

            logger.info(f'第{attempt + 1}次尝试获取cookie失败')

            if attempt < 2:  # 不是最后一次尝试
                # 重新尝试访问
                self.driver.get("http://libbooking.gzhu.edu.cn/#/ic/home")
                time.sleep(5)
            else:
                logger.error('3次尝试都无法获取cookie，跳过本次预约')
                self.fail = True
                return

        logger.info('primary cookie: ' + cookie)

        # 尝试获取用户ID
        user_id = self.get_user_info()

        # 尝试通过API获取正确的用户ID
        self.get_user_info_from_api(cookie)  # 只是为了获取可能的token

        # 尝试从学号生成用户ID
        possible_user_ids = self.generate_possible_user_ids()
        logger.info(f'可能的userID列表: {possible_user_ids}')

        # 测试每个可能的用户ID
        valid_user_id = None
        for test_id in possible_user_ids:
            logger.info(f'测试用户ID: {test_id}')
            test_result = self.test_user_id(cookie, test_id)
            if test_result:
                valid_user_id = test_id
                break

        if valid_user_id:
            user_id = valid_user_id
            logger.info(f'找到有效的用户ID: {user_id}')
        else:
            logger.warning(f'无法确定正确的用户ID，使用默认值: {user_id}')

        logger.info(f'最终使用用户ID: {user_id}')

        # 计算明天的日期，yyyy-MM-dd
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow = tomorrow.strftime('%Y-%m-%d')

        # 将下面的值转换成json格式
        reserve1 = json.loads(self.reserve_lib_seat(cookie, tomorrow, '9:00:00', '12:00:00', user_id))

        # 添加延迟避免请求频率限制
        time.sleep(2)

        reserve2 = json.loads(self.reserve_lib_seat(cookie, tomorrow, '14:00:00', '18:00:00', user_id))

        logger.info(reserve1)
        logger.info(reserve2)

        message = f'''{tomorrow} 座位101-{self.SEATNO}，上午预定：{'预约成功' if reserve1.get('code') == 0 else '预约失败，设备在该时间段内已被预约'}
            {tomorrow} 座位101-{self.SEATNO}，下午预定：{'预约成功' if reserve2.get('code') == 0 else '预约失败，设备在该时间段内已被预约'}
        '''

        logger.info(message)

        # 发送消息
        self.notify(message)

        # 发送请求成功，可以结束程序了
        self.fail = False
        self.driver.quit()
        exit(0)

    def reserve_lib_seat(self, cookie, tomorrow, startTime, endTime, user_id=None):
        url = "http://libbooking.gzhu.edu.cn/ic-web/reserve"

        # 使用传入的用户ID，如果没有则尝试从环境变量获取，再没有则使用默认值
        if user_id is None:
            user_id = os.environ.get('USER_ID', '101598216')

        payload = json.dumps({
            "sysKind": 8,
            "appAccNo": int(user_id),
            "memberKind": 1,
            "resvMember": [
                int(user_id)
            ],
            "resvBeginTime": f"{tomorrow} {startTime}",
            "resvEndTime": f"{tomorrow} {endTime}",
            "testName": "",
            "captcha": "",
            "resvProperty": 0,
            "resvDev": [
                self.calc_dev_no(int(self.SEATNO))
            ],
            "memo": ""
        })
        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.41',
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        return response.text

    def calc_dev_no(self, no):
        return 101266684 + no - 1

    def decalc_devno(self, no):
        return no - 101266684 + 1

    def generate_possible_user_ids(self):
        """根据学号生成可能的用户ID"""
        possible_ids = []

        # 添加默认ID
        possible_ids.append('101598216')

        # 尝试基于学号生成ID
        if self.xuhao:
            try:
                # 直接使用学号
                possible_ids.append(self.xuhao)

                # 学号转换为整数
                if self.xuhao.isdigit():
                    student_num = int(self.xuhao)
                    possible_ids.append(str(student_num))

                    # 尝试一些常见的转换方式
                    possible_ids.append(str(student_num + 100000000))
                    possible_ids.append(str(student_num + 101000000))
                    possible_ids.append(str(student_num + 101500000))
                    possible_ids.append(str(student_num + 101590000))
                    possible_ids.append(str(student_num + 101598000))

            except Exception as e:
                logger.warning(f"生成用户ID时出错: {e}")

        # 去重并保持顺序
        unique_ids = []
        for id_val in possible_ids:
            if id_val not in unique_ids:
                unique_ids.append(id_val)

        return unique_ids

    def test_user_id(self, cookie, user_id):
        """测试用户ID是否有效"""
        try:
            # 使用一个简单的预约请求来测试用户ID
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            tomorrow = tomorrow.strftime('%Y-%m-%d')

            url = "http://libbooking.gzhu.edu.cn/ic-web/reserve"
            payload = json.dumps({
                "sysKind": 8,
                "appAccNo": int(user_id),
                "memberKind": 1,
                "resvMember": [int(user_id)],
                "resvBeginTime": f"{tomorrow} 09:00:00",
                "resvEndTime": f"{tomorrow} 12:00:00",
                "testName": "",
                "captcha": "",
                "resvProperty": 0,
                "resvDev": [self.calc_dev_no(int(self.SEATNO))],
                "memo": ""
            })

            headers = {
                'Cookie': cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.41',
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload, timeout=5)
            result = response.json()

            logger.info(f"测试用户ID {user_id} 结果: {result}")

            # 如果返回的不是"请用户使用自己的账号预约"，说明这个ID可能是正确的
            if result.get('message') != '请用户使用自己的账号预约':
                logger.info(f"用户ID {user_id} 可能是正确的")
                return True
            else:
                logger.info(f"用户ID {user_id} 不正确")
                return False

        except Exception as e:
            logger.warning(f"测试用户ID {user_id} 时出错: {e}")
            return False

    def get_user_info_from_api(self, cookie):
        """通过API获取用户信息"""
        try:
            url = "http://libbooking.gzhu.edu.cn/ic-web/user/info"
            headers = {
                'Cookie': cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.41',
                'Accept': 'application/json'
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"用户信息API响应: {data}")

                if data.get('code') == 0 and data.get('data'):
                    user_data = data.get('data')

                    # 如果返回的是字符串，可能是一个token，我们可以尝试在预约时使用这个token
                    if isinstance(user_data, str):
                        logger.info(f"获取到用户token: {user_data[:20]}...")
                        # 将这个token存储起来，可能在预约时需要
                        self.user_token = user_data
                        return None  # 无法从token中提取用户ID，返回None

                    # 处理对象格式
                    elif isinstance(user_data, dict):
                        if user_data.get('accNo'):
                            logger.info(f"从API获取的用户ID: {user_data.get('accNo')}")
                            return str(user_data.get('accNo'))

            logger.warning(f"用户信息API调用失败: {response.status_code}, {response.text}")
            return None

        except Exception as e:
            logger.warning(f"获取用户信息API调用异常: {e}")
            return None

    def get_user_info(self):
        """尝试从页面获取用户信息"""
        try:
            # 1. 从localStorage/sessionStorage获取
            user_info = self.driver.execute_script(
                "return localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '{}'"
            )
            logger.info(f"用户信息: {user_info}")

            # 2. 尝试获取用户ID
            user_id = self.driver.execute_script(
                "return localStorage.getItem('userId') || sessionStorage.getItem('userId') || '101598216'"
            )

            # 3. 尝试从页面元素中获取用户信息
            try:
                user_elements = self.driver.execute_script(
                    """
                    var elements = document.querySelectorAll('[class*=\"user\"], [id*=\"user\"], .username, .userid');
                    for (var i = 0; i < elements.length; i++) {
                        if (elements[i].textContent && elements[i].textContent.trim()) {
                            return elements[i].textContent.trim();
                        }
                    }
                    return null;
                    """
                )
                if user_elements:
                    logger.info(f"从页面元素获取的用户信息: {user_elements}")
            except:
                pass

            # 4. 尝试从URL参数中获取
            current_url = self.driver.current_url
            if 'ticket=' in current_url:
                logger.info(f"当前URL包含ticket参数: {current_url}")

            logger.info(f"使用默认用户ID: {user_id}")
            return user_id

        except Exception as e:
            logger.warning(f"获取用户信息失败: {e}")
            return '101598216'

    def get_cookie(self):
        # 获取Cookie字符串
        current_url = self.driver.current_url
        logger.info(f'当前URL: {current_url}')

        ans = self.driver.get_cookies()
        logger.info('所有cookies: ' + str(ans))

        if len(ans) != 0:
            # 构建所有cookie的字符串
            cookie_parts = []
            for cookie in ans:
                domain = cookie.get('domain', '')
                name = cookie.get('name', '')
                value = cookie.get('value', '')

                logger.info(f'检查cookie: {name} (domain: {domain})')

                # 检查相关域名
                if (domain.endswith('libbooking.gzhu.edu.cn') or
                    domain.endswith('gzhu.edu.cn') or
                    'ic-cookie' in name or
                    'JSESSIONID' in name):

                    cookie_parts.append(f"{name}={value}")
                    logger.info(f"Added cookie: {name}")

            if cookie_parts:
                cookie_string = '; '.join(cookie_parts)
                logger.info(f"Final cookie string: {cookie_string}")
                return cookie_string
            else:
                logger.warning('没有找到相关的cookie')

        return ''

    def notify(self, content):
        """图书馆预约信息
        """
        if self.pushplus:
            data = {"token": self.pushplus, "title": "图书馆预约信息", "content": content}
            url = "http://www.pushplus.plus/send/"
            logger.info(requests.post(url, data=data).text)


# 限制10分钟内，必须运行完成，否则失败处理
@func_set_timeout(60 * 3)
def main():
    cl = clockIn()
    cl()


if __name__ == "__main__":
    main()
