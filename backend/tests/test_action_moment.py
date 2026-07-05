from __future__ import annotations

import unittest

from backend.electional.analysis.action_moment import resolve_action_moment


class ActionMomentTest(unittest.TestCase):
    def test_action_moment_email(self) -> None:
        action = resolve_action_moment("Email message")
        self.assertIn("message is sent", action.elected_moment)
        self.assertIn("Scheduled send", action.warnings[0])

    def test_action_moment_exam(self) -> None:
        action = resolve_action_moment("Exam / certification")
        self.assertIn("test officially begins", action.elected_moment)

    def test_action_moment_legal_filing(self) -> None:
        action = resolve_action_moment("Legal appeal")
        self.assertIn("submitted", action.elected_moment)

    def test_action_moment_business_launch_public(self) -> None:
        action = resolve_action_moment("Business launch")
        self.assertIn("public launch", action.elected_moment)

    def test_action_moment_purchase(self) -> None:
        action = resolve_action_moment("Purchase payment")
        self.assertIn("payment", action.elected_moment)

    def test_action_moment_relationship_message(self) -> None:
        action = resolve_action_moment("Relationship message")
        self.assertIn("message is sent", action.elected_moment)

    def test_action_moment_unknown_objective(self) -> None:
        action = resolve_action_moment("Unclear thing")
        self.assertIn("irreversible", action.elected_moment)
        self.assertLess(action.confidence, 0.7)

    def test_action_moment_scheduled_send_warning(self) -> None:
        action = resolve_action_moment("message")
        self.assertTrue(any("Scheduled send" in warning for warning in action.warnings))


if __name__ == "__main__":
    unittest.main()
