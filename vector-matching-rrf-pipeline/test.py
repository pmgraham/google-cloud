import asyncio
from httpx import AsyncClient
from ui.main import app

async def main():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/matches")
        print("GET matches", response.status_code, response.text)
        response = await ac.post("/api/decide", json={
            "customer_part_number":"CPN",
            "supplier_part_number":"SPN",
            "decision":"ACCEPTED",
            "is_match":True,
            "reasoning":"test"
        })
        print("POST decide", response.status_code, response.text)

asyncio.run(main())
