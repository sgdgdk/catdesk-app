"""
意图映射模块 v2
LLM 输出 {reply, emotion, action} → 本地查表 → BLE指令 + 响应管理

轮子命令: move_forward, move_backward, turn_left, turn_right, stop
云台命令: look_up, look_down, look_left, look_right, center_ptz
日常对话: none
"""
import json
import os
import random
import re
from typing import Optional


class IntentMapper:
    """意图→动作映射器"""

    def __init__(self, map_path: str = None):
        if map_path is None:
            map_path = os.path.join(os.path.dirname(__file__), "data", "intent_map.json")

        with open(map_path, "r", encoding="utf-8") as f:
            self._map = json.load(f)

    def get_ble_command(self, action: str) -> str:
        """action → BLE指令
        返回空字符串表示无动作
        """
        return self._map.get("actions", {}).get(action, {}).get("ble", "")

    def is_action_available(self, action: str) -> bool:
        """检查某个 action 是否有对应的 BLE 指令"""
        if action == "none":
            return True
        return action in self._map.get("actions", {})

    def get_anim_dir(self, emotion: str) -> str:
        """emotion → 动画目录名"""
        return self._map["emotion_to_anim"].get(emotion, "anim1")

    def get_servo_angles(self, emotion: str) -> dict:
        """emotion → 云台舵机角度 (yaw, pitch)"""
        return self._map["servo_emotion_to_angle"].get(emotion, {"yaw": 90, "pitch": 90})

    def has_impossible_keyword(self, text: str) -> bool:
        """检查是否包含不可能执行的关键词"""
        text_lower = text.lower()
        for kw in self._map.get("impossible_keywords", []):
            if kw in text_lower:
                return True
        return False

    def get_impossible_reply(self) -> str:
        """随机返回一条拒绝回复"""
        replies = self._map.get("impossible_replies", ["这个不可以喵~"])
        return random.choice(replies)

    def get_confirmation_reply(self) -> str:
        """随机返回一条确认回复"""
        replies = self._map.get("confirmation_replies", ["好的喵！"])
        return random.choice(replies)

    def parse_llm_json(self, raw: str) -> Optional[dict]:
        """
        解析LLM返回的JSON字符串 (v2)
        兼容 {reply, emotion, action} 格式
        """
        text = raw.strip()
        # 移除 markdown 代码块
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_match:
            text = code_match.group(1).strip()

        try:
            data = json.loads(text)
            action = data.get("action", "none")
            # 后向兼容旧的 move_intent 字段
            if action == "none" and "move_intent" in data:
                old = data.get("move_intent", "none")
                action = {
                    "slow_forward": "move_forward",
                    "slow_backward": "move_backward",
                    "turn_left": "turn_left",
                    "turn_right": "turn_right",
                    "stop": "stop",
                }.get(old, "none")

            return {
                "reply": data.get("reply", ""),
                "emotion": data.get("emotion", "neutral"),
                "action": action,
            }
        except json.JSONDecodeError:
            return None

    def match_action_from_text(self, text: str) -> str:
        """
        本地关键词匹配：用户原文 → 动作
        作为 LLM 的兜底，确保"往前走"这类明确命令不会丢失
        """
        text_lower = text.lower().strip()
        aliases = self._map.get("action_aliases", {})
        for action, keywords in aliases.items():
            for kw in keywords:
                if kw in text_lower:
                    return action
        return "none"
