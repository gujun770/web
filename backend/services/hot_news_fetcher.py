import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin, urlparse

from services.llm_client import LLMConfigError, call_chat_completion_sync


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    category_id: int | None = None
    kind: str = "rss"


CATEGORY_NAMES = {
    1: "头条",
    2: "社会",
    3: "国内",
    4: "国际",
    5: "娱乐",
    6: "体育",
    7: "军事",
    8: "科技",
    9: "财经",
}


# 只保留中文新闻源。英文源会让列表混入英文标题，已经全部移除。
CATEGORY_FEEDS: dict[int, list[FeedSource]] = {
    1: [
        FeedSource("新浪滚动-全部直连", "2509", 1, "sina_roll"),
        FeedSource("新浪滚动-全部", "https://rsshub.app/sina/rollnews/2509", 1),
        FeedSource("新浪滚动-全部备用", "https://rss.datuan.dev/sina/rollnews/2509", 1),
        FeedSource("中国新闻网", "https://www.chinanews.com.cn/rss/scroll-news.xml", 1),
        FeedSource("澎湃新闻", "https://rsshub.app/thepaper/featured", 1),
    ],
    2: [
        FeedSource("新浪滚动-社会直连", "2669", 2, "sina_roll"),
        FeedSource("新浪滚动-社会", "https://rsshub.app/sina/rollnews/2669", 2),
        FeedSource("新浪滚动-社会备用", "https://rss.datuan.dev/sina/rollnews/2669", 2),
        FeedSource("澎湃新闻-时事", "https://rsshub.app/thepaper/channel/25950", 2),
        FeedSource("新浪社会", "http://rss.sina.com.cn/news/society/focus15.xml", 2),
    ],
    3: [
        FeedSource("新浪滚动-国内直连", "2510", 3, "sina_roll"),
        FeedSource("新浪滚动-国内", "https://rsshub.app/sina/rollnews/2510", 3),
        FeedSource("新浪滚动-国内备用", "https://rss.datuan.dev/sina/rollnews/2510", 3),
        FeedSource("澎湃新闻-中国政库", "https://rsshub.app/thepaper/channel/25462", 3),
        FeedSource("澎湃新闻-时事", "https://rsshub.app/thepaper/channel/25950", 3),
        FeedSource("新浪国内", "http://rss.sina.com.cn/news/china/focus15.xml", 3),
    ],
    4: [
        FeedSource("新浪滚动-国际直连", "2511", 4, "sina_roll"),
        FeedSource("新浪滚动-国际", "https://rsshub.app/sina/rollnews/2511", 4),
        FeedSource("新浪滚动-国际备用", "https://rss.datuan.dev/sina/rollnews/2511", 4),
        FeedSource("澎湃新闻-全球速报", "https://rsshub.app/thepaper/channel/122908", 4),
        FeedSource("新浪国际", "http://rss.sina.com.cn/news/world/focus15.xml", 4),
    ],
    5: [
        FeedSource("新浪滚动-娱乐直连", "2513", 5, "sina_roll"),
        FeedSource("新浪滚动-娱乐", "https://rsshub.app/sina/rollnews/2513", 5),
        FeedSource("新浪滚动-娱乐备用", "https://rss.datuan.dev/sina/rollnews/2513", 5),
        FeedSource("新浪娱乐", "http://rss.sina.com.cn/ent/hot_roll.xml", 5),
        FeedSource("澎湃新闻-文艺范", "https://rsshub.app/thepaper/channel/25457", 5),
    ],
    6: [
        FeedSource("新浪滚动-体育直连", "2512", 6, "sina_roll"),
        FeedSource("新浪滚动-体育", "https://rsshub.app/sina/rollnews/2512", 6),
        FeedSource("新浪滚动-体育备用", "https://rss.datuan.dev/sina/rollnews/2512", 6),
        FeedSource("澎湃新闻-运动家", "https://rsshub.app/thepaper/channel/-21", 6),
        FeedSource("新浪体育", "http://rss.sina.com.cn/sports/global/focus15.xml", 6),
        FeedSource("虎扑-NBA", "https://rsshub.app/hupu/nba", 6),
        FeedSource("虎扑-足球", "https://rsshub.app/hupu/soccer", 6),
        FeedSource("虎扑-CBA", "https://rsshub.app/hupu/cba", 6),
    ],
    7: [
        FeedSource("新浪滚动-军事直连", "2514", 7, "sina_roll"),
        FeedSource("新浪滚动-军事", "https://rsshub.app/sina/rollnews/2514", 7),
        FeedSource("新浪滚动-军事备用", "https://rss.datuan.dev/sina/rollnews/2514", 7),
        FeedSource("新浪军事", "http://rss.sina.com.cn/jczs/focus15.xml", 7),
        FeedSource("新浪中国军情", "http://rss.sina.com.cn/jczs/china15.xml", 7),
        FeedSource("中华网军事", "https://rsshub.app/china/news/military", 7),
        FeedSource("中华网军事-备用", "https://rsshub.gneko.io/china/news/military", 7),
    ],
    8: [
        FeedSource("新浪滚动-科技直连", "2515", 8, "sina_roll"),
        FeedSource("新浪滚动-科技", "https://rsshub.app/sina/rollnews/2515", 8),
        FeedSource("新浪滚动-科技备用", "https://rss.datuan.dev/sina/rollnews/2515", 8),
        FeedSource("澎湃新闻-未来2%号", "https://rsshub.app/thepaper/channel/119908", 8),
        FeedSource("新浪科技", "http://rss.sina.com.cn/tech/rollnews.xml", 8),
    ],
    9: [
        FeedSource("新浪滚动-财经直连", "2516", 9, "sina_roll"),
        FeedSource("新浪滚动-财经", "https://rsshub.app/sina/rollnews/2516", 9),
        FeedSource("新浪滚动-财经备用", "https://rss.datuan.dev/sina/rollnews/2516", 9),
        FeedSource("澎湃新闻-财经上下游", "https://rsshub.app/thepaper/channel/25951", 9),
        FeedSource("新浪财经", "http://rss.sina.com.cn/finance/rollnews.xml", 9),
    ],
}

