"""火山方舟 Seedream 图片生成接口封装（OpenAI 兼容格式）。

火山方舟 Seedream 使用 OpenAI 兼容的 /images/generations 端点：
- 文生图：只传 prompt
- 图生图：把参考图放进 image 数组（元素为图片 URL 或 data URI）
- 官方接口没有独立的 negative_prompt 字段，这里把负面提示词拼接到 prompt。
"""
import os

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# 火山方舟 OpenAI 兼容客户端
client = OpenAI(
    base_url=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
    api_key=os.getenv("ARK_API_KEY"),
)


def generate_image(prompt, negative_prompt=None, size="1024x1024", input_image=None):
    """调用 Seedream 生成一张图片。

    参数：
        prompt          主提示词
        negative_prompt 负面提示词（拼接到 prompt，近似实现"排除某些内容"）
        size            尺寸，如 "1024x1024"、"1280x720"
        input_image     图生图参考图（data URI，如 "data:image/jpeg;base64,xxx"），None 表示文生图

    返回：生成的图片 URL
    """
    # 负面提示词处理：Seedream 官方 API 无 negative_prompt 字段，
    # 这里拼接到主提示词末尾实现近似效果。
    full_prompt = prompt
    if negative_prompt and negative_prompt.strip():
        full_prompt = f"{prompt}。请避免出现以下内容：{negative_prompt.strip()}"

    # OpenAI SDK 标准参数之外的扩展字段，通过 extra_body 透传给火山方舟
    extra_body = {"watermark": False}

    # 图生图：参考图放入 image 数组（元素为 URL 或 data URI）
    if input_image:
        extra_body["image"] = [input_image]

    resp = client.images.generate(
        model=os.getenv("ARK_MODEL", "doubao-seedream-5-0-pro-260628"),
        prompt=full_prompt,
        size=size,
        response_format="url",
        extra_body=extra_body,
    )

    item = resp.data[0]
    if getattr(item, "url", None):
        return item.url
    raise RuntimeError("Seedream 未返回图片链接，请检查 ARK_API_KEY 与 ARK_MODEL 配置")
