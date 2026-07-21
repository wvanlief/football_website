import os
import pytest
from unittest.mock import patch, MagicMock
from backend.services.ingestion import CacheAdapter, NameNormalizer, COUNTRY_ISO_MAP

def test_name_normalizer_country_codes():
    normalizer = NameNormalizer()
    
    assert normalizer.get_country_code("Spain") == "ESP"
    assert normalizer.get_country_code("Germany") == "GER"
    assert normalizer.get_country_code("USA") == "USA"
    assert normalizer.get_country_code("United States") == "USA"
    assert normalizer.get_country_code("Korea Republic") == "KOR"
    assert normalizer.get_country_code("Unknown Country") is None

def test_name_normalizer_aliases():
    normalizer = NameNormalizer()
    
    assert normalizer.normalize("Korea Republic") == "South Korea"
    assert normalizer.normalize("Czech Republic") == "Czechia"
    assert normalizer.normalize("Ivory Coast") == "Côte d'Ivoire"
    assert normalizer.normalize("  Spain  ") == "Spain"

def test_cache_adapter_path(tmp_path):
    cache_dir = str(tmp_path / "cache")
    adapter = CacheAdapter(cache_dir=cache_dir)
    
    path = adapter.get_cache_path("https://api-football.v3.com/teams", {"X-Auth": "123"})
    assert cache_dir in path
    assert path.endswith(".json")

def test_cache_adapter_clear(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "2026-07-21_dummy.json").write_text("{}")
    
    adapter = CacheAdapter(cache_dir=str(cache_dir))
    count = adapter.clear_cache()
    assert count == 1
    assert len(os.listdir(cache_dir)) == 0

def test_ingestor_service():
    from backend.services.ingestion import IngestorService
    service = IngestorService()
    assert service.cache is not None
    assert service.normalizer is not None

