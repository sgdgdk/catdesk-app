/**
 * 🐱 DeskCat-Nano v2.0 — ESP32-S3 Nano 下位机固件
 * ===============================================
 * 主控:     ESP32-S3 Nano (PSRAM 8MB, Flash 16MB)
 * 通信:     BLE UART ("DeskCat-Nano")
 * 云台:     2x SG90 舵机 (Yaw=GPIO4, Pitch=GPIO5)
 * 轮子:     2x 直流减速电机 + TB6612FNG
 * LED:      GPIO48 心跳指示
 *
 * 指令集:
 *   MOVE,FWD,速度   前进        例: MOVE,FWD,150
 *   MOVE,BACK,速度  后退             MOVE,BACK,150
 *   MOVE,LEFT,速度  左转             MOVE,LEFT,140
 *   MOVE,RIGHT,速度 右转             MOVE,RIGHT,140
 *   MOVE,STOP       停止
 *   PTZ:yaw,pitch   云台到角度       PTZ:90,90
 *   PTZ:CENTER      云台回中
 *   PTZ:yaw         仅调水平         PTZ:45
 *   PING            心跳检测
 *   RESET           重启
 * ===============================================
 */

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "config.h"

// ===================== BLE 全局对象 =====================
BLEServer*          g_pServer = nullptr;
BLECharacteristic*  g_pTxChar = nullptr;   // 手机→ESP32 (接收指令)
BLECharacteristic*  g_pRxChar = nullptr;   // ESP32→手机 (发送状态)
bool                g_bleConnected = false;

// 当前云台角度
int g_yaw   = 90;
int g_pitch = 90;

// 电机状态: 0=停止, 1=正转, -1=反转
int g_motorL = 0;
int g_motorR = 0;
int g_motorSpeed = 0;

// 前向声明
void handleCommand(const String& cmd);

// ===================== BLE 回调 =====================
class ServerCB : public BLEServerCallbacks {
    void onConnect(BLEServer* s) override {
        g_bleConnected = true;
        Serial.println("[BLE] 已连接");
    }
    void onDisconnect(BLEServer* s) override {
        g_bleConnected = false;
        Serial.println("[BLE] 已断开，重新广播...");
        delay(500);
        BLEDevice::startAdvertising();
    }
};

class CharCB : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        String val = c->getValue().c_str();
        val.trim();
        if (val.length() == 0) return;
        Serial.printf("[BLE] << %s\n", val.c_str());
        handleCommand(val);
    }
};

