import re
from typing import Optional, Dict

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
    "Türkiye": "TUR",
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
    "Sweden": "SWE",
    "Greece": "GRE",
    "Romania": "ROU",
    "Hungary": "HUN",
    "Slovakia": "SVK",
    "Slovenia": "SVN",
    "Albania": "ALB",
    "Georgia": "GEO",
    "Ireland": "IRL",
    "Republic of Ireland": "IRL",
    "Northern Ireland": "NIR",
    "Finland": "FIN",
    "Iceland": "ISL",
    "North Macedonia": "MKD",
    "Montenegro": "MNE",
    "Bulgaria": "BUL",
    "Israel": "ISR",
    "Cyprus": "CYP",
    "Luxembourg": "LUX",
    "Armenia": "ARM",
    "Azerbaijan": "AZE",
    "Kazakhstan": "KAZ",
    "Nigeria": "NGA",
    "Cameroon": "CMR",
    "Mali": "MLI",
    "DR Congo": "COD",
    "Congo DR": "COD",
    "Burkina Faso": "BFA",
    "Guinea": "GUI",
    "Zambia": "ZAM",
    "Angola": "ANG",
    "Costa Rica": "CRC",
    "Honduras": "HON",
    "El Salvador": "SLV",
    "Trinidad and Tobago": "TRI",
    "Guatemala": "GUA",
    "United Arab Emirates": "UAE",
    "UAE": "UAE",
    "China": "CHN",
    "India": "IND",
    "Oman": "OMA",
    "Bahrain": "BHR",
    "Thailand": "THA",
    "Vietnam": "VIE",
    "Indonesia": "IDN",
}

# National-team spelling variants plus club names used in the UEFA draw JSON
# that differ from API-Football / ClubElo canonical names.
TEAM_NAME_ALIASES = {
    "Korea Republic": "South Korea",
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegov.": "Bosnia and Herzegovina",
    "Bosnia & Herz.": "Bosnia and Herzegovina",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Ivory Coast": "Côte d'Ivoire",
    "Curacao": "Curaçao",
    "United States": "USA",
    "Club Brugge": "Club Brugge KV",
    "Bayern Munich": "Bayern München",
    "Paris Saint-Germain": "Paris Saint Germain",
    "Atletico Madrid": "Atlético Madrid",
    "Atletico de Madrid": "Atlético Madrid",
    "Atlético de Madrid": "Atlético Madrid",
    "Club Atlético de Madrid": "Atlético Madrid",
    "Bodo/Glimt": "Bodø/Glimt",
    "ŠK Slovan Bratislava": "Slovan Bratislava",
    "SK Slovan Bratislava": "Slovan Bratislava",
    "Inter Milan": "Inter",
    "Young Boys": "BSC Young Boys",
    "FC Salzburg": "Red Bull Salzburg",
    "Crvena Zvezda": "FK Crvena Zvezda",
    "Red Star Belgrade": "FK Crvena Zvezda",
    "Sparta Prague": "Sparta Praha",
    "Brest": "Stade Brestois 29",
    "Como 1907": "Como",
    "Man United": "Manchester United",
    "Manchester United FC": "Manchester United",
    "PSV": "PSV Eindhoven",
    "Bayern": "Bayern München",
    "Shaktar": "Shakhtar Donetsk",
    "Shakhtar": "Shakhtar Donetsk",
    "Atleti": "Atlético Madrid",
    "Porto": "FC Porto",
    "Braga": "SC Braga",
    "Arsenal FC": "Arsenal",
}


class NameNormalizer:
    """
    Provides team name normalization, ISO country code mapping, and fuzzy name matching.
    Implemented as a module singleton so all callers share the same cached instance.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(NameNormalizer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, iso_map: Optional[Dict[str, str]] = None):
        if getattr(self, "_initialized", False):
            return
        self.iso_map = iso_map if iso_map is not None else COUNTRY_ISO_MAP
        self._initialized = True

    def get_country_code(self, team_name: str) -> Optional[str]:
        """
        Returns the 3-letter ISO country code for a national team, or None if not found.
        """
        if not team_name:
            return None
        cleaned = self.normalize(team_name)
        return self.iso_map.get(cleaned) or self.iso_map.get(team_name.strip())

    def normalize(self, name: str) -> str:
        """
        Standardizes team name by stripping whitespace and mapping known alias variants.
        """
        if not name:
            return ""
        name = name.strip()
        return TEAM_NAME_ALIASES.get(name, name)

    def lookup_key(self, name: str) -> str:
        """Comparable club key: aliases, trailing years, and FC/SC prefixes stripped."""
        n = self.normalize(name)
        n = re.sub(r"\s+\d{4}$", "", n).strip().lower()
        for prefix in ("fc ", "sc ", "ac ", "as ", "fk ", "sk ", "rb ", "rc ", "us "):
            if n.startswith(prefix):
                n = n[len(prefix):]
                break
        for suffix in (" fc", " cf", " sc", " afc", " kv"):
            if n.endswith(suffix):
                n = n[: -len(suffix)]
                break
        return " ".join(n.split())

    def match_names(self, db_name: str, api_name: str) -> bool:
        """
        Compares two team names for equivalence, handling alias normalization,
        substring matching, and special team aliases (e.g. Wolves / Wolverhampton).
        """
        if not db_name or not api_name:
            return False

        norm1 = self.normalize(db_name).lower()
        norm2 = self.normalize(api_name).lower()

        if norm1 == norm2 or norm1 in norm2 or norm2 in norm1:
            return True

        special_pairs = [
            ("wolves", "wolverhampton"),
            ("nottingham", "forest"),
        ]
        for term1, term2 in special_pairs:
            if (term1 in norm1 and term2 in norm2) or (term2 in norm1 and term1 in norm2):
                return True

        return False


default_normalizer = NameNormalizer()