GENERAL_FEEDS = [
    FeedSource("中国新闻网-综合", "https://www.chinanews.com.cn/rss/scroll-news.xml", None),
    FeedSource("澎湃新闻-综合", "https://rsshub.app/thepaper/featured", None),
]

BACKFILL_BY_CATEGORY = {
    6: [
        FeedSource("懂球帝", "https://rsshub.app/dongqiudi/team/500005", 6),
        FeedSource("懂球帝-国际足球", "https://rsshub.app/dongqiudi/special/1", 6),
    ],
    7: [
        FeedSource("中华网军事-备用2", "https://rsshub.rssforever.com/china/news/military", 7),
        FeedSource("新浪中国军情-备用", "http://rss.sina.com.cn/rollnews/jczs/china/focus15.xml", 7),
    ],
}


CATEGORY_KEYWORDS = {
    2: ("社会", "民生", "教育", "医疗", "就业", "法治", "案件", "警方", "市民", "学校"),
    3: ("国内", "中国", "全国", "政策", "城市", "国务院", "北京", "上海", "广东", "浙江"),
    4: ("国际", "全球", "美国", "欧洲", "日本", "韩国", "俄罗斯", "外交", "海外", "国际"),
    5: ("娱乐", "电影", "明星", "综艺", "票房", "音乐", "演员", "导演", "剧集"),
    6: ("体育", "比赛", "足球", "篮球", "冠军", "联赛", "国足", "中超", "NBA", "奥运"),
    7: ("军事", "军情", "国防", "舰", "军", "防务", "演训", "导弹", "航母"),
    8: ("科技", "AI", "人工智能", "大模型", "芯片", "机器人", "算法", "数据", "互联网"),
    9: ("财经", "股", "基金", "市场", "经济", "消费", "金融", "投资", "银行", "A股"),
}


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript|iframe)[\s\S]*?</\1>", re.I)
PARAGRAPH_RE = re.compile(r"<p[^>]*>([\s\S]*?)</p>", re.I)
META_TAG_RE = re.compile(r"<meta[^>]+>", re.I)
ATTR_RE = re.compile(r'([:\w-]+)=["\']([^"\']*)["\']', re.I)
IMG_TAG_RE = re.compile(r"<img[^>]+>", re.I)
JSON_IMAGE_RE = re.compile(r'"image"\s*:\s*(?:"([^"]+)"|\[\s*"([^"]+)")', re.I)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
IMAGE_ATTRS = (
    "data-src",
    "data-original",
    "data-actualsrc",
    "data-lazy-src",
    "data-url",
    "data-img",
    "src",
)
BAD_IMAGE_KEYWORDS = (
    "logo",
    "icon",
    "avatar",
    "qrcode",
    "qr_code",
    "weixin",
    "wxcode",
    "placeholder",
    "thumb",
    "thumbnail",
    "small",
    "share",
    "loading",
    "blank",
    "spacer",
    "default",
    "transparent",
    "sprite",
    "appdownload",
    "favicon",
    "blank.gif",
    "grey.gif",
    "1x1",
    "pixel",
)
GOOD_IMAGE_KEYWORDS = (
    "upload",
    "image",
    "photo",
    "pic",
    "news",
    "content",
    "cms",
    "nimg",
    "sinaimg",
    "thepaper",
    "chinanews",
)
MIN_IMAGE_WIDTH = 260
MIN_IMAGE_HEIGHT = 140
MIN_IMAGE_BYTES = 8 * 1024
MAX_IMAGE_CHECKS = 4


