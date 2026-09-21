# pipeline/stream_utils.py
import re
from typing import List, Optional

class JsonStreamContentExtractor:
    """
    Incrementally extracts user-facing Markdown text from streaming LLM output.
    
    Supports:
    - Structured JSON output containing "sections": [{"content": "..."}, ...]
    - Handles escaped characters (\\n, \\", \\\\, \\t, \\r, unicode escapes) across chunk boundaries
    - Multiple sections with natural markdown spacing
    - Gracefully handles non-JSON output (raw Markdown) if the LLM responds without JSON braces
    """
    def __init__(self):
        self.buffer = ""
        self.in_content = False
        self.is_json: Optional[bool] = None  # None = undecided, True = JSON, False = raw Markdown
        self.escape_pending = ""
        self.section_count = 0

    def process_chunk(self, chunk: str) -> List[str]:
        if not chunk:
            return []

        self.buffer += chunk
        emitted_tokens: List[str] = []

        # Determine if output is JSON or raw Markdown
        if self.is_json is None:
            stripped = self.buffer.strip()
            if not stripped:
                return []
            if stripped.startswith("{") or stripped.startswith("```json") or stripped.startswith("```"):
                self.is_json = True
            else:
                self.is_json = False
                # If decided as raw markdown, return the accumulated buffer immediately
                return [self.buffer]

        if not self.is_json:
            # Raw markdown stream: return chunk directly
            return [chunk]

        # Process buffer for JSON content
        while True:
            if not self.in_content:
                # Match "content"\s*:\s*"
                match = re.search(r'"content"\s*:\s*"', self.buffer)
                if match:
                    start_idx = match.end()
                    self.buffer = self.buffer[start_idx:]
                    self.in_content = True
                    self.section_count += 1
                    if self.section_count > 1:
                        emitted_tokens.append("\n\n")
                else:
                    # Keep only last 40 chars in buffer in case '"content": "' is split across chunk boundaries
                    if len(self.buffer) > 50:
                        self.buffer = self.buffer[-40:]
                    break

            if self.in_content:
                i = 0
                out_chars: List[str] = []
                while i < len(self.buffer):
                    char = self.buffer[i]

                    if self.escape_pending:
                        esc_char = self.escape_pending + char
                        self.escape_pending = ""
                        if esc_char == r"\n":
                            out_chars.append("\n")
                        elif esc_char == r"\"":
                            out_chars.append('"')
                        elif esc_char == r"\\":
                            out_chars.append("\\")
                        elif esc_char == r"\t":
                            out_chars.append("\t")
                        elif esc_char == r"\r":
                            out_chars.append("\r")
                        else:
                            out_chars.append(char)
                        i += 1
                        continue

                    if char == "\\":
                        if i + 1 < len(self.buffer):
                            next_char = self.buffer[i + 1]
                            if next_char == "n":
                                out_chars.append("\n")
                            elif next_char == '"':
                                out_chars.append('"')
                            elif next_char == "\\":
                                out_chars.append("\\")
                            elif next_char == "t":
                                out_chars.append("\t")
                            elif next_char == "r":
                                out_chars.append("\r")
                            elif next_char == "u":
                                if i + 5 < len(self.buffer):
                                    try:
                                        code = int(self.buffer[i + 2:i + 6], 16)
                                        out_chars.append(chr(code))
                                        i += 6
                                        continue
                                    except ValueError:
                                        out_chars.append(self.buffer[i:i + 6])
                                        i += 6
                                        continue
                                else:
                                    # Incomplete unicode escape, wait for next chunk
                                    break
                            else:
                                out_chars.append(next_char)
                            i += 2
                            continue
                        else:
                            # Backslash is at end of buffer, hold for next chunk
                            self.escape_pending = "\\"
                            i += 1
                            break
                    elif char == '"':
                        # Closing quote for this content field
                        self.in_content = False
                        self.buffer = self.buffer[i + 1:]
                        if out_chars:
                            emitted_tokens.append("".join(out_chars))
                            out_chars = []
                        break
                    else:
                        out_chars.append(char)
                        i += 1

                if self.in_content:
                    if out_chars:
                        emitted_tokens.append("".join(out_chars))
                    self.buffer = self.buffer[i:]
                    break

        return emitted_tokens
