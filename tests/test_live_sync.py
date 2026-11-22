"""Regression tests for synchronized Guard, Student and Admin parking records."""
import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class ParkPulseAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.STATE_FILE = Path(cls.temp.name) / "state.json"
        server.ACCOUNTS_FILE = Path(cls.temp.name) / "accounts.json"
        server.DOC = {"revision": 1, "state": server.initial(), "requests": {}}
        server.ACCOUNTS = server.read_accounts()
        server.SESSIONS.clear()
        server.LOGIN_FAILURES.clear()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.worker = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.worker.start()
        cls.base_url = "http://127.0.0.1:" + str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.worker.join(timeout=2)
        cls.temp.cleanup()

    def api(self, path, method="GET", body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        req = Request(
            self.base_url + path,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=7) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def login(self, username, password, portal, role):
        status, document = self.api("/api/auth/login", "POST", {
            "username": username, "password": password,
            "portal": portal, "roleView": role
        })
        self.assertEqual(status, 200, document)
        self.assertEqual(document["user"]["role"], role)
        return document["token"]

    def snapshot(self, token):
        status, doc = self.api("/api/state", token=token)
        self.assertEqual(status, 200, doc)
        return doc

    def assert_count(self, doc, expected_occupied, expected_available):
        state = doc["state"]
        occupied = sum(
            state["bay"][f"S-{num:02}"] == "occupied"
            for num in range(1, state["capacity"] + 1)
        )
        self.assertEqual((occupied, state["capacity"] - occupied),
                         (expected_occupied, expected_available))

    def test_role_routes_and_flowboard_graph(self):
        from pathlib import Path
        root = Path(server.__file__).resolve().parent
        for route in ("/", "/student", "/guard", "/admin", "/flowboard"):
            with urlopen(self.base_url + route, timeout=7) as response:
                self.assertEqual(response.status, 200, route)
                self.assertIn(b"<html", response.read(170).lower())
        status, _ = self.api("/api/state")
        self.assertEqual(status, 401)

        page = (root / "index.html").read_text(encoding="utf-8")
        self.assertIn('<a href="/">Home</a>', page)
        self.assertNotIn('<a href="/flowboard">Flow Board</a>', page)
        portal = (root / "portal.html").read_text(encoding="utf-8")
        self.assertIn('href="/flowboard"', portal)

        board = (root / "FlowBoard.html").read_text(encoding="utf-8")
        begin = board.index("const screens=") + len("const screens=")
        end = board.index(";\nconst edges=", begin)
        edge_begin = board.index("const edges=", end) + len("const edges=")
        edge_end = board.index(";\nconst byId=", edge_begin)
        screens = json.loads(board[begin:end])
        edges = json.loads(board[edge_begin:edge_end])
        ids = {screen["id"] for screen in screens}
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(edges), 31)
        self.assertIn("H00_home", ids)
        self.assertIn("A00_admin_login", ids)
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in edges))
        self.assertIn('class="node-preview-home"', board)
        self.assertIn('id="lightHome"', board)
        self.assertTrue(all(0 <= s["x"] <= 2072 and 0 <= s["y"] <= 2460
                            for s in screens))

    def test_guard_and_admin_changes_reach_all_three_views(self):
        student = self.login("202600001", "DemoStudent#26", "student", "student")
        guard = self.login("guard.demo", "DemoGuard#26", "staff", "guard")
        admin = self.login("admin.demo", "DemoAdmin#26", "staff", "admin")

        tokens = (student, guard, admin)
        initial = [self.snapshot(t) for t in tokens]
        for doc in initial:
            self.assert_count(doc, 20, 14)
            self.assertEqual(doc["state"]["bay"]["S-12"], "available")
        revision = initial[0]["revision"]

        code, updated = self.api("/api/bay", "POST", {
            "space": "S-12", "status": "occupied",
            "requestId": "audit-guard-occupied-01"
        }, guard)
        self.assertEqual(code, 200, updated)
        self.assertTrue(updated["changed"])

        for token in tokens:
            doc = self.snapshot(token)
            self.assert_count(doc, 21, 13)
            self.assertEqual(doc["state"]["bay"]["S-12"], "occupied")
            self.assertEqual(doc["revision"], revision + 1)

        code, duplicate = self.api("/api/bay", "POST", {
            "space": "S-12", "status": "occupied",
            "requestId": "audit-guard-occupied-02"
        }, guard)
        self.assertEqual(code, 200, duplicate)
        self.assertFalse(duplicate["changed"])
        self.assertEqual(self.snapshot(student)["revision"], revision + 1)

        old = self.snapshot(admin)
        corrected = copy.deepcopy(old["state"])
        corrected["bay"]["S-12"] = "available"
        corrected["lastBayAt"] = server.now_ms()
        corrected["lastVerifiedAt"] = server.now_ms()
        corrected["log"].insert(0, {
            "id": "audit-correction-01", "time": server.now_ms(),
            "type": "CORRECTION", "space": "S-12",
            "before": "occupied", "after": "available",
            "actor": "Demo Admin", "note": "Verified physical observation",
            "countAfter": 20
        })
        code, saved = self.api("/api/state", "POST", {
            "revision": old["revision"], "state": corrected
        }, admin)
        self.assertEqual(code, 200, saved)
        self.assertTrue(saved["changed"])

        for token in tokens:
            doc = self.snapshot(token)
            self.assert_count(doc, 20, 14)
            self.assertEqual(doc["state"]["bay"]["S-12"], "available")
            self.assertEqual(doc["revision"], revision + 2)

        code, stale = self.api("/api/state", "POST", {
            "revision": old["revision"], "state": corrected
        }, admin)
        self.assertEqual(code, 409, stale)
        code, forbidden = self.api("/api/state", "POST", {
            "revision": saved["revision"], "state": saved["state"]
        }, student)
        self.assertEqual(code, 403, forbidden)


if __name__ == "__main__":
    unittest.main()
