import sys
import time
import requests


class NotionClient:
    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, token):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, body=None):
        return self._request("POST", path, json=body)

    def _request(self, method, path, **kwargs):
        url = f"{self.BASE_URL}{path}"
        for attempt in range(3):
            try:
                resp = requests.request(method, url, headers=self._headers, **kwargs)
            except requests.RequestException as exc:
                print(f"[WARN] API {method} {path}: network error: {exc}", file=sys.stderr)
                return None

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 1))
                print(f"[WARN] Rate limited, retrying in {wait}s (attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(wait)
                continue

            if not resp.ok:
                print(
                    f"[WARN] API {method} {path} returned {resp.status_code}: {resp.text[:300]}",
                    file=sys.stderr,
                )
                return None

            return resp.json()

        print(f"[WARN] API {method} {path}: max retries exceeded", file=sys.stderr)
        return None

    def paginate_post(self, path, body):
        cursor = None
        while True:
            payload = dict(body)
            if cursor:
                payload["start_cursor"] = cursor
            data = self.post(path, payload)
            if data is None:
                break
            yield from data.get("results", [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    def paginate_get(self, path, params=None):
        params = dict(params or {})
        while True:
            data = self.get(path, params)
            if data is None:
                break
            yield from data.get("results", [])
            if not data.get("has_more"):
                break
            params["start_cursor"] = data.get("next_cursor")
