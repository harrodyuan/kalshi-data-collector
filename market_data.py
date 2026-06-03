import time
import requests
from typing import Dict, List, Optional
from auth_manager import AuthManager

class MarketDataManager:
    # Backoff/retry config for Kalshi rate limits (HTTP 429) and transient 5xx.
    MAX_RETRIES = 6
    BASE_DELAY = 0.25  # seconds between successful requests
    BACKOFF_BASE = 1.0  # initial backoff on 429/5xx (doubles each retry)
    # def __init__(self, auth_manager: AuthManager, base_url: str = "https://trading-api.kalshi.com"):
    # def __init__(self, auth_manager: AuthManager, base_url: str = "https://api.kalshi.com"):
    # def __init__(self, auth_manager: AuthManager, base_url: str = "https://demo-api.kalshi.co"):
    def __init__(self, auth_manager: AuthManager, base_url: str = "https://api.elections.kalshi.com"):
        self.auth = auth_manager
        self.base_url = base_url

    def _request(self, method: str, path: str, params: Optional[Dict] = None) -> Dict:
        """Authenticated GET with exponential backoff on 429/5xx, and a small
        delay between calls to stay within Kalshi rate limits."""
        url = f"{self.base_url}{path}"
        delay = self.BACKOFF_BASE
        for attempt in range(self.MAX_RETRIES):
            headers = self.auth.generate_headers(method, path)
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                print(f"Rate-limited/{response.status_code} on {path}; retry {attempt + 1}/{self.MAX_RETRIES} in {wait:.1f}s")
                time.sleep(wait)
                delay = min(delay * 2, 16.0)
                continue

            if response.status_code == 404:
                print(f"404 Error Details: {response.text}")
            response.raise_for_status()
            time.sleep(self.BASE_DELAY)
            return response.json()

        # Exhausted retries
        response.raise_for_status()
        return response.json()

    def get_events(self, cursor: Optional[str] = None, limit: int = 100, status: Optional[str] = None) -> Dict:
        """Get available events with pagination support."""
        path = "/trade-api/v2/events"
        # Simple params - just limit, cursor, and status
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status

        print(f"Making request to: {self.base_url}{path}")
        return self._request("GET", path, params)  # Raw response includes events and cursor

    def get_markets(self, event_ticker: Optional[str] = None) -> Dict:
        """Get markets for an event."""
        path = "/trade-api/v2/markets"
        params = {}
        if event_ticker:
            params['event_ticker'] = event_ticker

        print(f"Making request to: {self.base_url}{path} with params: {params}")
        return self._request("GET", path, params)

    def get_all_markets(self, status: Optional[str] = "open", limit: int = 1000) -> List[Dict]:
        """Bulk-fetch all markets via cursor pagination (one call per `limit`
        markets) instead of one call per event. Much faster at scale."""
        path = "/trade-api/v2/markets"
        markets: List[Dict] = []
        cursor: Optional[str] = None
        page = 1
        while True:
            params = {"limit": limit}
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            data = self._request("GET", path, params)
            batch = data.get("markets", [])
            markets.extend(batch)
            print(f"markets page {page}: fetched {len(batch)} (total {len(markets)})")
            new_cursor = data.get("cursor")
            if not batch or not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor
            page += 1
        return markets

    def get_market_orderbook(self, ticker: str, depth: int = 5) -> Dict:
        """Get orderbook for a specific market with specified depth."""
        path = f"/trade-api/v2/markets/{ticker}/orderbook"
        params = {"depth": depth}  # Add depth parameter to show top N levels

        print(f"Requesting orderbook from: {self.base_url}{path}")
        return self._request("GET", path, params)
