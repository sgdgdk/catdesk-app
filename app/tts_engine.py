"""
TTS 语音合成引擎

桌面端 (PC):  edge-tts save_sync → pygame.mixer 播放
Android 端:  系统 TextToSpeech API → 手机扬声器
"""
import logging, os, tempfile, time
from typing import Optional, Callable
from app.config import TTS_VOICE

logger = logging.getLogger("TTS")


class TTSEngine:
    def __init__(self):
        self._is_speaking = False
        self._on_finish: Optional[Callable] = None
        self._is_android = self._detect_android()

    def _detect_android(self) -> bool:
        try:
            from jnius import autoclass
            autoclass('android.os.Build')
            return True
        except:
            return False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def sync_speak(self, text: str):
        """同步 TTS (后台线程调用, 不需要 asyncio)"""
        if not text.strip():
            return
        self._is_speaking = True
        logger.info(f"TTS: {text[:40]}...")

        try:
            if self._is_android:
                self._speak_android(text)
            else:
                self._speak_desktop(text)
        except Exception as e:
            logger.error(f"TTS失败: {e}")
        finally:
            self._is_speaking = False
            if self._on_finish:
                self._on_finish()

    def _speak_desktop(self, text: str):
        """电脑扬声器"""
        import edge_tts, pygame

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        edge_tts.Communicate(text, TTS_VOICE).save_sync(path)

        if not os.path.isfile(path):
            logger.error("MP3创建失败")
            return

        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()

        try: os.remove(path)
        except: pass
        logger.info("TTS播放完成")

    def _speak_android(self, text: str):
        """手机扬声器"""
        from jnius import autoclass, cast
        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        tts = TextToSpeech(cast('android.content.Context',
                               autoclass('org.renpy.pygame.PygameSurface').getContext()), None)
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, None)
        while tts.isSpeaking():
            time.sleep(0.1)
        tts.shutdown()
