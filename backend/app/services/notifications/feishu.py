from __future__ import annotations

import httpx


async def send_feishu(webhook_url: str, text: str) -> None:
    if not webhook_url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(webhook_url, json={"msg_type": "text", "content": {"text": text}})

