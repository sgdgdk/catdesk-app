# 🐱 DeskCat-Nano 固件烧录指南

## 接线图

```
           ┌──────────────────────────────────┐
           │          外部 5V/2A+ 电源         │
           │     (USB供电不够! 舵机会抽搐!)     │
           └──────┬──────────────┬────────────┘
                  │ 5V           │ GND
                  │              │
    ┌─────────────┴──────┐       │
    │    ESP32-S3 Nano    │       │
    │                     │       │
    │  GPIO4  → SG90 Yaw (橙)     │
    │  GPIO5  → SG90 Pitch(橙)    │
    │                     │       │
    │  GPIO6  → TB6612 IN1        │
    │  GPIO7  → TB6612 IN2        │
    │  GPIO8  → TB6612 PWMA  ────┤ 左轮
    │  GPIO15 → TB6612 IN3        │
    │  GPIO16 → TB6612 IN4        │
    │  GPIO17 → TB6612 PWMB  ────┤ 右轮
    │                     │       │
    │  5V    → 舵机VCC(红)├───────┘
    │         TB6612 VCC  │
    │  GND   → 舵机GND(棕)│
    │         TB6612 GND  │
    │                     │
    │  5V         GND     │
    └─────────────────────┘
```

**SG90 舵机线序**：橙(信号) — 红(VCC) — 棕(GND)
**LED 灯**：GPIO48 = 板载（约 200ms 快闪=已连接，1.5s慢闪=等待连接）

## 烧录步骤

### 1. 安装 PlatformIO

VS Code → 扩展 → 搜索 `PlatformIO IDE` → 安装

### 2. 打开项目

```bash
# 终端打开
cd E:\开源\cat_phone_app\firmware
code .
```

或 VS Code → **文件 → 打开文件夹** → 选 `firmware/`

### 3. 编译 + 上传

| 操作 | 方法 |
|------|------|
| 编译 | VS Code 底部 → `→` (Build) 或 `Ctrl+Alt+B` |
| 上传 | VS Code 底部 → `→` (Upload) 或 `Ctrl+Alt+U` |
| 串口监视 | VS Code 底部 → 🔌 (Serial Monitor) |

### 4. 如果上传失败 (最常见)

```
A fatal error occurred: Failed to connect to ESP32-S3: ...
```

**按住 BOOT 按钮不放 → 点上传 → 看到 Connecting... 时松手**

还不行？用 **低速模式**：确保 `platformio.ini` 里有：
```ini
upload_speed = 115200
```
然后重复上述步骤。

### 5. 验证成功

串口监视器(115200)看到：

```
========================================
 🐱 DeskCat-Nano v1.0
========================================
[LED] GPIO48 就绪
[PSRAM] OK: 8 MB
[Servo] Yaw=GPIO4 Pitch=GPIO5 (回中90°)
[Motor] 差速驱动就绪
[BLE] Name=DeskCat-Nano UUID=0000FFE0-...

✅ 启动完成! 等待 BLE 连接...
```

## BLE 连接

打开手机 App → 自动搜索 "DeskCat-Nano" → 连接成功

## 完整指令集

| BLE/串口指令 | 功能 | 示例 |
|-------------|------|------|
| `MOVE,FWD,速度` | 前进 | `MOVE,FWD,128` |
| `MOVE,BACK,速度` | 后退 | `MOVE,BACK,128` |
| `MOVE,LEFT,速度` | 左转 | `MOVE,LEFT,160` |
| `MOVE,RIGHT,速度` | 右转 | `MOVE,RIGHT,160` |
| `MOVE,STOP` | 停止 | `MOVE,STOP` |
| `MOTOR:左,右` | 直接电机 | `MOTOR:128,-64` |
| `SERVO:1,角度` | 舵机1(Yaw) | `SERVO:1,90` |
| `SERVO:2,角度` | 舵机2(Pitch) | `SERVO:2,45` |
| `SERVO:CENTER` | 回中 | `SERVO:CENTER` |
| `EXPR:情绪` | 表情(透传) | `EXPR:happy` |
| `LED:on/off` | 板载LED | `LED:on` |
| `PING` | 心跳 | `PING` → `[PONG]` |
| `RESET` | 重启 | `RESET` |

## 调试方法

手机 App 不开时，可以直接用串口发指令测试：

```
MOVE,FWD,128    ← 车前进
SERVO:1,90      ← 舵机回中
MOVE,STOP       ← 停止
```

## 引脚速查

| 功能 | GPIO | 连到 |
|------|------|------|
| 舵机Yaw(左右) | **4** | SG90 橙线 |
| 舵机Pitch(上下) | **5** | SG90 橙线 |
| 左轮IN1 | **6** | TB6612 IN1 |
| 左轮IN2 | **7** | TB6612 IN2 |
| 左轮PWM | **8** | TB6612 PWMA |
| 右轮IN3 | **15** | TB6612 IN3 |
| 右轮IN4 | **16** | TB6612 IN4 |
| 右轮PWM | **17** | TB6612 PWMB |
| 板载LED | **48** | 内置 |
