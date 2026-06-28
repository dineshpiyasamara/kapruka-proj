import os
import json
import re
import html
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


load_dotenv(override=True)

MCP_SERVERS = {
    "kapruka": {
        "url": "https://mcp.kapruka.com/mcp",
        "transport": "streamable_http",
    },
}


SYSTEM_PROMPT = """
You are Kapruka's AI shopping concierge for Sri Lankan customers.

Your job is not to behave like a boring search box.
You should feel warm, helpful, slightly witty, emotionally intelligent, and locally aware.

You are not only a product finder.
You are a helpful shopping companion who understands the situation behind the purchase.

Support:
- Everyday self-shopping: groceries, electronics, fashion, home items, daily essentials.
- Gift mode: birthdays, apologies, breakups, anniversaries, family events.
- Emotional shopping moments: apologies, missing someone, family care, celebrations, comfort gifts, thank-you gifts.
- Sinhala, English, and Tanglish when the user uses them.
- Multi-item carts.
- Delivery-date handling.
- Gift note suggestions.

Emotional concierge behavior:
- If the user shares an emotional situation, first acknowledge the feeling warmly.
- Then give a practical shopping plan.
- Then give one gentle human suggestion that fits the moment.
- Do not sound robotic or transactional.
- Do not overdo emotional advice. Keep it short, kind, and useful.
- Do not pressure the recipient.
- Do not suggest forcing a meeting, repeatedly contacting someone, or ignoring boundaries.
- For romantic apology or breakup situations, suggest calmness, sincerity, respect, and giving space.
- You may suggest hand-delivering a gift only when it feels appropriate and safe.
- If suggesting hand-delivery, phrase it respectfully: “only if she is comfortable meeting.”
- Avoid intimate or physical suggestions. Keep advice respectful and non-pushy.
- For family situations, sound caring and locally warm.
- For everyday shopping, be efficient and practical, not overly emotional.

Examples of the desired style:
- User: “I broke up with my girlfriend… I need to send some flowers.”
  Good style:
  “Aiyo, that sounds heavy. I’ll help you pick something thoughtful, but don’t make it look like you’re trying too hard. A simple bouquet with a sincere note is better than something dramatic. If she is comfortable meeting, hand-delivering it calmly may feel more genuine than just sending it through a courier.”

- User: “Mage amma ge birthday ekata gift ekak ona.”
  Good style:
  “Aww, amma gifts should feel useful and loving. Let’s pick something thoughtful, not just expensive. I’ll suggest a few options that feel warm, practical, and birthday-worthy.”

- User: “I need groceries for myself.”
  Good style:
  “Perfect, let’s build a sensible cart. I’ll focus on useful everyday items first, then we can add treats if the budget allows.”

Important behavior:
- Ask only the next most useful question.
- Recommend products with a reason.
- If the user is emotional, respond kindly and practically before recommending products.
- If product search is needed, use Kapruka tools.
- If delivery or checkout is needed, use Kapruka tools.
- Do not invent product details. Use tools.
- Do not claim a product exists unless it came from Kapruka tools.
- Do not create fake checkout links.
- Keep replies concise but full of personality.
- For Sinhala/Tanglish users, reply naturally in the same style when possible.

Product recommendation behavior:
- For gifts, explain why each product fits the situation.
- For emotional gifts, avoid overly expensive or dramatic recommendations unless the user asks.
- For everyday shopping, prioritize usefulness, budget, and availability.
- If the user gives a budget, stay within it where possible.
- If the user gives a delivery city/date, consider delivery availability before checkout.
- If the user asks for “something good,” ask one helpful follow-up or provide a few smart options.
- If the user asks for best-selling, most sold, popular, trending, top, or recommended products, use Kapruka product search with the closest available sort option such as best_selling, popularity, popular, or relevance.
- If the MCP does not support the requested sort, fall back to relevant available products.
- Do not claim “best-selling” unless the tool result clearly supports it. Otherwise say “popular-looking” or “good options.”

Checkout behavior:
- Do not ask for personal details when adding products to cart.
- Collect recipient, sender, delivery, and gift message details only during checkout.
- When checkout details are provided, check delivery availability first.
- If delivery seems possible, help continue to Kapruka guest checkout.
- If delivery is not possible, suggest a different date, location, or product option.
- If an order is created, put the actual payment or checkout link in checkout_url.
- Do not write the checkout URL only inside the reply text.
- Do not output a broken checkout link such as [Complete your order]( with no URL.

CRITICAL OUTPUT RULE:
You must always respond as STRICT JSON only.
Do not use Markdown product lists.
Do not write product links inside the reply text.
Do not write image URLs inside the reply text.
Do not write numbered product lists inside the reply text.
Do not duplicate product details in the reply text.
Put all product details only inside the products array.

The reply field should be a short human message only.
Example good reply:
“Aiyo, I found a few thoughtful flower options for you. I’d keep it sincere and simple — choose one that feels calm, not too dramatic.”

Example bad reply:
“1. **Product Name** Price: LKR... ![Image](...) [View More](...)”

Use this exact shape:
{
  "reply": "short friendly assistant reply with emotional support when relevant. No product list here.",
  "products": [
    {
      "id": "product id if available",
      "name": "product name",
      "price": "price if available",
      "image": "direct image url if available",
      "url": "product page url if available",
      "why": "short reason why this product fits the user's situation",
      "in_stock": true
    }
  ],
  "cart": [],
  "checkout_url": null,
  "quick_replies": ["short option 1", "short option 2", "short option 3"]
}

If there are no products, return an empty products array.
If there is no checkout URL, return null.
"""


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    reply: str
    products: List[Dict[str, Any]] = []
    cart: List[Dict[str, Any]] = []
    checkout_url: Optional[str] = None
    quick_replies: List[str] = []


