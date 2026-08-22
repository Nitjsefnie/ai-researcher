import contextlib
import io
import os
import pathlib
import unittest

from playwright.sync_api import sync_playwright

import build

# This box has a system Chromium and no playwright-managed browser; CI has the
# reverse (`playwright install chromium`). Prefer whatever is actually present
# rather than hard-coding one of them — passing executable_path=None makes
# playwright use its own download. CHROMIUM_PATH overrides both.
CHROMIUM = os.environ.get("CHROMIUM_PATH") or "/usr/bin/chromium"
CHROMIUM_EXECUTABLE = CHROMIUM if pathlib.Path(CHROMIUM).exists() else None


class BrowserInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=CHROMIUM_EXECUTABLE,
            headless=True,
            args=["--no-sandbox"],
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_non_frontier_points_pin_a_visible_name_on_capability_charts(self):
        for metric in ("coding", "agentic"):
            with self.subTest(metric=metric):
                page = self.browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(build.OUT.as_uri())
                point = page.locator(f"#svg-{metric} circle.pt[r='5']").first
                point.hover()
                model_name = page.locator(f"#tip-{metric} .tname").inner_text()

                point.click()

                labels = page.locator(f"#svg-{metric} text.lbl").all_text_contents()
                self.assertIn(model_name, labels)
                page.close()

    def test_chart_points_and_sort_headers_are_keyboard_operable(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())

        point = page.locator("#svg-coding circle.pt[r='5']").first
        point.hover()
        model_name = page.locator("#tip-coding .tname").inner_text()
        accessible_name = f"Pin {model_name} on the Coding Index chart"
        point.focus()
        point.press("Enter")
        point = page.get_by_role("button", name=accessible_name)
        self.assertEqual(point.get_attribute("aria-pressed"), "true")
        self.assertEqual(
            page.evaluate("document.activeElement.getAttribute('aria-label')"),
            accessible_name,
        )
        self.assertIn(
            model_name,
            page.locator("#svg-coding text.lbl").all_text_contents(),
        )
        point.press("Space")
        point = page.get_by_role("button", name=accessible_name)
        self.assertEqual(point.get_attribute("aria-pressed"), "false")
        self.assertEqual(
            page.evaluate("document.activeElement.getAttribute('aria-label')"),
            accessible_name,
        )

        header = page.locator("#tbl th[data-k='codingScore']")
        self.assertEqual(header.get_attribute("tabindex"), "0")
        self.assertEqual(header.get_attribute("aria-sort"), "none")
        header.press("Enter")
        self.assertEqual(header.get_attribute("aria-sort"), "descending")
        header.press("Space")
        self.assertEqual(header.get_attribute("aria-sort"), "ascending")
        page.close()

    def test_parameter_chart_has_shared_interactions_and_parameter_tooltip(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())

        point = page.locator("#svg-parameters circle.pt").first
        point.hover()
        model_name = page.locator("#tip-parameters .tname").inner_text()
        tooltip = page.locator("#tip-parameters").inner_text()
        self.assertIn("Parameters", tooltip)
        self.assertIn("Intelligence Index", tooltip)

        accessible_name = f"Pin {model_name} on the Parameter efficiency chart"
        point.focus()
        point.press("Enter")
        pinned = page.get_by_role("button", name=accessible_name)
        self.assertEqual(pinned.get_attribute("aria-pressed"), "true")
        self.assertIn(
            model_name,
            page.locator("#svg-parameters text.lbl").all_text_contents(),
        )

        page.locator("#fQ").fill(model_name)
        self.assertEqual(page.locator("#svg-parameters circle.pt").count(), 1)
        page.close()

    def test_parameter_frontier_is_exposed_in_accessible_table(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())

        frontier_point = page.locator("#svg-parameters circle.pt[r='6']").first
        frontier_point.hover()
        model_name = page.locator("#tip-parameters .tname").inner_text()
        row = page.locator("#tbl tbody tr").filter(has_text=model_name)

        self.assertEqual(
            row.locator("td").nth(6).locator(".tag.f").inner_text(),
            "parameter frontier",
        )
        page.close()


if __name__ == "__main__":
    unittest.main()
