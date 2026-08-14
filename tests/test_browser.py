import contextlib
import io
import unittest

from playwright.sync_api import sync_playwright

import build


class BrowserInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path="/usr/bin/chromium",
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


if __name__ == "__main__":
    unittest.main()
