import asyncio
import json
import redis.asyncio as redis


# async def test_redis():
#     r = redis.from_url("redis://localhost:6379", decode_responses=True)

#     session_id = "bfb99271-006c-424a-9ec5-0b3ebf3f6fe1"
#     key = f"session_cache:{session_id}"

#     data = await r.get(key)

#     if data:
#         messages = json.loads(data)

#         print("\n✅ ===== REDIS DATA =====")
#         print(f"📊 Total messages: {len(messages)}\n")

#         for i, msg in enumerate(messages, start=1):
#             role = msg.get("role", "unknown")
#             content = msg.get("content", "")
#             category = msg.get("category", "")
#             timestamp = msg.get("timestamp", "")

#             # trim long content
#             short_content = content[:80] + "..." if len(content) > 80 else content

#             print(f"{i}. 👤 Role      : {role}")
#             print(f"   📂 Category : {category}")
#             print(f"   ⏰ Time     : {timestamp}")
#             print(f"   💬 Content  : {short_content}")
#             print("-" * 50)

#     else:
#         print("❌ No data found in Redis")

#     # ✅ FIX (no warning)
#     await r.aclose()




async def debug_redis():
    r = redis.from_url("redis://localhost:6379", decode_responses=True)

    # -----------------------------
    # 🔹 INPUT USER ID
    # -----------------------------
    user_id = "bfaba271-44a6-42a9-b831-bf92b98ca775"

    print("\n🚀 ===== REDIS DEBUG START =====\n")

    # -----------------------------
    # 🔹 1. USER DATA
    # -----------------------------
    print("👤 ===== USER DATA =====")

    user_key = f"user:{user_id}"
    user_data = await r.get(user_key)

    if user_data:
        try:
            parsed_user = json.loads(user_data)
            print("✅ User found:")
            print(json.dumps(parsed_user, indent=2))
        except json.JSONDecodeError:
            print("⚠️ Raw user data:", user_data)
    else:
        print("❌ No user data found")

    print("\n" + "=" * 60 + "\n")

    # -----------------------------
    # 🔹 2. ACTIVE SESSION
    # -----------------------------
    print("🧠 ===== ACTIVE SESSION =====")

    active_session = await r.get(f"active_session:{user_id}")

    if active_session:
        print(f"✅ Active session: {active_session}")
        session_id = active_session  # ✅ FIX (use correct session)
    else:
        print("❌ No active session found")
        await r.aclose()
        return

    print("\n" + "=" * 60 + "\n")

    # -----------------------------
    # 🔹 3. SESSION MESSAGES
    # -----------------------------
    print("💬 ===== SESSION MESSAGES =====")

    key = f"session_cache:{session_id}"
    data = await r.get(key)

    if data:
        print("\n🧾 ===== RAW REDIS STRING =====\n")
        print(data)

        # try:
        #     messages = json.loads(data)
        # except json.JSONDecodeError:
        #     print("\n❌ Failed to parse Redis data as JSON")
        #     await r.aclose()
        #     return

        # print("\n✅ ===== PARSED REDIS DATA =====")
        # print(f"📊 Total messages: {len(messages)}\n")

        # for i, msg in enumerate(messages, start=1):
        #     role = msg.get("role", "unknown")
        #     content = msg.get("content", "")
        #     category = msg.get("category", "")
        #     timestamp = msg.get("timestamp", "")

        #     # Pretty print content if JSON
        #     try:
        #         parsed_content = json.loads(content)
        #         pretty_content = json.dumps(parsed_content, indent=2)
        #     except (json.JSONDecodeError, TypeError):
        #         pretty_content = content

        #     print(f"{i}. 👤 Role      : {role}")
        #     print(f"   📂 Category : {category}")
        #     print(f"   ⏰ Time     : {timestamp}")
        #     print("   💬 Content  :")
        #     print(pretty_content)
        #     print("-" * 60)

    else:
        print("❌ No session messages found")
        print("👉 Make sure you called CHAT API at least once!")

    print("\n" + "=" * 60 + "\n")

    # -----------------------------
    # 🔹 4. DEBUG ALL KEYS (optional)
    # -----------------------------
    print("🔑 ===== ALL REDIS KEYS =====")

    keys = await r.keys("*")
    for k in keys:
        print(k)

    print("\n✅ ===== REDIS DEBUG END =====\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(debug_redis())