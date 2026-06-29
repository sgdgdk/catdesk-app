python main.py"""
LLM API 客户端
使用 requests 直接调用 OpenAI 兼容接口（无需 openai 包，兼容 buildozer 交叉编译）
支持 DeepSeek / 阿里通义千问
"""
import json
import logging
from typing import AsyncGenerator, Optional
import requests

logger = logging.getLogger("LLM")


class LLMClient:
    """LLM 对话客户端 (直接 HTTP 调用，不依赖 openai 包)"""

    def __init__(self):
        from app.config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, LLM_PROVIDER

        self._api_key = LLM_API_KEY.strip() if LLM_API_KEY else ""
        self._model = LLM_MODEL
        self._base_url = LLM_BASE_URL.rstrip("/")
        self._provider = LLM_PROVIDER

        logger.info(f"LLM配置: provider=[{self._provider}] model=[{self._model}] url=[{self._base_url}] key={self._api_key[:12] if self._api_key else 'NONE'}...")
        if self._api_key:
            logger.info(f"LLM就绪: {self._provider} / {self._model}")

    @property
    def is_ready(self) -> bool:
        return bool(self._api_key) and len(self._api_key) > 8

    async def chat(
        self,
        text: str,
        history: list = None,
        system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        """调用LLM，使用 requests 流式请求"""
        if not self.is_ready:
            yield json.dumps({
                "reply": "API Key 未配置",
                "emotion": "sad",
                "move_intent": "none"
            }, ensure_ascii=False)
            return

        from app.config import SYSTEM_PROMPT as DEFAULT_SP

        messages = [
            {"role": "system", "content": system_prompt or DEFAULT_SP}
        ]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": text})

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            loop = asyncio.get_event_loop()

            def _sync():
                url = f"{self._base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self._model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 768,
                    "top_p": 0.9,
                }
                resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
                result = ""
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8", errors="ignore").strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    result += content
                            except json.JSONDecodeError:
                                continue
                return result

            with ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(pool, _sync)

            if result:
                yield result
            else:
                yield json.dumps({
                    "reply": "没有收到回复",
                    "emotion": "confused",
                    "move_intent": "none"
                }, ensure_ascii=False)

        except Exception as e:
            msg = str(e)
            logger.error(f"LLM失败: {msg}")
            if "401" in msg or "Unauthorized" in msg:
                hint = f"API Key 无效({self._provider})，请检查"
            elif "timeout" in msg.lower():
                hint = "请求超时，请检查网络"
            elif "connection" in msg.lower():
                hint = f"网络连接错误 ({self._base_url})"
            elif "insufficient_quota" in msg:
                hint = "API 额度不足"
            else:
                hint = f"出错了: {msg[:80]}"
            yield json.dumps({
                "reply": hint, "emotion": "sad", "move_intent": "none"
            }, ensure_ascii=False)
