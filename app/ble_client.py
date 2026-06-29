"""
BLE 通信模块（手机端）

使用 Android BLE API 通过 PyJNIus 与 ESP32-S3 Nano 通信

协议格式（兼容原项目）:
- 手机 → ESP32: MOVE,FWD,128  /  SERVO:1,90  /  EXPR:happy
- ESP32 → 手机: 状态回传 / 传感器数据

硬件:
- ESP32-S3 Nano (16MB Flash, 8MB PSRAM)
- 2x SG90 舵机 (头部yaw + pitch)
- 2x 直流减速电机 (左右轮)
"""
import logging
import threading
import time
from typing import Optional, Callable

logger = logging.getLogger("BLE")


class BLEClient:
    """
    BLE 客户端

    封装 Android BLE API:
    - 扫描设备
    - 连接 ESP32-S3 Nano
    - 发送指令
    - 接收状态

    桌面端: 自动尝试串口直连，失败则模拟模式
    """

    def __init__(self):
        self._connected = False
        self._serial = None
        self._serial_port = None
        self._on_message: Optional[Callable] = None
        self._on_connection_change: Optional[Callable] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_callbacks(
        self,
        on_message: Optional[Callable[[str], None]] = None,
        on_connection_change: Optional[Callable[[bool], None]] = None,
    ):
        """设置回调"""
        self._on_message = on_message
        self._on_connection_change = on_connection_change

    # ---- Android BLE (PyJNIus 桥接) ----

    async def start_scan(self, timeout: int = None) -> bool:
        if timeout is None:
            timeout = 10
        logger.info(f"正在扫描BLE设备 (超时{timeout}s)")
        return False

    async def connect(self, address: str = None) -> bool:
        # 桌面端：尝试自动找 ESP32 的串口
        port = self._find_esp32_port()
        if port:
            return await self._connect_serial(port)

        logger.warning("未找到 ESP32 串口，进入模拟模式")
        self._connected = True
        if self._on_connection_change:
            self._on_connection_change(True)
        logger.info("[BLE] 模拟模式: 已连接")
        return True

    async def disconnect(self):
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        self._connected = False
        if self._on_connection_change:
            self._on_connection_change(False)
        logger.info("已断开")

    async def send_command(self, command: str) -> bool:
        if not self._connected:
            logger.warning(f"未连接，无法发送: {command}")
            return False

        # 串口模式
        if self._serial:
            try:
                self._serial.write((command + "\n").encode())
                logger.info(f"[SERIAL] >> {command}")
                return True
            except Exception as e:
                logger.error(f"串口发送失败: {e}")
                self._serial = None
                self._connected = False
                return False

        # 模拟模式
        logger.info(f"[SIM] >> {command}")
        return True

    async def connect_simulated(self):
        """桌面调试: 模拟连接（保留兼容）"""
        return await self.connect()

    # ==================== 串口直连 ====================

    def _find_esp32_port(self) -> Optional[str]:
        """自动查找 ESP32 串口 (VID:PID=303A:1001)"""
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                # ESP32-S3 的 USB 串口
                if "303A:1001" in p.hwid or "VID:PID=303A" in p.hwid:
                    logger.info(f"[SERIAL] 发现 ESP32: {p.device}")
                    return p.device
                # 也匹配常见的 USB 串口
                if "USB 串行" in p.description and "COM" in p.device:
                    logger.info(f"[SERIAL] 可能 ESP32: {p.device}")
                    return p.device
        except Exception as e:
            logger.warning(f"串口扫描失败: {e}")
        return None

    async def _connect_serial(self, port: str) -> bool:
        """连接串口"""
        try:
            import serial
            self._serial = serial.Serial(
                port=port,
                baudrate=115200,
                timeout=0.05,
                write_timeout=0.1
            )
            time.sleep(1)  # 等 ESP32 重启完成
            # 清空缓冲区
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            self._serial_port = port
            self._connected = True
            if self._on_connection_change:
                self._on_connection_change(True)
            logger.info(f"[SERIAL] {port} 已连接!")
            return True
        except Exception as e:
            logger.error(f"串口连接失败 {port}: {e}")
            self._serial = None
            return False

    # ==================== 保留接口 ====================

    async def send_motor(self, left_speed: int, right_speed: int):
        cmd = f"MOTOR:{left_speed},{right_speed}"
        await self.send_command(cmd)

    async def send_servo(self, channel: int, angle: int):
        angle = max(0, min(180, angle))
        cmd = f"SERVO:{channel},{angle}"
        await self.send_command(cmd)

    async def send_emotion(self, emotion: str):
        await self.send_command(f"EXPR:{emotion}")
