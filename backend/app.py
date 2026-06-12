import os
import json
import re
from typing import Any, Dict, List, Optional

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
You should feel warm, helpful, slightly witty, and locally aware.

Support:
- Everyday self-shopping: groceries, electronics, fashion, home items, daily essentials.
- Gift mode: birthdays, apologies, breakups, anniversaries, family events.
- Sinhala, English, and Tanglish when the user uses them.
- Multi-item carts.
- Delivery-date handling.
- Gift note suggestions.

Important behavior:
- Ask only the next most useful question.
- Recommend products with a reason.
- If the user is emotional, respond kindly and practically.
- If product search is needed, use Kapruka tools.
- If delivery or checkout is needed, use Kapruka tools.
- Do not invent product details. Use tools.

Always respond as STRICT JSON only.

Use this shape:
{
  "reply": "friendly assistant reply",
  "products": [
    {
      "id": "product id if available",
      "name": "product name",
      "price": "price if available",
      "image": "image url if available",
      "url": "product url if available",
      "why": "short reason why this product fits",
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


def parse_agent_json(content: Any) -> Dict[str, Any]:
    if not isinstance(content, str):
        content = str(content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {
        "reply": content,
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

    result = await agent.ainvoke(
        {
            "messages": previous_messages
            + [
                {
                    "role": "user",
                    "content": req.message,
                }
            ]
        }
    )

    sessions[session_id] = result["messages"]

    assistant_content = result["messages"][-1].content
    parsed = parse_agent_json(assistant_content)

    return ChatResponse(
        reply=parsed.get("reply", "I found something for you."),
        products=parsed.get("products", []) or [],
        cart=parsed.get("cart", []) or [],
        checkout_url=parsed.get("checkout_url"),
        quick_replies=parsed.get("quick_replies", []) or [],
    )