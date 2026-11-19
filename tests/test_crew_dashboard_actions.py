"""POST /action/<name> (dashboard/plugin_api.py): the Hermes Desktop buttons. One allowlisted name per slash command,
each calling the same crew function the command calls and answering {ok, text}; Stop also needs confirm true."""
import os
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

HERE = os.path.dirname(os.path.abspath(__file__))
CREW_ROOT = os.path.dirname(HERE)
for p in (HERE, CREW_ROOT, os.path.join(CREW_ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dashboard.plugin_api import router  # noqa: E402
from test_crew_dashboard_customization import RealBoardCase  # noqa: E402
import kernel_board  # noqa: E402

API = "/api/plugins/crew"


class ActionRouteTests(RealBoardCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix=API)
        self.client = TestClient(app)
        import crew_card
        import crew_stop
        self.crew_card, self.crew_stop = crew_card, crew_stop

    def post(self, name, body):
        return self.client.post(API + "/action/" + name, json=body)

    def test_only_the_four_names_exist(self):
        for bad in ("safety", "exec", "..", "Unstuck", "ack"):
            r = self.post(bad, {"card": self.card})
            self.assertIn(r.status_code, (400, 404), bad)
        r = self.post("exec", {"card": self.card})
        self.assertEqual((r.status_code, r.json()["ok"]), (400, False))

    def test_bad_card_id_is_400_before_any_function_runs(self):
        with patch.object(self.crew_card, "unstuck_card") as fn:
            for body in ({}, {"card": ""}, {"card": "../x"}, {"card": "a b"}, {"card": 7}, {"card": "t_x.json"}):
                r = self.post("unstuck", body)
                self.assertEqual((r.status_code, r.json()["ok"]), (400, False), body)
            fn.assert_not_called()

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(API + "/action/unstuck").status_code, 405)

    def test_unstuck_calls_unstuck_card(self):
        with patch.object(self.crew_card, "unstuck_card", return_value=(True, "t_1: blocked -> ready")) as fn:
            r = self.post("unstuck", {"card": self.blocked})
        fn.assert_called_once_with(self.blocked)
        self.assertEqual(r.json(), {"ok": True, "text": "t_1: blocked -> ready"})
        with patch.object(self.crew_card, "unstuck_card", return_value=(False, "nothing to unstick")):
            self.assertEqual(self.post("unstuck", {"card": self.card}).json(), {"ok": False, "text": "nothing to unstick"})

    def test_unstuck_runs_the_real_function_on_a_missing_card(self):
        r = self.post("unstuck", {"card": "t_nosuchcard"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": False, "text": "no such card: t_nosuchcard"})

    def test_retry_calls_retry_card_with_its_defaults(self):
        res = {"ok": True, "card": "t_1", "status": "blocked", "assignee": "w", "spent": 10, "budget": 250000,
               "dry_run": False, "ledgers_moved": 1, "unblock": {"out": "ok", "rc": 0}}
        with patch.object(self.crew_card, "retry_card", return_value=res) as fn:
            r = self.post("retry", {"card": self.blocked}).json()
        args, kwargs = fn.call_args
        self.assertEqual(args, (self.blocked,))
        self.assertEqual(set(kwargs), {"profile"})
        self.assertTrue(r["ok"])
        self.assertIn("new ceiling: 250,000 tokens", r["text"])
        with patch.object(self.crew_card, "retry_card", return_value={"ok": False, "why": "no such card: t_9"}):
            self.assertEqual(self.post("retry", {"card": "t_9"}).json(), {"ok": False, "text": "no such card: t_9"})

    def test_proof_modes(self):
        with patch.object(self.crew_card, "owner_proof_answer", return_value="confirmed proof for t_1: ./p (brave); card ready") as fn:
            r = self.post("proof", {"card": self.card, "mode": "brave"}).json()
            fn.assert_called_once_with(self.card, brave=True)
        self.assertTrue(r["ok"])
        with patch.object(self.crew_card, "owner_proof_answer", return_value="no open proof question on t_1") as fn:
            r = self.post("proof", {"card": self.card}).json()   # no mode: the plain yes
            fn.assert_called_once_with(self.card, brave=False)
        self.assertEqual(r, {"ok": False, "text": "no open proof question on t_1"})
        self.assertEqual(self.post("proof", {"card": self.card, "mode": "rm"}).status_code, 400)

    def test_stop_needs_confirm_true(self):
        with patch.object(self.crew_stop, "run") as fn:
            for body in ({"card": self.card}, {"card": self.card, "confirm": False}, {"card": self.card, "confirm": "yes"}):
                r = self.post("stop", body)
                self.assertEqual((r.status_code, r.json()["ok"]), (400, False), body)
            fn.assert_not_called()

    def test_stop_calls_crew_stop_for_the_one_card(self):
        with patch.object(self.crew_stop, "run", return_value=(0, "stop: 1 card(s), 1 run(s) killed")) as fn:
            r = self.post("stop", {"card": self.card, "confirm": True})
        fn.assert_called_once_with([self.card])
        self.assertEqual(r.json(), {"ok": True, "text": "stop: 1 card(s), 1 run(s) killed"})
        with patch.object(self.crew_stop, "run", return_value=(1, "NOT DOWN")):
            self.assertEqual(self.post("stop", {"card": self.card, "confirm": True}).json(), {"ok": False, "text": "NOT DOWN"})

    def test_stop_on_a_missing_card_says_so(self):
        r = self.post("stop", {"card": "t_nosuchcard", "confirm": True})   # the real stop pass, a card it does not know
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["ok"])

    def test_a_raising_function_answers_ok_false_without_the_exception_text(self):
        with patch.object(self.crew_card, "unstuck_card", side_effect=OSError("db gone")):
            from dashboard import plugin_api
            with self.assertLogs(plugin_api._log, "ERROR") as logs:
                r = self.post("unstuck", {"card": self.card})
        self.assertEqual((r.status_code, r.json()), (200, {"ok": False, "text": "unstuck failed - see the dashboard log"}))
        self.assertNotIn("db gone", r.text)              # the exception's own words stay in the log (py/stack-trace-exposure)
        self.assertTrue(any("db gone" in line for line in logs.output), logs.output)


if __name__ == "__main__":
    unittest.main()


class CreateAndMoveRouteTests(RealBoardCase):
    """POST /cards and POST /cards/move: the board-operations routes the UI's New-card form, the
    Archive action, the Move picker and agents share (docs/board-operations-design.md)."""

    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix=API)
        self.client = TestClient(app)
        import crew_card
        self.crew_card = crew_card

    def post(self, name, body):
        return self.client.post(API + "/action/" + name, json=body)

    # --- the archive action ---
    def test_archive_calls_archive_card(self):
        with patch.object(self.crew_card, "archive_card", return_value=(True, "t_1 archived")) as fn:
            r = self.post("archive", {"card": self.card})
        fn.assert_called_once_with(self.card)
        self.assertEqual(r.json(), {"ok": True, "text": "t_1 archived"})

    def test_archive_refuses_a_running_card_without_a_subprocess(self):
        running = kernel_board.add_card(self.conn, title="live one")
        self.conn.execute("UPDATE tasks SET status='running', worker_pid=99 WHERE id = ?", (running,))
        self.conn.commit()
        with patch.object(self.crew_card, "_kanban") as kan:
            r = self.post("archive", {"card": running})
        kan.assert_not_called()
        self.assertFalse(r.json()["ok"])
        self.assertIn("stop it first", r.json()["text"])

    def test_archive_missing_card(self):
        self.assertEqual(self.post("archive", {"card": "t_nosuchcard"}).json(),
                         {"ok": False, "text": "no such card: t_nosuchcard"})

    # --- POST /cards ---
    def test_create_needs_board_and_title(self):
        self.assertEqual(self.client.post(API + "/cards", json={"title": "x"}).status_code, 400)
        self.assertEqual(self.client.post(API + "/cards", json={"board": "bogus", "title": "x"}).status_code, 404)
        r = self.client.post(API + "/cards", json={"board": "default", "title": "  "})
        self.assertEqual((r.status_code, r.json()["ok"]), (400, False))

    def test_create_spawns_the_cli_with_the_board_flag(self):
        with patch.object(self.crew_card.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{"id": "t_1", "title": "do it"}'
            r = self.client.post(API + "/cards", json={
                "title": "do it", "board": "default", "body": "goal\n- done: yes",
                "assignee": "crew-worker", "model": "GLM", "priority": 3, "created_by": "ui:me",
                "idempotency_key": "retry-1"})
        argv = run.call_args[0][0]
        self.assertEqual(argv[argv.index("--board") + 1], "default")
        for flag in ("--json", "--body-file", "--assignee", "--model", "--priority", "--created-by", "--idempotency-key"):
            self.assertIn(flag, argv, flag)
        self.assertEqual(run.call_args[1]["input"], "goal\n- done: yes")     # the body rides stdin, verbatim
        self.assertEqual(r.json(), {"ok": True, "board": "default", "card": {"id": "t_1", "title": "do it"}})

    def test_create_answers_the_cli_refusal(self):
        with patch.object(self.crew_card.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "unknown assignee"
            r = self.client.post(API + "/cards", json={"board": "default", "title": "x", "assignee": "nope"})
        self.assertEqual((r.status_code, r.json()["ok"]), (400, False))
        self.assertIn("unknown assignee", r.json()["text"])

    # --- POST /cards/move ---
    def test_move_needs_card_and_target(self):
        self.assertEqual((self.client.post(API + "/cards/move", json={"card": self.card}).status_code), 400)
        r = self.client.post(API + "/cards/move", json={"card": "bad id", "to_board": "default"})
        self.assertEqual((r.status_code, r.json()["ok"]), (400, False))

    def test_move_calls_move_card(self):
        with patch.object(self.crew_card, "move_card", return_value=(True, "t_1 moved to b")) as fn:
            r = self.client.post(API + "/cards/move", json={"card": self.card, "to_board": "b", "board": "default"})
        fn.assert_called_once_with(self.card, "b")
        self.assertEqual(r.json(), {"ok": True, "text": "t_1 moved to b", "board": "b", "card": self.card})

    def test_move_on_a_real_card_reached_by_the_body_board(self):
        import sqlite3 as s3
        from pathlib import Path
        import kernel_board as kbmod
        b2 = Path(self.home) / "kanban" / "boards" / "b2"
        b2.mkdir(parents=True, exist_ok=True)
        (b2 / "board.json").write_text('{"slug": "b2", "name": "B2"}', encoding="utf-8")   # the identity marker
        kbmod.kbc.connect(b2 / "kanban.db")            # the target board's db, same schema
        # the source board rides the body exactly like the UI sends it
        r = self.client.post(API + "/cards/move", json={"card": self.card, "to_board": "b2", "board": "default"})
        body = r.json()
        self.assertTrue(body["ok"], body)
        live = s3.connect("file:%s?mode=ro" % (b2 / "kanban.db"), uri=True)
        moved = live.execute("SELECT status FROM tasks WHERE id = ?", (self.card,)).fetchone()
        live.close()
        self.assertEqual(moved[0], "ready")             # the live card is on b2 now
        here = s3.connect("file:%s?mode=ro" % os.environ["KANBAN_DB"], uri=True)
        src = here.execute("SELECT status FROM tasks WHERE id = ?", (self.card,)).fetchone()
        here.close()
        if "could not be archived" in body["text"]:
            self.assertEqual(src[0], "ready")           # HERMES_BIN=/bin/false: the CLI step failed
        else:
            self.assertEqual(src[0], "archived")        # a real hermes binary: the trail is archived
