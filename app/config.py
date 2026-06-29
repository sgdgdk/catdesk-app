"""
全局配置文件
"""
import os

# ============================================================
# LLM 配置
# ============================================================
# 可选: "dashscope" (阿里通义千问) 或 "deepseek" (DeepSeek)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

# API Key (优先用环境变量，如果没有就用下面的默认值)
_DEFAULT_KEY = "sk-289d85b965d94023960ab185f8f6f876"
LLM_API_KEY = os.getenv("DASHSCOPE_API_KEY", _DEFAULT_KEY).strip()

# 根据提供商设置模型和端点
if LLM_PROVIDER == "deepseek":
    LLM_MODEL = "deepseek-chat"
    LLM_BASE_URL = "https://api.deepseek.com"
else:
    LLM_MODEL = "qwen-plus"
    LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ============================================================
# BLE 配置（ESP32-S3 Nano）
# ============================================================
BLE_DEVICE_NAME = "DeskCat-Nano"      # ESP32-S3 Nano BLE 广播名
BLE_SERVICE_UUID = "0000FFE0-0000-1000-8000-00805F9B34FB"
BLE_CHAR_TX_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"  # 手机→ESP32
BLE_CHAR_RX_UUID = "0000FFE2-0000-1000-8000-00805F9B34FB"  # ESP32→手机
BLE_SCAN_TIMEOUT = 10  # 扫描超时(秒)

# ============================================================
# TTS 配置
# ============================================================
TTS_VOICE = "zh-CN-XiaoxiaoNeural"   # Edge TTS 语音
TTS_SPEED = 1.0                       # 语速
TTS_PITCH = 0                         # 音调

# ============================================================
# 表情动画配置
# ============================================================
ANIM_DIR = os.path.join(os.path.dirname(__file__), "data", "anim")
ANIM_FPS = 20  # 动画播放帧率
ANIM_PLAY_COUNT = 1  # 非默认表情播放一次后切回默认

# 表情 → 动画目录映射 (对应 app/data/anim/ 下的实际目录名)
EMOTION_TO_ANIM_DIR = {
    "neutral":   "neut",      # 中性
    "happy":     "happy",     # 开心
    "sad":       "sad",       # 难过
    "surprised": "surpris",   # 惊讶
    "thinking":  "think",     # 思考
    "excited":   "smile",     # 兴奋
    "angry":     "serious",   # 生气
    "sleepy":    "helpless",  # 困倦
    "confused":  "helpless",  # 困惑
    "fear":      "helpless",  # 害怕
    "love":      "smile",     # 喜欢
    "shy":       "smile",     # 害羞
}

# 无有效动画时的表情符号回退
EMOTION_EMOJI = {
    "happy":     "😄",
    "sad":       "😢",
    "angry":     "😠",
    "surprised": "😮",
    "thinking":  "🤔",
    "sleepy":    "😴",
    "excited":   "🤩",
    "confused":  "😕",
    "love":      "🥰",
    "fear":      "😨",
    "shy":       "😊",
    "neutral":   "😐",
}

# ============================================================
# 系统提示词 — v2 支持 PTZ 云台 + 轮子 + 命令识别
# ============================================================
SYSTEM_PROMPT = """你是桌面小猫机器人"小喵"。你的核心是陪主人聊天，偶尔执行动作。

规则：
1. 用户在聊天/问问题/分享心情 → action 永远为 "none"，正常回答
2. 用户说"往前走/后退/左转/右转/看看上面/往下看/回中" → action 设为对应的动作
3. 做不到的事（飞/发射/变身）→ action 为 "none"，撒娇拒绝

格式：{"reply": "回复", "emotion": "情绪", "action": "动作"}

emotion: happy, sad, angry, surprised, thinking, sleepy, excited, confused, love, fear, shy, neutral
action: move_forward, move_backward, turn_left, turn_right, stop, look_up, look_down, look_left, look_right, center_ptz, none

例子：
{"reply":"你好呀！今天想聊什么？","emotion":"happy","action":"none"}
{"reply":"好的，出发！","emotion":"happy","action":"move_forward"}
{"reply":"臣妾做不到喵~","emotion":"shy","action":"none"}"""
