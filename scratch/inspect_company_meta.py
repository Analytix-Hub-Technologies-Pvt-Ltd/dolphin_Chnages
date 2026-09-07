import json

metas = json.load(open("retrieval/company_index.meta.json", "r", encoding="utf-8"))
print(f"Total company chunks: {len(metas)}")

centrifugal_chunks = []
cargo_pump_chunks = []

for idx, m in enumerate(metas):
    content = m.get("content", "")
    if "centrifugal" in content.lower():
        centrifugal_chunks.append((idx, m))
    if "cargo pump operation" in content.lower():
        cargo_pump_chunks.append((idx, m))

print(f"Centrifugal chunks: {len(centrifugal_chunks)}")
for idx, c in centrifugal_chunks:
    print(f"Idx: {idx}, chunk_index: {c.get('chunk_index')}, Doc: {c.get('document_title')}")
    print(f"Snippet: {c.get('content')[:300]}")
    print("=" * 50)

print(f"Cargo pump chunks count: {len(cargo_pump_chunks)}")
for idx, c in cargo_pump_chunks[:2]:
    print(f"Idx: {idx}, chunk_index: {c.get('chunk_index')}, Doc: {c.get('document_title')}")
    print(f"Snippet: {c.get('content')[:300]}")
    print("=" * 50)
