"""
Extract unique product ID from a retailer URL.

Supports 33 retailers. Returns the extracted ID string, or empty string
if the domain is recognized but no ID can be extracted from the URL.
Raises ValueError for truly unrecognized domains.
"""

import logging
import re
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


# Domains that are recognized but have no extractable URL-based unique ID
# (their unique IDs come from email image filenames, not product URLs)
_NO_URL_ID_DOMAINS = frozenset([
    "macys.com",
    "nordstrom.com",
    "sportsbasement.com",
    "fit2run.com",
    "gazellesports.com",
    "sneakerpolitics.com",
    "shopsimon.com",
    "bloomingdales.com",
    "hibbett.com",       # Amplience code extracted by Apps Script (Lambda gets 403)
])

# Domains where the URL doesn't uniquely identify a color variant.
# The handler will post a Slack message requesting manual ID entry.
MANUAL_ID_DOMAINS = frozenset([
    "als.com",
])


def extract_unique_id(url: str) -> str:
    """
    Extract a unique product ID from a retailer URL.

    Returns:
        str: The extracted unique ID, or "" if recognized but not extractable.

    Raises:
        ValueError: If the URL domain is not recognized.
    """
    if not url or not url.strip():
        return ""

    url = url.strip()
    url_lower = url.lower()

    # --- Check no-ID domains first ---
    for domain in _NO_URL_ID_DOMAINS:
        if domain in url_lower:
            return ""

    # --- Nike ---
    # URL: nike.com/t/{product-slug}/{style-color}
    # Extract: slug (lowercase)
    if "nike.com" in url_lower:
        m = re.search(r"nike\.com/t/([a-z0-9-]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- FootLocker ---
    # URL: footlocker.com/product/~/ID.html or /product/~/~/ID.html
    if "footlocker.com" in url_lower:
        m = re.search(r"/product/~/(?:~/)?([^/]+)\.html", url)
        if m:
            return m.group(1)
        return ""

    # --- Champs Sports ---
    # URL: champssports.com/product/~/ID.html
    if "champssports.com" in url_lower:
        m = re.search(r"/product/~/([^/]+)\.html", url)
        if m:
            return m.group(1)
        return ""

    # --- Finish Line / JD Sports ---
    # URL: .../pdp/.../prod.../STYLE/COLOR or /STYLE/COLOR/WIDTH
    # Extract: {style}_{color}, stripping width suffix from style
    if "finishline.com" in url_lower or "jdsports.com" in url_lower:
        m = re.search(r"/([A-Z0-9]+)/(\d+)(?:/|$)", url, re.IGNORECASE)
        if m:
            style = m.group(1)
            color = m.group(2)
            # Strip trailing single digit+letter width suffix (e.g. 1D, 2E)
            style = re.sub(r"\d[A-Za-z]$", "", style)
            return f"{style}_{color}"
        return ""

    # --- Revolve ---
    # URL: revolve.com/.../dp/CODE/ or ?code=CODE
    if "revolve.com" in url_lower:
        m = re.search(r"/dp/([A-Z0-9-]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r"code=([A-Z0-9-]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return ""

    # --- FWRD (Forward by Revolve) ---
    # URL: fwrd.com/product-{slug}/{CODE}/ or fwrd.com/.../DisplayProduct.jsp?code={CODE}
    if "fwrd.com" in url_lower:
        m = re.search(r"fwrd\.com/[^/]+/([A-Z]+-[A-Z0-9]+)/?", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r"code=([A-Z]+-[A-Z0-9]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return ""

    # --- ASOS ---
    # URL: asos.com/.../prd/NUMERIC_ID
    if "asos.com" in url_lower:
        m = re.search(r"/prd/(\d+)", url)
        if m:
            return m.group(1)
        return ""

    # --- Snipes ---
    # URL: snipesusa.com/...-STYLE-CODE-NUMERICID.html
    if "snipesusa.com" in url_lower:
        m = re.search(r"-([a-z0-9]+-\d{2,3})-\d+\.html", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        # Fallback: numeric ID before .html
        m = re.search(r"-(\d+)\.html", url, re.IGNORECASE)
        if m:
            return m.group(1)
        return ""

    # --- DTLR ---
    # Multi-brand: Nike/Jordan style-color, Adidas style code, HOKA style code
    if "dtlr.com" in url_lower:
        path_match = re.search(r"/products/(.+?)(?:\?|$)", url, re.IGNORECASE)
        if not path_match:
            return ""
        slug = path_match.group(1).lower()

        # Nike/Jordan: 2 letters + 4 digits + hyphen + 3 digits (e.g., bv1021-106, fn7432-161)
        m = re.search(r'(?:^|-)([a-z]{2}\d{4})-(\d{3})(?:-|$)', slug)
        if m:
            return f"{m.group(1)}-{m.group(2)}".upper()

        # HOKA: 5+ digits + hyphen + letters (e.g., 1127895-ncsw)
        if "hoka" in slug:
            m = re.search(r'(?:^|-)(\d{5,})-([a-z]+)(?:-|$)', slug)
            if m:
                return f"{m.group(1)}{m.group(2)}".upper()

        # Adidas: 2 letters + 4 digits at end of slug (e.g., js0039)
        m = re.search(r'-([a-z]{2}\d{4})$', slug)
        if m:
            return m.group(1).upper()

        return ""

    # --- END Clothing ---
    # URL: endclothing.com/.../{product-name}-{code}.html
    if "endclothing.com" in url_lower:
        m = re.search(r"([a-z]{2}\d{4}-\d{3})\.html", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- Shoe Palace ---
    # URL: shoepalace.com/products/BRAND-CODE-SLUG?variant=...
    if "shoepalace.com" in url_lower:
        m = re.search(r"/products/[^-]+-[^-]+-([^?]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- ShopWSS ---
    # URL: shopwss.com/products/CODE (xx####_### or xx#######)
    if "shopwss.com" in url_lower:
        m = re.search(r"/products/([a-z]{2}\d{4}_\d{3})", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        # Fallback: 9 chars without underscore -> insert underscore
        m = re.search(r"/products/([a-z]{2}\d{7})(?:\?|$|/)", url, re.IGNORECASE)
        if m:
            raw = m.group(1).lower()
            return f"{raw[:6]}_{raw[6:]}"
        return ""

    # --- On Running ---
    # URL: on.com/.../{product-name}-{CODE}?...
    if "on.com" in url_lower:
        m = re.search(r"-([A-Z0-9.]+)(?:\?|$)", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return ""

    # --- Adidas ---
    # URL: adidas.com/us/.../CODE.html
    if "adidas.com" in url_lower:
        m = re.search(r"adidas\.com/us/.*/([A-Z0-9]+)\.html", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return ""

    # --- Carbon38 ---
    # URL: carbon38.com/products/SLUG
    if "carbon38.com" in url_lower:
        m = re.search(r"carbon38\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?products/([a-z0-9-]+)", url, re.IGNORECASE)
        if m:
            slug = m.group(1).lower()
            # Strip standalone numbers (backend _simplify_slug behavior)
            parts = [p for p in slug.split("-") if not p.isdigit()]
            return "-".join(parts)
        return ""

    # --- CNCPTS (Concepts) ---
    # URL: cncpts.com/products/...-STYLECODE-...
    if "cncpts.com" in url_lower:
        m = re.search(r"/products/.*?-([a-z]{2}\d+-\d+)(?:-|$)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- NET-A-PORTER ---
    # URL: net-a-porter.com/.../LONG_NUMERIC_ID
    if "net-a-porter.com" in url_lower:
        m = re.search(r"/(\d{10,})", url)
        if m:
            return m.group(1)
        return ""

    # --- Orleans Shoe Co ---
    # URL: orleansshoes.com/products/SLUG
    if "orleansshoes.com" in url_lower:
        m = re.search(r"/products/([^/?]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- Urban Outfitters ---
    # URL: urbanoutfitters.com/shop/[optional-middle/]SLUG?color=CODE
    # Handles: /shop/slug?color=X   AND  /shop/hybrid/slug?color=X
    # Slug normalization MUST match backend/app/services/urban_parser.py _normalize_slug:
    #   1. Strip "womens"/"mens" segments
    #   2. Strip trailing digits glued to last word (sneaker2 -> sneaker)
    #   3. Strip trailing 's' from last segment (sneakers -> sneaker)
    if "urbanoutfitters.com" in url_lower:
        # Strip query string first so '/' in param values (e.g. size=US+7/UK+5)
        # can't be mistaken for a path separator.
        path_only = url.split('?', 1)[0]
        # Capture LAST segment after /shop/ (supports /shop/hybrid/slug paths).
        slug_match = re.search(r"/shop/(?:[^/]+/)*([^/]+)", path_only, re.IGNORECASE)
        color_match = re.search(r"[?&]color=(\d{3})", url)
        if slug_match:
            slug = slug_match.group(1).lower()
            # 1. Strip "womens"/"mens" segments (handles any position)
            parts = [p for p in slug.split('-') if p not in ('womens', 'mens')]
            slug = '-'.join(parts)
            # 2. Strip trailing digits glued to last word (e.g. sneaker2 -> sneaker)
            slug = re.sub(r'\d+$', '', slug).rstrip('-')
            # 3. Strip trailing 's' from last segment (plural -> singular)
            if len(slug) > 1 and slug.endswith('s'):
                slug = slug[:-1]
            if color_match:
                return f"{slug}-{color_match.group(1)}"
            return slug
        return ""

    # --- Anthropologie ---
    # URL: anthropologie.com/shop/SLUG
    if "anthropologie.com" in url_lower:
        m = re.search(r"/shop/([^/?]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- Sierra ---
    # URL: sierra.com/...~p~SKU...
    if "sierra.com" in url_lower:
        m = re.search(r"~p~([a-z0-9]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return ""

    # --- Al's Sporting Goods ---
    # URL: als.com/{product-name}-NUMERICID/p
    if "als.com" in url_lower:
        m = re.search(r"/[^/]+-(\d{5,})/p", url)
        if m:
            return m.group(1)
        return ""

    # --- SNS (Sneakersnstuff) ---
    # URL: sneakersnstuff.com/products/SLUG
    if "sneakersnstuff.com" in url_lower:
        m = re.search(r"/products/([^/?]+)", url, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    # --- Dick's Sporting Goods ---
    # URL: dickssportinggoods.com/p/{product-slug}/{product-code}?color=...
    # Example: /p/on-womens-cloud-6-shoes-24mazwcld6chmbrywftw/24mazwcld6chmbrywftw?color=Caper
    # Returns: {product-code}-{color} e.g. "24mazwcld6chmbrywftw-caper"
    if "dickssportinggoods.com" in url_lower:
        m = re.search(r"/p/[^/]+/([^/?]+)", url, re.IGNORECASE)
        if m:
            code = m.group(1).lower()
            # Append color if present (URL-decode, lowercase, slashes/spaces → hyphens)
            try:
                clean_url = url.replace("&amp;", "&")
                params = parse_qs(urlparse(clean_url).query)
                color = params.get("color", [None])[0]
                if color:
                    color = re.sub(r"[/\s]+", "-", color.strip()).lower()
                    return f"{code}-{color}"
            except Exception:
                pass
            return code
        return ""

    # --- Academy Sports ---
    # URL: academy.com/p/{slug}?sku={size}-{width}-{color}
    if "academy.com" in url_lower:
        slug_match = re.search(r'academy\.com/p/([a-z0-9-]+)', url, re.IGNORECASE)
        sku_match = re.search(r'[?&]sku=\d+(?:\.\d+)?-[a-z]-(.+?)(?:&|$)', url, re.IGNORECASE)
        if slug_match:
            slug = slug_match.group(1).lower()
            if sku_match:
                color = re.sub(r'[^a-z0-9]', '', sku_match.group(1).lower())
                return f"{slug}-{color}"
            return slug
        return ""

    # --- Scheels ---
    # URL: scheels.com/p/{PRODUCT_NUMBER} (unique per colorway)
    if "scheels.com" in url_lower:
        m = re.search(r'scheels\.com/p/(\d+)', url, re.IGNORECASE)
        if m:
            return m.group(1)
        return ""

    # --- Unrecognized domain ---
    raise ValueError(f"Unrecognized retailer URL: {url}")
