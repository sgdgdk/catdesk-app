"""
音频捕捉模块

桌面端 (PC):   sounddevice 连续监听麦克风 → 能量检测(VAD) → 捕获语音
Android 端:   AudioRecord API → 系统麦克风
"""
import logging, asyncio, time, threading
from typing import Optional, Callable

logger = logging.getLogger("Audio")


class AudioCapture:
    def __init__(self):
        self._is_recording = False
        self._is_android = self._detect_android()
        self._on_utterance: Optional[Callable[[bytes], None]] = None
        # VAD 参数 (默认值, 可通过 Web 调试面板调整)
        self.vad_threshold = 80
        self.vad_silence_max = 1.2
        self.vad_chunk_s = 0.3

    def _detect_android(self) -> bool:
        try:
            from jnius import autoclass
            autoclass('android.os.Build')
            return True
        except:
            return False

    def set_on_utterance(self, cb: Callable[[bytes], None]):
        """设置语音片段回调"""
        self._on_utterance = cb

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self):
        """开始持续监听"""
        self._is_recording = True
        if self._is_android:
            threading.Thread(target=self._loop_android, daemon=True).start()
        else:
            threading.Thread(target=self._loop_desktop, daemon=True).start()

    def stop(self):
        self._is_recording = False

    # ========== 桌面端: sounddevice 能量检测 ==========
    def _loop_desktop(self):
        """桌面端循环: 监听麦克风 → VAD → 捕获语音片段"""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.warning("sounddevice 未安装, 麦克风不可用")
            return

        fs = 16000
        chunk = int(fs * self.vad_chunk_s)

        logger.info("[Mic] 桌面端麦克风启动, 安静环境下说话")

        buffer = np.array([], dtype=np.int16)
        silent_time = 0.0
        is_speaking = False

        while self._is_recording:
            try:
                block = sd.rec(chunk, samplerate=fs, channels=1, dtype='int16')
                sd.wait()
                block = block.flatten()
                energy = np.abs(block).mean()

                if energy > self.vad_threshold:
                    if not is_speaking:
                        if energy > self.vad_threshold * 2:
                            is_speaking = True
                            buffer = np.array(block, dtype=np.int16)
                            silent_time = 0.0
                            logger.debug("[Mic] 开始说话 (能量=%.0f)" % energy)
                    else:
                        buffer = np.append(buffer, block)
                        silent_time = 0.0
                else:
                    if is_speaking:
                        silent_time += self.vad_chunk_s
                        buffer = np.append(buffer, block)
                        if silent_time >= self.vad_silence_max or len(buffer) > fs * 8.0:
                            avg_energy = np.abs(buffer).mean()
                            if avg_energy > self.vad_threshold:
                                margin = int(fs * 0.15)
                                if len(buffer) > margin * 2:
                                    buffer = buffer[margin:-margin]
                                self._on_desktop_utterance(buffer, fs)
                            buffer = np.array([], dtype=np.int16)
                            is_speaking = False
                            silent_time = 0.0
                    else:
                        # 空闲时保留最近 0.5 秒
                        if len(buffer) > fs // 2:
                            buffer = buffer[-fs//2:]

                time.sleep(0.05)
            except Exception as e:
                logger.error(f"[Mic] {e}")
                time.sleep(0.5)

    def _on_desktop_utterance(self, audio: 'np.ndarray', fs: int):
        """桌面端捕获到一段语音后的处理"""
        import io, wave
        duration = len(audio) / fs
        logger.info(f"[Voice] 捕获 {duration:.1f}s 语音")

        # 保存 WAV 到内存 → 传给回调
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(fs)
            w.writeframes(audio.tobytes())
        buf.seek(0)

        if self._on_utterance:
            self._on_utterance(buf.read())

    # ========== Android: AudioRecord ==========
    def _loop_android(self):
        """Android 端: AudioRecord"""
        try:
            from jnius import autoclass
            AudioRecord = autoclass('android.media.AudioRecord')
            AudioFormat = autoclass('android.media.AudioFormat')
            MediaRecorder = autoclass('android.media.MediaRecorder')

            fs = 16000
            buf_size = AudioRecord.getMinBufferSize(
                fs, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            recorder = AudioRecord(
                MediaRecorder.AudioSource.MIC, fs,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, buf_size)
            recorder.startRecording()

            chunk = int(fs * 0.5)
            buffer = bytearray()
            while self._is_recording:
                data = bytearray(chunk)
                n = recorder.read(data, 0, chunk)
                if n > 0:
                    buffer.extend(data[:n])
                    if len(buffer) > fs * 8:
                        if self._on_utterance:
                            self._on_utterance(bytes(buffer))
                        buffer = bytearray()
                time.sleep(0.05)
            recorder.stop()
            recorder.release()
        except Exception as e:
            logger.error(f"[Mic] Android录音失败: {e}")

