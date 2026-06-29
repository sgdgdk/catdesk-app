#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// 🐱 DeskCat-Nano v2.0 — 配置头文件
// 主控: ESP32-S3 Nano (PSRAM 8MB, Flash 16MB)
// ============================================================

// ---------- 板载 LED ----------
#define PIN_LED             48

// ---------- 云台舵机 (PTZ) — SG90 × 2 ----------
// 舵机 VCC(红) → 外部 5V   GND(棕) → 共地  信号(橙) → 引脚
#define PIN_SERVO_YAW       4     // 水平/左右
#define PIN_SERVO_PITCH     5     // 垂直/上下
#define SERVO_FREQ          50
#define SERVO_RES           12
#define SERVO_MIN_DUTY      102   // 0.5ms → 0°
#define SERVO_MAX_DUTY      512   // 2.5ms → 180°
#define SERVO_SPEED_STEP    2     // 每步移动度数(越小平滑)
#define SERVO_STEP_DELAY_MS 18    // 每步间隔(越小越快)

// ---------- 轮子电机 — TB6612FNG 驱动 × 2 ----------
// 左轮: IN1=GPIO6, IN2=GPIO7, PWM=GPIO8
// 右轮: IN3=GPIO15, IN4=GPIO16, PWM=GPIO17
#define PIN_MOTOR_L_IN1     6
#define PIN_MOTOR_L_IN2     7
#define PIN_MOTOR_L_PWM     8
#define PIN_MOTOR_R_IN3     15
#define PIN_MOTOR_R_IN4     16
#define PIN_MOTOR_R_PWM     17
#define MOTOR_PWM_FREQ      1000
#define MOTOR_PWM_RES       8
#define MOTOR_MAX_SPEED     200   // 最大PWM(0-255)
#define MOTOR_TURN_SPEED    140   // 转弯速度

// ---------- BLE 参数 ----------
#define BLE_NAME            "DeskCat-Nano"
#define BLE_SERVICE_UUID    "0000FFE0-0000-1000-8000-00805F9B34FB"
#define BLE_CHAR_TX_UUID    "0000FFE1-0000-1000-8000-00805F9B34FB"
#define BLE_CHAR_RX_UUID    "0000FFE2-0000-1000-8000-00805F9B34FB"

#endif
