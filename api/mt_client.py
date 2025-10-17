import httpx, asyncio

class MTClient:
    def __init__(self, base_url: str):
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10)

    async def fast(self, text: str, src: str, tgt: str) -> str:
        r = await self.client.post("/translate/fast", json={"text": text, "src": src, "tgt": tgt})
        r.raise_for_status(); return r.json()["text"]

    async def final(self, text: str, src: str, tgt: str) -> str:
        r = await self.client.post("/translate/final", json={"text": text, "src": src, "tgt": tgt})
        r.raise_for_status(); return r.json()["text"]
