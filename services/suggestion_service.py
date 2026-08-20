from __future__ import annotations

import random
import re
from typing import Dict, List


class SuggestionService:
    """Generate context-aware follow-up suggestions for the chat UI."""

    _STOPWORDS = {
        "the",
        "and",
        "or",
        "a",
        "an",
        "of",
        "for",
        "to",
        "in",
        "on",
        "about",
        "is",
        "are",
        "with",
        "at",
        "by",
        "from",
    }

    def _extract_keywords(self, query: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9]+", query.lower())
        keywords = [w for w in words if w not in self._STOPWORDS]
        # Preserve order but remove duplicates
        seen = set()
        unique_keywords: List[str] = []
        for word in keywords:
            if word in seen:
                continue
            seen.add(word)
            unique_keywords.append(word)
        return unique_keywords

    def generate(
        self,
        query: str,
        chunks: List[Dict],
        history: List[Dict],
        short_topic: str,
        category: str,
    ) -> List[str]:
        """Generate 2–3 marine question suggestions according to category rules."""

        category_normalized = (category or "").lower()
        chunks = chunks or []
        history = history or []

        def dedupe(items: List[str]) -> List[str]:
            seen = set()
            unique: List[str] = []
            for item in items:
                cleaned = re.sub(r"\s+", " ", item or "").strip()
                if not cleaned or cleaned.lower() in seen:
                    continue
                seen.add(cleaned.lower())
                if not cleaned.endswith("?"):
                    cleaned = f"{cleaned}?"
                unique.append(cleaned)
            return unique

        def word_count_within(question: str, low: int, high: int) -> bool:
            count = len(question.split())
            return low <= count <= high

        def collect_chunk_keywords(chunk_list: List[Dict]) -> List[str]:
            keywords: List[str] = []
            for chunk in chunk_list:
                raw_keywords = chunk.get("keywords")
                if isinstance(raw_keywords, str):
                    keywords.extend(self._extract_keywords(raw_keywords))
                elif isinstance(raw_keywords, list):
                    keywords.extend(self._extract_keywords(" ".join(map(str, raw_keywords))))
                else:
                    keywords.extend(
                        self._extract_keywords(
                            " ".join(
                                str(chunk.get(field, ""))
                                for field in ("title", "section", "topic")
                            )
                        )
                    )
            # Remove duplicates while preserving order
            seen_kw = set()
            ordered_keywords: List[str] = []
            for kw in keywords:
                if kw in seen_kw:
                    continue
                seen_kw.add(kw)
                ordered_keywords.append(kw)
            return ordered_keywords

        def previous_user_messages(msg_history: List[Dict]) -> List[str]:
            contents: List[str] = []
            for message in msg_history:
                if not isinstance(message, dict):
                    continue
                if (message.get("role") or message.get("author")) == "user" or message.get("node_type") in {"query", "summary"}:
                    content = str(message.get("content", "")).strip()
                    if content:
                        contents.append(content)
            return contents

        def build_llm_like_suggestions() -> List[str]:
            templates = [
                "How does {topic} aid navigation?",
                "What keeps {topic} safe at sea?",
                "Why is {topic} vital onboard?",
                "Where is {topic} used afloat?",
                "How to handle {topic} underway?",
            ]

            sources: List[List[str]] = []
            query_keywords = self._extract_keywords(query)
            if query_keywords:
                sources.append(query_keywords)

            topic_keywords = self._extract_keywords(short_topic)
            if topic_keywords:
                sources.append(topic_keywords)

            chunk_keywords = collect_chunk_keywords(chunks)
            if chunk_keywords:
                sources.append(chunk_keywords)

            for msg in reversed(previous_user_messages(history)):
                msg_keywords = self._extract_keywords(msg)
                if msg_keywords:
                    sources.append(msg_keywords)

            suggestions: List[str] = []
            for idx, keyword_group in enumerate(sources):
                if len(suggestions) >= 3:
                    break
                topic_phrase = " ".join(keyword_group[:2]).strip()
                if not topic_phrase:
                    continue
                template = templates[idx % len(templates)]
                question = template.format(topic=topic_phrase)
                if word_count_within(question, 5, 8):
                    suggestions.append(question)

            safe_pool = [
                "How does anchor scope aid navigation?",
                "Why is mooring line vital onboard?",
                "What keeps hull integrity safe at sea?",
            ]

            suggestions = dedupe(suggestions)

            for filler in safe_pool:
                if len(suggestions) >= 2:
                    break
                if filler not in suggestions:
                    suggestions.append(filler)

            return dedupe(suggestions)[:3]

        def build_chunk_based_suggestions() -> List[str]:
            chunk_pool: List[str] = []
            for chunk in chunks:
                title_or_topic = " ".join(
                    filter(
                        None,
                        [
                            str(chunk.get("title") or "").strip(),
                            str(chunk.get("section") or "").strip(),
                            str(chunk.get("topic") or "").strip(),
                        ],
                    )
                ).strip()
                keywords = collect_chunk_keywords([chunk]) or self._extract_keywords(title_or_topic)
                if not keywords and title_or_topic:
                    keywords = self._extract_keywords(title_or_topic)
                if keywords:
                    phrase = " ".join(keywords[:2])
                    chunk_pool.append(f"Learn about {phrase}?")
                elif title_or_topic:
                    chunk_pool.append(f"Explore {title_or_topic.split()[0]} basics?")

            random.shuffle(chunk_pool)

            fallback_short = [
                "Review anchor watch steps?",
                "Check marina docking tips?",
                "Study COLREGs crossing rules?",
                "Practice safe bilge checks?",
            ]

            if len(chunks) < 2:
                random.shuffle(fallback_short)
                chunk_pool.extend(fallback_short)

            chunk_pool = [q for q in chunk_pool if word_count_within(q, 3, 6)]
            chunk_pool = dedupe(chunk_pool)

            if len(chunk_pool) < 2:
                for filler in fallback_short:
                    if filler not in chunk_pool:
                        chunk_pool.append(filler)
                    if len(chunk_pool) >= 2:
                        break

            return chunk_pool[:3]

        if category_normalized == "quiz":
            return build_llm_like_suggestions()

        if category_normalized in {"greeting", "fallback"}:
            return build_chunk_based_suggestions()

        if category_normalized in {"query", "summary"}:
            return build_llm_like_suggestions()

        # Default to safe marine suggestions if category is unknown
        return dedupe([
            "How does anchor scope aid navigation?",
            "What keeps hull integrity safe at sea?",
        ])[:3]
