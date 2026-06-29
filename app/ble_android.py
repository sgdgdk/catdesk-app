"""
Android BLE 通信模块 (PyJNIus 桥接)

在 Android 上通过 Java BLE API 与 ESP32-S3 Nano 通信
使用场景: Kivy App 在手机上运行时
"""
import logging
import threading
import time
from typing import Optional, Callable

logger = logging.getLogger("BLE-Android")


class AndroidBLEClient:
    """Android BLE 客户端 (单例)"""

    def __init__(self):
        self._connected = False
        self._device_address = None
        self._gatt = None
        self._context = None
        self._bluetooth_manager = None
        self._adapter = None
        self._scanner = None
        self._characteristic = None
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._lock = threading.Lock()

        # BLE 配置（与 config.py 一致）
        self._target_name = "DeskCat-Nano"
        self._service_uuid = "0000ffe0-0000-1000-8000-00805f9b34fb"
        self._char_tx_uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_callbacks(self, on_connect=None, on_disconnect=None):
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    def _init_android(self) -> bool:
        """初始化 Android 蓝牙适配器"""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self._context = PythonActivity.mActivity
            self._bluetooth_manager = autoclass('android.bluetooth.BluetoothManager')
            manager = self._context.getSystemService(self._context.BLUETOOTH_SERVICE)
            self._adapter = manager.getAdapter()
            if not self._adapter:
                logger.error("设备不支持蓝牙")
                return False
            if not self._adapter.isEnabled():
                logger.error("蓝牙未开启")
                return False
            return True
        except Exception as e:
            logger.error(f"初始化蓝牙失败: {e}")
            return False

    def scan_and_connect(self, timeout: float = 10.0) -> bool:
        """
        扫描 BLE 设备并连接
        - 在 Android 上使用 BluetoothLeScanner
        - 扫描到目标设备后自动连接
        """
        if not self._init_android():
            return False

        logger.info(f"[BLE] 扫描中 (目标: {self._target_name})...")
        found_event = threading.Event()
        found_address = [None]
        scan_callback = self._create_scan_callback(found_event, found_address)

        try:
            # 获取 BluetoothLeScanner
            from jnius import autoclass
            self._scanner = self._adapter.getBluetoothLeScanner()
            if not self._scanner:
                logger.error("获取 BLE Scanner 失败")
                return False

            # 开始扫描
            self._scanner.startScan(scan_callback)
            found = found_event.wait(timeout=timeout)
            self._scanner.stopScan(scan_callback)

            if not found or not found_address[0]:
                logger.warning("[BLE] 未找到 DeskCat-Nano")
                return False

            # 连接设备
            return self._connect_device(found_address[0])

        except Exception as e:
            logger.error(f"[BLE] 扫描失败: {e}")
            try:
                if self._scanner:
                    self._scanner.stopScan(scan_callback)
            except:
                pass
            return False

    def _create_scan_callback(self, found_event, found_address):
        """创建 Android ScanCallback (通过 PyJNIus PythonJavaClass)"""
        from jnius import PythonJavaClass, java_method, autoclass

        class ScanCallback(PythonJavaClass):
            __javainterfaces__ = ['android/bluetooth/le/ScanCallback']

            def __init__(self, event, addr_list, target_name):
                super().__init__()
                self.event = event
                self.addr_list = addr_list
                self.target_name = target_name

            @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
            def onScanResult(self, callbackType, result):
                try:
                    device = result.getDevice()
                    name = device.getName()
                    address = device.getAddress()
                    # 某些 Android 版本 name 可能为空
                    if name and self.target_name in name:
                        logger.info(f"[BLE] 发现目标: {address} ({name})")
                        self.addr_list[0] = address
                        self.event.set()
                except Exception as e:
                    logger.warning(f"[BLE] onScanResult error: {e}")

            @java_method('(I)V')
            def onScanFailed(self, errorCode):
                logger.warning(f"[BLE] 扫描失败, errorCode={errorCode}")
                self.event.set()  # 容错: 防无限等待

        return ScanCallback(found_event, found_address, self._target_name)

    def _connect_device(self, address: str) -> bool:
        """通过地址连接 BLE 设备"""
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            self._device_address = address
            device = self._adapter.getRemoteDevice(address)
            if not device:
                logger.error(f"[BLE] 无效设备地址: {address}")
                return False

            connect_event = threading.Event()
            connect_result = [False]
            gatt_callback = self._create_gatt_callback(connect_event, connect_result)

            # 连接 GATT
            self._gatt = device.connectGatt(
                self._context,
                False,  # autoConnect = False
                gatt_callback,
                autoclass('android.bluetooth.BluetoothDevice').TRANSPORT_LE
            )

            if not self._gatt:
                logger.error("[BLE] connectGatt 返回 null")
                return False

            # 等待连接完成 + 服务发现
            connected = connect_event.wait(timeout=10.0)
            if not connected or not connect_result[0]:
                logger.warning("[BLE] 连接超时或失败")
                try:
                    self._gatt.disconnect()
                    self._gatt.close()
                except:
                    pass
                self._gatt = None
                return False

            self._connected = True
            logger.info(f"[BLE] 已连接到 {address}")
            if self._on_connect:
                self._on_connect()
            return True

        except Exception as e:
            logger.error(f"[BLE] 连接异常: {e}")
            return False

    def _create_gatt_callback(self, connect_event, connect_result):
        """创建 BluetoothGattCallback (PyJNIus)"""
        from jnius import PythonJavaClass, java_method, autoclass

        class GattCallback(PythonJavaClass):
            __javainterfaces__ = ['android/bluetooth/BluetoothGattCallback']

            def __init__(self, event, result, char_uuid, service_uuid, outer):
                super().__init__()
                self.event = event
                self.result = result
                self.char_uuid = char_uuid
                self.service_uuid = service_uuid
                self.outer = outer

            @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
            def onConnectionStateChange(self, gatt, status, newState):
                try:
                    from jnius import autoclass
                    BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
                    if newState == BluetoothProfile.STATE_CONNECTED:
                        logger.info("[BLE] GATT 已连接, 开始服务发现...")
                        gatt.discoverServices()
                    elif newState == BluetoothProfile.STATE_DISCONNECTED:
                        logger.info("[BLE] GATT 已断开")
                        self.outer._connected = False
                        self.outer._gatt = None
                        if self.outer._on_disconnect:
                            self.outer._on_disconnect()
                except Exception as e:
                    logger.warning(f"[BLE] onConnectionStateChange error: {e}")

            @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
            def onServicesDiscovered(self, gatt, status):
                try:
                    if status != 0:
                        logger.warning(f"[BLE] 服务发现失败: status={status}")
                        self.event.set()
                        return

                    logger.info("[BLE] 服务发现成功")
                    service = gatt.getService(
                        autoclass('java.util.UUID').fromString(self.service_uuid)
                    )
                    if not service:
                        logger.warning(f"[BLE] 未找到服务 {self.service_uuid}")
                        self.event.set()
                        return

                    characteristic = service.getCharacteristic(
                        autoclass('java.util.UUID').fromString(self.char_uuid)
                    )
                    if not characteristic:
                        logger.warning(f"[BLE] 未找到特征 {self.char_uuid}")
                        self.event.set()
                        return

                    self.outer._characteristic = characteristic
                    self.result[0] = True
                    logger.info("[BLE] 服务发现完成, 写入通道就绪")
                    self.event.set()
                except Exception as e:
                    logger.warning(f"[BLE] onServicesDiscovered error: {e}")
                    self.event.set()

            @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V')
            def onCharacteristicWrite(self, gatt, characteristic, status):
                if status != 0:
                    logger.warning(f"[BLE] 写入失败: status={status}")

            @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
            def onMtuChanged(self, gatt, mtu, status):
                logger.info(f"[BLE] MTU 已更新: {mtu}")

        return GattCallback(
            connect_event,
            connect_result,
            self._char_tx_uuid,
            self._service_uuid,
            self
        )

    def send_command(self, cmd: str) -> bool:
        """发送命令到 ESP32"""
        if not self._connected or not self._gatt or not self._characteristic:
            logger.warning("[BLE] 未连接, 无法发送")
            return False

        try:
            from jnius import autoclass
            data = (cmd + "\n").encode("utf-8")
            self._characteristic.setValue(data)
            self._characteristic.setWriteType(
                autoclass('android.bluetooth.BluetoothGattCharacteristic').WRITE_TYPE_NO_RESPONSE
            )
            result = self._gatt.writeCharacteristic(self._characteristic)
            if result:
                logger.info(f"[BLE] >> {cmd}")
            else:
                logger.warning(f"[BLE] 写入失败: {cmd}")
            return result
        except Exception as e:
            logger.error(f"[BLE] 发送异常: {e}")
            return False

    def disconnect(self):
        """断开 BLE 连接"""
        with self._lock:
            if self._gatt:
                try:
                    self._gatt.disconnect()
                    self._gatt.close()
                except:
                    pass
                self._gatt = None
            self._characteristic = None
            self._connected = False
            self._device_address = None
            logger.info("[BLE] 已断开")
            if self._on_disconnect:
                self._on_disconnect()
