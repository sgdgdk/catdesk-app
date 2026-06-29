"""
情绪关键词提取器
当 LLM 返回的 JSON 中 emotion 无效时，从 reply 文本中提取

继承自原项目 emotion_parser.py 的关键词匹配逻辑
"""
import re
from typing import Optional

# 显式情绪标签正则
EMOTION_TAG_RE = re.compile(r'\[(.*?)\]')

# 中英文关键词 → 情绪映射
EMOTION_KEYWORDS = {
    "happy":      ["开心", "高兴", "快乐", "哈哈", "太好", "喜欢",
                   "愉快", "太棒", "赞", "耶", "嘻嘻", "嘿嘿", "haha"],
    "sad":        ["难过", "伤心", "悲伤", "委屈", "可怜", "sad", "cry"],
    "angry":      ["生气", "愤怒", "火大", "angry", "哼", "烦", "真烦"],
    "surprised":  ["惊讶", "吃惊", "哇", "真的吗", "不会吧", "surprised", "wow"],
    "thinking":   ["思考", "想想", "hmm", "think"],
    "sleepy":     ["困了", "好困", "睡觉", "tired", "哈欠"],
    "excited":    ["兴奋", "激动", "excited", "amazing", "awesome"],
    "confused":   ["不懂", "confused", "迷茫", "奇怪"],
    "love":       ["爱你", "喜欢你", "love", "亲"],
    "fear":       ["害怕", "吓人", "fear", "scared", "可怕"],
    "shy":        ["害羞", "不好意思", "shy"],
}

# 权重: 越靠前的关键词权重越高
KEYWORD_WEIGHTS = {
    "开心": 3, "高兴": 3, "快乐": 3, "哈哈": 2, "太好": 3,
    "难过": 3, "伤心": 3, "生气": 3, "愤怒": 3,
    "爱你": 3, "喜欢": 2, "哇": 2, "嗯": 1, "困了": 2,
    "害怕": 3, "害羞": 3, "惊讶": 3,
}


def extract_emotion(text: str) -> Optional[str]:
    """
    从文本中提取情绪
    优先级: 显式标签 [happy] > 关键词匹配 > None

    Returns:
        emotion string (e.g. "happy") or None if can't determine
    """
    if not text:
        return None

    # 1. 尝试显式标签 [happy] 格式
    tag_match = EMOTION_TAG_RE.findall(text)
    for tag in tag_match:
        tag_lower = tag.strip().lower()
        if tag_lower in EMOTION_KEYWORDS:
            return tag_lower

    # 2. 关键词加权匹配
    scores = {}
    for emotion, words in EMOTION_KEYWORDS.items():
        for word in words:
            if word in text:
                weight = KEYWORD_WEIGHTS.get(word, 1)
                scores[emotion] = scores.get(emotion, 0) + weight

    if scores:
        return max(scores, key=scores.get)

    return None


def extract_emotion_safe(text: str, default: str = "neutral") -> str:
    """安全版本: 提取不到返回默认值"""
    result = extract_emotion(text)
    return result if result else default
