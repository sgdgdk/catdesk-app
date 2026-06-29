"""
DeskCat App - Fullscreen Emotion + Voice + Web Debug

Flow:
  Voice/Text -> LLM -> JSON {reply, emotion, move_intent}
       -> emotion self-check(extract from text) -> animation
       -> move_intent lookup -> BLE command
       -> reply -> TTS playback + Web display

Self-check: startup diagnostics for API Key, animations, Web server
"""
import json, os, sys, logging, threading, asyncio, socket, weakref
from http.server import HTTPServer, BaseHTTPRequestHandler

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivy.core.text import LabelBase

# 字体 - 兼容 Windows / Android
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\mingliub.ttc",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/system/fonts/DroidSansFallback.ttf",
]
for _f in _FONT_CANDIDATES:
    if os.path.isfile(_f):
        LabelBase.register(name="Roboto", fn_regular=_f)
        break

# 主线程初始化 pygame mixer (供 TTS 扬声器使用, 仅桌面)
try:
    import pygame
    if not hasattr(pygame, 'mixer') or not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
except Exception as e:
    print("[Audio] pygame init:", e)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import LLM_API_KEY
from app.intent_mapper import IntentMapper
from app.llm_client import LLMClient
from app.emotion_renderer import EmotionRenderer
from app.emotion_parser import extract_emotion_safe
from app.ble_client import BLEClient
from app.tts_engine import TTSEngine
from app.audio_capture import AudioCapture

# Android / 桌面 BLE 自适应
_IS_ANDROID = False
try:
    from jnius import autoclass
    autoclass('android.os.Build')
    _IS_ANDROID = True
except:
    pass

if _IS_ANDROID:
    from app.ble_android import AndroidBLEClient
    _ble_android = AndroidBLEClient()
else:
    from app.ble_direct import find_and_connect as ble_connect, send_command as ble_send, disconnect as ble_disconnect

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
logger = logging.getLogger("Main")


class DeskCatLayout(BoxLayout):
    pass


WEB_PORT = 8767


# ---------- Self Check ----------
def run_self_check():
    """Startup diagnostics"""
    checks = []
    def add(name, ok, msg):
        checks.append({"name": name, "ok": ok, "msg": msg})
    add("API Key", bool(LLM_API_KEY),
        LLM_API_KEY[:12] + "..." if LLM_API_KEY else "MISSING")
    anim_dir = os.path.join(os.path.dirname(__file__), "app", "data", "anim")
    anim_counts = {}
    if os.path.isdir(anim_dir):
        for d in sorted(os.listdir(anim_dir)):
            p = os.path.join(anim_dir, d)
            if os.path.isdir(p):
                n = len([f for f in os.listdir(p) if f.endswith((".jpg",".png"))])
                anim_counts[d] = n
    total = sum(anim_counts.values())
    add("Animations", total > 0,
        f"{len(anim_counts)} types, {total} frames" if anim_counts else "NOT FOUND")
    add("Web Port", True, f":{WEB_PORT}")
    return checks