app = FastAPI(title="Kapruka AI Shopping Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None
sessions: Dict[str, List[Any]] = {}


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)


def strip_json_code_fence(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    return cleaned


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = html.unescape(text)

    # Fix damaged numeric HTML entities such as #226; instead of &#226;
    text = re.sub(r"(?<!&)#(\d+);", r"&#\1;", text)
    text = html.unescape(text)

    fixes = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
        "â€¦": "...",
        "Â": "",
    }

    for bad, good in fixes.items():
        text = text.replace(bad, good)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_url(value: Any) -> str:
    if not value:
        return ""

    url = str(value).strip()
    url = html.unescape(url)
    url = url.replace("\\/", "/")
    url = url.strip("\"'` ")

    if url.startswith("//"):
        url = f"https:{url}"

    url = re.sub(r"[)\],.]+$", "", url)

    # Avoid returning obviously broken markdown fragments as URLs.
    if url in ["(", ")", "[", "]", "[]", "null", "None", "none"]:
        return ""

    return url


def is_image_url(url: str) -> bool:
    lower_url = clean_url(url).lower()

    return (
        "product-image" in lower_url
        or "productimages" in lower_url
        or "productimage" in lower_url
        or "flowerimages" in lower_url
        or lower_url.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"))
    )


def is_likely_checkout_url(url: str) -> bool:
    lower_url = clean_url(url).lower()

    if not lower_url.startswith("http"):
        return False

    if is_image_url(lower_url):
        return False

    checkout_keywords = [
        "checkout",
        "payment",
        "pay",
        "order",
        "cart",
        "guest",
        "invoice",
        "complete",
        "purchase",
    ]

    return any(keyword in lower_url for keyword in checkout_keywords)


def extract_checkout_url_from_text(text: Any) -> str:
    raw_text = content_to_text(text)

    markdown_patterns = [
        r"\[(?:complete your order|checkout|pay now|continue to payment|complete payment|payment link)[^\]]*\]\((https?://[^)\s]+)\)",
        r"(?:checkout url|checkout_url|checkoutUrl|payment url|payment_url|paymentUrl|payment link|checkout link|pay url|pay_url)\s*[:=]\s*(https?://[^\s)\]]+)",
    ]

    for pattern in markdown_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            url = clean_url(match.group(1))
            if is_likely_checkout_url(url):
                return url

    urls = re.findall(r"https?://[^\s\"'<>)\]]+", raw_text)

    likely_urls = []
    fallback_urls = []

    for url in urls:
        cleaned_url = clean_url(url)

        if not cleaned_url:
            continue

        if is_image_url(cleaned_url):
            continue

        if is_likely_checkout_url(cleaned_url):
            likely_urls.append(cleaned_url)
        else:
            fallback_urls.append(cleaned_url)

    if likely_urls:
        return likely_urls[0]

    # During checkout/order creation, sometimes the payment URL may not contain obvious keywords.
    # Only use fallback if there is exactly one non-image URL to avoid using product links by mistake.
    if len(fallback_urls) == 1:
        return fallback_urls[0]

    return ""


