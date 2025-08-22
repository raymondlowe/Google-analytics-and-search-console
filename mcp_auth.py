import re
from typing import Optional, Tuple


def extract_keys_from_request(request) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract key from Authorization-like headers and 'key' query param.

    Lookup is case-insensitive. Returns (key_from_header, key_from_query, raw_auth_header).
    """
    # Build a case-insensitive mapping of headers
    try:
        hdrs = {k.lower(): v for k, v in request.headers.items()}
    except Exception:
        # Fallback: request.headers may already be a dict-like
        hdrs = {k.lower(): v for k, v in dict(request.headers).items()} if hasattr(request, 'headers') else {}

    # Prefer Authorization, then common custom headers
    raw = hdrs.get('authorization') or hdrs.get('x-api-key') or hdrs.get('x-auth-token')

    key_from_header = None
    if raw:
        raw_str = raw
        # Normalize to start with 'Bearer ' so downstream logic can parse uniformly
        if not raw_str.lower().startswith('bearer '):
            raw_str = f'Bearer {raw_str}'
        if raw_str.lower().startswith('bearer '):
            key_from_header = raw_str[7:]

    key_from_query = None
    try:
        if 'key' in request.query_params:
            key_from_query = request.query_params.get('key')
    except Exception:
        # Some request objects may not expose query_params as expected
        pass

    return key_from_header, key_from_query, raw


def determine_token(key_from_header: Optional[str], key_from_query: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Choose token and auth method based on available values.

    Returns: (token, auth_method) where auth_method is 'header' or 'url_param' or None
    """
    if key_from_header:
        return key_from_header, "header"
    if key_from_query:
        return key_from_query, "url_param"
    return None, None


def strip_key_param_from_scope(request) -> None:
    """Remove 'key' param from request.scope['query_string'] if present.

    This mutates the request.scope in-place (Starlette/FastAPI Request compatible).
    It preserves other query params and handles both bytes and str query_string.
    """
    if not hasattr(request, 'scope') or 'query_string' not in request.scope:
        return

    qs = request.scope['query_string']
    if isinstance(qs, bytes):
        try:
            qs = qs.decode()
        except Exception:
            qs = ''

    if not qs:
        request.scope['query_string'] = b''
        return

    # Split on '&' and filter out any key=... entries
    parts = [p for p in qs.split('&') if not p.startswith('key=') and p != '']
    new_q = '&'.join(parts)
    request.scope['query_string'] = new_q.encode()
