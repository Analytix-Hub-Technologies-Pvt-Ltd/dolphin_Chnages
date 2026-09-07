import asyncio
import json
import sys
sys.path.insert(0, ".")
from models.database import get_pool
from pipeline.retrieval import search_matching_images_in_db, extract_images
from services.image_manager import ImageManager

async def check():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT content_id, topic_name, topic_image 
            FROM course_content 
            WHERE topic_image IS NOT NULL 
              AND topic_image::text != '[]' 
              AND topic_image::text != '"[]"' 
            LIMIT 10
        """)
        print(f"Total rows with topic_image: {len(rows)}")
        for r in rows:
            print(f"Topic: {r['topic_name']}")
            print(f"Images: {r['topic_image']}")
            print("-" * 40)

        # Check firefighting images
        fire_rows = await conn.fetch("""
            SELECT content_id, topic_name, topic_image 
            FROM course_content 
            WHERE (topic_name ILIKE '%fire%' OR topic_content ILIKE '%fire%')
              AND topic_image IS NOT NULL 
              AND topic_image::text != '[]' 
              AND topic_image::text != '"[]"' 
            LIMIT 10
        """)
        print(f"\nFirefighting rows with topic_image: {len(fire_rows)}")
        for r in fire_rows:
            print(f"Topic: {r['topic_name']}")
            print(f"Images: {r['topic_image']}")
            print("-" * 40)

    imgs = await search_matching_images_in_db("firefighting")
    print("\nsearch_matching_images_in_db('firefighting'):")
    print(json.dumps(imgs, indent=2))

    processed = await ImageManager.process_and_cache_images(imgs)
    print("\nProcessed images:")
    for p in processed:
        print(f"ID: {p.get('id')}, Title: {p.get('title')}, URL: {p.get('url')}, HasBase64: {bool(p.get('base64'))}")

if __name__ == "__main__":
    asyncio.run(check())
