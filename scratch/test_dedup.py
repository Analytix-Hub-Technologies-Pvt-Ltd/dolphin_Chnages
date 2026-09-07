import hashlib
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

def extract_section_for_seeds(doc_chunks, seed_indices):
    chunk_map = {c.get('chunk_index'): c for c in doc_chunks}
    all_indices = sorted(chunk_map.keys())
    if not all_indices:
        return []
    
    min_idx = all_indices[0]
    max_idx = all_indices[-1]
    
    sorted_seeds = sorted(set(seed_indices))
    clusters = []
    current_cluster = [sorted_seeds[0]] if sorted_seeds else []
    
    for s in sorted_seeds[1:]:
        if s - current_cluster[-1] <= 12:
            current_cluster.append(s)
        else:
            clusters.append(current_cluster)
            current_cluster = [s]
    if current_cluster:
        clusters.append(current_cluster)
        
    expanded_indices = set()
    section_break_pattern = re.compile(
        r'^(?:Section\s+[I|V|X|\d]+|Chapter\s+[I|V|X|\d]+|[I|V|X]+\.\d+|\d+\.\d+\s+[A-Z]|PART\s+[I|V|X|\d]+)',
        re.IGNORECASE
    )
    
    for cluster in clusters:
        c_start = min(cluster)
        c_end = max(cluster)
        span_indices = set(range(c_start, c_end + 1))
        
        back_steps = 0
        curr = c_start - 1
        while curr >= min_idx and back_steps < 10:
            content = chunk_map.get(curr, {}).get('content', '')
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines and section_break_pattern.match(lines[0]):
                span_indices.add(curr)
                break
            span_indices.add(curr)
            curr -= 1
            back_steps += 1
            
        fwd_steps = 0
        curr = c_end + 1
        while curr <= max_idx and fwd_steps < 15:
            content = chunk_map.get(curr, {}).get('content', '')
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines and section_break_pattern.match(lines[0]) and curr > c_end + 3:
                break
            span_indices.add(curr)
            curr += 1
            fwd_steps += 1
            
        expanded_indices.update(span_indices)
        
    return [chunk_map[i] for i in sorted(expanded_indices) if i in chunk_map]

def deduplicate_company_chunks(chunks):
    unique_chunks = []
    seen_meta_keys = set()
    seen_content_hashes = set()
    
    for c in chunks:
        doc_id = c.get('document_id')
        chunk_idx = c.get('chunk_index')
        meta_key = (doc_id, chunk_idx) if (doc_id is not None and chunk_idx is not None) else None
        
        if meta_key and meta_key in seen_meta_keys:
            continue
            
        raw_content = c.get('content', '') or ''
        norm_text = re.sub(r'\s+', ' ', raw_content).strip().lower()
        if not norm_text:
            continue
            
        content_hash = hashlib.md5(norm_text.encode('utf-8')).hexdigest()
        if content_hash in seen_content_hashes:
            continue
            
        if meta_key:
            seen_meta_keys.add(meta_key)
        seen_content_hashes.add(content_hash)
        unique_chunks.append(c)
        
    return unique_chunks

doc8_chunks = docs_by_id[8]
res = extract_section_for_seeds(doc8_chunks, [687, 701])
deduped = deduplicate_company_chunks(res)
print(f"Original: {len(res)} chunks -> Deduped: {len(deduped)} chunks")
print(f"Total character count: {sum(len(c.get('content', '')) for c in deduped)}")
