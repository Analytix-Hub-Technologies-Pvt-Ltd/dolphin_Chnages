from services.stream_extractor import StreamJsonExtractor

def test_stream_json_extractor_suppresses_core_definition():
    ext = StreamJsonExtractor()
    chunk1 = '{"sections": [{"topic_name": "EGCS", "content": "Core Definition & Principle:\\nAn EGCS is a scrubber system."}]}'
    events = ext.feed(chunk1)
    tokens = [ev[1] for ev in events if ev[0] == 'token']
    full_text = "".join(tokens)
    assert "Core Definition" not in full_text
    assert "Principle" not in full_text
    assert "An EGCS is a scrubber system." in full_text

def test_stream_json_extractor_normal_content():
    ext = StreamJsonExtractor()
    chunk1 = '{"sections": [{"topic_name": "ECDIS", "content": "Electronic Chart Display and Information System is essential."}]}'
    events = ext.feed(chunk1)
    tokens = [ev[1] for ev in events if ev[0] == 'token']
    full_text = "".join(tokens)
    assert full_text == "Electronic Chart Display and Information System is essential."
