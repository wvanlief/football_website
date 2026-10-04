def normalize_weights(w: dict) -> dict:
    """Normalizes a weights dictionary so the sum equals 1.0."""
    total = w["elo"] + w["odds"] + w["form"] + w["narrative"]
    if total == 0:
        return {k: 0.25 for k in w}
    return {k: w[k] / total for k in w}
