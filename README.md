# 🐱 桌面猫手机App (DeskCat Phone App) v2 — 云台版

> 将原 ESP32-S3 Sense 硬件方案替换为 **手机App + BLE 控制 ESP32-S3 Nano**
> v2 新增: PTZ 云台控制 + 轮子移动 + LLM 命令识别

## ✨ 核心特性

- **手机显示表情** — 使用原项目 JPEG 帧动画，全彩高清显示
- **手机语音交互** — 扬声器播放 TTS，麦克风语音输入
- **LLM 智能对话** — DeepSeek/通义千问，自动分析说话意图
- **BLE 控制机器人** — 本地映射表，零延迟指令下发
- **PTZ 双舵机云台** — 2×SG90 控制摄像头上下左右看
- **双轮差速驱动** — 前进/后退/左转/右转
- **智能命令识别** — LLM 自动区分"前进/后退/左转/右转/向上看/向下看/日常聊天"
- **智能拒绝** — "飞起来/发射子弹"等不可能指令会自动撒娇拒绝

## 🏗️ 项目结构

```
cat_phone_app/
├── main.py                    # Kivy App 主入口
├── main.kv                    # Kivy UI 布局
├── buildozer.spec             # Buildozer APK 打包配置
├── requirements.txt           # Python 依赖
├── app/
│   ├── config.py              # 全局配置 + System Prompt
│   ├── intent_mapper.py       # 意图→BLE指令 映射器
│   ├── llm_client.py          # 通义千问 LLM 客户端
│   ├── emotion_renderer.py    # 表情动画渲染引擎
│   ├── ble_client.py          # BLE 通信模块
│   ├── tts_engine.py          # TTS 语音合成
│   ├── audio_capture.py       # 音频捕捉
│   └── data/
│       ├── intent_map.json    # 意图映射表 (不消耗token)
│       └── anim/              # 表情动画帧 (JPEG序列)
│           ├── anim1/         # neutral
│           ├── anim2/         # thinking
│           ├── anim3/         # sleepy/confused
│           ├── anim4/         # fear (cry)
│           ├── anim5/         # angry
│           ├── anim6/         # happy/surprised/excited
│           ├── anim7/         # sad
│           └── anim8/         # love/shy
├── esp32_firmware/
│   ├── esp32_nano_firmware.ino  # 主程序
│   ├── config.h                 # 引脚配置 (S3 Nano)
│   ├── ble_uart.h               # BLE UART 服务
│   ├── servo_control.h          # SG90 舵机控制
│   ├── motor_control.h          # 直流电机控制
│   └── command_parser.h         # 指令解析器
└── docs/
    └── architecture.md        # 完整架构文档
```

## 🚀 快速开始

### 1. 手机 App (Android)

```bash
# 安装依赖
pip install -r requirements.txt

# 桌面调试运行
python main.py

# 打包 APK (需要 Buildozer 环境)
# buildozer android debug
```

### 2. ESP32-S3 Nano 固件

用 Arduino IDE 打开 `esp32_firmware/esp32_nano_firmware.ino`：
1. 板型选择: **ESP32S3 Dev Module**
2. Flash Size: **16MB (128Mb)**
3. PSRAM: **OPI PSRAM**
4. 上传固件

### 3. 配置环境变量

```bash
# 阿里通义千问 API 密钥 (必填)
set DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
```

## 🔧 硬件接线

### ESP32-S3 Nano ↔ SG90 舵机

| ESP32-S3 Nano | SG90 1 (Yaw) | SG90 2 (Pitch) |
|--------------|-------------|---------------|
| GPIO4 (PWM)  | 信号线(橙)  | - |
| GPIO5 (PWM)  | -           | 信号线(橙) |
| 5V           | 红线(VCC)   | 红线(VCC) |
| GND          | 棕线(GND)   | 棕线(GND) |

### ESP32-S3 Nano ↔ TB6612FNG 直流电机驱动

| ESP32-S3 Nano | TB6612FNG | 电机 |
|--------------|-----------|------|
| GPIO6        | IN1       | - |
| GPIO7        | IN2       | - |
| GPIO8 (PWM)  | PWMA      | 左轮 |
| GPIO15       | IN3       | - |
| GPIO16       | IN4       | - |
| GPIO17 (PWM) | PWMB      | 右轮 |

## 🎯 核心设计 (对齐 LOOI)

```
LLM (云端)         手机App (上位机)          ESP32 (下位机)
    │                   │                        │
    │  ┌──────────────┐ │                        │
    ├─→│ JSON 意图标签 │ │                        │
    │  │ emotion: happy│ │                        │
    │  │ move: forward │ │                        │
    │  └──────┬───────┘ │                        │
    │         │         │                        │
    │         ├─────┬───┤                        │
    │         │     │   │                        │
    │         ▼     ▼   │                        │
    │    [查表]  [查表]  │                        │
    │    anim6   MOVE.. │                        │
    │         │     │   │                        │
    │         ▼     ▼   │                        │
    │   渲染表情  BLE发送 ├─────────────────────→ │
    │   手机屏幕  指令   │   MOVE,FWD,128         │
    │                   │                        │
    │                   │                    ┌───┴───┐
    │                   │                    │执行运动│
    │                   │                    │舵机动作│
    │                   │                    └───────┘
```

## 📱 手机端功能

- [x] 表情动画播放 (JPEG帧序列)
- [x] LLM 对话 (通义千问)
- [x] BLE 设备扫描与连接
- [x] 意图→BLE指令映射
- [x] TTS 语音播放
- [x] 对话历史记录
- [x] 语音输入 (基础)

## 🔄 与原项目兼容性

| 原项目 | 新项目 | 状态 |
|--------|--------|------|
| `emotion_parser.py` → | `intent_mapper.py` | ✅ 重构 |
| `emotion_renderer.py` → | `emotion_renderer.py` | ✅ 手机端重写 |
| `cat_motion.py` → | `intent_map.json` | ✅ 映射表 |
| `ble_protocol.py` → | BLE 指令透传 | ✅ 简化 |
| JPEG 动画帧 → | `data/anim/` | ✅ 直接复用 |
| 表情映射表 → | `EMOTION_TO_ANIM_DIR` | ✅ 继承 |
