import pytest
from backend.services.ingestion import NameNormalizer, COUNTRY_ISO_MAP

def test_country_code_lookup_valid_national_teams():
    normalizer = NameNormalizer()

    assert normalizer.get_country_code("Spain") == "ESP"
    assert normalizer.get_country_code("Germany") == "GER"
    assert normalizer.get_country_code("England") == "ENG"
    assert normalizer.get_country_code("France") == "FRA"
    assert normalizer.get_country_code("Brazil") == "BRA"
    assert normalizer.get_country_code("Argentina") == "ARG"
    assert normalizer.get_country_code("South Korea") == "KOR"
    assert normalizer.get_country_code("Korea Republic") == "KOR"
    assert normalizer.get_country_code("United States") == "USA"
    assert normalizer.get_country_code("USA") == "USA"
    assert normalizer.get_country_code("Greece") == "GRE"
    assert normalizer.get_country_code("Sweden") == "SWE"
    assert normalizer.get_country_code("Nigeria") == "NGA"
    assert normalizer.get_country_code("Republic of Ireland") == "IRL"
    assert normalizer.get_country_code("Ireland") == "IRL"
    assert normalizer.get_country_code("United Arab Emirates") == "UAE"

def test_country_code_lookup_club_names_returns_none():
    normalizer = NameNormalizer()

    # Club teams must return None instead of faulty sliced substrings (e.g. WOL, NOT, REA)
    assert normalizer.get_country_code("Wolverhampton") is None
    assert normalizer.get_country_code("Wolverhampton Wanderers") is None
    assert normalizer.get_country_code("Nottingham Forest") is None
    assert normalizer.get_country_code("Real Madrid") is None
    assert normalizer.get_country_code("Arsenal") is None
    assert normalizer.get_country_code("Bayern Munich") is None
    assert normalizer.get_country_code("Paris Saint-Germain") is None
    assert normalizer.get_country_code("Juventus") is None

def test_country_code_lookup_empty_or_none():
    normalizer = NameNormalizer()

    assert normalizer.get_country_code("") is None
    assert normalizer.get_country_code(None) is None
    assert normalizer.get_country_code("   ") is None
