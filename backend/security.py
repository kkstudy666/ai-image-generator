"""上传文件安全校验：限制格式（jpg/png/webp）、大小上限、文件头（magic bytes）校验。

参考图以 base64 data URI 传入，这里解码后逐项校验，防止伪装格式的恶意文件。
"""
import base64
import binascii

from config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES

# 各格式的文件头魔数（magic bytes）
_MAGIC_BYTES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89\x50\x4e\x47",),
    "image/webp": (b"RIFF",),  # webp 结构：RIFF + 4 字节大小 + "WEBP"
}


def validate_and_decode_image(data_uri: str) -> tuple[str, bytes]:
    """校验参考图 data URI，返回 (content_type, 原始字节)。

    校验项：data URI 格式、允许的 MIME 类型、base64 合法性、大小上限、文件头。
    不合法时抛 ValueError，由调用方转为 400 响应。
    """
    if not data_uri or not data_uri.startswith("data:image/"):
        raise ValueError("参考图必须是 data:image/ 格式")

    try:
        header, b64 = data_uri.split(",", 1)
    except ValueError:
        raise ValueError("参考图 data URI 格式错误")

    # header 形如 "data:image/png;base64"，取 "image/png"
    content_type = header.split(";")[0][len("data:"):]
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("仅支持 jpg / png / webp 格式的参考图")

    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("参考图 base64 解码失败")

    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("参考图大小超过 10MB 上限")

    if not any(raw.startswith(m) for m in _MAGIC_BYTES[content_type]):
        raise ValueError("文件内容与声明格式不符，已拒绝")
    if content_type == "image/webp" and raw[8:12] != b"WEBP":
        raise ValueError("文件内容与声明格式不符，已拒绝")

    return content_type, raw
