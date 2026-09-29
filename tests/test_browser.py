import contextlib
import hashlib
import io
import json
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from playwright.sync_api import sync_playwright

import build

# This box has a system Chromium and no playwright-managed browser; CI has the
# reverse (`playwright install chromium`). Prefer whatever is actually present
# rather than hard-coding one of them — passing executable_path=None makes
# playwright use its own download. CHROMIUM_PATH overrides both.
CHROMIUM = os.environ.get("CHROMIUM_PATH") or "/usr/bin/chromium"
CHROMIUM_EXECUTABLE = CHROMIUM if pathlib.Path(CHROMIUM).exists() else None


class BrowserInteractionTests(unittest.TestCase):
    # V8 coverage for the JavaScript ratchet. With JS_COVERAGE_OUT set (the
    # coverage job sets it), every page this class creates records V8 block
    # coverage and its dump joins a class-level list written out when the
    # class tears down; unset, nothing changes. One pytest run then produces
    # both measurements the coverage gates read.
    _coverage_entries = []
    _open_pages = []

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
        cls._coverage_entries = []
        cls._open_pages = []
        original_new_page = cls.browser.new_page

        def new_page(**kwargs):
            page = original_new_page(**kwargs)
            # playwright-python ships no page.coverage wrapper, so the V8
            # block coverage comes straight from Chromium's Profiler domain
            # over a CDP session — the same {url, source,
            # functions[].ranges[]} evidence stop_js_coverage() would have
            # handed back.
            session = page.context.new_cdp_session(page)
            session.send("Debugger.enable")
            session.send("Profiler.enable")
            session.send("Profiler.startPreciseCoverage",
                         {"callCount": True, "detailed": True})
            original_close = page.close

            def close(**close_kwargs):
                # the list holds (page, session) pairs — membership must be
                # tested the same way, or a closed page stays queued for a
                # second, doomed collection in tearDownClass
                if (page, session) in cls._open_pages:
                    cls._open_pages.remove((page, session))
                cls._coverage_entries.extend(
                    cls._collect_coverage(session))
                return original_close(**close_kwargs)

            page.close = close
            cls._open_pages.append((page, session))
            return page

        cls.browser.new_page = new_page

    @classmethod
    def _collect_coverage(cls, session):
        """Take and stop precise V8 coverage; one entry per compiled script."""
        entries = []
        blocks = session.send("Profiler.takePreciseCoverage")["result"]
        for block in blocks:
            try:
                source = session.send(
                    "Debugger.getScriptSource",
                    {"scriptId": block["scriptId"]})["scriptSource"]
            except Exception:
                source = None
            entries.append({
                "url": block.get("url", ""),
                "source": source,
                "functions": block.get("functions", []),
            })
        session.send("Profiler.stopPreciseCoverage")
        session.send("Profiler.disable")
        session.detach()
        return entries

    @classmethod
    def tearDownClass(cls):
        # A test that failed mid-way leaves its page open; take its coverage
        # here so the dump still describes the whole run.
        for _page, session in list(cls._open_pages):
            try:
                cls._coverage_entries.extend(cls._collect_coverage(session))
            except Exception:
                pass
        cls._open_pages.clear()
        dump = os.environ.get("JS_COVERAGE_OUT")
        if dump:
            pathlib.Path(dump).write_text(
                json.dumps(cls._coverage_entries), encoding="utf-8")
        cls.browser.close()
        cls.playwright.stop()

    def first_point(self, page, selector):
        """A point locator that fails SAYING SO rather than timing out.

        `hover()` on a selector that matches nothing waits the full 30s and
        reports a locator timeout -- which is what an emptied chart looked like
        when AA dropped the cost slugs the coding axis was built on. Counting
        first turns that into "the chart is empty", named, in under a second.
        """
        points = page.locator(selector)
        self.assertGreater(
            points.count(), 0,
            f"no points matched {selector!r} -- the chart rendered empty, so "
            "every interaction below would time out instead of failing here")
        return points.first

    def test_non_frontier_points_pin_a_visible_name_on_capability_charts(self):
        for metric in ("coding", "agentic"):
            with self.subTest(metric=metric):
                page = self.browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(build.OUT.as_uri())
                point = self.first_point(page, f"#svg-{metric} circle.pt[r='5']")
                point.hover()
                model_name = page.locator(f"#tip-{metric} .tname").inner_text()

                point.click()

                labels = page.locator(f"#svg-{metric} text.lbl").all_text_contents()
                self.assertIn(model_name, labels)
                page.close()

    def test_chart_points_and_sort_headers_are_keyboard_operable(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())

        point = self.first_point(page, "#svg-coding circle.pt[r='5']")
        point.hover()
        model_name = page.locator("#tip-coding .tname").inner_text()
        accessible_name = f"Pin {model_name} on the Coding Agent Index chart"
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

        point = self.first_point(page, "#svg-parameters circle.pt")
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

        frontier_point = self.first_point(page, "#svg-parameters circle.pt[r='6']")
        frontier_point.hover()
        model_name = page.locator("#tip-parameters .tname").inner_text()
        row = page.locator("#tbl tbody tr").filter(has_text=model_name)

        self.assertEqual(
            row.locator("td").nth(6).locator(".tag.f").inner_text(),
            "parameter frontier",
        )
        page.close()

    def test_superseded_points_draw_de_emphasis_gray_on_all_four_charts(self):
        # The colour rule is stated once for the page (AGENTS.md: superseded
        # models draw in de-emphasis gray), so every off-frontier point draws
        # var(--muted) on every chart, and every legend documents the swatch.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        for chart in ("coding", "intelligence", "agentic", "parameters"):
            with self.subTest(chart=chart):
                off_frontier = page.evaluate(
                    "sel => [...new Set([...document.querySelectorAll(sel)]"
                    ".map(c => c.getAttribute('fill')))]",
                    f"#svg-{chart} circle.pt[r='5']",
                )
                self.assertEqual(off_frontier, ["var(--muted)"])

                # frontier points keep their weights fill -- the gray is a
                # superseded verdict, not a repainting of the whole chart
                on_frontier = page.locator(f"#svg-{chart} circle.pt[r='6']")
                self.assertGreater(on_frontier.count(), 0)
                self.assertNotIn(
                    "var(--muted)",
                    page.evaluate(
                        "sel => [...new Set([...document.querySelectorAll(sel)]"
                        ".map(c => c.getAttribute('fill')))]",
                        f"#svg-{chart} circle.pt[r='6']",
                    ),
                )

                legend = page.locator(f"#{chart} .legend .item").filter(
                    has_text="Superseded"
                )
                self.assertEqual(legend.count(), 1)
                style = legend.locator(".swatch").first.get_attribute("style")
                assert style is not None, "Superseded swatch has no style attribute"
                self.assertIn("var(--muted)", style)
        page.close()

    def test_pinned_names_stay_labelled_on_every_chart(self):
        # #27: a pin is an explicit reader request. The capability charts
        # guarantee a pinned label with a last-resort clamp; the intelligence
        # chart used to drop pinned names the same view kept labelled
        # elsewhere. Every pinned name must be visible on every chart that
        # draws the pinned point. A pin is page-global, so pins made on one
        # chart must also survive wherever the pinned row renders on another.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        chart_labels = {"coding": "Coding Agent Index",
                        "intelligence": "Intelligence Index",
                        "agentic": "GDPval-AA v2",
                        "parameters": "Parameter efficiency"}
        # 40 pins on the intelligence chart -- the crowd the audit used, enough
        # to exhaust the clear slots -- plus a couple on every other chart so
        # each chart guarantees its own pins. Agent-run rows never share names
        # with model rows, so the coding chart can only pin its own rows.
        pin_counts = {"intelligence": 40, "coding": 2, "agentic": 2,
                      "parameters": 2}
        pinned = {}
        already = set()
        for chart, label in chart_labels.items():
            suffix = f" on the {label} chart"
            points = page.locator(f"#svg-{chart} circle.pt")
            aris = page.evaluate(
                "sel => [...document.querySelectorAll(sel)]"
                ".map(c => c.getAttribute('aria-label'))",
                f"#svg-{chart} circle.pt")
            # a pin is keyed by name and page-global, so pinning the same row
            # through a second chart would toggle it OFF again -- pick rows
            # no earlier chart has pinned
            pick = []
            for i, aria in enumerate(aris):
                if not (aria.startswith("Pin ") and aria.endswith(suffix)):
                    continue
                name = aria[len("Pin "):-len(suffix)]
                if name in already:
                    continue
                pick.append((i, name))
                if len(pick) == pin_counts[chart]:
                    break
            self.assertEqual(len(pick), pin_counts[chart],
                             f"could not pick {pin_counts[chart]} fresh names on {chart}")
            for i, _ in pick:
                points.nth(i).focus()
                points.nth(i).press("Enter")
            pinned[chart] = [n for _, n in pick]
            already.update(pinned[chart])

        # every chart labels every one of its own pinned points
        for chart in chart_labels:
            labels = page.locator(f"#svg-{chart} text.lbl").all_text_contents()
            missing = [n for n in pinned[chart] if n not in labels]
            self.assertEqual(
                missing, [],
                f"pinned names dropped on the {chart} chart")

        # and wherever a pinned row renders on ANOTHER chart, its label
        # survives there too (the pin set is page-global)
        for chart, label in chart_labels.items():
            aria = page.evaluate(
                "sel => [...document.querySelectorAll(sel)]"
                ".map(c => c.getAttribute('aria-label'))",
                f"#svg-{chart} circle.pt")
            foreign = {n for names in pinned.values() for n in names
                       if f"Pin {n} on the {label} chart" in aria}
            labels = page.locator(f"#svg-{chart} text.lbl").all_text_contents()
            self.assertEqual(
                [n for n in foreign if n not in labels], [],
                f"cross-chart pinned names dropped on the {chart} chart")
        page.close()

    def test_unpinned_labels_still_refuse_when_no_clear_space(self):
        # #27's flip side, as a guard: the pin fallback must stay pin-only.
        # Thirty-one unpinned models crowd one spot (plus one anchor so the
        # y-scale is not degenerate); the placer offers each label exactly 14
        # candidate offsets from its dot, so at most 15 labels can ever place
        # here whatever the platform's font metrics are -- well under the 31
        # points. If this ever exceeds the bound, unpinned labels have begun
        # overlapping, which the placer is designed to refuse.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        cluster = []
        for i in range(30):
            cluster.append({
                "name": f"Cluster Model {i:02d}",
                "modelCreatorName": "Cluster Lab",
                "isOpenWeights": i % 2 == 0,
                "slug": f"cluster-{i}",
                "intelligenceIndex": 51,
                "gdpvalNormalized": 0.47,
                "parameters": 27,
                "intelligenceIndexCostPerTask": {
                    "cost": {"total": 0.75},
                    "evaluations": [{"slug": "gdpval-aa",
                                     "weightedCostPerTask": 0.075}],
                },
            })
        cluster.append({
            "name": "Cluster Anchor",
            "modelCreatorName": "Cluster Lab",
            "isOpenWeights": False,
            "slug": "cluster-anchor",
            "intelligenceIndex": 80,
            "gdpvalNormalized": 0.47,
            "parameters": 27,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": 8.0},
                "evaluations": [{"slug": "gdpval-aa",
                                 "weightedCostPerTask": 0.8}],
            },
        })
        agent = {
            "id": "cluster-agent", "displayLabel": "Cluster Agent",
            "agentName": "Cluster Agent CLI",
            "hostModelSlug": "vendor_cluster-0",
            "display": {"creator": {"agent": "Agent Lab",
                                    "model": "Cluster Lab"}},
            "indexScore": 0.64,
            "mean": {"costUsd": 2.5, "agentWallTimeSec": 900.0},
        }
        with tempfile.TemporaryDirectory(prefix=".issue-27-browser-",
                                         dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw, agents_raw = root / "models.json", root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps(cluster), encoding="utf-8")
            agents_raw.write_text(json.dumps([agent]), encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page.goto(output.as_uri())
                self.assertEqual(
                    page.locator("#svg-intelligence circle.pt").count(), 31)
                self.assertLess(
                    page.locator("#svg-intelligence text.lbl").count(), 20)
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out
                page.close()

    def test_missing_lab_renders_as_em_dash_on_every_surface(self):
        # #28: the two "Devin Fusion CLI" coding-agent rows carry creator:"",
        # and a missing value must render as the page's em dash everywhere --
        # never as a blank option, cell or export field (AGENTS.md).
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())

        with self.subTest("lab filter dropdown"):
            options = page.locator("#fLab option").all_text_contents()
            self.assertNotIn("", options)
            self.assertEqual(options[0], "All labs")

        with self.subTest("chart tooltip"):
            devin = page.locator(
                "#svg-coding circle.pt[aria-label^='Pin Devin Fusion CLI']")
            self.assertGreater(devin.count(), 0)
            devin.first.hover()
            lab_row = page.locator("#tip-coding .trow").filter(has_text="Lab")
            self.assertEqual(lab_row.count(), 1)
            self.assertEqual(lab_row.first.locator(".tv").inner_text(), "—")

        with self.subTest("full table"):
            rows = page.locator("#tbl tbody tr").filter(
                has_text="Devin Fusion CLI")
            self.assertEqual(rows.count(), 2)
            for row in rows.all():
                self.assertEqual(row.locator("td").nth(1).inner_text(), "—")

        stub = """() => {
          window.__copied = null;
          Object.defineProperty(navigator, 'clipboard', {
            value: { writeText: t => { window.__copied = t;
                                       return Promise.resolve(); } },
            configurable: true,
          });
        }"""
        with self.subTest("copy as markdown"):
            page.evaluate(stub)
            page.locator("#copyMd").click()
            md = page.evaluate("() => window.__copied")
            self.assertIsNotNone(md)
            devin_lines = [line for line in md.split("\n")
                           if line.startswith("| Devin Fusion CLI")]
            self.assertEqual(len(devin_lines), 2)
            for line in devin_lines:
                self.assertEqual(line.split(" | ")[1], "—")

        with self.subTest("copy as json"):
            page.evaluate(stub)
            page.locator("#copyJson").click()
            exported = json.loads(page.evaluate("() => window.__copied"))
            devin_rows = [m for m in exported["models"]
                          if m["name"].startswith("Devin Fusion CLI")]
            self.assertEqual(len(devin_rows), 2)
            for row in devin_rows:
                self.assertEqual(row["creator"], "—")
        page.close()

    def test_tooltip_secondary_rows_identical_across_charts(self):
        # #29: one record must read the same wherever it is hovered. The
        # intelligence tooltip used to carry "Output speed" and "Context"
        # rows the three capability tooltips omitted. All four tooltips now
        # share one secondary-row builder; the chart's own metric rows stay
        # chart-specific and first.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        chart_labels = {"coding": "Coding Agent Index",
                        "intelligence": "Intelligence Index",
                        "agentic": "GDPval-AA v2",
                        "parameters": "Parameter efficiency"}
        secondary = ["Lab", "Weights", "Output speed", "Context"]

        def tip_rows(chart):
            out = {}
            rows = page.locator(f"#tip-{chart} .trow")
            for i in range(rows.count()):
                row = rows.nth(i)
                out[row.locator("span").first.inner_text()] = \
                    row.locator("span.tv").inner_text()
            return out

        def hover_by_name(chart, name):
            aria = f"Pin {name} on the {chart_labels[chart]} chart"
            self.assertNotIn('"', name)
            page.locator(
                f'#svg-{chart} circle.pt[aria-label="{aria}"]').hover()
            return tip_rows(chart)

        # a model present on the intelligence, agentic and parameter charts
        name_sets = {}
        for chart in ("intelligence", "agentic", "parameters"):
            aris = page.evaluate(
                "sel => [...document.querySelectorAll(sel)]"
                ".map(c => c.getAttribute('aria-label'))",
                f"#svg-{chart} circle.pt")
            suffix = f" on the {chart_labels[chart]} chart"
            name_sets[chart] = {
                a[len("Pin "):-len(suffix)] for a in aris
                if a.startswith("Pin ") and a.endswith(suffix)
            }
        common = name_sets["intelligence"] & name_sets["agentic"] \
            & name_sets["parameters"]
        self.assertTrue(common)
        model = sorted(n for n in common if '"' not in n)[0]

        snapshots = {chart: hover_by_name(chart, model)
                     for chart in ("intelligence", "agentic", "parameters")}
        for chart, rows in snapshots.items():
            with self.subTest(chart=chart):
                for key in secondary:
                    self.assertIn(key, rows)
        for key in secondary:
            values = {snapshots[c][key]
                      for c in ("intelligence", "agentic", "parameters")}
            self.assertEqual(len(values), 1,
                             f"{key} differs across charts: {values}")

        # agent rows carry no speed/context fields -- the shared builder must
        # render those as the em dash rather than omitting the rows
        aris = page.evaluate(
            "sel => [...document.querySelectorAll(sel)]"
            ".map(c => c.getAttribute('aria-label'))", "#svg-coding circle.pt")
        agent_names = [
            a[len("Pin "):-len(" on the Coding Agent Index chart")]
            for a in aris
            if a.startswith("Pin ") and a.endswith(" on the Coding Agent Index chart")
        ]
        agent = next(n for n in agent_names if '"' not in n)
        agent_rows = hover_by_name("coding", agent)
        for key in secondary:
            self.assertIn(key, agent_rows)
        self.assertEqual(agent_rows["Output speed"], "—")
        self.assertEqual(agent_rows["Context"], "—")
        page.close()

    def test_script_terminators_in_remote_strings_cannot_execute(self):
        lower = "</script><script>document.documentElement.dataset.auditLower=1</script>"
        mixed = "</ScRiPt><ScRiPt>document.documentElement.dataset.auditMixed=1</sCrIpT>"
        upper = "</SCRIPT><SCRIPT>document.documentElement.dataset.auditUpper=1</SCRIPT>"
        ordinary = "".join([
            "ordinary <tag> & 'quotes' \"slashes",
            "\\",
            "\" \n",
            "\u2028",
            "\u2029",
        ])
        model = {
            "name": lower,
            "modelCreatorName": mixed,
            "modelCreatorCountry": upper,
            "licenseName": ordinary,
            "releaseDate": ordinary,
            "isOpenWeights": True,
            "slug": "audit-model",
            "intelligenceIndex": 51,
            "gdpvalNormalized": 0.47,
            "totalParameters": 27,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": 0.75},
                "evaluations": [
                    {"slug": "gdpval-aa", "weightedCostPerTask": 0.80},
                    {"slug": "scicode", "weightedCostPerTask": 0.24},
                ],
            },
        }
        # The agent capture carries AA strings too -- an agent's display label
        # reaches the same inline JSON -- so it gets the same hostile input.
        agent = {
            "id": "audit-agent",
            "displayLabel": lower,
            "agentName": mixed,
            "hostModelSlug": "vendor_audit-model",
            "display": {"creator": {"agent": upper, "model": mixed}},
            "indexScore": 0.64,
            "mean": {"costUsd": 2.5, "agentWallTimeSec": 900.0},
        }

        with tempfile.TemporaryDirectory(prefix=".issue-6-browser-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw = root / "models.json"
            agents_raw = root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps([model]), encoding="utf-8")
            agents_raw.write_text(json.dumps([agent]), encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page = self.browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(output.as_uri())
                self.assertIsNone(page.evaluate("document.documentElement.dataset.auditLower"))
                self.assertIsNone(page.evaluate("document.documentElement.dataset.auditMixed"))
                self.assertIsNone(page.evaluate("document.documentElement.dataset.auditUpper"))
                self.assertIn(lower, page.locator("body").inner_text())
                self.assertIn("ordinary <tag>", page.locator("body").inner_text())
                page.close()
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out

    # The hostile fixture shared by the two copy-export tests: a name whose
    # pipes, backticks and script tags are exactly what breaks a pasted
    # markdown table while being legitimate raw data for the JSON export.
    HOSTILE_NAME = "P|ipe `Tick` Model <script>alert(1)</script>"

    def _hostile_export_page(self):
        """Build a one-model page whose captured strings carry markdown-
        significant characters, and return a page with the clipboard stubbed."""
        model = {
            "name": self.HOSTILE_NAME,
            "modelCreatorName": "Hostile Lab",
            "isOpenWeights": True,
            "slug": "hostile-model",
            "intelligenceIndex": 51,
            "gdpvalNormalized": 0.47,
            "parameters": 27,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": 0.75},
                "evaluations": [{"slug": "gdpval-aa",
                                 "weightedCostPerTask": 0.80}],
            },
        }
        agent = {
            "id": "hostile-agent", "displayLabel": "Hostile Agent",
            "agentName": "Hostile Agent CLI",
            "hostModelSlug": "vendor_hostile-model",
            "display": {"creator": {"agent": "Agent Lab",
                                    "model": "Hostile Lab"}},
            "indexScore": 0.64,
            "mean": {"costUsd": 2.5, "agentWallTimeSec": 900.0},
        }
        # The directory outlives this helper -- the test cleans it up in its
        # own finally, next to the page close -- so it cannot live in a with.
        tmp = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
            prefix=".issue-48-browser-", dir=build.ROOT)
        root = pathlib.Path(tmp.name)
        raw, agents_raw = root / "models.json", root / "coding-agents.json"
        output = root / "frontier-models.html"
        raw.write_text(json.dumps([model]), encoding="utf-8")
        agents_raw.write_text(json.dumps([agent]), encoding="utf-8")
        old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
        build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
        except BaseException:
            tmp.cleanup()
            build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out
            raise
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(output.as_uri())
        page.evaluate("""() => {
          window.__copied = null;
          Object.defineProperty(navigator, 'clipboard', {
            value: { writeText: t => { window.__copied = t;
                                       return Promise.resolve(); } },
            configurable: true,
          });
        }""")
        return tmp, (old_raw, old_agents, old_out), page

    def test_copy_as_markdown_escapes_markdown_significant_cell_text(self):
        # #48: the markdown export interpolated raw captured strings into a
        # markdown table, where a literal pipe closes the cell, a backtick
        # opens a code span and a backslash reads as an escape -- so a pasted
        # row fell apart as text. Cells now carry the escaped display text.
        tmp, saved, page = self._hostile_export_page()
        try:
            page.locator("#copyMd").click()
            md = page.evaluate("() => window.__copied")
            self.assertIsNotNone(md)
            escaped = (self.HOSTILE_NAME.replace("\\", "\\\\")
                                        .replace("|", "\\|")
                                        .replace("`", "\\`"))
            rows = [line for line in md.split("\n") if escaped in line]
            self.assertTrue(
                rows,
                "no markdown row carries the escaped name -- the export "
                "embedded the captured string without escaping it")
            row = rows[0]
            # every cell separator survived: 13 columns -> exactly 14 pipes,
            # so no captured pipe leaked through into the row structure
            self.assertEqual(len(re.findall(r"(?<!\\)\|", row)), 14)
            self.assertIn("P\\|ipe", row)
            self.assertIn("\\`Tick\\`", row)
            self.assertNotIn(self.HOSTILE_NAME, row)
        finally:
            page.close()
            build.RAW, build.AGENTS_RAW, build.OUT = saved
            tmp.cleanup()

    def test_copy_as_json_keeps_raw_values_and_documents_the_rawness(self):
        # #48's documented alternative: the JSON export stays RAW -- structured
        # data goes out exactly as captured -- and the rawness is documented
        # where the reader of the button sees it (the button's title).
        tmp, saved, page = self._hostile_export_page()
        try:
            page.locator("#copyJson").click()
            exported = json.loads(page.evaluate("() => window.__copied"))
            rows = [m for m in exported["models"]
                    if m["name"] == self.HOSTILE_NAME]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], self.HOSTILE_NAME)
            self.assertEqual(rows[0]["creator"], "Hostile Lab")

            title = page.locator("#copyJson").get_attribute("title")
            assert title is not None, (
                "#copyJson documents nowhere that its export is raw captured "
                "data, unescaped")
            self.assertIn("raw", title.lower())
            self.assertIn("unescaped", title.lower())
        finally:
            page.close()
            build.RAW, build.AGENTS_RAW, build.OUT = saved
            tmp.cleanup()

    def test_empty_filter_result_renders_an_announced_empty_state(self):
        # #58: an empty filtered slice used to render a silent zero-row table
        # -- the reader could not tell "nothing matches" from a broken page.
        # The table region now carries an aria-live empty state, announced
        # when the filtered slice empties and gone when rows return.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        empty = page.locator("#tblEmpty")
        self.assertGreater(page.locator("#tbl tbody tr").count(), 0)
        self.assertFalse(empty.is_visible())

        page.locator("#fQ").fill("zzqq-no-model-matches-this")
        self.assertTrue(empty.is_visible())
        self.assertEqual(empty.get_attribute("aria-live"), "polite")
        self.assertEqual(empty.inner_text(),
                         "No models match the current filters")
        self.assertEqual(page.locator("#tbl tbody tr").count(), 0)

        page.locator("#fQ").fill("")
        self.assertFalse(empty.is_visible())
        self.assertGreater(page.locator("#tbl tbody tr").count(), 0)
        page.close()

    def test_tooltip_transition_honours_prefers_reduced_motion(self):
        # #57: the tooltip's opacity fade ran unconditionally. Under
        # prefers-reduced-motion the transition must be gone entirely so the
        # tooltip appears and vanishes instantly.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        duration = ("getComputedStyle(document.getElementById"
                    "('tip-intelligence')).transitionDuration")
        page.emulate_media(reduced_motion="reduce")
        self.assertEqual(page.evaluate(duration), "0s")
        page.emulate_media(reduced_motion="no-preference")
        self.assertEqual(page.evaluate(duration), "0.12s")
        page.close()

    @staticmethod
    def _srgb_to_linear(channel):
        c = channel / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    @classmethod
    def _wcag_contrast(cls, fg, bg):
        """WCAG 2.x contrast ratio between two [r, g, b] byte triples."""
        def luminance(rgb):
            return (0.2126 * cls._srgb_to_linear(rgb[0])
                    + 0.7152 * cls._srgb_to_linear(rgb[1])
                    + 0.0722 * cls._srgb_to_linear(rgb[2]))
        l1, l2 = luminance(fg), luminance(bg)
        hi, lo = max(l1, l2), min(l1, l2)
        return (hi + 0.05) / (lo + 0.05)

    def test_light_theme_text_surfaces_meet_wcag_aa_contrast(self):
        # #56: light-theme table headers (--muted on --surface-1) and the
        # frontier tags (--accent on the same surface) sat below the 4.5:1
        # WCAG AA floor for their sizes. The ratio is computed here from the
        # computed styles over the WCAG 2.x relative-luminance formula -- the
        # test never trusts a pinned number.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        page.evaluate("document.documentElement.dataset.theme = 'light'")
        pairs = page.evaluate("""() => {
          const bgOf = el => {
            for (let cur = el; cur; cur = cur.parentElement) {
              const bg = getComputedStyle(cur).backgroundColor;
              if (bg && bg !== 'transparent' && !/rgba\\([^)]+, 0\\)/.test(bg))
                return bg;
            }
            return 'rgb(255, 255, 255)';
          };
          const pick = sel => {
            const el = document.querySelector(sel);
            return el ? {fg: getComputedStyle(el).color, bg: bgOf(el)} : null;
          };
          return {th: pick('#tbl th'), tag: pick('#tbl td .tag.f')};
        }""")
        page.close()
        self.assertIsNotNone(pairs["th"], "no table header rendered")
        self.assertIsNotNone(pairs["tag"], "no frontier tag rendered in the table")
        for name, pair in pairs.items():
            fg = [int(v) for v in re.findall(r"\d+", pair["fg"])][:3]
            bg = [int(v) for v in re.findall(r"\d+", pair["bg"])][:3]
            ratio = self._wcag_contrast(fg, bg)
            self.assertGreaterEqual(
                ratio, 4.5,
                f"light-theme {name} measures {ratio:.2f}:1, below the WCAG "
                f"AA 4.5:1 floor (fg={pair['fg']}, bg={pair['bg']})")


