import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app


class FoundationTest(unittest.TestCase):
    def test_image_requires_local_origin_and_jpeg(self):
        jpeg = bytes.fromhex("ffd8ffd9")
        headers = {"content-type": "image/jpeg"}
        with TestClient(app) as client, patch("app.check_live", return_value="Spines visible.") as live:
            client.post("/test-image", headers=headers, content=jpeg)
            headers["origin"] = "http://127.0.0.1:8000"
            client.post("/test-image", headers=headers, content=b"invalid")
            live.assert_not_awaited()
            result = client.post("/test-image", headers=headers, content=jpeg)
            self.assertEqual(result.json()["message"], "Gemini Live transcript: Spines visible.")
            live.assert_awaited_once_with(request_reply=True, image=jpeg, inventory=False)
            live.reset_mock()
            client.post("/test-image?inventory=true", headers=headers, content=jpeg)
            live.assert_awaited_once_with(request_reply=True, image=jpeg, inventory=True)

    def test_live_command(self):
        with TestClient(app) as client, patch("app.check_live", return_value="Ready to scan.") as live:
            with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8000"}) as socket:
                socket.send_text("test_live")
                self.assertEqual(socket.receive_json(), {
                    "type": "live_result",
                    "message": "Gemini Live transcript: Ready to scan.",
                })
            live.assert_awaited_once_with(request_reply=True)

    def test_page_and_mock_inventory(self):
        with TestClient(app) as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Load mock inventory", page.text)
            with client.websocket_connect("/ws") as socket:
                socket.send_text("unknown")
                self.assertEqual(socket.receive_json()["type"], "error")
                for _ in range(2):
                    socket.send_text("scan")
                    result = socket.receive_json()
                    self.assertEqual(result["type"], "inventory")
                    self.assertEqual(result["mode"], "mock")
                    books = result["books"]
                    self.assertEqual(len(books), 27)
                    self.assertEqual(len({book["id"] for book in books}), 27)
                    self.assertEqual(books[0]["title"], "测试书 1")
                    self.assertEqual(books[-1]["title"], "Test Book 13")
