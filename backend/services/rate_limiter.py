import time
import threading
from collections import defaultdict
from typing import Dict

class APIRateLimiter:
    """
    Thread-safe singleton rate limiter supporting both per-minute and per-day quotas.
    Enforces user-configured aggressive safeguards to prevent external API quota exhaustion.
    """
    LIMITS: Dict[str, Dict[str, int]] = {
        "api_football": {"per_min": 10, "per_day": 100},
        "football_data_org": {"per_min": 10, "per_day": 100},
        "the_odds_api": {"per_min": 2, "per_day": 30},
        "clubelo": {"per_min": 2, "per_day": 20},
        "eloratings": {"per_min": 2, "per_day": 20},
    }

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.min_history = defaultdict(list)
                    cls._instance.day_history = defaultdict(list)
        return cls._instance

    def try_call(self, provider: str) -> bool:
        """
        Checks if a call to the specified provider is allowed under minute and daily quotas.
        If allowed, records the call timestamp and returns True.
        If quota is reached, logs a warning and returns False.
        """
        with self._lock:
            now = time.time()
            min_cutoff = now - 60
            day_cutoff = now - 86400

            # Prune expired timestamps
            self.min_history[provider] = [t for t in self.min_history[provider] if t > min_cutoff]
            self.day_history[provider] = [t for t in self.day_history[provider] if t > day_cutoff]

            limits = self.LIMITS.get(provider, {"per_min": 1, "per_day": 50})

            if len(self.min_history[provider]) >= limits["per_min"]:
                print(f"⚠️ RATE LIMIT SAFEGUARD: '{provider}' minute quota reached ({limits['per_min']}/min). Network call skipped.")
                return False

            if len(self.day_history[provider]) >= limits["per_day"]:
                print(f"⚠️ RATE LIMIT SAFEGUARD: '{provider}' daily quota reached ({limits['per_day']}/day). Network call skipped.")
                return False

            self.min_history[provider].append(now)
            self.day_history[provider].append(now)
            return True

    def reset(self):
        """Clears call history (useful for testing)."""
        with self._lock:
            self.min_history.clear()
            self.day_history.clear()

rate_limiter = APIRateLimiter()
