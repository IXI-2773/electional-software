from __future__ import annotations

import unittest

from backend.electional.web import render_app
from backend.electional.professional import engine_name


class PythonInterfaceTest(unittest.TestCase):
    def test_render_app_is_server_rendered_without_scripts(self) -> None:
        html = render_app({"preset": ["traditional-lilly"], "location": ["paris"]})

        self.assertIn("Electional Software - Python Interface", html)
        self.assertIn("Traditional Lilly", html)
        self.assertIn("Paris, France", html)
        self.assertIn("No JavaScript required for this screen.", html)
        self.assertIn("Python now owns the interface and chart calculations.", html)
        self.assertIn("Candidate windows", html)
        self.assertIn(engine_name(), html)
        self.assertNotIn("<script", html.lower())

    def test_render_app_falls_back_to_defaults(self) -> None:
        html = render_app({})

        self.assertIn("Transit 1 Degree", html)
        self.assertIn("Los Angeles, CA", html)
        self.assertIn("Python interface", html)


if __name__ == "__main__":
    unittest.main()
