"""
表情帧提取工具
从原项目的 MP4 视频提取 JPEG 帧，放入 phone_app 的 anim 目录

用法:
    python tools/extract_frames.py

注意:
    cv2.imwrite 不支持中文路径，使用 PIL 保存文件
"""
import os
import sys
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

# ============================================================
# 配置
# ============================================================
# 原项目表情视频目录 (8个MP4)
VIDEO_DIR = r"E:\开源\AI_DesktopCat_Qwen3.5Omni-main(备份)\AI_DesktopCat_Qwen3.5Omni-main\upload_facial_expression\表情"

# 手机App动画输出目录
OUTPUT_DIR = r"E:\开源\cat_phone_app\app\data\anim"

# 表情编号→情绪名称映射
ANIM_MAP = {
    1: "anim1",   # neutral
    2: "anim2",   # thinking
    3: "anim3",   # sleepy/confused
    4: "anim4",   # fear
    5: "anim5",   # angry
    6: "anim6",   # happy/surprised/excited
    7: "anim7",   # sad
    8: "anim8",   # love/shy
}

# 目标参数
TARGET_FRAME_COUNT = 60   # 手机端可少一些，省空间
JPEG_QUALITY = 75          # 质量
TARGET_SIZE = (284, 240)   # 保持原尺寸


def extract_all():
    """提取所有表情动画帧"""
    print("=" * 50)
    print("🐱 桌面猫 - 表情帧提取工具")
    print("=" * 50)

    if not os.path.isdir(VIDEO_DIR):
        print(f"❌ 视频目录不存在: {VIDEO_DIR}")
        # 尝试查找其他位置
        alt_paths = [
            os.path.join(os.path.dirname(OUTPUT_DIR), "..", "表情"),
        ]
        for p in alt_paths:
            if os.path.isdir(p):
                print(f"✅ 找到替代路径: {p}")
                globals()["VIDEO_DIR"] = p
                break

    for anim_num in range(1, 9):
        video_path = os.path.join(VIDEO_DIR, f"{anim_num}.mp4")
        anim_name = ANIM_MAP[anim_num]
        output_dir = os.path.join(OUTPUT_DIR, anim_name)

        if not os.path.exists(video_path):
            print(f"⚠️ 跳过 {anim_num}.mp4 (文件不存在)")
            continue

        print(f"\n🎬 处理: {anim_num}.mp4 → {anim_name}/")
        extract_frames(video_path, output_dir)

    print("\n✅ 所有表情帧提取完成！")


def extract_frames(video_path, output_dir, target_size=None, target_frame_count=None, quality=None):
    """从视频提取JPEG帧"""
    if target_size is None:
        target_size = TARGET_SIZE
    if target_frame_count is None:
        target_frame_count = TARGET_FRAME_COUNT
    if quality is None:
        quality = JPEG_QUALITY

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ❌ 无法打开: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"  分辨率: {width}x{height}, FPS: {fps:.1f}, 总帧: {total_frames}")

    if total_frames <= 0:
        cap.release()
        return

    # 均匀采样
    if target_frame_count == 1:
        sample_indices = [total_frames // 2]
    else:
        step = (total_frames - 1) / (target_frame_count - 1)
        sample_indices = [int(round(i * step)) for i in range(target_frame_count)]

    # 去重
    seen = set()
    unique_indices = []
    for idx in sample_indices:
        idx = max(0, min(total_frames - 1, idx))
        if idx not in seen:
            seen.add(idx)
            unique_indices.append(idx)

    saved = 0
    for i, target_idx in enumerate(unique_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        # 裁切边缘黑边
        if frame.shape[0] > target_size[1] + 20:
            crop = 25
            frame = frame[crop:-crop, crop:-crop]

        # 缩放
        if frame.shape[1] != target_size[0] or frame.shape[0] != target_size[1]:
            frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

        # 保存（使用 PIL 以支持中文路径）
        filename = f"{saved + 1:04d}.jpg"
        filepath = os.path.join(output_path, filename)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        Image.fromarray(frame_rgb).save(filepath, quality=quality)
        saved += 1

    cap.release()
    print(f"  ✅ 已保存 {saved} 帧到 {output_path}")


if __name__ == "__main__":
    extract_all()
