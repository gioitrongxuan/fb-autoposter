import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_profile() -> dict:
    path = Path(__file__).parent / "post_profile.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_system_prompt() -> str:
    profile = load_profile()
    brand_name = profile.get("brand_name", "")
    shop_context = profile.get("shop_context", "")
    brand_voice = profile.get("brand_voice", "thân thiện, gần gũi, chuyên nghiệp")
    post_length = profile.get("post_length", "3-5 câu, súc tích")
    emoji_usage = profile.get("emoji_usage", "vừa phải, 1-2 emoji mỗi bài")
    hashtag_style = profile.get("hashtag_style", "3-5 hashtag liên quan cuối bài")
    avoid = profile.get("avoid", [])

    avoid_str = "\n".join(f"- {a}" for a in avoid) if avoid else "- Không có"
    brand_parts = []
    if brand_name:
        brand_parts.append(f"Tên thương hiệu: {brand_name}")
    if shop_context:
        brand_parts.append(shop_context)
    brand_info = "\n".join(brand_parts) if brand_parts else "Chưa cấu hình"

    return f"""Bạn là chuyên gia content marketing Facebook.
Viết bài đăng Facebook hấp dẫn, tự nhiên theo yêu cầu.

THÔNG TIN THƯƠNG HIỆU:
{brand_info}

PHONG CÁCH VIẾT:
- Giọng điệu: {brand_voice}
- Độ dài: {post_length}
- Dùng emoji: {emoji_usage}
- Hashtag: {hashtag_style}

TRÁNH:
{avoid_str}

Chỉ trả về nội dung bài đăng hoàn chỉnh, không thêm tiêu đề hay giải thích."""
