# pipeline/manual_filter.py
from loguru import logger

def is_manual_allowed_for_ship_type(document_title: str, ship_type: str) -> bool:
    """
    Strictly check if a company document matches the user's vessel type.
    - If user belongs to a specific ship type (e.g. Chemical Carrier/Tanker, Oil Tanker, Container, OSV),
      they must ONLY receive the company SMS manual and documents specifically matching their ship type.
    - General non-ship-specific manuals (Vol. I Except for OSVs, EMM, PAM, etc.) are excluded for specific ship types.
    - Work permits (Hot Work, Cold Work, Enclosed Space, etc.) are common to all vessels.
    """
    if not ship_type:
        return True

    doc_title_lower = document_title.lower()
    ship_type_lower = ship_type.lower()
    
    # 1. Common Work Permits are allowed for all ship types
    if "permit" in doc_title_lower:
        return True

    # 2. Exclude office-level environmental & policy manuals from vessel-specific SMS queries
    if (
        "environment management manual" in doc_title_lower 
        or "emm-" in doc_title_lower
        or "policy and administration" in doc_title_lower 
        or "pam" in doc_title_lower
    ):
        return False

    # 3. OSV ship type
    is_osv_user = (
        "osv" in ship_type_lower 
        or "offshore" in ship_type_lower 
        or "supply" in ship_type_lower
    )
    is_osv_doc = "osv" in doc_title_lower and "except for osv" not in doc_title_lower

    if is_osv_user:
        return is_osv_doc

    if is_osv_doc:
        return False

    # 4. Chemical Carrier / Chemical Tanker / Chemical Ship
    is_chemical_user = "chemical" in ship_type_lower
    is_chemical_doc = "chemical" in doc_title_lower

    if is_chemical_user:
        return is_chemical_doc

    if is_chemical_doc:
        return False

    # 5. Oil Tanker / Product Tanker / Crude Tanker
    is_oil_user = "oil" in ship_type_lower or (ship_type_lower == "tanker" and not is_chemical_user)
    is_oil_doc = "oil tanker" in doc_title_lower

    if is_oil_user:
        return is_oil_doc

    if is_oil_doc:
        return False

    # 6. Container Ship
    is_container_user = "container" in ship_type_lower
    is_container_doc = "container" in doc_title_lower

    if is_container_user:
        return is_container_doc

    if is_container_doc:
        return False

    # 7. For other general vessels (e.g. Bulk Carrier, General Cargo)
    if "except for osv" in doc_title_lower:
        return True

    # Common ship safety/contingency manuals
    if any(m in doc_title_lower for m in ["emergency", "contingency", "health and safety", "navigation and mooring", "technical and maintenance"]):
        return True

    return False
