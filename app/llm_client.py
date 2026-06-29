"""
LLM API 客户端
使用 OpenAI 兼容接口，支持 DeepSeek / 阿里通义千问
"""
import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger("LLM")


class LLMClient:
    """LLM 对话客户端 (OpenAI兼容接口)"""

    def __init__(self):
        from app.config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, LLM_PROVIDER

        # 去除可能的尾部空格/换行
        self._api_key = LLM_API_KEY.strip() if LLM_API_KEY else ""
        self._model = LLM_MODEL
        self._base_url = LLM_BASE_URL.rstrip("/")
        self._provider = LLM_PROVIDER
        self._client = None

        logger.info(f"LLM配置: provider=[{self._provider}] model=[{self._model}] url=[{self._base_url}] key={self._api_key[:12] if self._api_key else 'NONE'}...")

        if self._api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
                logger.info(f"LLM就绪: {self._provider} / {self._model}")
            except Exception as e:
                logger.error(f"OpenAI初始化失败: {e}")

    @property
    def is_ready(self) -> bool:
        return self._client is not None and bool(self._api_key)

    async def chat(
        self,
        text: str,
        history: list = None,
        system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        """调用LLM，一次性返回完整JSON字符串"""
        if not self.is_ready:
            yield json.dumps({
                "reply": "API Key 未配置，请设置 DASHSCOPE_API_KEY",
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
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=768,
                    top_p=0.9,
                )
                result = ""
                for chunk in resp:
                    if chunk.choices and chunk.choices[0].delta.content:
                        d = chunk.choices[0].delta.content
                        if d:
                            result += d
                return result

            with ThreadPoolExecutor(max_workers=1) as pool:
                text = await loop.run_in_executor(pool, _sync)

            if text:
                yield text
            else:
                yield json.dumps({
                    "reply": "没有收到回复",
                    "emotion": "confused",
                    "move_intent": "none"
                }, ensure_ascii=False)

        except Exception as e:
            msg = str(e)
            logger.error(f"LLM失败: {msg}")
            if "401" in msg or "Unauthorized" in msg or "invalid_api_key" in msg:
                hint = f"API Key 无效({self._provider})，请检查后重试"
            elif "timeout" in msg.lower() or "timed out" in msg.lower():
                hint = "请求超时，请检查网络"
            elif "connection" in msg.lower():
                hint = f"网络连接错误，请检查网络 ({self._base_url})"
            elif "insufficient_quota" in msg:
                hint = "API 额度不足"
            else:
                hint = f"出错了: {msg[:80]}"
            yield json.dumps({
                "reply": hint, "emotion": "sad", "move_intent": "none"
            }, ensure_ascii=False)
