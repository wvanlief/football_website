import os
import shutil
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from backend.utils import fetch_url_with_retry, _get_cache_path

@pytest.fixture(autouse=True)
def clean_cache():
    # Clean cache directory before and after tests
    cache_dir = os.path.join("backend", "data", "cache")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    yield
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
        except Exception:
            pass

def test_cache_creation_and_hit():
    url = "https://example.com/test-cache-api"
    headers = {"X-Test": "123"}
    
    mock_response = MagicMock()
    mock_response.read.return_value = b"Hello, World!"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # First call: Cache miss, network call
        data = fetch_url_with_retry(url, headers=headers, use_cache=True)
        assert data == b"Hello, World!"
        assert mock_urlopen.call_count == 1
        
        # Verify cache file exists
        cache_path = _get_cache_path(url, headers)
        assert os.path.exists(cache_path)
        
        # Second call: Cache hit, no network call
        mock_urlopen.reset_mock()
        data2 = fetch_url_with_retry(url, headers=headers, use_cache=True)
        assert data2 == b"Hello, World!"
        assert mock_urlopen.call_count == 0

def test_cache_bypass():
    url = "https://example.com/test-bypass-api"
    headers = {"X-Test": "456"}
    
    mock_response = MagicMock()
    mock_response.read.return_value = b"Bypassed Data"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Call with use_cache=False: Network call
        data = fetch_url_with_retry(url, headers=headers, use_cache=False)
        assert data == b"Bypassed Data"
        assert mock_urlopen.call_count == 1
        
        # Verify cache file does NOT exist
        cache_path = _get_cache_path(url, headers)
        assert not os.path.exists(cache_path)
        
        # Second call with use_cache=False: Network call again
        mock_urlopen.reset_mock()
        data2 = fetch_url_with_retry(url, headers=headers, use_cache=False)
        assert data2 == b"Bypassed Data"
        assert mock_urlopen.call_count == 1

def test_cache_expiration_on_new_day():
    url = "https://example.com/test-expiration-api"
    headers = {"X-Test": "789"}
    
    mock_response = MagicMock()
    mock_response.read.return_value = b"Expiring Data"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # First call: Cache miss, network call
        data = fetch_url_with_retry(url, headers=headers, use_cache=True)
        assert data == b"Expiring Data"
        assert mock_urlopen.call_count == 1
        
        # Mock datetime.now inside backend.utils to return tomorrow
        tomorrow_dt = datetime.now(timezone.utc) + timedelta(days=1)
        with patch("backend.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = tomorrow_dt
            # timezone class mock wrapper in case of isinstance checks or utc property
            mock_datetime.timezone = timezone
            
            # Since the date changed, it should be a cache miss, network call again
            mock_urlopen.reset_mock()
            data2 = fetch_url_with_retry(url, headers=headers, use_cache=True)
            assert data2 == b"Expiring Data"
            assert mock_urlopen.call_count == 1