def extract_checkout_url_from_any_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return extract_checkout_url_from_text(value)

    if isinstance(value, list):
        for item in value:
            url = extract_checkout_url_from_any_value(item)
            if url:
                return url
        return ""

    if isinstance(value, dict):
        checkout_keys = [
            "checkout_url",
            "checkoutUrl",
            "checkout_link",
            "checkoutLink",
            "payment_url",
            "paymentUrl",
            "payment_link",
            "paymentLink",
            "pay_url",
            "payUrl",
            "url",
            "link",
        ]

        for key in checkout_keys:
            if key in value:
                possible_url = clean_url(value.get(key))

                if not possible_url:
                    continue

                if is_image_url(possible_url):
                    continue

                # For explicit checkout/payment keys, accept any valid non-image URL.
                # For generic url/link keys, require checkout-like keywords.
                if key.lower() not in ["url", "link"]:
                    if possible_url.startswith("http"):
                        return possible_url
                elif is_likely_checkout_url(possible_url):
                    return possible_url

        for child in value.values():
            url = extract_checkout_url_from_any_value(child)
            if url:
                return url

    return ""


def extract_checkout_url_from_messages(messages: List[Any]) -> str:
    # Prefer later messages because tool outputs / final replies usually appear later.
    for message in reversed(messages):
        content = getattr(message, "content", None)

        if content is None and isinstance(message, dict):
            content = message.get("content")

        url = extract_checkout_url_from_any_value(content)

        if url:
            return url

    return ""


def sanitize_checkout_reply(reply: Any, checkout_url: Optional[str]) -> str:
    text = content_to_text(reply).strip()

    # Remove broken or valid markdown checkout URL lines from the reply.
    text = re.sub(
        r"Checkout URL\s*:\s*\[[^\]]*\]\([^)]*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"(?:Checkout URL|Payment URL|Payment link|Checkout link|Pay URL)\s*:\s*https?://[^\s]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\[(?:Complete your order|Checkout|Pay now|Continue to payment|Complete payment)[^\]]*\]\([^)]*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = clean_text(text)

    if checkout_url:
        return text or "Your order is ready. You can continue to payment using the button below."

    return text


def find_first_url(value: Any, prefer_image: bool = False) -> str:
    text = content_to_text(value)
    urls = re.findall(r"https?://[^\s\"'<>)\]]+", text)

    if not urls:
        return ""

    cleaned_urls = [clean_url(url) for url in urls]

    if prefer_image:
        for url in cleaned_urls:
            lower_url = url.lower()
            if (
                "product-image" in lower_url
                or "productimages" in lower_url
                or "productimage" in lower_url
                or "flowerimages" in lower_url
                or lower_url.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
            ):
                return url

    return cleaned_urls[0]


def get_value_case_insensitive(data: Dict[str, Any], aliases: List[str]) -> Any:
    if not isinstance(data, dict):
        return ""

    lowered = {str(key).lower(): value for key, value in data.items()}

    for alias in aliases:
        value = lowered.get(alias.lower())
        if value not in [None, ""]:
            return value

    return ""


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def normalize_products(products: Any) -> List[Dict[str, Any]]:
    if not isinstance(products, list):
        return []

    normalized = []

    for product in products:
        if not isinstance(product, dict):
            continue

        name = (
            product.get("name")
            or product.get("title")
            or product.get("product_name")
            or product.get("productName")
            or product.get("item_name")
            or product.get("itemName")
            or ""
        )

        url = (
            product.get("url")
            or product.get("link")
            or product.get("product_url")
            or product.get("productUrl")
            or product.get("product_link")
            or product.get("productLink")
            or product.get("item_url")
            or product.get("itemUrl")
            or ""
        )

        image = (
            product.get("image")
            or product.get("image_url")
            or product.get("imageUrl")
            or product.get("img")
            or product.get("img_url")
            or product.get("imgUrl")
            or product.get("thumbnail")
            or product.get("thumbnail_url")
            or product.get("thumbnailUrl")
            or product.get("product_image")
            or product.get("productImage")
            or product.get("product_image_url")
            or product.get("productImageUrl")
            or product.get("main_image")
            or product.get("mainImage")
            or product.get("picture")
            or product.get("picture_url")
            or product.get("pictureUrl")
            or ""
        )

        price = (
            product.get("price")
            or product.get("selling_price")
            or product.get("sellingPrice")
            or product.get("amount")
            or product.get("unit_price")
            or product.get("unitPrice")
            or ""
        )

        why = (
            product.get("why")
            or product.get("reason")
            or product.get("description")
            or product.get("short_description")
            or product.get("shortDescription")
            or "This matches what you asked for."
        )

        if isinstance(url, (dict, list)):
            url = find_first_url(url)

        if isinstance(image, (dict, list)):
            image = find_first_url(image, prefer_image=True)

        url = clean_url(url)
        image = clean_url(image)

        if not image:
            image = find_first_url(product, prefer_image=True)

        if not url:
            possible_url = find_first_url(product)
            if possible_url and possible_url != image:
                url = possible_url

        name = clean_text(name)

        if not name:
            continue

        normalized.append(
            {
                "id": clean_text(
                    product.get("id")
                    or product.get("product_id")
                    or product.get("productId")
                    or url
                    or name
                ),
                "name": name,
                "price": clean_text(price) if price else "",
                "image": clean_url(image) if image else "",
                "url": clean_url(url) if url else "",
                "why": clean_text(why) if why else "This matches what you asked for.",
                "in_stock": product.get("in_stock", product.get("inStock", True)),
            }
        )

    return normalized


def dedupe_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}

    for product in normalize_products(products):
        key = product.get("url") or normalize_name(product.get("name"))

        if not key:
            continue

        if key not in deduped:
            deduped[key] = product
            continue

        existing = deduped[key]

        for field in ["image", "url", "price", "why"]:
            if not existing.get(field) and product.get(field):
                existing[field] = product[field]

    return list(deduped.values())


