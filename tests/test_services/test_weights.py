from backend.services.weights import normalize_weights

def test_normalize_weights_standard():
    weights = {"elo": 0.5, "odds": 0.3, "form": 0.2, "narrative": 0.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.5
    assert normalized["odds"] == 0.3
    assert normalized["form"] == 0.2
    assert normalized["narrative"] == 0.0

def test_normalize_weights_all_zero():
    weights = {"elo": 0.0, "odds": 0.0, "form": 0.0, "narrative": 0.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.25
    assert normalized["odds"] == 0.25
    assert normalized["form"] == 0.25
    assert normalized["narrative"] == 0.25

def test_normalize_weights_non_normalized():
    weights = {"elo": 1.0, "odds": 1.0, "form": 1.0, "narrative": 1.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.25
