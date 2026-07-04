"""Test FX rate fetching."""
import asyncio
from app.services import fx

async def main():
    print("\n=== Testing FX Rate Fetch ===\n")
    
    try:
        print("Fetching USD to NGN rate from open.er-api.com...")
        rate = await fx.get_usd_to_ngn()
        
        print(f"✓ Success!")
        print(f"  Rate: 1 USD = ₦{rate.rate}")
        print(f"  Source: {rate.source}")
        print(f"  Fetched at: {rate.fetched_at}")
        
        # Test conversion
        test_usd = 0.001
        test_ngn = test_usd * rate.rate
        test_kobo = int(test_ngn * 100)
        
        print(f"\n=== Test Conversion ===")
        print(f"  ${test_usd} USD")
        print(f"  = ₦{test_ngn:.4f} NGN")
        print(f"  = {test_kobo} kobo")
        
    except Exception as e:
        print(f"✗ Error fetching FX rate:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
