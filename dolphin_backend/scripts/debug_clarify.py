"""
Offline diagnostic for the "Did you mean...?" feature - no OpenAI / DB calls.

Usage (from the backend/ folder, same venv as the app):
    python scripts/debug_clarify.py temperature
    python scripts/debug_clarify.py SMS --show 25

It loads your FAISS metadata (the .bin / meta files the app uses), then prints:
  1. how many topics have the word in their NAME and in their TEXT,
  2. a simulated "top 10 retrieved" list (keyword-ranked approximation),
  3. what ClarificationService decides, with the options it would show.
"""
import argparse
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from services.clarification_service import ClarificationService, _stem_set, _stem, _tokens  # noqa: E402


def topic_of(meta):
    return str(meta.get("topic_name") or meta.get("title") or meta.get("Topic Name") or meta.get("name") or "").strip()


def body_of(meta):
    return str(meta.get("topic_content") or meta.get("content") or meta.get("text") or "")


def analyse(term, metadata, show=15, top_k=10):
    svc = ClarificationService(openai_service=None, use_llm=False)
    stems = [_stem(t) for t in _tokens(term)]

    name_hits, body_hits = {}, {}
    for m in metadata:
        if not isinstance(m, dict):
            continue
        name = topic_of(m)
        if not name:
            continue
        if all(s in _stem_set(name) for s in stems):
            name_hits[name] = m
        elif all(s in _stem_set(body_of(m)) for s in stems):
            body_hits[name] = m

    print(f"\nTerm: {term!r}   stems={stems}")
    print(f"Topics in index (unique names): {len({topic_of(m) for m in metadata if isinstance(m, dict)})}")
    print(f"Topics with the word in the NAME : {len(name_hits)}")
    for n in list(name_hits)[:show]:
        print(f"   - {n}")
    print(f"Topics with the word only in TEXT: {len(body_hits)}")
    for n in list(body_hits)[:show]:
        print(f"   - {n}")

    # crude retrieval stand-in: name hits first, then text hits ranked by occurrences
    def occurrences(m):
        return sum(1 for t in _tokens(body_of(m)) if _stem(t) in stems)
    ranked = list(name_hits.values()) + sorted(body_hits.values(), key=occurrences, reverse=True)
    chunks = [
        {"topic_name": topic_of(m), "topic_code": str(m.get("topic_code") or ""), "topic_content": body_of(m)}
        for m in ranked[:top_k]
    ]
    print(f"\nSimulated retrieval (top {len(chunks)}): {[c['topic_name'] for c in chunks]}")

    all_names = list({topic_of(m) for m in metadata if isinstance(m, dict) and topic_of(m)})
    clar = asyncio.run(svc.maybe_clarify(term, chunks, all_names))
    print("\nDECISION:", "ASK the user" if clar else "ANSWER directly (not ambiguous)")
    if clar:
        print(clar.render_text())
        print("\nButtons:", [o.label for o in clar.options])
    else:
        print("Reason: see the [CLARIFY] log lines above (fewer than 2 distinct matching topics, "
              "or the query is not a bare term).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term", nargs="+", help="Term or phrase to test")
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()

    from retrieval.faiss_store import FAISSStore
    store = FAISSStore()
    store.load()
    if not store.id_to_metadata:
        print("No metadata loaded - check FAISS_INDEX_PATH / the meta file path in retrieval/faiss_store.py")
        return
    term = " ".join(args.term) if isinstance(args.term, list) else args.term
    analyse(term, store.id_to_metadata, show=args.show)


if __name__ == "__main__":
    main()