void initBLE() {
    BLEDevice::init(BLE_NAME);
    BLEDevice::setMTU(256);                    // 降低 MTU 更稳定
    BLEDevice::setPower(ESP_PWR_LVL_P9);       // 最大发射功率

    g_pServer = BLEDevice::createServer();
    g_pServer->setCallbacks(new ServerCB());

    BLEService* svc = g_pServer->createService(BLE_SERVICE_UUID);

    g_pTxChar = svc->createCharacteristic(
        BLE_CHAR_TX_UUID,
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_WRITE_NR |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    g_pTxChar->addDescriptor(new BLE2902());
    g_pTxChar->setCallbacks(new CharCB());

    g_pRxChar = svc->createCharacteristic(
        BLE_CHAR_RX_UUID,
        BLECharacteristic::PROPERTY_NOTIFY |
        BLECharacteristic::PROPERTY_READ
    );
    g_pRxChar->addDescriptor(new BLE2902());
    g_pRxChar->setValue("OK");
    svc->start();

    // BLE 广播参数优化
    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(BLE_SERVICE_UUID);
    adv->setAppearance(0x0080);                // 显示为电脑设备
    adv->setScanResponse(true);
    adv->setMinPreferred(0x12);                // 36ms 广播间隔
    adv->setMaxPreferred(0x24);                // 72ms
    adv->setMinInterval(0x20);                 // 40ms 连接间隔
    adv->setMaxInterval(0x40);                 // 80ms
    adv->setAdvertisementType(ADV_TYPE_IND);   // 可连接广播

    BLEDevice::startAdvertising();
    Serial.printf("[BLE] Name=%s\n", BLE_NAME);
}

void bleSend(const String& msg) {
    if (g_bleConnected && g_pRxChar) {
        g_pRxChar->setValue(msg.c_str());
        g_pRxChar->notify();
    }
}

// ===================== 云台舵机 =====================
/** 立即设置一个舵机到指定角度 */
void setServoAngle(int pin, int channel, int angle) {
    angle = constrain(angle, 0, 180);
    int duty = map(angle, 0, 180, SERVO_MIN_DUTY, SERVO_MAX_DUTY);
    ledcWrite(channel, duty);
}

/** 逐度平滑移动云台到目标角度（带阻尼效果） */
void movePTZSmooth(int targetYaw, int targetPitch) {
    targetYaw   = constrain(targetYaw,   0, 180);
    targetPitch = constrain(targetPitch, 0, 180);

    int steps = 0;
    int dY = targetYaw - g_yaw;
    int dP = targetPitch - g_pitch;
    int maxDelta = max(abs(dY), abs(dP));
    steps = max(1, maxDelta / SERVO_SPEED_STEP);

    for (int i = 1; i <= steps; i++) {
        g_yaw   = map(i, 0, steps, g_yaw,   targetYaw);
        g_pitch = map(i, 0, steps, g_pitch, targetPitch);
        setServoAngle(PIN_SERVO_YAW,   0, g_yaw);
        setServoAngle(PIN_SERVO_PITCH, 1, g_pitch);
        delay(SERVO_STEP_DELAY_MS);
    }
    g_yaw   = targetYaw;
    g_pitch = targetPitch;
}

/** 初始化舵机 (回中) */
void initServos() {
    ledcSetup(0, SERVO_FREQ, SERVO_RES);
    ledcSetup(1, SERVO_FREQ, SERVO_RES);
    ledcAttachPin(PIN_SERVO_YAW, 0);
    ledcAttachPin(PIN_SERVO_PITCH, 1);
    g_yaw = 90; g_pitch = 90;
    setServoAngle(PIN_SERVO_YAW,   0, g_yaw);
    setServoAngle(PIN_SERVO_PITCH, 1, g_pitch);
    Serial.println("[Servo] Yaw=GPIO4 Pitch=GPIO5 -> 90° 回中");
}

// ===================== 轮子电机 =====================
void setMotor(int left, int right) {
    left  = constrain(left,  -255, 255);
    right = constrain(right, -255, 255);

    // 如果右轮前进/后退反了，取消下面这行的注释
    // right = -right;

    // 左轮: IN1=方向, IN2=反向, PWM=速度
    digitalWrite(PIN_MOTOR_L_IN1, left > 0 ? HIGH : LOW);
    digitalWrite(PIN_MOTOR_L_IN2, left < 0 ? HIGH : LOW);

    // 右轮
    digitalWrite(PIN_MOTOR_R_IN3, right > 0 ? HIGH : LOW);
    digitalWrite(PIN_MOTOR_R_IN4, right < 0 ? HIGH : LOW);

    ledcWrite(2, abs(left));
    ledcWrite(3, abs(right));
}

void initMotors() {
    pinMode(PIN_MOTOR_L_IN1, OUTPUT);
    pinMode(PIN_MOTOR_L_IN2, OUTPUT);
    pinMode(PIN_MOTOR_R_IN3, OUTPUT);
    pinMode(PIN_MOTOR_R_IN4, OUTPUT);
    ledcSetup(2, MOTOR_PWM_FREQ, MOTOR_PWM_RES);
    ledcSetup(3, MOTOR_PWM_FREQ, MOTOR_PWM_RES);
    ledcAttachPin(PIN_MOTOR_L_PWM, 2);
    ledcAttachPin(PIN_MOTOR_R_PWM, 3);
    setMotor(0, 0);
    Serial.println("[Motor] 差速驱动 OK (L=GPIO6-8, R=GPIO15-17)");
}

// ===================== 指令解析 =====================
void handleCommand(const String& cmd) {
    // LED 闪一下确认收到命令
    digitalWrite(PIN_LED, HIGH); delay(15); digitalWrite(PIN_LED, LOW);

    // ---------- MOVE 轮子指令（先直接写，再保持状态）----------
    if (cmd.startsWith("MOVE,")) {
        int c1 = cmd.indexOf(',');
        int c2 = cmd.indexOf(',', c1 + 1);
        String dir = cmd.substring(c1 + 1, c2 > c1 ? c2 : cmd.length());
        int spd = (c2 > c1) ? constrain(cmd.substring(c2 + 1).toInt(), 0, 255) : 200;

        Serial.printf("[MOVE] dir=%s spd=%d\n", dir.c_str(), spd);

        if (dir == "FWD") {
            digitalWrite(PIN_MOTOR_L_IN1, HIGH); digitalWrite(PIN_MOTOR_L_IN2, LOW); ledcWrite(2, spd);
            digitalWrite(PIN_MOTOR_R_IN3, HIGH); digitalWrite(PIN_MOTOR_R_IN4, LOW); ledcWrite(3, spd);
            g_motorL = 1; g_motorR = 1; g_motorSpeed = spd;
            Serial.println("[MOVE] FWD");
        } else if (dir == "BACK") {
            digitalWrite(PIN_MOTOR_L_IN1, LOW); digitalWrite(PIN_MOTOR_L_IN2, HIGH); ledcWrite(2, spd);
            digitalWrite(PIN_MOTOR_R_IN3, LOW); digitalWrite(PIN_MOTOR_R_IN4, HIGH); ledcWrite(3, spd);
            g_motorL = -1; g_motorR = -1; g_motorSpeed = spd;
            Serial.println("[MOVE] BACK");
        } else if (dir == "LEFT") {
            digitalWrite(PIN_MOTOR_L_IN1, LOW); digitalWrite(PIN_MOTOR_L_IN2, HIGH); ledcWrite(2, 160);
            digitalWrite(PIN_MOTOR_R_IN3, HIGH); digitalWrite(PIN_MOTOR_R_IN4, LOW); ledcWrite(3, 160);
            g_motorL = -1; g_motorR = 1; g_motorSpeed = 160;
            Serial.println("[MOVE] LEFT");
        } else if (dir == "RIGHT") {
            digitalWrite(PIN_MOTOR_L_IN1, HIGH); digitalWrite(PIN_MOTOR_L_IN2, LOW); ledcWrite(2, 160);
            digitalWrite(PIN_MOTOR_R_IN3, LOW); digitalWrite(PIN_MOTOR_R_IN4, HIGH); ledcWrite(3, 160);
            g_motorL = 1; g_motorR = -1; g_motorSpeed = 160;
            Serial.println("[MOVE] RIGHT");
        } else {
            digitalWrite(PIN_MOTOR_L_IN1, LOW); digitalWrite(PIN_MOTOR_L_IN2, LOW); ledcWrite(2, 0);
            digitalWrite(PIN_MOTOR_R_IN3, LOW); digitalWrite(PIN_MOTOR_R_IN4, LOW); ledcWrite(3, 0);
            g_motorL = 0; g_motorR = 0; g_motorSpeed = 0;
            Serial.println("[MOVE] STOP");
        }
        return;
    }

    // ---------- MOTOR 直接控制 ----------
    if (cmd.startsWith("MOTOR:")) {
        int co = cmd.indexOf(':');
        int cm = cmd.indexOf(',', co + 1);
        int l = (cm > co) ? cmd.substring(co + 1, cm).toInt() : 0;
        int r = (cm > co) ? cmd.substring(cm + 1).toInt() : 0;
        g_motorL = constrain(l, -1, 1);
        g_motorR = constrain(r, -1, 1);
        g_motorSpeed = max(abs(l), abs(r));
        return;
    }

    // ---------- PTZ 云台 ----------
    if (cmd.startsWith("PTZ:")) {
        String rest = cmd.substring(4);
        rest.trim();
        if (rest == "CENTER") { g_yaw = 90; g_pitch = 90; }
        else {
            int cm = rest.indexOf(',');
            if (cm > 0) { g_yaw = rest.substring(0, cm).toInt(); g_pitch = rest.substring(cm + 1).toInt(); }
            else { g_yaw = rest.toInt(); }
        }
        g_yaw = constrain(g_yaw, 0, 180);
        g_pitch = constrain(g_pitch, 0, 180);
        ledcWrite(0, map(g_yaw, 0, 180, SERVO_MIN_DUTY, SERVO_MAX_DUTY));
        ledcWrite(1, map(g_pitch, 0, 180, SERVO_MIN_DUTY, SERVO_MAX_DUTY));
        Serial.printf("[PTZ] yaw=%d pitch=%d\n", g_yaw, g_pitch);
        return;
    }
    // ---------- 硬件直接测试 ----------
    if (cmd == "TEST") {
        Serial.println("[TEST] 开始硬件测试...");
        // 测试舵机: GPIO4 来回转
        Serial.println("[TEST] 舵机 Yaw(GPIO4) 0°");
        ledcWrite(0, SERVO_MIN_DUTY);
        delay(1000);
        Serial.println("[TEST] 舵机 Yaw(GPIO4) 180°");
        ledcWrite(0, SERVO_MAX_DUTY);
        delay(1000);
        Serial.println("[TEST] 舵机 Yaw(GPIO4) 90°");
        ledcWrite(0, map(90, 0, 180, SERVO_MIN_DUTY, SERVO_MAX_DUTY));
        delay(500);
        // 测试电机: GPIO6~8 左轮前进
        Serial.println("[TEST] 左轮前进 1秒");
        digitalWrite(PIN_MOTOR_L_IN1, HIGH);
        digitalWrite(PIN_MOTOR_L_IN2, LOW);
        ledcWrite(2, 200);
        delay(1000);
        ledcWrite(2, 0);
        // 测试电机: GPIO15~17 右轮前进
        Serial.println("[TEST] 右轮前进 1秒");
        digitalWrite(PIN_MOTOR_R_IN3, HIGH);
        digitalWrite(PIN_MOTOR_R_IN4, LOW);
        ledcWrite(3, 200);
        delay(1000);
        ledcWrite(3, 0);
        Serial.println("[TEST] 测试完成");
        return;
    }
    // ---------- SERVO 兼容指令 ----------
    if (cmd.startsWith("SERVO:")) {
        String rest = cmd.substring(6);
        if (rest == "CENTER") {
            movePTZSmooth(90, 90);
            return;
        }
        int cm = rest.indexOf(',');
        if (cm < 0) return;
        int ch = rest.substring(0, cm).toInt();
        int ang = rest.substring(cm + 1).toInt();
        if (ch == 1) movePTZSmooth(ang, g_pitch);
        else         movePTZSmooth(g_yaw, ang);
        return;
    }

    // ---------- EXPR 表情透传 ----------
    if (cmd.startsWith("EXPR:")) {
        Serial.printf("[EXPR] %s\n", cmd.substring(5).c_str());
        return;
    }

    // ---------- LED ----------
    if (cmd.startsWith("LED:")) {
        digitalWrite(PIN_LED, cmd.endsWith("on") ? HIGH : LOW);
        return;
    }

    // ---------- 系统 ----------
    if (cmd == "PING")  { bleSend("PONG"); return; }
    if (cmd == "RESET") { Serial.println("[RESET]"); delay(100); ESP.restart(); }
}

// ===================== setup / loop =====================
void setup() {
    Serial.begin(115200);
    delay(200);
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

    Serial.println(F("\n=== DeskCat-Nano v3.0 ==="));
    pinMode(PIN_LED, OUTPUT);
    for (int i = 0; i < 3; i++) { digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100); }

    initServos();
    initMotors();
    initBLE();

    Serial.println(F("Ready! BLE=DeskCat-Nano  CMD: MOVE PTZ TEST"));
}

