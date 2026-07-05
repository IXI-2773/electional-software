from __future__ import annotations

import unittest

from backend.electional.analysis.playbooks import build_event_playbook


class PlaybookTest(unittest.TestCase):
    def test_playbook_exam(self) -> None:
        playbook = build_event_playbook("Exam")
        self.assertEqual(playbook.objective_type, "exam")
        self.assertTrue(playbook.before_window)

    def test_playbook_legal(self) -> None:
        self.assertIn("Legal", build_event_playbook("Legal notice").title)

    def test_playbook_business_launch(self) -> None:
        self.assertIn("Business", build_event_playbook("Business launch").title)

    def test_playbook_relationship(self) -> None:
        self.assertIn("Relationship", build_event_playbook("Relationship message").title)

    def test_playbook_unknown_general(self) -> None:
        self.assertIn("General", build_event_playbook("Unknown").title)

    def test_playbook_contains_action_moment(self) -> None:
        playbook = build_event_playbook("Exam")
        self.assertTrue(any("officially begins" in note for note in playbook.timing_notes))


if __name__ == "__main__":
    unittest.main()
