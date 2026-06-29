[app]

# ============================================================
# Buildozer 配置 - 打包 APK (Android)
# ============================================================
title = 桌面猫小喵

package.name = catdeskapp
package.domain = com.catdesk.app

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,ttf,txt

version = 1.0.0
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

orientation = portrait

# ============================================================
# Android 权限 (BLE + 麦克风 + 网络)
# ============================================================
android.permissions = \
    BLUETOOTH, \
    BLUETOOTH_ADMIN, \
    BLUETOOTH_SCAN, \
    BLUETOOTH_CONNECT, \
    BLUETOOTH_ADVERTISE, \
    ACCESS_FINE_LOCATION, \
    ACCESS_COARSE_LOCATION, \
    RECORD_AUDIO, \
    MODIFY_AUDIO_SETTINGS, \
    INTERNET, \
    ACCESS_NETWORK_STATE, \
    ACCESS_WIFI_STATE, \
    FOREGROUND_SERVICE

# ============================================================
# Android 功能特性声明 (告知系统需要 BLE 硬件)
# ============================================================
android.features = \
    android.hardware.bluetooth, \
    android.hardware.bluetooth_le, \
    android.hardware.microphone

android.api = 33
android.minapi = 26
android.sdk = 33
android.ndk = 25.1.8937393

# ============================================================
# Android 附加依赖
# ============================================================
android.gradle_dependencies = \
    'androidx.core:core:1.9.0', \
    'androidx.appcompat:appcompat:1.6.1'

# ============================================================
# Python 依赖 (仅打包 Android 所需的库)
# - openai: DeepSeek LLM API 调用
# - pyjnius: BLE / TTS / 麦克风 (Android Java 桥接)
# - plyer: Android 系统功能
# 桌面专用库 (edge-tts, sounddevice, soundfile, numpy, bleak)
# 不打包, 安装包更小
# ============================================================
requirements = \
    python3==3.10.0, \
    kivy==2.3.1, \
    openai>=1.0.0, \
    Pillow>=9.0.0, \
    requests>=2.28.0, \
    pyjnius>=1.5.0, \
    plyer>=2.1.0

# ============================================================
# 图标 & 启动画面
# ============================================================
# 文件不存在时 buildozer 自动跳过, 不影响打包
icon = app/data/icon.png
presplash = app/data/splash.png

# ============================================================
# 存储 & 调试
# ============================================================
android.writable_external_storage = True

# 日志过滤 (只显示 Python / Kivy 日志)
android.logcat_filters = *:S python:V pyjnius:V kivy:V

# ============================================================
# 全屏模式 (隐藏状态栏, 猫表情全屏)
# ============================================================
android.fullscreen = 1

# AndroidX 兼容库
android.enable_androidx = True

[buildozer]

log_level = 2
warn_on_root = 1