def extract_products_from_markdown(text: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, int]]]:
    """
    Extract products from both formats:

    1. **Product Name**
       Price: LKR 1000
       Description
       ![Image](https://...)
       [View More](https://...)

    and:

    1. **[Product Name](https://...)**
       - Price: LKR 1000
       - ![Image](https://...)
    """
    products: List[Dict[str, Any]] = []
    spans: List[Tuple[int, int]] = []

    block_pattern = re.compile(
        r"(?:^|\n)\s*\d+\.\s*(.*?)(?=(?:\n\s*\d+\.\s*)|\Z)",
        re.DOTALL,
    )

    image_pattern = re.compile(
        r"!\[[^\]]*\]\((https?://[^\s)]+)\)|"
        r"(?:Image|image|image_url|img|thumbnail)\s*[:\-]\s*(https?://[^\s\n\r]+)",
        re.IGNORECASE,
    )

    price_pattern = re.compile(
        r"(?:Price|price)\s*[:\-]\s*([^\n\r]+)",
        re.IGNORECASE,
    )

    link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")

    for match in block_pattern.finditer(text):
        block = match.group(0).strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        if not lines:
            continue

        first_line = re.sub(r"^\d+\.\s*", "", lines[0]).strip()
        first_line = first_line.strip("*").strip()

        name = ""
        url = ""

        title_link = link_pattern.search(first_line)
        if title_link:
            name = clean_text(title_link.group(1))
            url = clean_url(title_link.group(2))
        else:
            name = clean_text(re.sub(r"\*\*", "", first_line))

        image_match = image_pattern.search(block)
        image = ""
        if image_match:
            image = next(
                (group.strip() for group in image_match.groups() if group),
                "",
            )
        image = clean_url(image)

        price_match = price_pattern.search(block)
        price = clean_text(price_match.group(1)) if price_match else ""

        if not url:
            links = link_pattern.findall(block)
            for link_text, link_url in links:
                if "view" in link_text.lower() or "more" in link_text.lower() or "kapruka.com" in link_url:
                    url = clean_url(link_url)
                    break

        if not url:
            possible_url = find_first_url(block, prefer_image=False)
            if possible_url and possible_url != image:
                url = possible_url

        why = ""
        for line in lines[1:]:
            cleaned_line = line.strip()
            cleaned_line = cleaned_line.lstrip("-").strip()
            cleaned_line = re.sub(r"\*\*", "", cleaned_line)

            if not cleaned_line:
                continue
            if price_pattern.search(cleaned_line):
                continue
            if image_pattern.search(cleaned_line):
                continue
            if "[View More]" in cleaned_line:
                continue
            if cleaned_line.lower().startswith("image"):
                continue
            if cleaned_line.startswith("http"):
                continue

            cleaned_line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned_line)
            why = clean_text(cleaned_line)
            break

        if name and (url or image or price):
            products.append(
                {
                    "id": url or name,
                    "name": name,
                    "price": price,
                    "image": image,
                    "url": url,
                    "why": why or "This matches what you asked for.",
                    "in_stock": True,
                }
            )

            spans.append(match.span())

    return dedupe_products(products), spans