def get_feed_sources(category_id: int = 1) -> list[FeedSource]:
    raw = os.getenv("HOT_NEWS_FEEDS", "").strip()
    if raw:
        sources: list[FeedSource] = []
        for chunk in raw.split(","):
            parts = [part.strip() for part in chunk.split("|")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                fixed_category = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else category_id
                sources.append(FeedSource(parts[0], parts[1], fixed_category))
        if sources:
            return sources

    return CATEGORY_FEEDS.get(category_id) or CATEGORY_FEEDS[1]


def classify_category_id(text: str, default_category_id: int = 1) -> int:
    lowered = text.lower()
    for category_id, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return category_id
    return default_category_id


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now()
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        tag = child.tag.split("}", 1)[-1].lower()
        if tag not in names:
            continue
        if tag == "link":
            return child.attrib.get("href") or child.text or ""
        return child.text or ""
    return ""


def has_chinese(value: str) -> bool:
    return bool(CHINESE_RE.search(value or ""))


def is_real_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_image_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(IMAGE_EXTENSIONS)


def parse_srcset(value: str) -> list[str]:
    result = []
    for chunk in (value or "").split(","):
        url = chunk.strip().split(" ")[0].strip()
        if url:
            result.append(url)
    return result


def normalize_image_url(value: str, base_url: str) -> str | None:
    if not value:
        return None

    candidate = html.unescape(value).strip().replace("\\/", "/")
    if "," in candidate and " " in candidate:
        candidate = candidate.split(",")[-1].strip().split(" ")[0]
    if candidate.startswith("data:") or candidate.startswith("blob:"):
        return None

    url = urljoin(base_url, candidate)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def image_dimensions_from_bytes(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if len(data) >= 10 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8 " and len(data) >= 30:
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        if data[12:16] == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if data[12:16] == b"VP8X" and len(data) >= 30:
            return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    if len(data) > 4 and data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return int.from_bytes(data[index + 7:index + 9], "big"), int.from_bytes(data[index + 5:index + 7], "big")
            block_size = int.from_bytes(data[index + 2:index + 4], "big")
            if block_size < 2:
                break
            index += 2 + block_size
    return None, None


@lru_cache(maxsize=512)
def probe_image(url: str) -> tuple[bool, int | None, int | None, str]:
    lowered = url.lower()
    if any(keyword in lowered for keyword in BAD_IMAGE_KEYWORDS):
        return False, None, None, "bad-keyword"

    parsed = urlparse(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 DeepResearchAgent/1.0",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "Range": "bytes=0-262143",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=2.2) as response:
            content_type = (response.headers.get_content_type() or "").lower()
            data = response.read(262144)
    except Exception:
        return False, None, None, "request-failed"

    if not content_type.startswith("image/") or content_type in {"image/svg+xml", "image/gif"}:
        return False, None, None, content_type or "not-image"
    if len(data) < MIN_IMAGE_BYTES:
        return False, None, None, "too-small-bytes"

    width, height = image_dimensions_from_bytes(data)
    if width is not None and height is not None:
        if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
            return False, width, height, "too-small-dimensions"
        if width / max(height, 1) > 5 or height / max(width, 1) > 3:
            return False, width, height, "bad-ratio"

    return True, width, height, content_type


def is_usable_news_image(url: str) -> bool:
    if not is_real_url(url):
        return False
    usable, _width, _height, _reason = probe_image(url)
    return usable


def image_score(url: str, attrs: dict[str, str] | None = None, priority: int = 0) -> int:
    lowered = url.lower()
    if any(keyword in lowered for keyword in BAD_IMAGE_KEYWORDS):
        return -100

    score = priority
    if re.search(r"[/_-](?:60|80|100|120|150|160|180|200)[x_](?:60|80|100|120|150|160|180|200)(?:[._/-]|$)", lowered):
        score -= 60
    if re.search(r"(?:^|[?&])(?:w|width)=(?:60|80|100|120|150|160|180|200)(?:&|$)", lowered):
        score -= 50
    if is_image_url(url):
        score += 30
    if any(keyword in lowered for keyword in GOOD_IMAGE_KEYWORDS):
        score += 18
    if attrs:
        for key in ("width", "height"):
            value = attrs.get(key, "")
            match = re.search(r"\d+", value)
            if match and int(match.group(0)) >= 180:
                score += 12
            if match and int(match.group(0)) < 160:
                score -= 45
        alt = attrs.get("alt", "")
        if has_chinese(alt):
            score += 8
    return score


def image_key(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".lower()


def sorted_valid_images(candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
    valid = [(url, score) for url, score in candidates if score >= 0 and is_real_url(url)]
    valid.sort(key=lambda item: item[1], reverse=True)
    return valid


def choose_best_image(candidates: list[tuple[str, int]], validate: bool = False) -> str | None:
    valid = sorted_valid_images(candidates)
    if validate:
        seen = set()
        checked = 0
        for url, _score in valid:
            key = image_key(url)
            if key in seen:
                continue
            seen.add(key)
            checked += 1
            if is_usable_news_image(url):
                return url
            if checked >= MAX_IMAGE_CHECKS:
                break
        return None
    return valid[0][0] if valid else None


def decode_response(raw: bytes, charset: str | None) -> str:
    encodings = [charset, "utf-8", "gb18030", "gbk", "big5"]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_url(url: str, timeout: float = 4.5) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 DeepResearchAgent/1.0",
            "Accept": "text/html,application/rss+xml,application/xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset()
        final_url = response.geturl()
    return decode_response(raw, charset), final_url


def parse_feed(xml_text: str, source: FeedSource, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries = [
        node
        for node in root.iter()
        if node.tag.split("}", 1)[-1].lower() in {"item", "entry"}
    ]

    result = []
    for index, node in enumerate(entries, start=1):
        if len(result) >= limit:
            break

        title = strip_html(child_text(node, ("title",)))
        link = child_text(node, ("link",)).strip()
        raw_description = child_text(node, ("description", "summary", "content", "encoded"))
        description = strip_html(raw_description)
        image_candidates = extract_feed_image_candidates(node, raw_description, link)
        image = choose_best_image(image_candidates)
        published = child_text(node, ("pubdate", "published", "updated"))

        if not title or not is_real_url(link) or not has_chinese(title):
            continue

        resolved_category_id = source.category_id or classify_category_id(f"{title} {description}", 1)
        result.append(
            {
                "title": title[:255],
                "description": (description or title)[:500],
                "content": f"{description or title}\n\n原文链接：{link}".strip(),
                "image": image,
                "source_name": source.name,
                "source_url": link,
                "publish_time": parse_time(published),
                "hot_score": max(50, 1000 - index * 20),
                "category_id": resolved_category_id,
                "_image_candidates": image_candidates,
            }
        )
    return result


def extract_feed_image_candidates(node: ET.Element, description: str, link: str) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    for child in list(node):
        tag = child.tag.split("}", 1)[-1].lower()
        if tag in {"enclosure", "thumbnail", "content"}:
            url = child.attrib.get("url")
            media_type = child.attrib.get("type", "")
            if url and (media_type.startswith("image/") or is_image_url(url)):
                normalized = normalize_image_url(url, link)
                if normalized:
                    candidates.append((normalized, image_score(normalized, child.attrib, 80)))

    candidates.extend(extract_image_candidates(description or "", link, priority=40))
    return candidates


def fetch_feed(source: FeedSource, limit: int) -> list[dict[str, Any]]:
    if source.kind == "sina_roll":
        return fetch_sina_roll(source, limit)

    xml_text, _ = read_url(source.url, timeout=4.5)
    return parse_feed(xml_text, source, limit)


def fetch_sina_roll(source: FeedSource, limit: int) -> list[dict[str, Any]]:
    api_url = (
        "https://feed.mix.sina.com.cn/api/roll/get?"
        f"pageid=153&lid={source.url}&k=&num={max(limit * 2, 20)}&page=1"
    )
    text, _ = read_url(api_url, timeout=4)
    payload = json.loads(text)
    raw_items = payload.get("result", {}).get("data", [])

    result = []
    for index, raw in enumerate(raw_items, start=1):
        if len(result) >= limit:
            break

        title = strip_html(raw.get("title") or raw.get("stitle") or "")
        link = (raw.get("url") or raw.get("wapurl") or "").strip()
        if not title or not is_real_url(link) or not has_chinese(title):
            continue

        description = strip_html(raw.get("intro") or raw.get("summary") or raw.get("keywords") or title)
        image = extract_sina_image(raw, link)
        ctime = raw.get("ctime") or raw.get("time")
        publish_time = datetime.fromtimestamp(int(ctime)) if str(ctime).isdigit() else datetime.now()
        result.append(
            {
                "title": title[:255],
                "description": (description or title)[:500],
                "content": f"{description or title}\n\n原文链接：{link}".strip(),
                "image": image,
                "source_name": source.name.replace("直连", ""),
                "source_url": link,
                "publish_time": publish_time,
                "hot_score": max(50, 1000 - index * 20),
                "category_id": source.category_id or classify_category_id(f"{title} {description}", 1),
                "_image_candidates": [(image, 90)] if image else [],
            }
        )
    return result


def extract_sina_image(raw: dict[str, Any], link: str) -> str | None:
    candidates: list[tuple[str, int]] = []
    keys = ("img", "image", "thumb", "pic", "kpic", "wap_pic", "thumbnail_pic")
    for key in keys:
        normalized = normalize_image_url(str(raw.get(key) or ""), link)
        if normalized:
            candidates.append((normalized, image_score(normalized, None, 100)))

    for key in ("images", "pics"):
        value = raw.get(key)
        if isinstance(value, list):
            for item in value:
                image_value = item.get("url") if isinstance(item, dict) else item
                normalized = normalize_image_url(str(image_value or ""), link)
                if normalized:
                    candidates.append((normalized, image_score(normalized, None, 100)))
        elif isinstance(value, str):
            normalized = normalize_image_url(value, link)
            if normalized:
                candidates.append((normalized, image_score(normalized, None, 100)))
    return choose_best_image(candidates)


def extract_meta(html_text: str, link: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    image_candidates: list[tuple[str, int]] = []
    for tag in META_TAG_RE.findall(html_text):
        attrs = {key.lower(): html.unescape(value).strip() for key, value in ATTR_RE.findall(tag)}
        key = attrs.get("property") or attrs.get("name") or ""
        value = attrs.get("content") or ""
        normalized_key = key.lower().strip()
        normalized_value = value.strip()
        if normalized_key in {"og:image", "twitter:image", "image"} and normalized_value:
            normalized_url = normalize_image_url(normalized_value, link)
            if normalized_url:
                image_candidates.append((normalized_url, image_score(normalized_url, attrs, 45)))
        elif normalized_key in {"description", "og:description"} and normalized_value:
            meta.setdefault("description", strip_html(normalized_value))

    article_block = extract_article_container(SCRIPT_STYLE_RE.sub("", html_text))
    if article_block:
        image_candidates.extend(extract_image_candidates(article_block, link, priority=120))
    image_candidates.extend(extract_jsonld_images(html_text, link))
    image_candidates.extend(extract_image_candidates(html_text, link, priority=25))
    meta["image_candidates"] = image_candidates
    image = choose_best_image(image_candidates)
    if image:
        meta["image"] = image
    return meta


def extract_jsonld_images(html_text: str, link: str) -> list[tuple[str, int]]:
    candidates = []
    for first, second in JSON_IMAGE_RE.findall(html_text):
        normalized = normalize_image_url(first or second, link)
        if normalized:
            candidates.append((normalized, image_score(normalized, None, 55)))
    return candidates


def extract_image_candidates(html_text: str, link: str, priority: int = 0) -> list[tuple[str, int]]:
    candidates = []
    for tag in IMG_TAG_RE.findall(html_text):
        attrs = {key.lower(): html.unescape(value).strip() for key, value in ATTR_RE.findall(tag)}
        for attr in IMAGE_ATTRS:
            normalized = normalize_image_url(attrs.get(attr, ""), link)
            if normalized:
                candidates.append((normalized, image_score(normalized, attrs, priority)))
                break

        srcset = attrs.get("srcset") or attrs.get("data-srcset")
        if srcset:
            for srcset_url in parse_srcset(srcset):
                normalized = normalize_image_url(srcset_url, link)
                if normalized:
                    candidates.append((normalized, image_score(normalized, attrs, priority + 10)))
    return candidates


def extract_article_text(html_text: str) -> str:
    cleaned = SCRIPT_STYLE_RE.sub("", html_text)
    focused = extract_article_container(cleaned) or cleaned
    paragraphs = []
    for raw in PARAGRAPH_RE.findall(focused):
        text = strip_html(raw)
        if len(text) < 12 or not has_chinese(text):
            continue
        if any(skip in text for skip in ("责任编辑", "版权声明", "举报", "下载客户端")):
            continue
        paragraphs.append(text)

    deduped = []
    seen = set()
    for paragraph in paragraphs:
        if paragraph in seen:
            continue
        seen.add(paragraph)
        deduped.append(paragraph)
        if sum(len(item) for item in deduped) > 4500:
            break
    return "\n\n".join(deduped)


def extract_article_container(html_text: str) -> str | None:
    patterns = (
        r"<article[^>]*>([\s\S]*?)</article>",
        r'<div[^>]+class=["\'][^"\']*(?:article|content|main|detail|text|news_txt|artibody)[^"\']*["\'][^>]*>([\s\S]*?)</div>',
        r'<section[^>]+class=["\'][^"\']*(?:article|content|main|detail|text)[^"\']*["\'][^>]*>([\s\S]*?)</section>',
    )
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, html_text, re.I):
            block = match.group(1)
            text = strip_html(block)
            if len(text) >= 120 and has_chinese(text):
                candidates.append((len(text), block))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda item: item[0])
    return candidates[0][1]


def title_terms(title: str) -> list[str]:
    compact = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", title or "")
    terms = set()
    for size in (4, 3, 2):
        for index in range(0, max(0, len(compact) - size + 1)):
            term = compact[index:index + size]
            if has_chinese(term):
                terms.add(term)
    return sorted(terms, key=len, reverse=True)


def article_matches_title(title: str, article_text: str, html_text: str = "") -> bool:
    if not article_text or len(article_text) < 80:
        return False
    haystack = f"{article_text[:1800]}\n{strip_html(html_text)[:1800]}"
    if title and title in haystack:
        return True

    terms = title_terms(title)[:16]
    if not terms:
        return True
    hits = sum(1 for term in terms if term in haystack)
    return hits >= min(3, max(1, len(terms) // 4))


def generate_ai_description(title: str, article_text: str) -> str | None:
    if os.getenv("HOT_NEWS_USE_LLM", "1") != "1":
        return None
    if not article_text or len(article_text) < 80:
        return None

    prompt = (
        "请只基于下面这篇中文新闻正文，生成一段 70 字以内的中文摘要。"
        "不要添加正文没有的信息，不要写英文，不要输出标题。\n\n"
        f"标题：{title}\n\n正文：{article_text[:2500]}"
    )
    try:
        return call_chat_completion_sync(
            [
                {"role": "system", "content": "你是严谨的中文新闻编辑，只做忠实摘要，不编造。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
        ).strip()[:500]
    except (LLMConfigError, Exception):
        return None


def enrich_item(item: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
    link = item.get("source_url", "")
    if not is_real_url(link):
        return item

    try:
        html_text, final_url = read_url(link, timeout=4.5)
    except Exception:
        return item

    meta = extract_meta(html_text, final_url)
    article_text = extract_article_text(html_text)
    article_trusted = article_matches_title(item.get("title", ""), article_text, html_text)
    item["_article_trusted"] = article_trusted
    image_candidates = list(item.get("_image_candidates") or [])
    image_candidates.extend(meta.get("image_candidates") or [])
    item["_image_candidates"] = image_candidates
    best_image = choose_best_image(image_candidates, validate=True)
    item["image"] = best_image
    if meta.get("description") and (not item.get("description") or item["description"] == item["title"]):
        item["description"] = meta["description"][:500]
    if article_trusted:
        item["content"] = f"{article_text}\n\n原文链接：{final_url}"
        if not item.get("description") or item["description"] == item["title"]:
            item["description"] = article_text[:160]
    if use_llm and article_trusted:
        ai_description = generate_ai_description(item["title"], article_text)
        if ai_description:
            item["description"] = ai_description
    return item


def dedupe_news(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for item in items:
        key = item.get("source_url") or item.get("title")
        title = item.get("title", "").strip()
        if not title or not has_chinese(title) or not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def enrich_items(items: list[dict[str, Any]], use_llm: bool = False) -> list[dict[str, Any]]:
    if not items:
        return []

    max_workers = min(8, len(items))
    enriched: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(enrich_item, item, use_llm) for item in items]
        for future in as_completed(futures):
            try:
                enriched.append(future.result())
            except Exception:
                continue
    order = {item.get("source_url"): index for index, item in enumerate(items)}
    enriched = sorted(enriched, key=lambda item: order.get(item.get("source_url"), 0))
    resolve_duplicate_images(enriched)
    for item in enriched:
        item.pop("_image_candidates", None)
        item.pop("_article_trusted", None)
    return enriched


def enrich_missing_images(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [item for item in items if is_real_url(item.get("source_url", ""))]
    if not candidates:
        resolve_duplicate_images(items, validate=True)
        return items

    def fill_image(item: dict[str, Any]) -> dict[str, Any]:
        current_image = item.get("image")
        if current_image and is_usable_news_image(current_image):
            return item

        try:
            html_text, final_url = read_url(item["source_url"], timeout=2.5)
            meta = extract_meta(html_text, final_url)
            image_candidates = list(item.get("_image_candidates") or [])
            image_candidates.extend(meta.get("image_candidates") or [])
            item["_image_candidates"] = image_candidates
            item["image"] = choose_best_image(image_candidates, validate=True)
        except Exception:
            item["image"] = None
            pass
        return item

    with ThreadPoolExecutor(max_workers=min(12, len(candidates))) as executor:
        futures = [executor.submit(fill_image, item) for item in candidates]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                continue
    resolve_duplicate_images(items, validate=True)
    for item in items:
        item.pop("_image_candidates", None)
    return items


def resolve_duplicate_images(items: list[dict[str, Any]], validate: bool = False) -> None:
    used: set[str] = set()
    duplicate_count: dict[str, int] = {}
    for item in items:
        image = item.get("image")
        if image:
            key = image_key(image)
            duplicate_count[key] = duplicate_count.get(key, 0) + 1

    for item in items:
        candidates = sorted_valid_images(item.get("_image_candidates") or [])
        chosen = None
        current = item.get("image")
        current_key = image_key(current) if current else ""
        if current and (not validate or is_usable_news_image(current)) and duplicate_count.get(current_key, 0) <= 1 and current_key not in used:
            item["image"] = current
            used.add(current_key)
            continue
        for url, _score in candidates:
            key = image_key(url)
            if key in used:
                continue
            if duplicate_count.get(key, 0) > 1 and key == current_key:
                continue
            if validate and not is_usable_news_image(url):
                continue
            chosen = url
            used.add(key)
            break
        item["image"] = chosen


def fetch_hot_news(
    limit: int = 20,
    default_category_id: int = 1,
    enrich: bool = True,
    use_llm: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    sources = get_feed_sources(default_category_id)
    per_source_limit = max(limit, 15)

    executor = ThreadPoolExecutor(max_workers=min(6, len(sources)))
    future_map = {executor.submit(fetch_feed, source, per_source_limit): source for source in sources}
    try:
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                collected.extend(future.result())
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
            if len(dedupe_news(collected, limit)) >= limit:
                break
    finally:
        for future in future_map:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    if default_category_id != 1:
        collected = [item for item in collected if item.get("category_id") == default_category_id]

    if default_category_id != 1 and len(collected) < limit:
        with ThreadPoolExecutor(max_workers=min(4, len(GENERAL_FEEDS))) as executor:
            future_map = {executor.submit(fetch_feed, source, per_source_limit * 2): source for source in GENERAL_FEEDS}
            for future in as_completed(future_map):
                source = future_map[future]
                try:
                    collected.extend(
                        item for item in future.result()
                        if item.get("category_id") == default_category_id
                    )
                except Exception as exc:
                    errors.append(f"{source.name}: {exc}")

    backfill_sources = BACKFILL_BY_CATEGORY.get(default_category_id, [])
    if default_category_id != 1 and len(collected) < limit and backfill_sources:
        with ThreadPoolExecutor(max_workers=min(4, len(backfill_sources))) as executor:
            future_map = {executor.submit(fetch_feed, source, per_source_limit): source for source in backfill_sources}
            for future in as_completed(future_map):
                source = future_map[future]
                try:
                    collected.extend(
                        item for item in future.result()
                        if item.get("category_id") == default_category_id
                    )
                except Exception as exc:
                    errors.append(f"{source.name}: {exc}")

    items = dedupe_news(collected, limit)
    if enrich:
        items = enrich_items(items, use_llm=use_llm)
    return items, errors


def fetch_all_channel_hot_news(limit_per_category: int = 10, enrich: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    errors: list[str] = []
    seen = set()

    def fetch_category(category_id: int):
        items, category_errors = fetch_hot_news(limit_per_category, category_id, enrich=enrich, use_llm=False)
        return category_id, items, category_errors

    with ThreadPoolExecutor(max_workers=min(5, len(CATEGORY_NAMES))) as executor:
        futures = [executor.submit(fetch_category, category_id) for category_id in CATEGORY_NAMES]
        for future in as_completed(futures):
            try:
                _category_id, items, category_errors = future.result()
            except Exception as exc:
                errors.append(f"频道抓取失败: {exc}")
                continue
            errors.extend(category_errors)
            for item in items:
                key = item.get("source_url") or item.get("title")
                category_key = (item.get("category_id"), key)
                if not key or category_key in seen:
                    continue
                seen.add(category_key)
                result.append(item)

    result = enrich_missing_images(result)
    return result, errors


def extract_source_url(content: str | None) -> str | None:
    if not content:
        return None
    match = re.search(r"原文链接：\s*(https?://\S+)", content)
    return match.group(1).strip() if match else None


def fetch_article_detail_from_content(
    content: str | None,
    title: str,
    use_llm: bool = False,
    source_url: str | None = None,
) -> dict[str, str | None]:
    source_url = source_url or extract_source_url(content)
    if not source_url:
        return {"content": content, "image": None, "description": None}

    item = {
        "title": title,
        "description": "",
        "content": content or "",
        "image": None,
        "source_url": source_url,
    }
    enriched = enrich_item(item, use_llm=use_llm)
    return {
        "content": enriched.get("content") or content,
        "image": enriched.get("image"),
        "description": enriched.get("description"),
        "trusted": enriched.get("_article_trusted"),
    }
