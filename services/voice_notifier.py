"""语音通知服务模块"""

import logging
import threading

from services.config_manager import get_config_manager

logger = logging.getLogger(__name__)


class VoiceNotifier:
    """语音通知器 - 使用 pyttsx3 进行文字转语音"""

    def __init__(self):
        self._engine = None

    def speak(self, text: str):
        """
        异步播报语音（不阻塞主线程）

        Args:
            text: 要播报的文字内容
        """
        thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
        thread.start()

    def _speak_sync(self, text: str):
        """同步播报语音"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)  # 语速
            engine.setProperty('volume', 0.9)  # 音量
            engine.say(text)
            engine.runAndWait()
        except ImportError:
            logger.warning("pyttsx3 未安装，无法播报语音。请运行: pip install pyttsx3")
        except Exception as e:
            logger.error(f"语音播报失败: {e}")

    def announce_moment_complete(self, remaining: int, code: str = ""):
        """
        播报朋友圈发布完成
        Args:
            remaining: 剩余待发朋友圈数量
            code: 当前内容编号
        """
        config = get_config_manager()
        template = config.get(
            "voice.moment_complete_text",
            "又发了一条朋友圈，还剩{remaining}条朋友圈待发，日拱一卒，财务自由。"
        )
        try:
            text = template.format(code=code or "", remaining=remaining)
        except Exception as e:
            logger.warning(f"语音播报模板格式化失败，使用默认文案: {e}")
            text = f"又发了一条朋友圈，还剩{remaining}条朋友圈待发，日拱一卒，财务自由。"

        logger.info(f"语音播报: {text}")
        self.speak(text)

    def announce_group_complete(self, remaining: int, code: str = ""):
        """
        播报代理群发布完成
        Args:
            remaining: 剩余待发代理群任务数量
            code: 当前内容编号
        """
        config = get_config_manager()
        template = config.get(
            "voice.agent_group_complete_text",
            "代理群发送成功，还有{remaining}个待发送"
        )
        try:
            text = template.format(code=code or "", remaining=remaining)
        except Exception as e:
            logger.warning(f"语音播报模板格式化失败，使用默认文案: {e}")
            text = f"代理群发送成功，还有{remaining}个待发送"

        logger.info(f"语音播报: {text}")
        self.speak(text)

    def announce_customer_group_complete(self, remaining: int, code: str = ""):
        """
        播报客户群发布完成
        Args:
            remaining: 剩余待发客户群任务数量
            code: 当前内容编号
        """
        config = get_config_manager()
        template = config.get(
            "voice.customer_group_complete_text",
            "客户群发送成功，还有{remaining}个待发送"
        )
        try:
            text = template.format(code=code or "", remaining=remaining)
        except Exception as e:
            logger.warning(f"语音播报模板格式化失败，使用默认文案: {e}")
            text = f"客户群发送成功，还有{remaining}个待发送"

        logger.info(f"语音播报: {text}")
        self.speak(text)


# 全局实例
_voice_notifier = None


def get_voice_notifier() -> VoiceNotifier:
    """获取语音通知器单例"""
    global _voice_notifier
    if _voice_notifier is None:
        _voice_notifier = VoiceNotifier()
    return _voice_notifier