# ---------- Web Server ----------
def start_web(ref, checks):
    """Web debug panel"""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _json(self, c, d):
            self.send_response(c)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(d, ensure_ascii=False).encode("utf-8"))
        def _body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        def do_GET(self):
            a = ref()
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(WEB_HTML.encode("utf-8"))
            elif self.path == "/status":
                self._json(200, {
                    "emotion": a.current_emotion if a else "?",
                    "ble": a.ble_status if a else "?",
                    "voice": a.is_recording if a else False,
                    "vad_threshold": a._mic.vad_threshold if a else 80,
                    "vad_silence_max": a._mic.vad_silence_max if a else 1.2,
                    "checks": checks,
                    "has_api": bool(LLM_API_KEY),
                    "reply": a._last_llm_reply if a else "",
                    "reply_emotion": a._last_llm_emotion if a else "",
                })
            elif self.path.startswith("/favicon"):
                self.send_response(204); self.end_headers()
            else:
                self._json(404, {"error": "not found"})
        def do_POST(self):
            a = ref()
            if not a: return self._json(500, {"error": "no app"})
            b = self._body(); p = self.path
            if p == "/chat":
                t = b.get("text", "")
                if t.strip():
                    threading.Thread(target=a._do_llm, args=(t,), daemon=True).start()
                    self._json(200, {"ok": True})
                else: self._json(400, {"error": "empty"})
            elif p == "/emotion":
                a.set_emotion(b.get("emotion", "neutral"))
                self._json(200, {"ok": True})
            elif p == "/ble":
                cmd = b.get("cmd", "MOVE,STOP")
                try:
                    a._serial_send(cmd)
                    self._json(200, {"ok": True, "cmd": cmd})
                except Exception as ex:
                    self._json(200, {"ok": False, "error": str(ex)})
            elif p == "/vad":
                t = b.get("threshold", 0)
                s = b.get("silence_max", 0.0)
                if t > 0: a._mic.vad_threshold = t
                if s > 0: a._mic.vad_silence_max = s
                logger.info(f"[VAD] threshold={a._mic.vad_threshold} silence={a._mic.vad_silence_max}")
                self._json(200, {"ok": True, "threshold": a._mic.vad_threshold, "silence_max": a._mic.vad_silence_max})
            else: self._json(404, {"error": "unknown"})
    try:
        s = HTTPServer(("0.0.0.0", WEB_PORT), H)
        ips = set()
        try:
            for info in socket.getaddrinfo(socket.gethostname(), WEB_PORT):
                ip = info[4][0]
                if ip and not ip.startswith("127."): ips.add(ip)
        except: pass
        if not _IS_ANDROID:
            try:
                import subprocess
                r = subprocess.run(["ipconfig"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                for line in r.stdout.splitlines():
                    if "IPv4" in line:
                        ip = line.split(":")[-1].strip()
                        if ip: ips.add(ip)
            except: pass
        first_ip = next(iter(ips), "127.0.0.1")
        logger.info("[Web] http://" + first_ip + ":" + str(WEB_PORT))
        s.serve_forever()
    except Exception as e:
        logger.error("[Web] " + str(e))


WEB_HTML = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeskCat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:sans-serif;background:#1a1a2e;color:#eee;padding:20px;max-width:800px;margin:auto}
h1{font-size:20px;color:#e94560;margin-bottom:15px;display:flex;align-items:center;gap:10px}
.card{background:#16213e;border-radius:10px;padding:15px;margin-bottom:15px}
.card h2{font-size:14px;color:#aaa;margin-bottom:10px}
.row{display:flex;gap:8px;margin-bottom:8px;align-items:center;flex-wrap:wrap}
input,button{padding:8px 12px;border:none;border-radius:6px;font-size:14px}
input{flex:1;background:#0f3460;color:#fff}
button{background:#e94560;color:#fff;cursor:pointer;min-width:50px}
button:hover{opacity:.8}
.green{background:#2ecc71};.blue{background:#3498db};.gray{background:#555}
#stat{font-size:13px;color:#aaa;padding:5px 0;line-height:1.8}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin:2px;color:#fff}
.ok{background:#2ecc71};.warn{background:#e67e22};.fail{background:#e74c3c}
#logs{background:#0a0a1a;border-radius:6px;padding:10px;height:250px;overflow-y:auto;font-size:12px;font-family:monospace;line-height:1.6}
#logs .in{color:#8be9fd};#logs .out{color:#50fa7b};#logs .emo{color:#ff79c6};#logs .ble{color:#f1fa8c};#logs .sys{color:#6272a4}
.vad-slider{width:120px;cursor:pointer}
.vad-label{font-size:12px;color:#888;min-width:40px}
</style></head><body>
<h1>🐱 DeskCat <span id="apiBadge" class="badge warn">?</span></h1>
<div id="stat"></div>
<div class="card"><h2>Chat</h2><div class="row"><input id="chatInput" placeholder="..." onkeydown="if(event.key==='Enter')sendChat()"><button onclick="sendChat()">Send</button></div></div>
<div id="replyBox" class="card" style="background:#1e2a3a;display:none"><h2>AI Reply</h2><div style="font-size:14px;line-height:1.6;color:#eee;word-break:break-word"></div></div>
<div class="card"><h2>VAD (麦克风检测)</h2><div class="row">
<span class="vad-label">阈值</span>
<input class="vad-slider" id="vadThresh" type="range" min="20" max="500" value="80" oninput="updateVad()">
<span id="vadThreshVal" class="vad-label">80</span>
<span class="vad-label">静音</span>
<input class="vad-slider" id="vadSilence" type="range" min="0.3" max="3.0" step="0.1" value="1.2" oninput="updateVad()">
<span id="vadSilenceVal" class="vad-label">1.2s</span>
</div></div>
<div class="card"><h2>Emotions</h2><div class="row">
<button class="green" onclick="setEmotion('happy')">Hap</button>
<button style="background:#3498db" onclick="setEmotion('sad')">Sad</button>
<button style="background:#e74c3c" onclick="setEmotion('angry')">Ang</button>
<button style="background:#9b59b6" onclick="setEmotion('thinking')">Think</button>
<button style="background:#7f8c8d" onclick="setEmotion('sleepy')">Slp</button>
<button style="background:#e84393" onclick="setEmotion('love')">Love</button>
<button onclick="setEmotion('neutral')">Neut</button>
</div></div>
<div class="card"><h2>BLE</h2><div class="row">
<button class="green" onclick="sendBle('MOVE,FWD,150')">FWD</button>
<button style="background:#e67e22" onclick="sendBle('MOVE,BACK,120')">BACK</button>
<button class="blue" onclick="sendBle('MOVE,LEFT,140')">LEFT</button>
<button style="background:#9b59b6" onclick="sendBle('MOVE,RIGHT,140')">RIGHT</button>
<button onclick="sendBle('MOVE,STOP')">STOP</button>
</div></div>
<div class="card"><h2>PTZ 云台</h2><div class="row">
<button onclick="sendBle('PTZ:90,45')">↑上</button>
<button onclick="sendBle('PTZ:90,135')">↓下</button>
<button onclick="sendBle('PTZ:45,90')">←左</button>
<button onclick="sendBle('PTZ:135,90')">→右</button>
<button class="gray" onclick="sendBle('PTZ:CENTER')">回中</button>
</div></div>
<div class="card"><h2>Log</h2><div id="logs"></div></div>
<script>
function addLog(m,t){
 var d=document.getElementById('logs'),x=document.createElement('div');
 x.textContent='['+new Date().toLocaleTimeString()+'] '+m;
 if(t)x.className=t;d.appendChild(x);d.scrollTop=d.scrollHeight
}
async function sendChat(){
 var i=document.getElementById('chatInput'),t=i.value.trim();if(!t)return;
 i.value='';addLog('>> '+t,'in');
 var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
 var j=await r.json();addLog(j.ok?'[sent]':'[err]','sys')
}
async function setEmotion(e){addLog('[emo] '+e,'emo');await fetch('/emotion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({emotion:e})})}
async function sendBle(c){addLog('[BLE] '+c,'ble');await fetch('/ble',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c})})}
async function updateVad(){
 var t=document.getElementById('vadThresh').value;
 var s=document.getElementById('vadSilence').value;
 document.getElementById('vadThreshVal').textContent=t;
 document.getElementById('vadSilenceVal').textContent=s+'s';
 await fetch('/vad',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({threshold:parseInt(t),silence_max:parseFloat(s)})});
}
var _lastReply="",_replyEl=document.getElementById('replyBox');
setInterval(async function(){
 try{
  var r=await fetch('/status');var j=await r.json();
  document.getElementById('stat').innerHTML=
   'Emotion: <b>'+j.emotion+'</b> | BLE: '+j.ble+
   ' | VAD阈值: '+j.vad_threshold+' 静音: '+j.vad_silence_max+'s'+
   ' | Checks: '+j.checks.map(function(c){return c.name+':'+(c.ok?'OK':'!!')}).join(' ');
  var ab=document.getElementById('apiBadge');
  ab.textContent=j.has_api?'API OK':'NO API';
  ab.className='badge '+(j.has_api?'ok':'fail');
  if(j.reply && j.reply!=_lastReply){
   _lastReply=j.reply;
   _replyEl.innerHTML='<b>['+j.reply_emotion+']</b> '+j.reply;
   _replyEl.style.display='block';
   addLog('[AI] '+j.reply,'out');
  }
 }catch(e){}
},1500)
</script></body></html>"""


class CatDesktopApp(App):
    current_emotion = StringProperty("neutral")
    ble_status = StringProperty("BLE: --")
    is_recording = BooleanProperty(False)
    anim_frame = StringProperty("")
    web_url = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mapper = IntentMapper()
        self._llm = LLMClient()
        self._renderer = EmotionRenderer()
        self._ble = BLEClient()
        self._tts = TTSEngine()
        self._mic = AudioCapture()
        self._mic.set_on_utterance(self._on_voice_utterance)
        self._history = []
        self._frames = []
        self._idx = 0
        self._once_tick = None
        self._checks = run_self_check()
        self._last_llm_reply = ""
        self._last_llm_emotion = ""
        self._req_id = 0
        self._is_llm_busy = False
        try:
            self.web_url = "http://" + socket.gethostbyname(socket.gethostname()) + ":" + str(WEB_PORT)
        except:
            self.web_url = "http://127.0.0.1:" + str(WEB_PORT)

        # 串口对象（常开，避免 DTR 复位 ESP32）
        self._ser = None

    def build(self):
        self.title = "DeskCat"
        return DeskCatLayout()

    def on_start(self):
        logger.info("========== SELF CHECK ==========")
        for c in self._checks:
            logger.info("  [" + ("OK" if c["ok"] else "!!") + "] " + c["name"] + ": " + c["msg"])
        logger.info("  Web: " + self.web_url)
        logger.info("================================")

        self.set_emotion("neutral")
        threading.Thread(target=start_web, args=(weakref.ref(self), self._checks), daemon=True).start()
        Clock.schedule_once(lambda d: self._start_mic(), 2)
        Clock.schedule_once(lambda d: threading.Thread(target=self._auto_connect, daemon=True).start(), 3)

    # ---- Emotion ----
    def set_emotion(self, emotion):
        emotion = emotion.lower()
        self.current_emotion = emotion
        Clock.unschedule(self._tick)
        if self._once_tick:
            Clock.unschedule(self._once_tick)
            self._once_tick = None
        if emotion == "neutral" or emotion == "thinking":
            self._play_loop(emotion)
        else:
            self._play_once(emotion)
        self._serial_send("EXPR:" + emotion)

    def _play_loop(self, emotion):
        self._frames = self._renderer.get_play_frames(emotion)
        self._idx = 0
        if self._frames:
            self.anim_frame = self._frames[0]
            Clock.schedule_interval(self._tick, 1.0/20)
        else:
            self.anim_frame = ""

    def _tick(self, dt):
        if not self._frames: return False
        self._idx = (self._idx + 1) % len(self._frames)
        self.anim_frame = self._frames[self._idx]

    def _play_once(self, emotion):
        self._frames = self._renderer.get_play_frames(emotion)
        if not self._frames:
            self.set_emotion("neutral"); return
        self._idx = 0
        self.anim_frame = self._frames[0]
        total = len(self._frames)
        def _cb(dt):
            self._idx += 1
            if self._idx >= total:
                Clock.unschedule(_cb); self._once_tick = None; self.set_emotion("neutral"); return
            self.anim_frame = self._frames[self._idx]
        self._once_tick = _cb
        Clock.schedule_interval(self._once_tick, 1.0/20)

    # ---- Voice ----
    def _start_mic(self):
        self.is_recording = True
        logger.info("[Mic] Auto-listening (desktop=sounddevice, android=AudioRecord)")
        self._mic.start()

    def _on_voice_utterance(self, wav_data: bytes):
        """语音识别 → LLM → TTS (异步执行, 不阻塞音频线程)"""
        logger.info(f"[Voice] 捕获 {len(wav_data)} bytes 语音")

        # 在后台线程执行 ASR+LLM, 避免阻塞麦克风循环
        threading.Thread(target=self._asr_and_llm, args=(wav_data,), daemon=True).start()

    def _asr_and_llm(self, wav_data: bytes):
        """语音识别 (Whisper离线, 自动找imageio提供的ffmpeg)"""
        text = None
        # 自动配置ffmpeg PATH
        try:
            import imageio_ffmpeg
            ff_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
            os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
        except: pass

        try:
            import whisper, tempfile, re
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with open(path, "wb") as f:
                f.write(wav_data)
            model = whisper.load_model("tiny")
            result = model.transcribe(path, language="zh", temperature=0.0)
            text = result["text"].strip()
            os.remove(path)
            if text and len(text) >= 2:
                logger.info("[ASR] Whisper: " + text)
            else:
                text = None
                logger.info("[ASR] 结果无效(太短或乱码)")
        except Exception as e:
            logger.warning("ASR: " + str(e)[:60])

        if text:
            self._do_llm(text)
        else:
            logger.info("[ASR] 未检测到有效语音")

    # ---- LLM ----
    @mainthread
    def _show_thinking(self):
        """安全地在主线程显示thinking表情"""
        self.set_emotion("thinking")

    def _do_llm(self, text):
        """Voice/Web text -> LLM (v2 支持命令检测)"""
        if not LLM_API_KEY: return

        # 断开上一次
        self._req_id += 1
        req_id = self._req_id
        threading.Thread(target=self._tts_stop_sync, daemon=True).start()
        self._show_thinking()
        self._is_llm_busy = True

        # 先检查是不是不可能的指令
        if self._mapper.has_impossible_keyword(text):
            reply = self._mapper.get_impossible_reply()
            if req_id == self._req_id:
                self._on_llm_result(reply, "shy", "none")
            self._is_llm_busy = False
            return

        self._history.append({"role": "user", "content": text})
        self._history = self._history[-20:]
        try:
            async def _run():
                full = ""
                async for c in self._llm.chat(text, self._history):
                    if c: full += c
                return full
            r = asyncio.run(_run())
            if r and req_id == self._req_id:
                self._on_llm(r, text)  # 传用户原文做本地兜底
            self._is_llm_busy = False
        except Exception as e:
            logger.error("LLM: " + str(e))
            self._is_llm_busy = False
            if req_id == self._req_id:
                self.set_emotion("neutral")

    @mainthread
    def _on_llm(self, raw, user_text=""):
        """
        LLM reply handler v2:
        解析 {reply, emotion, action} → 表情 + BLE + TTS
        user_text: 用户原始输入，用于本地命令兜底
        """
        parsed = self._mapper.parse_llm_json(raw)
        if parsed:
            reply   = parsed.get("reply", "")
            emotion = parsed.get("emotion", "neutral")
            action  = parsed.get("action", "none")
        else:
            reply = raw.strip()
            emotion = "neutral"
            action = "none"
            logger.info("LLM reply not JSON, fallback text")

        # 本地命令兜底：如果 LLM 返回 none 但用户确实说了命令
        if action == "none" and user_text:
            local_action = self._mapper.match_action_from_text(user_text)
            if local_action != "none":
                logger.info(f"本地命令匹配: {user_text} -> {local_action}")
                action = local_action

        self._on_llm_result(reply, emotion, action)

    def _on_llm_result(self, reply: str, emotion: str, action: str):
        """统一的 LLM 结果处理"""
        # 情感自检
        if emotion == "neutral":
            extracted = extract_emotion_safe(reply, default="neutral")
            if extracted != "neutral":
                emotion = extracted

        logger.info(f"LLM => emotion={emotion} action={action}")

        # 保存回复
        self._last_llm_reply = reply
        self._last_llm_emotion = emotion

        # 显示表情
        self.set_emotion(emotion)

        # BLE 动作（轮子 / 云台）
        ble = self._mapper.get_ble_command(action)
        if ble:
            self._serial_send(ble)

        # 如果是有动作的命令，情绪改为相应的云台角度
        if action and action != "none":
            angles = self._mapper.get_servo_angles(emotion)
            yaw = angles.get("yaw", 90)
            pitch = angles.get("pitch", 90)
            self._serial_send(f"PTZ:{yaw},{pitch}")

        # TTS 播放回复
        if reply:
            threading.Thread(target=self._tts_sync, args=(reply,), daemon=True).start()

    # ---- 串口直连 / BLE 直连 ----
    def _auto_connect(self):
        """自动连接：Android → BLE，桌面 → USB串口 → BLE"""
        if _IS_ANDROID:
            # Android: 仅有 BLE
            logger.info("[BLE] 手机模式, 尝试蓝牙连接 DeskCat-Nano...")
            try:
                ok = _ble_android.scan_and_connect(timeout=10.0)
                if ok:
                    self.ble_status = "BLE: 已连接"
                    logger.info("[BLE] 蓝牙已连接!")
                    return
            except Exception as e:
                logger.warning(f"[BLE] 连接失败: {e}")
            self.ble_status = "BLE: --"
            logger.info("[BLE] 未找到 ESP32")
            return

        # 桌面: 串口优先
        try:
            import serial
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                if "303A" in p.hwid or "USB 串行" in p.description:
                    self._ser = serial.Serial(p.device, 115200, timeout=0.05, write_timeout=0.1)
                    self._ser.dtr = False
                    self._ser.rts = False
                    import time
                    time.sleep(0.5)
                    self._ser.reset_input_buffer()
                    self.ble_status = "SERIAL: " + p.device
                    logger.info(f"[SERIAL] {p.device} 已连接")
                    return
        except Exception as e:
            logger.warning(f"[SERIAL] 扫描失败: {e}")

        # USB 不可用 → 尝试 BLE 直连
        logger.info("[BLE] 尝试蓝牙连接 DeskCat-Nano...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(ble_connect())
            loop.close()
            if ok:
                self.ble_status = "BLE: 已连接"
                logger.info("[BLE] 蓝牙已连接，Web面板可用!")
                return
        except Exception as e:
            logger.warning(f"[BLE] 连接失败: {e}")

        self._ser = None
        self.ble_status = "SERIAL: --"
        logger.info("[SERIAL/BLE] 未找到 ESP32")

    def _serial_send(self, cmd):
        """串口发送 → BLE 后备 (自动适配 Android/桌面)"""
        if _IS_ANDROID:
            try:
                ok = _ble_android.send_command(cmd)
                if ok:
                    return True
            except Exception as e:
                logger.warning(f"[BLE] 发送失败: {e}")
            logger.info(f"[SIM] >> {cmd}")
            return True

        # === 桌面端 ===
        if getattr(self, '_ser', None):
            try:
                self._ser.write((cmd + "\n").encode())
                self._ser.flush()
                logger.info(f"[SERIAL] >> {cmd}")
                return True
            except Exception as e:
                logger.warning(f"[SERIAL] 发送失败: {e}")
                self._ser = None

        # 串口不可用 → 走 BLE
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(ble_send(cmd))
            loop.close()
            if ok:
                return True
        except Exception as e:
            logger.warning(f"[BLE] 发送失败: {e}")

        logger.info(f"[SIM] >> {cmd}")
        return True

    def _tts_sync(self, text):
        self._tts.sync_speak(text)
        # TTS播完后如果当前没有新的LLM请求, 确保回neutral
        if not self._is_llm_busy and self.current_emotion != "neutral":
            self.set_emotion("neutral")

    def _tts_stop_sync(self):
        """打断TTS播放 (兼容无 pygame 环境)"""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except:
            pass


if __name__ == "__main__":
    CatDesktopApp().run()
