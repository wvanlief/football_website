import urllib.request
import urllib.error
import json
import time
import ssl
from typing import Any

def fetch_url_with_retry(
    url: str,
    headers: dict = None,
    timeout: int = 20,
    retries: int = 5,
    backoff_factor: float = 1.5
) -> bytes:
    """
    Fetches the content of a URL with retry logic for transient errors.
    Handles timeouts, connection errors, and SSL handshake/EOF violations.
    """
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
        
    req = urllib.request.Request(url, headers=headers)
    context = ssl.create_default_context()
    
    last_error = None
    delay = 1.0
    
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            # Retry on 5xx server errors or 429 Too Many Requests
            if e.code in (429, 500, 502, 503, 504):
                last_error = e
                print(f"HTTP error {e.code} fetching {url} (attempt {attempt}/{retries}). Retrying in {delay}s...")
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
    timeout: int = 20,
    retries: int = 5,
    backoff_factor: float = 1.5
) -> Any:
    """Fetches a URL and parses it as JSON."""
    content = fetch_url_with_retry(
        url, headers=headers, timeout=timeout, retries=retries, backoff_factor=backoff_factor
    )
    return json.loads(content.decode('utf-8'))
