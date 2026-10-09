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
                    events.append(('topic', self.current_topic_code, self.current_topic_name, self.section_count))

            elif self.state == 'IN_CONTENT':
                if self.unicode_escape:
                    self.unicode_chars.append(char)
                    if len(self.unicode_chars) == 4:
                        try:
                            uni_char = chr(int("".join(self.unicode_chars), 16))
                            events.append(('token', uni_char))
                            self.total_tokens_emitted += 1
                        except Exception:
                            fallback_str = "\\u" + "".join(self.unicode_chars)
                            events.append(('token', fallback_str))
                            self.total_tokens_emitted += 1
                        self.unicode_escape = False
                        self.unicode_chars = []
                elif self.escape:
                    if char == 'n':
                        events.append(('token', '\n'))
                    elif char == 't':
                        events.append(('token', '\t'))
                    elif char == '"':
                        events.append(('token', '"'))
                    elif char == '\\':
                        events.append(('token', '\\'))
                    elif char == 'r':
                        events.append(('token', '\r'))
                    elif char == '/':
                        events.append(('token', '/'))
                    elif char == 'u':
                        self.unicode_escape = True
                        self.unicode_chars = []
                    else:
                        events.append(('token', char))
                    self.total_tokens_emitted += 1
                    self.escape = False
                elif char == '\\':
                    self.escape = True
                elif char == '"':
                    self.state = 'FIND_FIELD'
                    self.buffer = ''
                    self.current_topic_code = ""
                    self.current_topic_name = ""
                else:
                    events.append(('token', char))
                    self.total_tokens_emitted += 1

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
