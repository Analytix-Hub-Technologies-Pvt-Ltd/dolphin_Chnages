import asyncio
import sys
sys.path.insert(0, ".")
from services.image_manager import ImageManager

async def test():
    # Test fetching an image that is not locally stored yet
    test_id = "024bdb22-a8e8-ec11-b844-00505682a06a"
    res = await ImageManager.fetch_and_cache_image(test_id)
    print(f"Fetched {test_id}: {bool(res)} (length: {len(res) if res else 0})")

    # Test an existing local image
    local_id = "01f629cf-33c5-e811-b80a-005056828eb6"
    res_local = await ImageManager.fetch_and_cache_image(local_id)
    print(f"Local {local_id}: {bool(res_local)} (length: {len(res_local) if res_local else 0})")

if __name__ == "__main__":
    asyncio.run(test())
