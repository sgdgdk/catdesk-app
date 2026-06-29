"""
轻量 Web 调试面板 - 不依赖 Kivy
"""
import json, os, sys, threading, socket, serial, time
from http.server import HTTPServer, BaseHTTPRequestHandler

WEB_PORT = 8767
API_KEY = "sk-289d85b965d94023960ab185f8f6f876"

# 串口连接
ser = None

def find_serial():
    global ser
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            if "303A" in p.hwid or "USB 串行" in p.description:
                ser = serial.Serial(p.device, 115200, timeout=0.05, write_timeout=0.1)
                ser.dtr = False
                ser.rts = False
                time.sleep(0.5)
                ser.reset_input_buffer()
                return f"SERIAL: {p.device}"
    except:
        pass
    return "SERIAL: --"

def send_cmd(cmd):
    global ser
    if ser:
        try:
            ser.write((cmd + "\n").encode())
            ser.flush()
            return True
        except:
            ser = None
    return False

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
.green{background:#2ecc71}.blue{background:#3498db}.gray{background:#555}.orange{background:#e67e22}
#stat{font-size:13px;color:#aaa;padding:5px 0;line-height:1.8}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin:2px;color:#fff}
.ok{background:#2ecc71}.fail{background:#e74c3c}
#logs{background:#0a0a1a;border-radius:6px;padding:10px;height:250px;overflow-y:auto;font-size:12px;font-family:monospace;line-height:1.6}
</style></head><body>
<h1>🐱 DeskCat <span id="statusBadge" class="badge fail">?</span></h1>
<div id="stat"></div>
<div class="card"><h2>BLE 轮子控制</h2><div class="row">
<button class="green" onclick="sendCmd('MOVE,FWD,150')">FWD</button>
<button class="orange" onclick="sendCmd('MOVE,BACK,120')">BACK</button>
<button class="blue" onclick="sendCmd('MOVE,LEFT,140')">LEFT</button>
<button style="background:#9b59b6" onclick="sendCmd('MOVE,RIGHT,140')">RIGHT</button>
<button onclick="sendCmd('MOVE,STOP')">STOP</button>
</div></div>
<div class="card"><h2>PTZ 云台</h2><div class="row">
<button onclick="sendCmd('PTZ:90,45')">↑上</button>
<button onclick="sendCmd('PTZ:90,135')">↓下</button>
<button onclick="sendCmd('PTZ:45,90')">←左</button>
<button onclick="sendCmd('PTZ:135,90')">→右</button>
<button class="gray" onclick="sendCmd('PTZ:CENTER')">回中</button>
</div></div>
<div class="card"><h2>表情</h2><div class="row">
<button class="green" onclick="sendCmd('EXPR:happy')">Hap</button>
<button style="background:#3498db" onclick="sendCmd('EXPR:sad')">Sad</button>
<button style="background:#e74c3c" onclick="sendCmd('EXPR:angry')">Ang</button>
<button style="background:#9b59b6" onclick="sendCmd('EXPR:thinking')">Thk</button>
<button onclick="sendCmd('EXPR:neutral')">Neu</button>
</div></div>
<div class="card"><h2>硬件测试</h2><div class="row"><button style="background:#555" onclick="sendCmd('TEST')">运行 TEST</button></div></div>
<div class="card"><h2>Log</h2><div id="logs"></div></div>
<script>
function addLog(m,t){ var d=document.getElementById('logs'),x=document.createElement('div'); x.textContent='['+new Date().toLocaleTimeString()+'] '+m; if(t)x.className=t; d.appendChild(x); d.scrollTop=d.scrollHeight; }
async function sendCmd(c){ addLog('>> '+c,''); await fetch('/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c})}); }
setInterval(async function(){
 try{
  var r=await fetch('/status'); var j=await r.json();
  document.getElementById('stat').innerHTML='串口: <b>'+j.serial+'</b>';
  document.getElementById('statusBadge').textContent=j.serial.includes('COM')?'OK':'!';
  document.getElementById('statusBadge').className='badge '+(j.serial.includes('COM')?'ok':'fail');
 }catch(e){}
},2000)
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
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
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_HTML.encode("utf-8"))
        elif self.path == "/status":
            s = find_serial() if ser is None else f"SERIAL: {ser.port}"
            self._json(200, {"serial": s})
        else:
            self._json(404, {"error": "not found"})
    def do_POST(self):
        b = self._body()
        if self.path == "/cmd":
            cmd = b.get("cmd", "")
            ok = send_cmd(cmd) if cmd else False
            print(f"[CMD] {cmd} -> {'OK' if ok else 'FAIL'}")
            self._json(200, {"ok": ok, "cmd": cmd})
        else:
            self._json(404, {"error": "unknown"})

if __name__ == "__main__":
    s = find_serial()
    print(f"[Web] http://0.0.0.0:{WEB_PORT}")
    print(f"[Serial] {s}")
    HTTPServer(("0.0.0.0", WEB_PORT), Handler).serve_forever()
