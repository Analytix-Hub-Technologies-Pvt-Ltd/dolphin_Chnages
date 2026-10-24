# services/stream_extractor.py
import re
from typing import List, Tuple, Any

class StreamJsonExtractor:
    """
    Incrementally extracts markdown content tokens from an OpenAI streaming JSON response.
    Expected schema:
    {
      "sections": [
        {
          "topic_code": "...",
          "topic_name": "...",
          "content": "..."
        }
      ],
      "suggestions": [...]
    }
    
    Yields events in real-time:
    - ('topic', topic_code, topic_name, section_count)
    - ('token', text)
    """
    def __init__(self):
        self.state = 'FIND_FIELD'
        self.buffer = ''
        self.escape = False
        self.unicode_escape = False
        self.unicode_chars: List[str] = []
        self.current_topic_code = ""
        self.current_topic_name = ""
        self.section_count = 0
        self.total_tokens_emitted = 0
        self.in_lead_check = False
        self.lead_token_buf: List[str] = []

    def _emit_token(self, text: str, events: List[Tuple[str, Any]]):
        if not text:
            return
        if self.in_lead_check:
            self.lead_token_buf.append(text)
            current_lead = "".join(self.lead_token_buf)
            if '\n' in current_lead or len(current_lead) >= 45:
                # Strip robotic "Core Definition & Principle" label if present
                clean_lead = re.sub(
                    r'(?i)^\s*[-*#]*\s*(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*\n*',
                    '',
                    current_lead
                )
                self.in_lead_check = False
                self.lead_token_buf = []
                if clean_lead:
                    events.append(('token', clean_lead))
                    self.total_tokens_emitted += len(clean_lead)
        else:
            events.append(('token', text))
            self.total_tokens_emitted += len(text)

    def feed(self, chunk: str) -> List[Tuple[str, Any]]:
        events = []
        for char in chunk:
            if self.state == 'FIND_FIELD':
                self.buffer += char
                # Check for topic_name
                m_name = re.search(r'"topic_name"\s*:\s*"([^"]*)"', self.buffer)
                if m_name and not self.current_topic_name:
                    self.current_topic_name = m_name.group(1)

                # Check for topic_code
                m_code = re.search(r'"topic_code"\s*:\s*"([^"]*)"', self.buffer)
                if m_code and not self.current_topic_code:
                    self.current_topic_code = m_code.group(1)

                # Check for content start
                m_cont = re.search(r'"content"\s*:\s*"', self.buffer)
                if m_cont:
                    self.state = 'IN_CONTENT'
                    self.buffer = ''
                    self.section_count += 1
                    self.in_lead_check = True
                    self.lead_token_buf = []
                    events.append(('topic', self.current_topic_code, self.current_topic_name, self.section_count))

            elif self.state == 'IN_CONTENT':
                if self.unicode_escape:
                    self.unicode_chars.append(char)
                    if len(self.unicode_chars) == 4:
                        try:
                            uni_char = chr(int("".join(self.unicode_chars), 16))
                            self._emit_token(uni_char, events)
                        except Exception:
                            fallback_str = "\\u" + "".join(self.unicode_chars)
                            self._emit_token(fallback_str, events)
                        self.unicode_escape = False
                        self.unicode_chars = []
                elif self.escape:
                    if char == 'n':
                        self._emit_token('\n', events)
                    elif char == 't':
                        self._emit_token('\t', events)
                    elif char == '"':
                        self._emit_token('"', events)
                    elif char == '\\':
                        self._emit_token('\\', events)
                    elif char == 'r':
                        self._emit_token('\r', events)
                    elif char == '/':
                        self._emit_token('/', events)
                    elif char == 'u':
                        self.unicode_escape = True
                        self.unicode_chars = []
                    else:
                        self._emit_token(char, events)
                    self.escape = False
                elif char == '\\':
                    self.escape = True
                elif char == '"':
                    if self.in_lead_check and self.lead_token_buf:
                        current_lead = "".join(self.lead_token_buf)
                        clean_lead = re.sub(
                            r'(?i)^\s*[-*#]*\s*(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*\n*',
                            '',
                            current_lead
                        )
                        self.in_lead_check = False
                        self.lead_token_buf = []
                        if clean_lead:
                            events.append(('token', clean_lead))
                            self.total_tokens_emitted += len(clean_lead)
                    self.state = 'FIND_FIELD'
                    self.buffer = ''
                    self.current_topic_code = ""
                    self.current_topic_name = ""
                else:
                    self._emit_token(char, events)

        # Merge consecutive token events to minimize queue overhead
        merged_events: List[Tuple[str, Any]] = []
        token_acc: List[str] = []
        for ev in events:
            if ev[0] == 'token':
                token_acc.append(ev[1])
            else:
                if token_acc:
                    merged_events.append(('token', "".join(token_acc)))
                    token_acc = []
                merged_events.append(ev)
        if token_acc:
            merged_events.append(('token', "".join(token_acc)))

        return merged_events
