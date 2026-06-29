"""
🐱 DeskCat 看门狗 - 独立监控程序
实时监控串口连接和 Web 服务器，自动重连

用法: 
  在终端启动后最小化即可
  python watchdog.py
"""
import subprocess
import sys
import time
import os
import threading

APP_PATH = os.path.join(os.path.dirname(__file__), "main.py")
VENV_PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
if not os.path.isfile(VENV_PYTHON):
    VENV_PYTHON = sys.executable

app_process = None
app_lock = threading.Lock()


def start_app():
    """启动主程序"""
    global app_process
    with app_lock:
        if app_process and app_process.poll() is None:
            return  # 已运行
        print(f"[看门狗] 启动 App...")
        app_process = subprocess.Popen(
            [VENV_PYTHON, APP_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATED_NO_WINDOW') else 0
        )
        print(f"[看门狗] App PID={app_process.pid}")


def check_serial():
    """检查 COM18 是否存在"""
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            if "303A" in p.hwid or "USB 串行" in p.description:
                return True
    except:
        pass
    return False


def check_web():
    """检查 Web 端口 8767 是否在监听"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex(('127.0.0.1', 8767))
        s.close()
        return result == 0
    except:
        return False


def monitor():
    """监控循环"""
    serial_last_ok = 0
    web_last_ok = 0
    serial_disconnects = 0
    web_disconnects = 0

    while True:
        now = time.time()

        # 1. App 进程是否还活着
        app_alive = app_process and app_process.poll() is None

        # 2. 串口检测
        serial_ok = check_serial()
        if serial_ok:
            serial_last_ok = now
            serial_disconnects = 0
        elif now - serial_last_ok > 5:
            serial_disconnects += 1
            print(f"[看门狗] ⚠ 串口断开 (第{serial_disconnects}次)")
            serial_last_ok = now

        # 3. Web 检测
        web_ok = check_web()
        if web_ok:
            web_last_ok = now
            web_disconnects = 0
        elif now - web_last_ok > 8:
            web_disconnects += 1
            print(f"[看门狗] ⚠ Web 无响应 (第{web_disconnects}次)")
            web_last_ok = now

        # 4. 如果 App 没在运行 → 重启
        if not app_alive:
            print(f"[看门狗] 🔄 App 未运行，启动...")
            start_app()

        # 5. Web 一直连不上 → 重启 App
        if web_disconnects >= 3:
            print(f"[看门狗] 🔄 Web 多次断开，重启 App...")
            if app_process and app_process.poll() is None:
                app_process.terminate()
                time.sleep(2)
            start_app()
            web_disconnects = 0
        elif serial_disconnects >= 3 and not serial_ok:
            print(f"[看门狗] 🔄 串口多次断开，重启 App...")
            if app_process and app_process.poll() is None:
                pass  # 串口断开不需要重启 App，App 会自动重连
            serial_disconnects = 0

        time.sleep(3)


if __name__ == "__main__":
    # 先启动 App
    start_app()
    # 再启动监控
    try:
        monitor()
    except KeyboardInterrupt:
        print("\n[看门狗] 退出")
        if app_process and app_process.poll() is None:
            app_process.terminate()
