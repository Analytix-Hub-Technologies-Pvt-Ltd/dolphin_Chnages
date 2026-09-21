# tests/quick_test.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def quick_test():
    """Quick test to verify the fix works"""
    from services.openai_service import OpenAIService
    
    print("🚀 Quick Test: OpenAI Embedding Fix")
    
    service = OpenAIService()
    
    # Test the problematic case from the logs
    test_input = [0.013956458307802677, 0.006552327889949083, 0.058918531984090805]  # This was causing the error
    
    print(f"🧪 Testing with problematic input: {type(test_input)}")
    
    try:
        result = await service.embed(test_input)
        print(f"✅ SUCCESS! Embedding generated: {len(result)} dimensions")
        print("🎉 The fix is working!")
    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(quick_test())