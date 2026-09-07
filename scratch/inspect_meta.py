import json
import os

meta_path = "retrieval/company_index.meta.json"
if os.path.exists(meta_path):
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    print("Total chunks in company_index.meta.json:", len(meta))
    company_ids = set()
    sample_by_cid = {}
    for item in meta:
        cid = item.get("company_id") or item.get("CompanyId")
        company_ids.add(str(cid))
        if str(cid) not in sample_by_cid:
            sample_by_cid[str(cid)] = item
    print("Unique company_ids in FAISS metadata:", company_ids)
    for cid, sample in sample_by_cid.items():
        print(f"\nSample for company_id={cid}:")
        print("Keys:", list(sample.keys()))
        print("Title:", sample.get("document_title") or sample.get("title"))
        print("Company Name:", sample.get("company_name") or sample.get("CompanyName"))
        print("Ship Type:", sample.get("ship_type"))
else:
    print("File does not exist:", meta_path)
