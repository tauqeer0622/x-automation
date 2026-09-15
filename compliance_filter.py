import re
from typing import List, Optional
from config import config
from database import add_log

# Well-known government & regulatory handles that post about crypto/stocks
KNOWN_GOVT_HANDLES = {
    "secgov", "cftc", "federalreserve", "whitehouse", "potus", "vpotus", "treasury",
    "fbi", "doj", "irsnews", "irs", "statedept", "fca1", "bankofengland", "ecb",
    "bis_org", "imfnews", "worldbank", "finma_ch", "mas_sg", "sfcgovhk", "rbi",
    "baboriginal", "bundesbank", "dfaboriginal", "eu_commission", "europarl_en"
}

# Strong government keywords that indicate official state affiliation
DEFAULT_GOVT_PATTERNS = [
    r"\bgov\b",
    r"\bgovt\b",
    r"\bgovernment\b",
    r"\bminister\b",
    r"\bministry\b",
    r"\bparliament\b",
    r"\bsenator\b",
    r"\bcongress\b",
    r"\bcongressman\b",
    r"\bcongresswoman\b",
    r"\bwhitehouse\b",
    r"\btreasury\b",
    r"\bcentral\s*bank\b",
    r"\bfederal\s*reserve\b",
    r"\bpolice\b",
    r"\bembassy\b",
    r"\bconsulate\b",
    r"\bambassador\b",
    r"\bdiplomat\b",
    r"\bstate[- ]affiliated\b",
    r"\belected\s*official\b",
    r"\bgovernment\s*official\b",
    r"\bgovernment\s*organization\b",
    r"\bregulator\b",
    r"\bsec\s*chair\b"
]

def is_government_affiliated(
    handle: str,
    display_name: str = "",
    badge_label: str = "",
    extra_text: str = ""
) -> bool:
    """
    Evaluates whether an account is government-connected, government-affiliated,
    a public official, or a regulatory body.
    Returns True if government affiliation is detected.
    """
    clean_handle = (handle or "").strip().lower().replace("@", "")
    clean_name = (display_name or "").lower()
    clean_badge = (badge_label or "").lower()
    clean_extra = (extra_text or "").lower()

    # 1. Check known government and regulatory handle list
    if clean_handle in KNOWN_GOVT_HANDLES:
        add_log("WARN", f"Blocked tweet by @{clean_handle} (Matched known government handle)")
        return True

    # Check for .gov in handle or display name
    if ".gov" in clean_handle or ".gov" in clean_name or "_gov" in clean_handle or "gov_" in clean_handle:
        add_log("WARN", f"Blocked tweet by @{clean_handle} (Matched .gov handle pattern)")
        return True

    # 2. Check X's official Government / State-Affiliated badge or label
    # On X, government badges have labels like 'Government organization' or 'State-affiliated media'
    govt_badge_terms = [
        "government", "state-affiliated", "elected official", "official candidate",
        "multilateral organization", "public official"
    ]
    for term in govt_badge_terms:
        if term in clean_badge or term in clean_extra:
            add_log("WARN", f"Blocked tweet by @{clean_handle} (Detected X government badge/label: '{term}')")
            return True

    # 3. Check regex patterns against display name and handle
    for pattern in DEFAULT_GOVT_PATTERNS:
        if re.search(pattern, clean_handle) or re.search(pattern, clean_name):
            add_log("WARN", f"Blocked tweet by @{clean_handle} (Matched government keyword: '{pattern}')")
            return True

    # 4. Check user-configured government keywords from config
    for custom_kw in config.government_keywords:
        if custom_kw and (custom_kw in clean_handle or custom_kw in clean_name or custom_kw in clean_badge):
            add_log("WARN", f"Blocked tweet by @{clean_handle} (Matched custom government keyword: '{custom_kw}')")
            return True

    return False
