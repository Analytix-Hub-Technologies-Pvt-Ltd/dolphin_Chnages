from __future__ import annotations

import re
from typing import List


class TTSNormalizer:
    """
    Dedicated normalization layer to convert raw Dolphin AI Markdown/RAG responses
    into clean, natural, TTS-friendly spoken sentences.

    Crucial Rules:
    - Never read markdown syntax ('pipe', 'dash', 'hash', 'asterisk', 'bracket').
    - Convert tables into conversational, grammatically clear sentences.
    - Remove citation brackets, raw URLs, and formatting artefacts.
    - Split into natural sentence chunks for streaming synthesis.
    - Do NOT alter the visual response shown to the user.
    """

    @staticmethod
    def _clean_table_to_speech(table_text: str) -> str:
        """
        Convert Markdown table into natural spoken sentences.
        """
        lines = [l.strip() for l in table_text.strip().splitlines() if l.strip()]
        if not lines:
            return ""

        # Filter out separator rows like |---|---|
        rows = []
        for line in lines:
            if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", line):
                continue
            if line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line[1:-1].split("|")]
                if any(cells):
                    rows.append(cells)

        if not rows:
            return ""

        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        if not data_rows:
            return ". ".join(" ".join(r) for r in rows) + "."

        speech_sentences = []
        is_two_column = len(headers) == 2

        for row in data_rows:
            if not any(row):
                continue

            if is_two_column:
                item_name = row[0] if len(row) > 0 else ""
                val = row[1] if len(row) > 1 else ""
                val_lower = val.lower().strip()

                if not item_name:
                    continue

                if val_lower in {"yes", "required", "true", "mandatory"}:
                    speech_sentences.append(f"{item_name} is required.")
                elif val_lower in {"no", "optional", "false", "not required", "n/a", "none"}:
                    speech_sentences.append(f"{item_name} is not required.")
                elif val:
                    speech_sentences.append(f"{item_name}: {val}.")
                else:
                    speech_sentences.append(f"{item_name}.")
            else:
                # Multi-column table: pair each cell with header
                row_parts = []
                for i, cell in enumerate(row):
                    if not cell:
                        continue
                    header = headers[i] if i < len(headers) and headers[i] else ""
                    val_lower = cell.lower().strip()

                    if header:
                        if val_lower in {"yes", "required", "true", "mandatory"}:
                            row_parts.append(f"{header} is required")
                        elif val_lower in {"no", "optional", "false", "not required"}:
                            row_parts.append(f"{header} is not required")
                        else:
                            row_parts.append(f"{header}: {cell}")
                    else:
                        row_parts.append(cell)

                if row_parts:
                    speech_sentences.append(", ".join(row_parts) + ".")

        return " ".join(speech_sentences)

    @classmethod
    def normalize_for_tts(cls, text: str) -> str:
        """
        Transforms raw Dolphin AI markdown text into speech-optimized plain text.
        """
        if not text or not isinstance(text, str):
            return ""

        content = text.strip()

        # 1. Convert Markdown tables to spoken text
        # Regex to capture markdown tables
        table_pattern = re.compile(
            r"(?:(?:^|\n)\|[^\n]+\|\r?\n(?:\|(?:\s*:?-+:?\s*\|)+\r?\n)(?:\|[^\n]+\|\r?\n?)+)",
            re.MULTILINE
        )
        content = table_pattern.sub(lambda m: "\n" + cls._clean_table_to_speech(m.group(0)) + "\n", content)

        # 2. Strip code blocks ```...```
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"`([^`]+)`", r"\1", content)

        # 3. Clean citations, doc tags, topic codes: e.g. [Doc: Safety Manual], [Topic: 123], [1]
        content = re.sub(r"\[(?:Doc|Document|Source|Topic|Section|Ref|Citation)?:?\s*([^\]]+)\]\([^\)]*\)", r"\1", content)
        content = re.sub(r"\[(?:Doc|Document|Source|Topic|Section|Ref|Citation)?:?\s*([^\]]+)\]", r"\1", content)
        content = re.sub(r"\[\d+\]", "", content)

        # 4. Clean Markdown links [Anchor Text](http...) -> Anchor Text
        content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)
        # Strip raw URLs
        content = re.sub(r"https?://\S+", "", content)

        # 5. Clean Markdown headers (# Heading -> Heading.)
        content = re.sub(r"^#{1,6}\s*(.+)$", r"\1.", content, flags=re.MULTILINE)

        # 6. Clean bold and italic markdown
        content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        content = re.sub(r"\*([^*]+)\*", r"\1", content)
        content = re.sub(r"__([^_]+)__", r"\1", content)
        content = re.sub(r"_([^_]+)_", r"\1", content)
        content = re.sub(r"~~([^~]+)~~", r"\1", content)

        # 7. Clean bullet points and list markers (* , - , + , 1. ) -> Natural sentence breaks
        content = re.sub(r"^\s*[\*\-\+]\s+", "", content, flags=re.MULTILINE)
        content = re.sub(r"^\s*\d+\.\s+", "", content, flags=re.MULTILINE)

        # 8. Clean HTML tags
        content = re.sub(r"<[^>]+>", "", content)

        # 9. Clean special symbols & expand abbreviations for clear pronunciation
        content = content.replace("&", " and ")
        content = content.replace("@", " at ")
        content = content.replace("%", " percent ")
        content = content.replace("°C", " degrees Celsius ")
        content = content.replace("°F", " degrees Fahrenheit ")
        content = content.replace("°", " degrees ")
        content = content.replace("≥", " greater than or equal to ")
        content = content.replace("≤", " less than or equal to ")
        content = content.replace(">", " greater than ")
        content = content.replace("<", " less than ")
        content = content.replace("=", " equals ")
        content = content.replace("/", " / ")

        # 10. Clean leftover markdown artifacts (pipes, excessive dashes, underscores)
        content = re.sub(r"[\|_~]", " ", content)
        content = re.sub(r"-{2,}", " ", content)

        # 11. Normalize whitespace & line breaks
        content = re.sub(r"\s+", " ", content).strip()

        # 12. Fix repetitive punctuation (e.g. "..", "!!", "??", ".,")
        content = re.sub(r"\.+", ".", content)
        content = re.sub(r"\s+([.,!?:;])", r"\1", content)

        return content

    @classmethod
    def split_into_tts_sentences(cls, text: str, max_chunk_words: int = 35) -> List[str]:
        """
        Splits normalized text into natural, punctuated sentence chunks for real-time streaming TTS.
        Ensures chunks do not break in the middle of words or ideas.
        """
        normalized = cls.normalize_for_tts(text)
        if not normalized:
            return []

        # Sentence boundary split regex (. ! ?)
        raw_sentences = re.split(r"(?<=[.!?])\s+", normalized)
        chunks: List[str] = []

        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            words = s_clean.split()
            # If sentence is within normal length, keep as is
            if len(words) <= max_chunk_words:
                chunks.append(s_clean)
            else:
                # Sub-split long sentences at clauses (comma, semicolon, colon, conjunctions)
                sub_parts = re.split(r"(?<=[,;:])\s+", s_clean)
                cur_chunk: List[str] = []
                cur_len = 0

                for part in sub_parts:
                    p_words = part.split()
                    if cur_len + len(p_words) <= max_chunk_words:
                        cur_chunk.append(part)
                        cur_len += len(p_words)
                    else:
                        if cur_chunk:
                            chunks.append(" ".join(cur_chunk))
                        cur_chunk = [part]
                        cur_len = len(p_words)

                if cur_chunk:
                    chunks.append(" ".join(cur_chunk))

        return chunks
