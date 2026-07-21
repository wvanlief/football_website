import os
import json
import hashlib
import base64
from datetime import datetime, timezone
from typing import Any, Optional, Dict

from backend.utils import fetch_url_with_retry, fetch_json_with_retry

# 3-Letter ISO Country Code Mapping for National Teams
COUNTRY_ISO_MAP: Dict[str, str] = {
    "Spain": "ESP",
    "Argentina": "ARG",
    "France": "FRA",
    "England": "ENG",
    "Brazil": "BRA",
    "Portugal": "POR",
    "Colombia": "COL",
    "Netherlands": "NED",
    "Germany": "GER",
    "Norway": "NOR",
    "Japan": "JPN",
    "Turkey": "TUR",
    "Uruguay": "URU",
    "Switzerland": "SUI",
    "Senegal": "SEN",
    "Mexico": "MEX",
    "USA": "USA",
    "United States": "USA",
    "Canada": "CAN",
    "Morocco": "MAR",
    "Algeria": "ALG",
    "Croatia": "CRO",
    "Ecuador": "ECU",
    "Austria": "AUT",
    "Paraguay": "PAR",
    "South Korea": "KOR",
    "Korea Republic": "KOR",
    "Australia": "AUS",
    "Scotland": "SCO",
    "Iran": "IRN",
    "Uzbekistan": "UZB",
    "Qatar": "QAT",
    "South Africa": "RSA",
    "Haiti": "HAI",
    "Curaçao": "CUW",
    "Cape Verde": "CPV",
    "Panama": "PAN",
    "Ghana": "GHA",
    "New Zealand": "NZL",
    "Jordan": "JOR",
    "Czechia": "CZE",
    "Czech Republic": "CZE",
    "Bosnia and Herzegovina": "BIH",
    "Côte d'Ivoire": "CIV",
    "Ivory Coast": "CIV",
    "Tunisia": "TUN",
    "Poland": "POL",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Saudi Arabia": "KSA",
    "Iraq": "IRQ",
    "Jamaica": "JAM",
    "Italy": "ITA",
    "Denmark": "DEN",
    "Serbia": "SRB",
    "Ukraine": "UKR",
    "Wales": "WAL",
    "Chile": "CHI",
    "Peru": "PER",
    "Venezuela": "VEN",
    "Bolivia": "BOL",
}

class CacheAdapter:
    """
    Adapter providing local filesystem caching for API requests.
    Supports date-prefixed namespacing and explicit cache control.
    """
    def __init__(self, cache_dir: str = os.path.join("backend", "data", "cache")):
        self.cache_dir = cache_dir

    def get_cache_path(self, url: str, headers: Optional[dict] = None) -> str:
        headers_str = json.dumps(headers or {}, sort_keys=True)
        hash_input = f"{url}||{headers_str}".encode('utf-8')
        h = hashlib.md5(hash_input).hexdigest()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{today}_{h}.json"
        return os.path.join(self.cache_dir, filename)

    def fetch_json(self, url: str, headers: Optional[dict] = None, use_cache: bool = True) -> Any:
        return fetch_json_with_retry(url, headers=headers, use_cache=use_cache)

    def is_cached(self, url: str, headers: Optional[dict] = None) -> bool:
        path = self.get_cache_path(url, headers)
        return os.path.exists(path)

    def clear_cache(self) -> int:
        """Clears all cached files in the cache directory."""
        if not os.path.exists(self.cache_dir):
            return 0
        count = 0
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                count += 1
        return count


class NameNormalizer:
    """
    Provides team name normalization and ISO country code mapping.
    """
    def __init__(self, iso_map: Optional[Dict[str, str]] = None):
        self.iso_map = iso_map if iso_map is not None else COUNTRY_ISO_MAP

    def get_country_code(self, team_name: str) -> Optional[str]:
        """
        Returns the 3-letter ISO country code for a national team, or None if not found.
        """
        if not team_name:
            return None
        cleaned = team_name.strip()
        return self.iso_map.get(cleaned)

    def normalize(self, name: str) -> str:
        """
        Standardizes team name by stripping whitespace and mapping known alias variants.
        """
        if not name:
            return ""
        name = name.strip()
        alias_map = {
            "Korea Republic": "South Korea",
            "Czech Republic": "Czechia",
            "Ivory Coast": "Côte d'Ivoire",
            "United States": "USA",
        }
        return alias_map.get(name, name)


class IngestorService:
    """
    High-level service interface for data ingestion and database seeding.
    """
    def __init__(self, cache_adapter: Optional[CacheAdapter] = None, normalizer: Optional[NameNormalizer] = None):
        self.cache = cache_adapter or CacheAdapter()
        self.normalizer = normalizer or NameNormalizer()

    def seed_world_cup(self, db):
        from backend.ingestor import seed_database
        return seed_database(db)

    def seed_competition(self, db, competition_name: str, season: str):
        from backend.ingestor import seed_competition
        return seed_competition(db, competition_name, season)

