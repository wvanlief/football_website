from backend.services.ingestion import NameNormalizer

def test_normalize_aliases():
    norm = NameNormalizer()
    assert norm.normalize("Czech Republic") == "Czechia"
    assert norm.normalize("Korea Republic") == "South Korea"
    assert norm.normalize("Ivory Coast") == "Côte d'Ivoire"
    assert norm.normalize("Cote d'Ivoire") == "Côte d'Ivoire"
    assert norm.normalize("United States") == "USA"
    assert norm.normalize("Bosnia & Herzegovina") == "Bosnia and Herzegovina"
    assert norm.normalize("Curacao") == "Curaçao"
    assert norm.normalize("  Spain  ") == "Spain"

def test_get_country_code():
    norm = NameNormalizer()
    assert norm.get_country_code("Spain") == "ESP"
    assert norm.get_country_code("Czech Republic") == "CZE"
    assert norm.get_country_code("Ivory Coast") == "CIV"
    assert norm.get_country_code("NonExistentCountry") is None

def test_match_names():
    norm = NameNormalizer()
    # Exact and alias matches
    assert norm.match_names("Czech Republic", "Czechia") is True
    assert norm.match_names("Ivory Coast", "Côte d'Ivoire") is True
    
    # Substring / partial matches
    assert norm.match_names("Arsenal", "Arsenal FC") is True
    assert norm.match_names("Chelsea FC", "Chelsea") is True
    
    # Special team aliases
    assert norm.match_names("Wolves", "Wolverhampton Wanderers") is True
    assert norm.match_names("Wolverhampton", "Wolves") is True
    assert norm.match_names("Nottingham Forest", "Forest") is True
    
    # Negative matches
    assert norm.match_names("Arsenal", "Chelsea") is False
    assert norm.match_names("", "Spain") is False
