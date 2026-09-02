from backend.services.ingestion import NameNormalizer, default_normalizer, COUNTRY_ISO_MAP
from backend.services.elo import elo_to_form

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

def test_name_normalizer_singleton():
    n1 = NameNormalizer()
    n2 = NameNormalizer()
    assert n1 is n2
    assert default_normalizer is n1

def test_elo_to_form():
    # Base case: default ELO 1500 -> 50.0
    assert elo_to_form(1500) == 50.0
    assert elo_to_form(None) == 50.0

    # Intermediate calculations
    assert elo_to_form(2000) == 75.0  # 50 + (500 * 0.05) = 75.0
    assert elo_to_form(1800) == 65.0  # 50 + (300 * 0.05) = 65.0
    assert elo_to_form(1923) == 71.2  # 50 + (423 * 0.05) = 71.15 -> rounded 71.2

    # Clamping bounds: min 45.0, max 95.0
    assert elo_to_form(1000) == 45.0
    assert elo_to_form(3000) == 95.0

