"""Task 2 tests: Notion API client — auth, metadata fetch, pagination, retry."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from unittest.mock import patch, MagicMock
import requests

TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "15426c37bff781f9b6b5ead5af23a85f")


def make_response(status, body, headers=None):
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.ok = status < 300
    r.json.return_value = body
    r.text = str(body)
    r.headers = headers or {}
    return r


class TestNotionClient(unittest.TestCase):

    def test_auth_live(self):
        if not TOKEN:
            self.skipTest("NOTION_TOKEN not set")
        from notion_exporter.notion_client import NotionClient
        client = NotionClient(TOKEN)
        me = client.get("/users/me")
        self.assertIsNotNone(me, "GET /users/me returned None")
        self.assertIn("type", me, "Response missing 'type' key")
        print(f"  Authenticated as: {me.get('name', me.get('id'))}")

    def test_database_metadata_live(self):
        if not TOKEN:
            self.skipTest("NOTION_TOKEN not set")
        from notion_exporter.notion_client import NotionClient
        client = NotionClient(TOKEN)
        data = client.get(f"/databases/{DATABASE_ID}")
        self.assertIsNotNone(data)
        self.assertIn("properties", data)
        print(f"  Database has {len(data['properties'])} properties")

    def test_retry_on_429(self):
        from notion_exporter.notion_client import NotionClient
        client = NotionClient("fake-token")

        rate_limit_resp = make_response(429, {}, headers={"Retry-After": "0"})
        ok_resp = make_response(200, {"object": "user", "type": "bot"})

        with patch("requests.request", side_effect=[rate_limit_resp, ok_resp]) as mock_req:
            with patch("time.sleep"):
                result = client.get("/users/me")
        self.assertIsNotNone(result)
        self.assertEqual(mock_req.call_count, 2)
        print("  PASS: 429 → retry → success")

    def test_non_2xx_returns_none(self):
        from notion_exporter.notion_client import NotionClient
        client = NotionClient("bad-token")
        bad_resp = make_response(401, {"message": "Unauthorized"})
        with patch("requests.request", return_value=bad_resp):
            result = client.get("/users/me")
        self.assertIsNone(result)
        print("  PASS: 401 → None returned")

    def test_pagination_live(self):
        """Fetch all database entries with page_size=10 to exercise pagination."""
        if not TOKEN:
            self.skipTest("NOTION_TOKEN not set")
        from notion_exporter.notion_client import NotionClient
        client = NotionClient(TOKEN)
        results = list(client.paginate_post(
            f"/databases/{DATABASE_ID}/query",
            {"page_size": 10},
        ))
        print(f"  Paginated total: {len(results)} results")
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
