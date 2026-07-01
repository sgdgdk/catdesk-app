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
android.features =

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
# ============================================================
requirements = \
    python3==3.10.0, \
    kivy, \
    Pillow, \
    requests, \
    pyjnius, \
    plyer

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