def remove_markdown_product_blocks(text: str, spans: List[Tuple[int, int]]) -> str:
    cleaned = text

    for start, end in reversed(spans):
        cleaned = cleaned[:start] + "\n" + cleaned[end:]

    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
    cleaned = re.sub(r"\[View More\]\((https?://[^)]+)\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://[^\s]+", "", cleaned)
    cleaned = re.sub(r"\*\*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return clean_text(cleaned.strip())


def sanitize_reply_for_product_cards(reply: Any, products: List[Dict[str, Any]]) -> str:
    """
    Prevent duplicate product rendering:
    - Product details should appear only in cards.
    - Reply should be short intro/emotional guidance.
    """
    text = clean_text(reply)

    if not text:
        if products:
            return "I found a few good options for you."
        return ""

    markdown_products, spans = extract_products_from_markdown(text)
    if spans:
        text = remove_markdown_product_blocks(text, spans)

    # Remove any remaining markdown image/link/product noise.
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[View More\]\((https?://[^)]+)\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://[^\s]+", "", text)
    text = re.sub(r"\*\*", "", text)

    # Remove leftover numbered product-looking blocks.
    text = re.sub(
        r"(?:^|\n)\s*\d+\.\s+.*?(?:Price\s*:\s*.*?)(?=(?:\n\s*\d+\.)|\Z)",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = clean_text(text)

    if products:
        # Keep only a short intro, not long product descriptions.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        short_text = " ".join(sentences[:2]).strip()

        if short_text and len(short_text) <= 280:
            return short_text

        return "I found a few good options for you. Pick the one that feels right, and I can help with delivery or a gift note next."

    return text


def extract_products_from_any_value(value: Any) -> List[Dict[str, Any]]:
    extracted: List[Dict[str, Any]] = []

    def walk(item: Any):
        if item is None:
            return

        if isinstance(item, str):
            text = strip_json_code_fence(item)

            try:
                parsed_json = json.loads(text)
                walk(parsed_json)
                return
            except Exception:
                pass

            markdown_products, _ = extract_products_from_markdown(text)
            if markdown_products:
                extracted.extend(markdown_products)

            return

        if isinstance(item, list):
            for child in item:
                walk(child)
            return

        if isinstance(item, dict):
            name = get_value_case_insensitive(
                item,
                [
                    "name",
                    "title",
                    "product_name",
                    "productName",
                    "item_name",
                    "itemName",
                ],
            )

            url = get_value_case_insensitive(
                item,
                [
                    "url",
                    "link",
                    "product_url",
                    "productUrl",
                    "product_link",
                    "productLink",
                    "item_url",
                    "itemUrl",
                    "page_url",
                    "pageUrl",
                ],
            )

            image = get_value_case_insensitive(
                item,
                [
                    "image",
                    "image_url",
                    "imageUrl",
                    "img",
                    "img_url",
                    "imgUrl",
                    "thumbnail",
                    "thumbnail_url",
                    "thumbnailUrl",
                    "product_image",
                    "productImage",
                    "product_image_url",
                    "productImageUrl",
                    "main_image",
                    "mainImage",
                    "picture",
                    "picture_url",
                    "pictureUrl",
                ],
            )

            price = get_value_case_insensitive(
                item,
                [
                    "price",
                    "selling_price",
                    "sellingPrice",
                    "amount",
                    "unit_price",
                    "unitPrice",
                ],
            )

            why = get_value_case_insensitive(
                item,
                [
                    "why",
                    "reason",
                    "description",
                    "short_description",
                    "shortDescription",
                ],
            )

            if isinstance(url, (dict, list)):
                url = find_first_url(url)

            if isinstance(image, (dict, list)):
                image = find_first_url(image, prefer_image=True)

            url = clean_url(url)
            image = clean_url(image)

            if not image:
                image = find_first_url(item, prefer_image=True)

            if not url:
                possible_url = find_first_url(item)
                if possible_url and possible_url != image:
                    url = possible_url

            name = clean_text(name)

            if name and (url or image or price):
                extracted.append(
                    {
                        "id": clean_text(
                            item.get("id")
                            or item.get("product_id")
                            or item.get("productId")
                            or url
                            or name
                        ),
                        "name": name,
                        "price": clean_text(price) if price else "",
                        "image": clean_url(image) if image else "",
                        "url": clean_url(url) if url else "",
                        "why": clean_text(why) if why else "This matches what you asked for.",
                        "in_stock": item.get("in_stock", item.get("inStock", True)),
                    }
                )

            for child_value in item.values():
                if isinstance(child_value, (dict, list, str)):
                    walk(child_value)

    walk(value)

    return dedupe_products(extracted)


def extract_products_from_messages(messages: List[Any]) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []

    for message in messages:
        content = getattr(message, "content", None)

        if content is None and isinstance(message, dict):
            content = message.get("content")

        if content is None:
            continue

        products.extend(extract_products_from_any_value(content))

    return dedupe_products(products)


def merge_product_images(
    primary_products: List[Dict[str, Any]],
    source_products: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    primary = dedupe_products(primary_products)
    sources = dedupe_products(source_products)

    if not primary:
        return sources

    for product in primary:
        product_name_key = normalize_name(product.get("name"))
        product_url = product.get("url", "")

        for source in sources:
            source_name_key = normalize_name(source.get("name"))
            source_url = source.get("url", "")

            same_url = product_url and source_url and product_url == source_url
            same_name = product_name_key and source_name_key and (
                product_name_key == source_name_key
                or product_name_key in source_name_key
                or source_name_key in product_name_key
            )

            if same_url or same_name:
                if not product.get("image") and source.get("image"):
                    product["image"] = source["image"]

                if not product.get("url") and source.get("url"):
                    product["url"] = source["url"]

                if not product.get("price") and source.get("price"):
                    product["price"] = source["price"]

                if not product.get("why") and source.get("why"):
                    product["why"] = source["why"]

    return primary


def parse_agent_json(content: Any) -> Dict[str, Any]:
    text = content_to_text(content)
    cleaned_text = strip_json_code_fence(text)

    try:
        parsed = json.loads(cleaned_text)
        parsed["products"] = normalize_products(parsed.get("products", []))
        parsed["reply"] = clean_text(parsed.get("reply", "")) or "I found something for you."
        parsed["cart"] = parsed.get("cart", []) if isinstance(parsed.get("cart", []), list) else []
        parsed["checkout_url"] = clean_url(parsed.get("checkout_url"))
        parsed["quick_replies"] = (
            parsed.get("quick_replies", [])
            if isinstance(parsed.get("quick_replies", []), list)
            else []
        )
        return parsed
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            parsed["products"] = normalize_products(parsed.get("products", []))
            parsed["reply"] = clean_text(parsed.get("reply", "")) or "I found something for you."
            parsed["cart"] = parsed.get("cart", []) if isinstance(parsed.get("cart", []), list) else []
            parsed["checkout_url"] = clean_url(parsed.get("checkout_url"))
            parsed["quick_replies"] = (
                parsed.get("quick_replies", [])
                if isinstance(parsed.get("quick_replies", []), list)
                else []
            )
            return parsed
        except json.JSONDecodeError:
            pass

    products, spans = extract_products_from_markdown(cleaned_text)

    if products:
        reply = remove_markdown_product_blocks(cleaned_text, spans)

        if not reply:
            reply = "I found a few good options for you."

        return {
            "reply": reply,
            "products": products,
            "cart": [],
            "checkout_url": None,
            "quick_replies": [
                "Add to cart",
                "Need help with delivery",
                "Suggest a gift note",
            ],
        }

    return {
        "reply": clean_text(cleaned_text),
        "products": [],
        "cart": [],
        "checkout_url": None,
        "quick_replies": [],
    }


@app.on_event("startup")
async def startup_event():
    global agent

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")

    client = MultiServerMCPClient(MCP_SERVERS)
    tools = await client.get_tools()

    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.4,
    )

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )


@app.get("/")
def health():
    return {"status": "ok", "message": "Kapruka AI backend is running"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    global agent

    if agent is None:
        return ChatResponse(
            reply="Backend is still starting. Please try again.",
            products=[],
            cart=[],
            checkout_url=None,
            quick_replies=[],
        )

    session_id = req.session_id or "default"
    previous_messages = sessions.get(session_id, [])

    # Small hint to the agent when user explicitly asks for popular/best-selling items.
    user_message = req.message
    popularity_words = [
        "most sold",
        "best sold",
        "best-selling",
        "bestselling",
        "popular",
        "trending",
        "top selling",
        "top-rated",
    ]

    if any(word in req.message.lower() for word in popularity_words):
        user_message = (
            req.message
            + "\n\nImportant: The user is asking for popular or best-selling options. "
            "Use Kapruka search sort if available. If exact best-selling sort is not available, "
            "return strong relevant options and do not falsely claim they are confirmed best-sellers."
        )

    result = await agent.ainvoke(
        {
            "messages": previous_messages
            + [
                {
                    "role": "user",
                    "content": user_message,
                }
            ]
        }
    )

    sessions[session_id] = result["messages"]

    assistant_content = result["messages"][-1].content
    parsed = parse_agent_json(assistant_content)

    new_messages = result["messages"][len(previous_messages):] or result["messages"]

    mcp_products = extract_products_from_messages(new_messages)

    parsed["products"] = merge_product_images(
        parsed.get("products", []) or [],
        mcp_products,
    )

    parsed["reply"] = sanitize_reply_for_product_cards(
        parsed.get("reply", ""),
        parsed.get("products", []) or [],
    )

    checkout_url = (
        parsed.get("checkout_url")
        or extract_checkout_url_from_messages(new_messages)
        or extract_checkout_url_from_text(assistant_content)
    )

    checkout_url = clean_url(checkout_url)

    if checkout_url and checkout_url.startswith("http") and not is_image_url(checkout_url):
        parsed["checkout_url"] = checkout_url
    else:
        parsed["checkout_url"] = None

    parsed["reply"] = sanitize_checkout_reply(
        parsed.get("reply", ""),
        parsed.get("checkout_url"),
    )

    if parsed.get("checkout_url"):
        parsed["quick_replies"] = [
            "Start a new cart",
            "Track this order",
            "Need help with delivery",
        ]
    elif parsed.get("products") and not parsed.get("quick_replies"):
        parsed["quick_replies"] = [
            "Add one to cart",
            "Need help with delivery",
            "Suggest a gift note",
        ]
    elif (
        "order reference" in parsed.get("reply", "").lower()
        or "order has been successfully created" in parsed.get("reply", "").lower()
    ):
        parsed["quick_replies"] = [
            "Try checkout link again",
            "Start a new cart",
            "Need help",
        ]

    print("PRODUCTS SENT TO FRONTEND:")
    print(json.dumps(parsed.get("products", []), indent=2, ensure_ascii=False)[:5000])

    print("CHECKOUT URL SENT TO FRONTEND:")
    print(parsed.get("checkout_url"))

    print("CLEAN REPLY SENT TO FRONTEND:")
    print(parsed.get("reply", ""))

    return ChatResponse(
        reply=parsed.get("reply", "I found something for you."),
        products=parsed.get("products", []) or [],
        cart=parsed.get("cart", []) or [],
        checkout_url=parsed.get("checkout_url"),
        quick_replies=parsed.get("quick_replies", []) or [],
    )