class BuildProvenanceTests(unittest.TestCase):
    """#49: the footer's provenance — source commit when the build
    environment carries one, and a sha256 over the two capture files that a
    reader can verify today, by hashing the committed files."""

    COMMIT = "e5e10f1c0ffee4215deadbeefcafe0123456789a"

    def _build(self, destination, commit=None):
        """Run build.main() to `destination`, with AA_SOURCE_COMMIT set or
        unset, and return the page bytes."""
        old_out = build.OUT
        build.OUT = destination
        try:
            env = {} if commit is None else {"AA_SOURCE_COMMIT": commit}
            with mock.patch.dict(os.environ, env, clear=False):
                if commit is None:
                    os.environ.pop("AA_SOURCE_COMMIT", None)
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
            return destination.read_bytes()
        finally:
            build.OUT = old_out

    def test_footer_carries_the_source_commit_and_the_content_hash(self):
        with tempfile.TemporaryDirectory(prefix=".issue-49-build-",
                                         dir=build.ROOT) as tmp:
            output = pathlib.Path(tmp) / "frontier-models.html"
            html = self._build(output, commit=self.COMMIT).decode("utf-8")

            # verbatim in the footer, not merely somewhere in the payload
            foot = html[html.index('class="foot"'):]
            self.assertIn(self.COMMIT, foot)
            # the content hash equals an independently computed sha256 over
            # the two capture files, read straight off the data directory
            digest = hashlib.sha256()
            digest.update(build.RAW.read_bytes())
            digest.update(build.AGENTS_RAW.read_bytes())
            self.assertIn(digest.hexdigest(), foot)

    def test_footer_omits_the_source_commit_when_the_environment_is_unset(self):
        with tempfile.TemporaryDirectory(prefix=".issue-49-build-",
                                         dir=build.ROOT) as tmp:
            output = pathlib.Path(tmp) / "frontier-models.html"
            html = self._build(output).decode("utf-8")

            self.assertNotIn(self.COMMIT, html)
            foot = html[html.index('class="foot"'):]
            self.assertNotIn("source commit", foot)
            # the content hash is verifiable today without any workflow
            # change, so it renders with or without the commit
            digest = hashlib.sha256()
            digest.update(build.RAW.read_bytes())
            digest.update(build.AGENTS_RAW.read_bytes())
            self.assertIn(digest.hexdigest(), foot)

    def test_rebuild_without_the_env_var_stays_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix=".issue-49-build-",
                                         dir=build.ROOT) as tmp:
            first = pathlib.Path(tmp) / "first.html"
            second = pathlib.Path(tmp) / "second.html"
            self._build(first)
            self._build(second)

            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
