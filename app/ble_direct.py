"""
BLE 直连模块
电脑通过蓝牙直接发命令到 ESP32，不走串口
这样拔掉 USB 后 Web 面板依然能控制硬件
"""
import asyncio
import logging
from bleak import BleakScanner, BleakClient

logger = logging.getLogger("BLE-Direct")

BLE_NAME = "DeskCat-Nano"
BLE_TX_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

_client = None


async def find_and_connect():
    """扫描并连接 DeskCat-Nano"""
    global _client
    if _client and _client.is_connected:
        return True

    try:
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for addr, (ble_device, adv_data) in devices.items():
            name = adv_data.local_name if adv_data and adv_data.local_name else ""
            if BLE_NAME in name or (ble_device and BLE_NAME in (ble_device.name or "")):
                logger.info(f"发现: {addr} ({name})")
                _client = BleakClient(addr, timeout=15.0)
                await _client.connect()
                logger.info(f"已连接!")
                return True
    except Exception as e:
        logger.warning(f"BLE 连接失败: {e}")

    _client = None
    return False


async def send_command(cmd: str) -> bool:
    """通过 BLE 发送命令"""
    global _client
    if not _client or not _client.is_connected:
        logger.warning("BLE 未连接")
        return False

    try:
        data = (cmd + "\n").encode("utf-8")
        await _client.write_gatt_char(BLE_TX_UUID, data, response=False)
        logger.info(f"[BLE] >> {cmd}")
        return True
    except Exception as e:
        logger.warning(f"BLE 发送失败: {e}")
        _client = None
        return False


async def disconnect():
    """断开 BLE"""
    global _client
    if _client and _client.is_connected:
        await _client.disconnect()
    _client = None
