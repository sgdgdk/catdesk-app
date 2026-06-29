"""
表情渲染引擎 - 手机端实现

对标 LOOI 的分层渲染系统:
- LOOI: 手机 App 实时渲染 PNG 分层 → 显示在 App 内
- 本实现: 使用原项目 JPEG 序列帧，在手机屏幕上播放动画

架构:
1. 手机端从 data/anim/ 目录加载 JPEG 序列帧
2. 根据 emotion 查表定位动画目录
3. 使用 Kivy Image + Clock 实现帧动画播放
4. 支持渐变过渡
"""
import os
import glob
import random
from typing import List, Optional
from app.config import ANIM_DIR, EMOTION_TO_ANIM_DIR, ANIM_FPS, ANIM_PLAY_COUNT


class EmotionRenderer:
    """
    表情渲染器
    管理动画帧加载和播放状态
    """

    def __init__(self):
        self._anim_dir = ANIM_DIR
        self._cache = {}  # anim_name -> [frame_paths]

    def get_anim_paths(self, emotion: str) -> List[str]:
        """
        获取情绪对应的动画帧文件列表
        自动排序 jpg/png 文件
        """
        anim_name = EMOTION_TO_ANIM_DIR.get(emotion, "neut")
        if anim_name in self._cache:
            return self._cache[anim_name]

        anim_path = os.path.join(self._anim_dir, anim_name)
        if not os.path.isdir(anim_path):
            return self._get_fallback_frames(emotion)

        # 收集所有 jpg/png 文件并排序
        frames = (
            sorted(glob.glob(os.path.join(anim_path, "*.jpg"))) +
            sorted(glob.glob(os.path.join(anim_path, "*.jpeg"))) +
            sorted(glob.glob(os.path.join(anim_path, "*.png")))
        )

        if not frames:
            return self._get_fallback_frames(emotion)

        self._cache[anim_name] = frames
        return frames

    def get_play_frames(self, emotion: str) -> List[str]:
        """
        获取播放用的帧列表（按播放次数重复）
        """
        frames = self.get_anim_paths(emotion)
        if len(frames) <= 1:
            return frames
        return frames * ANIM_PLAY_COUNT

    @property
    def fps(self) -> int:
        return ANIM_FPS

    def _get_fallback_frames(self, emotion: str) -> List[str]:
        """无有效动画文件时的回退"""
        return []

    def get_emotion_emoji(self, emotion: str) -> str:
        """获取情绪对应的emoji"""
        from app.config import EMOTION_EMOJI
        return EMOTION_EMOJI.get(emotion, "😐")

    def prefetch(self, emotion: str):
        """预加载某情绪的动画到缓存"""
        self.get_anim_paths(emotion)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
