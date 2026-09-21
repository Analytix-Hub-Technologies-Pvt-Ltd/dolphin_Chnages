from __future__ import annotations

import random
import re
from typing import Dict, List


class SuggestionService:
    """Generate context-aware follow-up suggestions for the chat UI."""

    _STOPWORDS = {
        "the", "and", "or", "a", "an", "of", "for", "to", "in", "on", "about",
        "is", "are", "with", "at", "by", "from", "describe", "explain", "what",
        "how", "tell", "details", "used", "onboard", "ships", "ship", "give",
        "show", "list", "can", "you", "please", "me", "i", "we", "my", "our",
        "procedure", "procedures", "process", "define", "definition", "discuss"
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

    def generate_from_response(
        self,
        query: str,
        response_text: str = "",
        topic_name: str = "",
        company_name: str = "",
        chunks: List[Dict] = None,
    ) -> List[str]:
        """
        Dynamically generates 2-3 precise, context-aware follow-up questions
        directly relevant to the response content, procedure, roles, and maritime topics.
        """
        response_text = response_text or ""
        query = query or ""
        chunks = chunks or []

        # 1. Extract Metadata from Section 1 (if company SMS response)
        doc_title_m = re.search(r'(?:\*\*|\*|#)*\s*Document\s*Title\s*:\s*(?:\*\*)?\s*([^\n*]+)', response_text, re.IGNORECASE)
        sop_name_m = re.search(r'(?:\*\*|\*|#)*\s*SOP\s*Name\s*:\s*(?:\*\*)?\s*([^\n*]+)', response_text, re.IGNORECASE)
        section_m = re.search(r'(?:\*\*|\*|#)*\s*Section\s*:\s*(?:\*\*)?\s*([^\n*]+)', response_text, re.IGNORECASE)

        doc_title = doc_title_m.group(1).strip() if doc_title_m else ""
        sop_name = sop_name_m.group(1).strip() if sop_name_m else ""
        section_val = section_m.group(1).strip() if section_m else ""

        clean_doc = re.sub(r'\.(?:docx?|pdf|txt|xlsx?)$', '', doc_title, flags=re.IGNORECASE).strip()
        clean_sop = re.sub(r'^(?:SOP\s*[-:]?\s*|Procedure\s*for\s*)', '', sop_name, flags=re.IGNORECASE).strip()

        # 2. Extract Subheadings from markdown (e.g. #### Despatch of SMS Documents:, #### Technical Requirements)
        raw_headings = re.findall(r'(?:^|\n)#{2,5}\s*(?:\*\*)?([^\n*#]+)(?:\*\*)?', response_text)
        subheadings = []
        for h in raw_headings:
            h_clean = re.sub(r'^(?:\d+[\.\)]\s*|[-*•]\s*|🏢|📘|🔍|💡|\d+\s*)', '', h).strip().rstrip(':')
            h_clean = re.sub(r'\s+', ' ', h_clean)
            if (
                len(h_clean) >= 4
                and len(h_clean) <= 65
                and not any(ignore in h_clean.lower() for ignore in [
                    "safety management system", "sms / qms", "dolphin internal knowledge",
                    "comparison & ai", "ai advisory", "governance notice", "conclusion",
                    "document title", "sop name", "section"
                ])
            ):
                subheadings.append(h_clean)

        # 3. Extract Tables / Checklist topics / Form numbers mentioned in text
        form_matches = re.findall(r'\b(?:Form\s+[A-Z0-9_-]{2,10}|[A-Z]{2,4}\s*\d{3,4}|(?:[A-Z][a-z]+\s+)+Log(?:book)?|Transmittal\s+Note|Permit\s+to\s+Work|Checklist)\b', response_text)
        clean_forms = [f.strip() for f in form_matches if len(f.strip()) > 3 and not f.strip().lower().startswith("form:")]

        # 4. Extract Roles mentioned in text (Master, Chief Officer, Second Officer, DO, ISM Cell, etc.)
        role_matches = re.findall(r'\b(Master|Chief\s+Officer|Second\s+Officer|Third\s+Officer|Chief\s+Engineer|Second\s+Engineer|Duty\s+Engineer|Duty\s+Officer|Division\s+Officer|DO|Group\s+I/C|ISM\s+Cell|Safety\s+Officer|Standby\s+Person|Pumpman|Bosun|OOW)\b', response_text, re.IGNORECASE)
        found_roles = list(dict.fromkeys([r.title() for r in role_matches]))

        # 5. Extract Maritime Regulations / Codes mentioned in text (IGC, IGF, SOLAS, MARPOL, STCW, ISM, COLREGs)
        reg_matches = re.findall(r'\b(IGC\s+Code|IGF\s+Code|SOLAS(?:\s+Chapter\s+[IVX0-9]+)?|MARPOL(?:\s+Annex\s+[IVX0-9]+)?|STCW|ISM\s+Code|ISGOTT|TMSA)\b', response_text, re.IGNORECASE)
        found_regs = list(dict.fromkeys([r.upper() for r in reg_matches]))

        # 6. Extract key technical terms from query, topic_name, and chunks
        query_kw = self._extract_keywords(query)
        primary_topic = topic_name or (clean_sop if clean_sop else " ".join(query_kw[:3]))
        if not primary_topic and chunks:
            primary_topic = str(chunks[0].get("topic_name") or chunks[0].get("title") or "")
        primary_topic = re.sub(r'^(?:DBMS-\d+-|Course:\s*|Topic:\s*)', '', primary_topic).strip()
        if primary_topic:
            primary_topic = " ".join([w for w in primary_topic.split() if w.lower() not in self._STOPWORDS])

        # Build candidate questions
        candidates: List[str] = []

        # Category A: Specific Subheading & Procedural Questions
        for sub in subheadings[:3]:
            sub_lower = sub.lower()
            if "responsibilit" in sub_lower or "dut" in sub_lower:
                candidates.append(f"What are the specific personnel responsibilities for {sub}?")
            elif "checklist" in sub_lower or "check" in sub_lower:
                candidates.append(f"What are the mandatory checks listed under {sub}?")
            elif "precaution" in sub_lower or "safety" in sub_lower:
                candidates.append(f"What safety precautions apply to {sub}?")
            elif "maintenance" in sub_lower:
                candidates.append(f"What is the procedure for {sub}?")
            elif "emergency" in sub_lower:
                candidates.append(f"What are the emergency protocols for {sub}?")
            elif "permit" in sub_lower or "form" in sub_lower or "document" in sub_lower:
                candidates.append(f"What entries and documentation are required for {sub}?")
            elif "limit" in sub_lower or "parameter" in sub_lower or "threshold" in sub_lower or "testing" in sub_lower:
                candidates.append(f"What are the permissible limits and thresholds for {sub}?")
            else:
                candidates.append(f"What are the specific requirements for {sub}?")

        # Category B: Forms, Logs & Checklist Questions
        if clean_forms:
            form_name = clean_forms[0]
            candidates.append(f"What entries and verifications are required for {form_name}?")
            if len(clean_forms) > 1:
                candidates.append(f"How is {clean_forms[1]} maintained during operations?")

        # Category C: Role-specific Questions
        if found_roles:
            role = found_roles[0]
            target_topic = clean_sop or primary_topic or "this procedure"
            candidates.append(f"What are the {role}'s responsibilities for {target_topic}?")

        # Category D: Regulations & Statutory Requirements
        if found_regs:
            reg = found_regs[0]
            candidates.append(f"What are the {reg} regulatory requirements for {primary_topic or 'this operation'}?")

        # Category E: SOP & Topic Specific Questions
        if clean_sop and clean_sop.lower() not in (primary_topic.lower() if primary_topic else ""):
            candidates.append(f"What are the key steps in the {clean_sop} procedure?")
            candidates.append(f"What safety equipment and precautions are required for {clean_sop}?")

        # Category F: Query / Chunk Derived Questions
        if primary_topic:
            candidates.append(f"What precautions must be observed during {primary_topic}?")
            candidates.append(f"What are the operational parameters and limits for {primary_topic}?")
            candidates.append(f"How is {primary_topic} managed under safety regulations?")

        # Category G: Generic Maritime Fallback (Ground in query keywords)
        kw_phrase = " ".join(query_kw[:2]).strip()
        if kw_phrase:
            candidates.append(f"What are the safety requirements for {kw_phrase}?")
            candidates.append(f"What are the operational guidelines for {kw_phrase}?")
            candidates.append(f"How are risk controls implemented for {kw_phrase}?")

        # Deduplicate and Clean
        seen = set()
        final_suggestions: List[str] = []
        for q in candidates:
            cleaned = re.sub(r'\s+', ' ', q or '').strip()
            if not cleaned.endswith('?'):
                cleaned = f"{cleaned}?"
            norm = cleaned.lower()
            if norm in seen or len(cleaned.split()) < 4 or len(cleaned.split()) > 15:
                continue
            seen.add(norm)
            final_suggestions.append(cleaned)
            if len(final_suggestions) >= 3:
                break

        return final_suggestions[:3]

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

        return self.generate_from_response(
            query=query,
            response_text="",
            topic_name=short_topic,
            chunks=chunks,
        )
