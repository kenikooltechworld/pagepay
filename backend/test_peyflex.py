"""Test Peyflex API — try multiple formats."""
import asyncio
import httpx
import sys

async def test():
    key = "013a12a05d233457dd51302fee5109436d3a24b8"

    async with httpx.AsyncClient(timeout=15) as client:
        # Try 1: curl exact format from docs — GET with format=json param
        print("=== Test: GET with format=json ===")
        try:
            resp = await client.get(
                "https://client.peyflex.com.ng/api/v1/airtime",
                params={"format": "json", "phone": "08069744462", "amount": 100, "network": "mtn"},
                headers={
                    "Authorization": f"Token {key}",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        # Try 2: With referer + origin
        print("\n=== Test: With referer + origin ===")
        try:
            resp = await client.post(
                "https://client.peyflex.com.ng/api/v1/airtime",
                json={"phone": "08069744462", "amount": 100, "network": "mtn"},
                headers={
                    "Authorization": f"Token {key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": "https://client.peyflex.com.ng",
                    "Referer": "https://client.peyflex.com.ng/",
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        # Try 3: Direct curl style - query params + no body
        print("\n=== Test: Curl-style POST with query params ===")
        try:
            resp = await client.post(
                "https://client.peyflex.com.ng/api/v1/airtime",
                data="format=json&phone=08069744462&amount=100&network=mtn",
                headers={
                    "Authorization": f"Token {key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
    sys.stdout.flush()
