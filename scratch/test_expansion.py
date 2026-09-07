import json
import re

with open('retrieval/company_index.meta.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Build an index of doc_id -> list of metadata dicts
docs_by_id = {}
for i, d in enumerate(data):
    doc_id = d.get('document_id')
    if doc_id not in docs_by_id:
        docs_by_id[doc_id] = []
    d['_idx'] = i
    docs_by_id[doc_id].append(d)

print(f"Loaded {len(docs_by_id)} documents.")

# Let's test a section expansion algorithm on sample seed hits
# E.g. Seed hits for COW in doc 8: [687, 701]
def extract_section_for_seeds(doc_chunks, seed_indices, max_expansion_per_cluster=30):
    """
    Given a sorted list of doc_chunks (by chunk_index) and seed chunk_indices,
    expand to full contiguous sections.
    """
    chunk_map = {c.get('chunk_index'): c for c in doc_chunks}
    all_indices = sorted(chunk_map.keys())
    if not all_indices:
        return []
    
    min_idx = all_indices[0]
    max_idx = all_indices[-1]
    
    # 1. Cluster seed indices that are close to each other (e.g. within 15 chunks of each other)
    sorted_seeds = sorted(set(seed_indices))
    clusters = []
    current_cluster = [sorted_seeds[0]] if sorted_seeds else []
    
    for s in sorted_seeds[1:]:
        if s - current_cluster[-1] <= 12: # gap of 12 chunks or less belongs to same procedure/topic
            current_cluster.append(s)
        else:
            clusters.append(current_cluster)
            current_cluster = [s]
    if current_cluster:
        clusters.append(current_cluster)
        
    expanded_indices = set()
    
    # Major section boundary regex
    section_break_pattern = re.compile(
        r'^(?:'
        r'Section\s+[I|V|X|\d]+|'
        r'Chapter\s+[I|V|X|\d]+|'
        r'[I|V|X]+\.\d+|'
        r'\d+\.\d+\s+[A-Z]|'
        r'PART\s+[I|V|X|\d]+'
        r')',
        re.IGNORECASE
    )
    
    for cluster in clusters:
        c_start = min(cluster)
        c_end = max(cluster)
        
        # Bridge the entire span between c_start and c_end
        span_indices = set(range(c_start, c_end + 1))
        
        # Expand backwards until a section boundary or max backward steps (e.g. 8)
        back_steps = 0
        curr = c_start - 1
        while curr >= min_idx and back_steps < 10:
            content = chunk_map.get(curr, {}).get('content', '')
            # If current chunk has a major section header at its start, include it and stop
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines and section_break_pattern.match(lines[0]):
                span_indices.add(curr)
                break
            span_indices.add(curr)
            curr -= 1
            back_steps += 1
            
        # Expand forwards until next major section boundary or max forward steps (e.g. 15)
        fwd_steps = 0
        curr = c_end + 1
        while curr <= max_idx and fwd_steps < 15:
            content = chunk_map.get(curr, {}).get('content', '')
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            # If next chunk starts a completely new major section, stop before it
            if lines and section_break_pattern.match(lines[0]) and curr > c_end + 3:
                break
            span_indices.add(curr)
            curr += 1
            fwd_steps += 1
            
        expanded_indices.update(span_indices)
        
    result_chunks = [chunk_map[i] for i in sorted(expanded_indices) if i in chunk_map]
    return result_chunks

# Test on doc 8 with COW seeds [687, 701]
doc8_chunks = docs_by_id[8]
res = extract_section_for_seeds(doc8_chunks, [687, 701])
print(f"Extracted {len(res)} chunks for COW in doc 8 (indices: {min(c.get('chunk_index') for c in res)} to {max(c.get('chunk_index') for c in res)})")
for c in res[:5]:
    lines = [l.strip() for l in c.get('content', '').split('\n') if l.strip()]
    print(f"  Chunk {c.get('chunk_index')}: {lines[0] if lines else 'EMPTY'}")