void loop() {
    // 串口读取
    static String buf;
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (buf.length() > 0) {
                buf.trim();
                handleCommand(buf);
                buf = "";
            }
        } else if (c >= ' ') {
            buf += c;
        }
    }

    // 持续刷新电机状态（确保 PWM 持续输出）
    if (g_motorL == 0 && g_motorR == 0) {
        // 停止
        digitalWrite(PIN_MOTOR_L_IN1, LOW); digitalWrite(PIN_MOTOR_L_IN2, LOW);
        digitalWrite(PIN_MOTOR_R_IN3, LOW); digitalWrite(PIN_MOTOR_R_IN4, LOW);
        ledcWrite(2, 0); ledcWrite(3, 0);
    } else {
        // 左轮
        digitalWrite(PIN_MOTOR_L_IN1, g_motorL > 0 ? HIGH : LOW);
        digitalWrite(PIN_MOTOR_L_IN2, g_motorL < 0 ? HIGH : LOW);
        ledcWrite(2, g_motorSpeed);
        // 右轮
        digitalWrite(PIN_MOTOR_R_IN3, g_motorR > 0 ? HIGH : LOW);
        digitalWrite(PIN_MOTOR_R_IN4, g_motorR < 0 ? HIGH : LOW);
        ledcWrite(3, g_motorSpeed);
    }

    // LED 心跳
    static unsigned long lastBlink = 0;
    unsigned long now = millis();
    if (now - lastBlink > 1000) {
        digitalWrite(PIN_LED, !digitalRead(PIN_LED));
        lastBlink = now;
    }
}
