# pipeline/manual_filter.py
from loguru import logger

def is_manual_allowed_for_ship_type(document_title: str, ship_type: str) -> bool:
    """
    Strictly check if a company document matches the user's vessel type.
    - If user has a specific vessel type (Chemical, Oil Tanker, Container, OSV),
      retrieval is strictly restricted to that vessel's dedicated SMS manual and Permits.
    - If user has a general/unassigned vessel type, standard fleet manuals (Vol I, NMM, TMM, ECM, Permits) are allowed.
    - Office-level environmental & policy manuals (EMM, PAM) are excluded from vessel SMS queries.
    """
    if not ship_type:
        return True

    doc_title_lower = (document_title or "").lower()
    ship_type_lower = (ship_type or "").lower()

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

    is_osv_user = (
        "osv" in ship_type_lower 
        or "offshore" in ship_type_lower 
        or "supply" in ship_type_lower
    )
    is_osv_doc = "osv" in doc_title_lower and "except for osv" not in doc_title_lower
    is_except_osv_doc = "except for osv" in doc_title_lower

    if is_osv_user:
        return is_osv_doc

    if is_osv_doc and not is_osv_user:
        return False

    is_chemical_user = "chemical" in ship_type_lower
    is_chemical_doc = "chemical" in doc_title_lower
    if is_chemical_user:
        return is_chemical_doc

    if is_chemical_doc and not is_chemical_user:
        return False

    is_oil_user = "oil" in ship_type_lower or (ship_type_lower == "tanker" and not is_chemical_user)
    is_oil_doc = "oil tanker" in doc_title_lower
    if is_oil_user:
        return is_oil_doc

    if is_oil_doc and not is_oil_user:
        return False

    is_container_user = "container" in ship_type_lower
    is_container_doc = "container" in doc_title_lower
    if is_container_user:
        return is_container_doc

    if is_container_doc and not is_container_user:
        return False

    # For other / generic vessel types (e.g. LNG/LPG Carrier, Bulk Carrier, General):
    # Vol I Except for OSVs and general ship manuals are allowed
    if is_except_osv_doc:
        return not is_osv_user

    # Common ship safety/contingency manuals
    if any(
        m in doc_title_lower
        for m in [
            "emergency",
            "contingency",
            "health and safety",
            "navigation and mooring",
            "technical and maintenance",
            "nmm",
            "tmm",
            "ecm",
            "vol. i",
            "vol i",
        ]
    ):
        return True

    return True

