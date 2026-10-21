"""火山方舟 Seedream 图片生成接口封装（OpenAI 兼容格式），含超时与熔断保护。

火山方舟 Seedream 使用 OpenAI 兼容的 /images/generations 端点：
- 文生图：只传 prompt
- 图生图：把参考图放进 image 数组（元素为图片 URL 或 data URI）
- 官方接口没有独立的 negative_prompt 字段，这里把负面提示词拼接到 prompt。

密钥安全：ARK_API_KEY 只从环境变量读取（见 config.py），日志中一律脱敏输出。
"""
from openai import OpenAI

from circuit_breaker import CircuitBreaker
from config import (
    ARK_API_KEY,
    ARK_BASE_URL,
    ARK_MODEL,
    SEEDREAM_TIMEOUT_SECONDS,
    mask_secret,
)
from logging_config import get_logger

logger = get_logger("ark_client")

# 火山方舟 OpenAI 兼容客户端（密钥来自环境变量，禁止硬编码）
client = OpenAI(
    base_url=ARK_BASE_URL,
    api_key=ARK_API_KEY,
    timeout=SEEDREAM_TIMEOUT_SECONDS,
)

# 全局熔断器实例
_breaker = CircuitBreaker()


def generate_image(prompt, negative_prompt=None, size="1024x1024", input_image=None):
    """调用 Seedream 生成一张图片（受熔断器保护）。

    返回：生成的图片 URL
    抛 CircuitOpenError：熔断打开（调用方应友好提示，不重试）
    抛其他异常：调用失败（调用方按策略重试）
    """
    # 熔断检查（在 try 外，CircuitOpenError 不会触发 on_failure）
    _breaker.before_call()

    try:
        full_prompt = prompt
        if negative_prompt and negative_prompt.strip():
            full_prompt = f"{prompt}。请避免出现以下内容：{negative_prompt.strip()}"

        # OpenAI SDK 标准参数之外的扩展字段，通过 extra_body 透传给火山方舟
        extra_body = {"watermark": False}
        if input_image:
            extra_body["image"] = [input_image]

        logger.info(
            "调用 Seedream（模型=%s，尺寸=%s，密钥=%s）",
            ARK_MODEL, size, mask_secret(ARK_API_KEY),
        )

        resp = client.images.generate(
            model=ARK_MODEL,
            prompt=full_prompt,
            size=size,
            response_format="url",
            extra_body=extra_body,
        )

        item = resp.data[0]
        if not getattr(item, "url", None):
            raise RuntimeError("Seedream 未返回图片链接，请检查 ARK_API_KEY 与 ARK_MODEL 配置")

        _breaker.on_success()
        return item.url
    except Exception:
        _breaker.on_failure()
        raise
