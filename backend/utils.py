import urllib.request
import urllib.error
import json
import time
import ssl
import os
import hashlib
import base64
from datetime import datetime, timezone
from typing import Any

def _get_cache_path(url: str, headers: dict = None) -> str:
    """Generates a date-prefixed file path for caching the request, matching existing cached files regardless of date."""
    # Serialize headers deterministically
    headers_str = json.dumps(headers or {}, sort_keys=True)
    hash_input = f"{url}||{headers_str}".encode('utf-8')
    h = hashlib.md5(hash_input).hexdigest()
    
    cache_dir = os.path.join("backend", "data", "cache")
    if os.path.exists(cache_dir):
        for filename in os.listdir(cache_dir):
            if filename.endswith(f"_{h}.json"):
                return os.path.join(cache_dir, filename)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{today}_{h}.json"
    return os.path.join(cache_dir, filename)


def fetch_url_with_retry(
    url: str,
    headers: dict = None,
    timeout: int = 10,
    retries: int = 3,
    backoff_factor: float = 1.5,
    use_cache: bool = True,
    provider: str = None
) -> bytes:
    """
    Fetches the content of a URL with retry logic for transient errors.
    Handles timeouts, connection errors, and SSL handshake/EOF violations.
    Caches successful responses locally when use_cache is True.
    Enforces global rate limits if provider is specified.
    """
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
        
    # Check cache first (cached hits do not consume API quota)
    if use_cache:
        cache_path = _get_cache_path(url, headers)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                return base64.b64decode(cache_data["content"].encode('utf-8'))
            except Exception as cache_err:
                print(f"Warning: Failed to read cache file {cache_path}: {cache_err}. Proceeding with live request.")

    # Check rate limiter before making live external call
    if provider:
        from backend.services.rate_limiter import rate_limiter
        if not rate_limiter.try_call(provider):
            raise RuntimeError(f"Rate limit safeguard triggered for '{provider}'. External network call blocked.")

    req = urllib.request.Request(url, headers=headers)
    context = ssl.create_default_context()
    
    last_error = None
    delay = 1.0
    
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                content = response.read()
                
                # Write to cache if request was successful
                if use_cache:
                    try:
                        cache_path = _get_cache_path(url, headers)
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        cache_data = {
                            "url": url,
                            "headers": headers,
                            "content": base64.b64encode(content).decode('utf-8')
                        }
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(cache_data, f)
                    except Exception as cache_write_err:
                        print(f"Warning: Failed to write to cache file: {cache_write_err}")
                        
                return content
        except urllib.error.HTTPError as e:
            # Retry on 5xx server errors or 429 Too Many Requests
            if e.code in (429, 500, 502, 503, 504):
                last_error = e
                wait_time = 30.0 if e.code == 429 else delay
                print(f"HTTP error {e.code} fetching {url} (attempt {attempt}/{retries}). Retrying in {wait_time}s...")
                if attempt < retries:
                    time.sleep(wait_time)
                    delay *= backoff_factor
                continue
            else:
                # Fail immediately for other 4xx errors (e.g. 404, 403, 400)
                print(f"HTTP error {e.code} fetching {url}. Failing immediately.")
                raise e
        except (urllib.error.URLError, ConnectionError, TimeoutError, ssl.SSLError) as e:
            last_error = e
            print(f"Network/SSL error fetching {url}: {e} (attempt {attempt}/{retries}). Retrying in {delay}s...")
        
        if attempt < retries:
            time.sleep(delay)
            delay *= backoff_factor
            
    print(f"Failed to fetch {url} after {retries} attempts. Last error: {last_error}")
    raise last_error

def fetch_json_with_retry(
    url: str,
    headers: dict = None,
    timeout: int = 10,
    retries: int = 3,
    backoff_factor: float = 1.5,
    use_cache: bool = True,
    provider: str = None
) -> Any:
    """Fetches a URL and parses it as JSON."""
    try:
        content = fetch_url_with_retry(
            url,
            headers=headers,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
            use_cache=use_cache,
            provider=provider
        )
        return json.loads(content.decode('utf-8'))
    except RuntimeError as r_err:
        print(f"{r_err}")
        return {}

fetch_json = fetch_json_with_retry


