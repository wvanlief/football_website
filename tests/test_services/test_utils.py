import urllib.error
import ssl
import pytest
from unittest.mock import patch, MagicMock
from backend.utils import fetch_url_with_retry, fetch_json_with_retry

def test_fetch_url_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"success content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        content = fetch_url_with_retry("https://example.com/api", retries=3, backoff_factor=0.01)
        assert content == b"success content"
        mock_urlopen.assert_called_once()

def test_fetch_url_retry_and_succeed():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        
        # When entering context manager, first call raises SSLError, second returns mock_response
        mock_enter = MagicMock()
        mock_enter.__enter__.side_effect = [
            ssl.SSLError("SSL: UNEXPECTED_EOF_WHILE_READING"),
            mock_response
        ]
        mock_urlopen.return_value = mock_enter
        
        content = fetch_url_with_retry("https://example.com/api", retries=3, backoff_factor=0.01)
        assert content == b'{"status": "ok"}'
        assert mock_urlopen.call_count == 2

def test_fetch_url_persistent_failure():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_enter = MagicMock()
        mock_enter.__enter__.side_effect = urllib.error.URLError("DNS lookup failed")
        mock_urlopen.return_value = mock_enter
        
        with pytest.raises(urllib.error.URLError):
            fetch_url_with_retry("https://example.com/api", retries=3, backoff_factor=0.01)
        assert mock_urlopen.call_count == 3

def test_fetch_url_non_retryable_http_error():
    fp = MagicMock()
    http_err = urllib.error.HTTPError("https://example.com/api", 404, "Not Found", {}, fp)
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_enter = MagicMock()
        mock_enter.__enter__.side_effect = http_err
        mock_urlopen.return_value = mock_enter
        
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            fetch_url_with_retry("https://example.com/api", retries=3, backoff_factor=0.01)
        assert exc_info.value.code == 404
        assert mock_urlopen.call_count == 1

def test_fetch_url_retryable_http_error():
    fp = MagicMock()
    http_err_503 = urllib.error.HTTPError("https://example.com/api", 503, "Service Unavailable", {}, fp)
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        
        mock_enter = MagicMock()
        mock_enter.__enter__.side_effect = [http_err_503, mock_response]
        mock_urlopen.return_value = mock_enter
        
        content = fetch_url_with_retry("https://example.com/api", retries=3, backoff_factor=0.01)
        assert content == b"ok"
        assert mock_urlopen.call_count == 2

def test_fetch_json_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"key": "value"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        data = fetch_json_with_retry("https://example.com/api", retries=2, backoff_factor=0.01)
        assert data == {"key": "value"}
