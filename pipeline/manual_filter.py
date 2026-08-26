# pipeline/manual_filter.py
from loguru import logger

def is_manual_allowed_for_ship_type(document_title: str, ship_type: str) -> bool:
    """
    Check if a company document title matches the user's ship type.
    - If ship_type is not provided, allow all documents for backward compatibility.
    - Special OSV-specific documents are allowed only for OSV/offshore/supply vessels.
    - Vol. I "Except for OSVs" is allowed for all except OSVs.
    - Tanker, Chemical, and Container manuals are restricted to their matching vessels.
    - General manuals/permits are always allowed.
    """
    if not ship_type:
        return True

    doc_title_lower = document_title.lower()
    ship_type_lower = ship_type.lower()
    
    # 1. OSV-specific and OSV-exclusion rules
    is_osv_doc = "osv" in doc_title_lower
    is_osv_user = (
        "osv" in ship_type_lower 
        or "offshore" in ship_type_lower 
        or "supply" in ship_type_lower
    )
    
    if is_osv_doc:
        # "except for osvs" is a general manual, NOT an osv-specific manual
        if "except for osv" in doc_title_lower:
            return not is_osv_user
        # OSV-specific manual requires OSV user
        return is_osv_user
    
    # If the user is on an OSV, exclude other specific vessel types
    if is_osv_user and (
        "oil tanker" in doc_title_lower 
        or "container" in doc_title_lower 
        or "chemical" in doc_title_lower
    ):
        return False

    # 2. Oil Tanker manual
    if "oil tanker" in doc_title_lower:
        return "oil" in ship_type_lower or ship_type_lower == "tanker"
        
    # 3. Chemical manual
    if "chemical" in doc_title_lower:
        return "chemical" in ship_type_lower
        
    # 4. Container manual
    if "container" in doc_title_lower:
        return "container" in ship_type_lower

    # 5. General manuals are allowed for all ship types
    return True
