import json
import re

with open('retrieval/company_index.meta.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total chunks: {len(data)}")

# Search for section heading patterns in data
section_patterns = [
    r'^(?:Section\s+\d+|Chapter\s+\d+|Clause\s+\d+|[I|V|X]+\.|\d+\.\d+(?:\.\d+)*)',
    r'^[A-Z0-9\.\s\-]{3,50}$',
]

def find_headings_in_chunk(text):
    headings = []
    for line in text.split('\n'):
        l = line.strip()
        if not l or len(l) > 100:
            continue
        if re.match(r'^(?:Section\s+\d+|Chapter\s+\d+|Clause\s+\d+|[I|V|X]+\.|\d+\.\d+(?:\.\d+)*)', l, re.IGNORECASE):
            headings.append(l)
    return headings

doc_sections = {}
for d in data:
    doc_id = d.get('document_id')
    doc_title = d.get('document_title')
    hdgs = find_headings_in_chunk(d.get('content', ''))
    if hdgs:
        if (doc_id, doc_title) not in doc_sections:
            doc_sections[(doc_id, doc_title)] = []
        doc_sections[(doc_id, doc_title)].extend(hdgs)

for (doc_id, doc_title), hdgs in list(doc_sections.items())[:5]:
    print(f"\nDocument {doc_id}: {doc_title}")
    unique_hdgs = list(dict.fromkeys(hdgs))[:10]
    for h in unique_hdgs:
        print(f"  - {h}")
