import contextlib
import gzip
import hashlib
import io
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright)

import test_build

import build

# This box has a system Chromium and no playwright-managed browser; CI has the
# reverse (`playwright install chromium`). Prefer whatever is actually present
# rather than hard-coding one of them — passing executable_path=None makes
# playwright use its own download. CHROMIUM_PATH overrides both.
CHROMIUM = os.environ.get("CHROMIUM_PATH") or "/usr/bin/chromium"
CHROMIUM_EXECUTABLE = CHROMIUM if pathlib.Path(CHROMIUM).exists() else None


def _data_payload(page_html):
    """The `const DATA = {...}` payload parsed out of the built page.

    Sliced at the same two landmarks the payload tests use -- the `const
    DATA = ` assignment and the IIFE that follows it -- so the row count the
    static tbody is held to is the payload's own count, not a hand-kept
    number that drifts from the capture.
    """
    marker = "const DATA = "
    start = page_html.index(marker) + len(marker)
    end = page_html.index(";\n(function(){", start)
    return json.loads(page_html[start:end])


def collect_page_coverage(session):
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


class BrowserInteractionTests(unittest.TestCase):
    # pylint: disable=too-many-public-methods
    # One behaviour, one test: #85's per-chart label-distinctness guarantee is
    # a 21st method here, not a subTest of an unrelated test.
    # V8 coverage for the JavaScript ratchet. With JS_COVERAGE_OUT set (the
    # coverage job sets it), every page this class creates records V8 block
    # coverage and its dump joins a class-level list written out when the
    # class tears down; unset, nothing changes. One pytest run then produces
    # both measurements the coverage gates read.
    _coverage_entries = []
    _open_pages = []

    @classmethod
    def setUpClass(cls):
        # The class builds its page into a temp dir under ROOT (build.main()
        # prints OUT.relative_to(ROOT)) and keeps build.OUT pointed there for
        # the class's lifetime, since every test navigates
        # build.OUT.as_uri(). The real out/frontier-models.html is never
        # touched (#114); tearDownClass restores the module path.
        cls._saved_out = build.OUT
        # The directory outlives this setup -- tearDownClass cleans it up
        # after the browser closes -- so it cannot live in a with.
        cls._page_dir = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
            prefix=".issue-114-browser-", dir=build.ROOT)
        build.OUT = pathlib.Path(cls._page_dir.name) / "frontier-models.html"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
            # The launch is inside the handler's reach too: setUpClass
            # failure skips tearDownClass, so a raise from playwright's
            # start or the launch itself would strand build.OUT at the
            # temp path and leave the dir on disk.
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(
                executable_path=CHROMIUM_EXECUTABLE,
                headless=True,
                args=["--no-sandbox"],
            )
        except BaseException:
            build.OUT = cls._saved_out
            cls._page_dir.cleanup()
            raise
        cls._coverage_entries = []
        cls._open_pages = []
        original_new_page = cls.browser.new_page

        def new_page(**kwargs):
            page = original_new_page(**kwargs)
            if kwargs.get("java_script_enabled") is False:
                # A JavaScript-disabled page compiles no script, so it has no
                # V8 block coverage to give: wiring a Profiler session onto it
                # would only add empty records to the dump js_coverage.py
                # folds. Skipped, the dump stays the JS-enabled run's.
                return page
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
                cls._coverage_entries.extend(collect_page_coverage(session))
                return original_close(**close_kwargs)

            page.close = close
            cls._open_pages.append((page, session))
            return page

        cls.browser.new_page = new_page

    @classmethod
    def tearDownClass(cls):
        # Restore the module path first: every later step here may raise,
        # and a stale build.OUT would send the NEXT class's build.main()
        # into this class's deleted temp dir.
        build.OUT = cls._saved_out
        cls._page_dir.cleanup()
        # A test that failed mid-way leaves its page open; take its coverage
        # here so the dump still describes the whole run.
        for _page, session in list(cls._open_pages):
            try:
                cls._coverage_entries.extend(collect_page_coverage(session))
            except Exception:
                pass
        cls._open_pages.clear()
        dump = os.environ.get("JS_COVERAGE_OUT")
        if dump:
            # The coverage job runs more than one page-building class, and
            # each dumps at ITS teardown: merge with whatever an earlier
            # class already wrote, or the later teardown would erase the
            # earlier class's whole contribution.
            path = pathlib.Path(dump)
            entries = cls._coverage_entries
            if path.exists():
                try:
                    entries = json.loads(
                        path.read_text(encoding="utf-8")) + entries
                except (OSError, json.JSONDecodeError):
                    pass
            path.write_text(json.dumps(entries), encoding="utf-8")
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

    def _hoverable_point(self, page, selector, attempts=8):
        """The first point at `selector` playwright can actually hover.

        A point's action point can be covered by a later-drawn neighbour, so
        the DOM-first point is not hoverable on every page shape. Candidates
        are tried in DOM order; the first that hovers carries the pin, and
        exhaustion fails naming the selector.
        """
        points = page.locator(selector)
        self.assertGreater(
            points.count(), 0,
            f"no points matched {selector!r} -- the chart rendered empty, so "
            "every interaction below would time out instead of failing here")
        last = None
        for index in range(min(attempts, points.count())):
            point = points.nth(index)
            try:
                point.hover(timeout=2000)
            except PlaywrightTimeoutError as exc:
                last = exc
                continue
            return point
        self.fail(
            f"no point at {selector!r} was hoverable in {attempts} candidates "
            f"(last error: {last})")

    def test_non_frontier_points_pin_a_visible_name_on_capability_charts(self):
        for metric in ("coding", "agentic"):
            with self.subTest(metric=metric):
                page = self.browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(build.OUT.as_uri())
                point = self._hoverable_point(
                    page, f"#svg-{metric} circle.pt[r='5']")
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
        # #163: the search matches case-insensitive substrings of name AND
        # creator (build.py's filteredBase), so a runtime-read name's match
        # set on the ambient capture is whatever AA published today -- any
        # ambient pair where one name or creator contains the other turned
        # this test's hardcoded `exactly one` into `2 != 1`. The page is
        # this test's own deterministic fixture and the expected match set
        # derives from it with the page's own matching semantics, over both
        # axes the search reads: the fixture carries a name-substring pair
        # and a creator-substring row deliberately, so the guarantee
        # survives whatever names and creators AA publishes.
        models = _probe_models(6)
        # The issue's first counterexample class: the pair's shorter name is
        # a substring of the longer one, so the shorter name's query
        # legitimately matches both rows.
        models[1]["name"] = "Probe Model 0000 Extended"
        # The second class: the name is unique but the creator contains the
        # query, which the search reads too.
        models[2]["name"] = "Probe Isolator"
        models[2]["modelCreatorName"] = "Probe Model 0000 Labs"

        def expected_slice(query):
            """The fixture's own match set, by the page's matching
            semantics: a case-insensitive substring over name AND creator."""
            ql = query.strip().lower()
            return [m for m in models
                    if ql in m["name"].lower()
                    or ql in m["modelCreatorName"].lower()]

        def assert_slice(page, query):
            """The visible parameter points are exactly the fixture's match
            set -- identity, not just a count."""
            shown = page.locator("#svg-parameters circle.pt")
            aris = [el.get_attribute("aria-label") for el in shown.all()]
            expected = [f"Pin {m['name']} on the Parameter efficiency chart"
                        for m in expected_slice(query)]
            self.assertEqual(
                len(aris), len(expected),
                f"search {query!r} shows {len(aris)} points, the fixture's "
                f"match set holds {len(expected)}")
            self.assertEqual(
                set(aris), set(expected),
                f"search {query!r} shows a different slice than the "
                "fixture's match set")

        target = models[5]  # unique name and creator against the fixture
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        with tempfile.TemporaryDirectory(prefix=".issue-163-search-",
                                         dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw, agents_raw = root / "models.json", root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps(models), encoding="utf-8")
            agents_raw.write_text(json.dumps(_PROBE_AGENTS), encoding="utf-8")
            old_raw, old_agents, old_out = (
                build.RAW, build.AGENTS_RAW, build.OUT)
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    raw, agents_raw, output)
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page.goto(output.as_uri())

                # The shared interactions, on a point looked up BY the
                # fixture's own name: hover tooltip, keyboard pin, label.
                aria = (f"Pin {target['name']} on the "
                        "Parameter efficiency chart")
                point = page.locator(
                    f'#svg-parameters circle.pt[aria-label="{aria}"]')
                self.assertEqual(point.count(), 1)
                point.hover()
                model_name = page.locator("#tip-parameters .tname").inner_text()
                self.assertEqual(model_name, target["name"])
                tooltip = page.locator("#tip-parameters").inner_text()
                self.assertIn("Parameters", tooltip)
                self.assertIn("Intelligence Index", tooltip)

                accessible_name = (
                    f"Pin {model_name} on the Parameter efficiency chart")
                point.focus()
                point.press("Enter")
                pinned = page.get_by_role("button", name=accessible_name)
                self.assertEqual(pinned.get_attribute("aria-pressed"), "true")
                self.assertIn(
                    model_name,
                    page.locator("#svg-parameters text.lbl").all_text_contents(),
                )

                # The search, both directions the issue pins, both
                # fixture-derived: a matched row found and only it, and an
                # ambiguous pair handled the way the page's semantics say --
                # every row the query legitimately matches stays visible.
                with self.subTest("unique query finds its row and only it"):
                    page.locator("#fQ").fill(models[1]["name"])
                    assert_slice(page, models[1]["name"])

                with self.subTest("ambiguous pair matches per the semantics"):
                    page.locator("#fQ").fill(models[0]["name"])
                    assert_slice(page, models[0]["name"])
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    old_raw, old_agents, old_out)
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
        # models draw in de-emphasis gray), so every off-frontier point
        # draws var(--muted) on every chart, and every legend documents the
        # swatch, while a frontier point carries no verdict fill.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        for chart in ("coding", "intelligence", "agentic", "parameters"):
            with self.subTest(chart=chart):
                off_frontier = page.evaluate(
                    "sel => [...new Set([...document.querySelectorAll(sel)]"
                    ".map(c => c.getAttribute('fill')))]",
                    f"#svg-{chart} circle.pt[r='5']",
                )
                self.assertTrue(
                    off_frontier and set(off_frontier) <= {"var(--muted)"},
                    f"{chart}: off-frontier fills {off_frontier} leave the "
                    "legit set ['var(--muted)']")

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
        # #153: the page is this test's own deterministic fixture, and every
        # expectation -- which names exist, how many are pickable -- derives
        # from that fixture, never from the ambient capture. AA's rollout size
        # moves freely, so pin expectations read off the live page break in
        # exactly the hours the suite must stay green.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        chart_labels = {"coding": "Coding Agent Index",
                        "intelligence": "Intelligence Index",
                        "agentic": "GDPval-AA v2",
                        "parameters": "Parameter efficiency"}
        # 40 probe pins on the intelligence chart -- the crowd the audit used,
        # enough to exhaust the clear slots -- plus a couple on every other
        # chart so each chart guarantees its own pins. Agent-run rows never
        # share names with model rows, so the coding chart can only pin its
        # own rows. Two more crafted intelligence pins carry the name shapes
        # the crowd lacks: full names over the 34-character chart cap (the
        # #27 guarantee is the FULL pinned name -- wide labels render r.name
        # unclipped, so a truncation regression must red here), a shared long
        # prefix pressuring distinctness, an effort suffix that must survive
        # display_name, and Unicode. A crafted coding agent carries the same
        # shape onto the coding chart. The picks are looked up on the page BY
        # the fixture's own names, and the label checks hold those exact
        # strings -- long ones included -- so nothing but the full name
        # passes.
        pin_long = "Probe Dynamics Ultra Long Benchmark Model Alpha (Reasoning)"
        pin_unicode = "Probe Dynamics Ultra Long Benchmark Model Ünïcödé — 東京"
        crafted = [
            {"name": pin_long,
             "modelCreatorName": "Probe Lab",
             "isOpenWeights": False,
             "slug": "probe-crafted-alpha",
             "intelligenceIndex": 79.0,
             "gdpvalNormalized": 0.42,
             "parameters": 33,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 0.6},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.06}],
             }},
            {"name": pin_unicode,
             "modelCreatorName": "Probe Lab",
             "isOpenWeights": True,
             "slug": "probe-crafted-unicode",
             "intelligenceIndex": 78.5,
             "gdpvalNormalized": 0.44,
             "parameters": 61,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 0.9},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.09}],
             }},
            {"name": "Probe Dynamics Ultra Long Benchmark Model Beta "
                     "(Reasoning)",
             "modelCreatorName": "Probe Lab",
             "isOpenWeights": False,
             "slug": "probe-crafted-beta",
             "intelligenceIndex": 60.0,
             "gdpvalNormalized": 0.5,
             "parameters": 95,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 1.6},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.16}],
             }},
            {"name": "Probe Short Beta",
             "modelCreatorName": "Probe Lab",
             "isOpenWeights": False,
             "slug": "probe-crafted-gamma",
             "intelligenceIndex": 59.0,
             "gdpvalNormalized": 0.52,
             "parameters": 130,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 2.4},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.24}],
             }},
            {"name": "Probe Dynamics Ultra Long Benchmark Model Delta",
             "modelCreatorName": "Probe Lab",
             "isOpenWeights": True,
             "slug": "probe-crafted-delta",
             "intelligenceIndex": 40.0,
             "gdpvalNormalized": 0.6,
             "parameters": 180,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 6.0},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.6}],
             }},
            {"name": "Probe Short Delta",
             "modelCreatorName": "Probe Lab",
             "slug": "probe-crafted-epsilon",
             "isOpenWeights": True,
             "intelligenceIndex": 39.0,
             "gdpvalNormalized": 0.62,
             "parameters": 220,
             "intelligenceIndexCostPerTask": {
                 "cost": {"total": 9.0},
                 "evaluations": [{"slug": "gdpval-aa",
                                  "weightedCostPerTask": 0.9}],
             }},
        ]
        agents = list(_PROBE_AGENTS) + [
            {"id": "probe-agent-long", "displayLabel":
             "Probe Coding Agent With A Very Long Display Label",
             "agentName": "Probe Coding Agent Long CLI",
             "hostModelSlug": "probe-model-0000",
             "display": {"creator": {"agent": "Probe Agent Lab",
                                     "model": "Probe Lab"}},
             "indexScore": 0.45, "mean": {"costUsd": 1.2,
                                          "agentWallTimeSec": 600.0}},
        ]
        pin_counts = {"intelligence": PIN_CROWD + 2,
                      "coding": len(agents), "agentic": 2, "parameters": 2}
        models = _probe_models(PIN_CROWD) + crafted
        fresh = {
            "coding": [a["displayLabel"] for a in agents],
            "intelligence": ([m["name"] for m in models
                              if m["name"].startswith("Probe Model")]
                             + [pin_long, pin_unicode]),
            "agentic": ["Probe Dynamics Ultra Long Benchmark Model Beta "
                        "(Reasoning)", "Probe Short Beta"],
            "parameters": ["Probe Dynamics Ultra Long Benchmark Model Delta",
                           "Probe Short Delta"],
        }
        with tempfile.TemporaryDirectory(prefix=".issue-153-pins-",
                                         dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw, agents_raw = root / "models.json", root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps(models), encoding="utf-8")
            agents_raw.write_text(json.dumps(agents), encoding="utf-8")
            old_raw, old_agents, old_out = (
                build.RAW, build.AGENTS_RAW, build.OUT)
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    raw, agents_raw, output)
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page.goto(output.as_uri())

                pinned = {}
                for chart, label in chart_labels.items():
                    suffix = f" on the {label} chart"
                    points = page.locator(f"#svg-{chart} circle.pt")
                    aris = page.evaluate(
                        "sel => [...document.querySelectorAll(sel)]"
                        ".map(c => c.getAttribute('aria-label'))",
                        f"#svg-{chart} circle.pt")
                    pick = []
                    for want in fresh[chart]:
                        aria = f"Pin {want}{suffix}"
                        matches = [i for i, a in enumerate(aris) if a == aria]
                        self.assertEqual(
                            len(matches), 1,
                            f"{want!r} is not pinnable exactly once on "
                            f"{chart}: {aris}")
                        pick.append((matches[0], want))
                    self.assertEqual(
                        len(pick), pin_counts[chart],
                        f"could not pick {pin_counts[chart]} fresh names "
                        f"on {chart}")
                    for i, _ in pick:
                        points.nth(i).focus()
                        points.nth(i).press("Enter")
                    pinned[chart] = [n for _, n in pick]

                # every chart labels every one of its own pinned points
                for chart in chart_labels:
                    labels = page.locator(
                        f"#svg-{chart} text.lbl").all_text_contents()
                    missing = [n for n in pinned[chart] if n not in labels]
                    self.assertEqual(
                        missing, [],
                        f"pinned names dropped on the {chart} chart")

                # and wherever a pinned row renders on ANOTHER chart, its
                # label survives there too (the pin set is page-global)
                for chart, label in chart_labels.items():
                    aria = page.evaluate(
                        "sel => [...document.querySelectorAll(sel)]"
                        ".map(c => c.getAttribute('aria-label'))",
                        f"#svg-{chart} circle.pt")
                    foreign = {n for names in pinned.values() for n in names
                               if f"Pin {n} on the {label} chart" in aria}
                    labels = page.locator(
                        f"#svg-{chart} text.lbl").all_text_contents()
                    self.assertEqual(
                        [n for n in foreign if n not in labels], [],
                        f"cross-chart pinned names dropped on the {chart} "
                        "chart")
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    old_raw, old_agents, old_out)
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
        # #28: a coding-agent run whose capture record carries no creator
        # (today's Devin Fusion CLI rows: display carries agent/model but no
        # creator) must render the em dash everywhere -- never a blank
        # option, cell or export field (AGENTS.md). #159: the page is this
        # test's own deterministic fixture and every expectation -- which
        # rows exist and how many match -- derives from it, never from the
        # ambient capture, so AA republishing a different Devin run count
        # leaves the guarantee intact and the suite green.
        devin_runs = [
            {"id": "devin-probe-1",
             "agentName": "Devin Fusion CLI Probe Run One",
             "displayLabel": "Devin Fusion CLI - Probe Run One",
             "hostModelSlug": "probe-model-0000",
             "display": {"agent": "Devin Fusion CLI",
                         "model": "Probe Run One"},
             "indexScore": 0.61, "mean": {"costUsd": 3.1,
                                          "agentWallTimeSec": 810.0}},
            {"id": "devin-probe-2",
             "agentName": "Devin Fusion CLI Probe Run Two",
             "displayLabel": "Devin Fusion CLI - Probe Run Two",
             "hostModelSlug": "probe-model-0001",
             "display": {"agent": "Devin Fusion CLI",
                         "model": "Probe Run Two"},
             "indexScore": 0.52, "mean": {"costUsd": 2.3,
                                          "agentWallTimeSec": 760.0}},
            {"id": "devin-probe-3",
             "agentName": "Devin Fusion CLI Probe Run Three",
             "displayLabel": "Devin Fusion CLI - Probe Run Three",
             "hostModelSlug": "probe-model-0002",
             "display": {"agent": "Devin Fusion CLI",
                         "model": "Probe Run Three"},
             "indexScore": 0.44, "mean": {"costUsd": 1.7,
                                          "agentWallTimeSec": 690.0}},
        ]

        # No creator key in display -- the ambient shape of a run whose
        # model's lab AA has not published -- so every Devin row's creator
        # is "" and must render as the em dash. The probe agents and models
        # carry "Probe Lab", the present-lab contrast.
        agents = list(_PROBE_AGENTS) + devin_runs
        models = _probe_models(6)
        devin_count = len(devin_runs)
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        with tempfile.TemporaryDirectory(prefix=".issue-159-missing-lab-",
                                         dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw, agents_raw = root / "models.json", root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps(models), encoding="utf-8")
            agents_raw.write_text(json.dumps(agents), encoding="utf-8")
            old_raw, old_agents, old_out = (
                build.RAW, build.AGENTS_RAW, build.OUT)
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    raw, agents_raw, output)
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page.goto(output.as_uri())

                with self.subTest("lab filter dropdown"):
                    options = page.locator("#fLab option").all_text_contents()
                    self.assertNotIn("", options)
                    self.assertEqual(options[0], "All labs")

                with self.subTest("chart tooltip"):
                    devin = page.locator(
                        "#svg-coding "
                        "circle.pt[aria-label^='Pin Devin Fusion CLI']")
                    self.assertEqual(devin.count(), devin_count)
                    devin.first.hover()
                    lab_row = page.locator("#tip-coding .trow").filter(
                        has_text="Lab")
                    self.assertEqual(lab_row.count(), 1)
                    self.assertEqual(
                        lab_row.first.locator(".tv").inner_text(), "—")

                with self.subTest("full table"):
                    rows = page.locator("#tbl tbody tr").filter(
                        has_text="Devin Fusion CLI")
                    self.assertEqual(rows.count(), devin_count)
                    for row in rows.all():
                        self.assertEqual(
                            row.locator("td").nth(1).inner_text(), "—")

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
                    self.assertEqual(len(devin_lines), devin_count)
                    for line in devin_lines:
                        self.assertEqual(line.split(" | ")[1], "—")

                with self.subTest("copy as json"):
                    page.evaluate(stub)
                    page.locator("#copyJson").click()
                    copied = page.evaluate("() => window.__copied")
                    exported = json.loads(copied)
                    devin_rows = [m for m in exported["models"]
                                  if m["name"].startswith("Devin Fusion CLI")]
                    self.assertEqual(len(devin_rows), devin_count)
                    for row in devin_rows:
                        self.assertEqual(row["creator"], "—")
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = (
                    old_raw, old_agents, old_out)
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
            # The CURRENT field name: the empty-axis guard refuses a capture
            # still carrying the pre-rename `totalParameters` (issue #60), so
            # a stale name here would fail the build before the browser opens.
            "parameters": 27,
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

    @staticmethod
    def _markdown_cells(row):
        """A markdown table row -> its cell texts, by the table's own
        grammar: cells separate on UNESCAPED pipes, a backslash escapes the
        next character, and a renderer trims the padding around a cell.
        The round-trip the payload must survive."""
        assert row.startswith("| ") and row.endswith(" |"), row
        body = row[2:-2]
        cells, buf, i = [], [], 0
        while i < len(body):
            ch = body[i]
            if ch == "\\" and i + 1 < len(body):
                buf.append(body[i + 1])
                i += 2
                continue
            if ch == "|":
                cells.append("".join(buf).strip())
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
        cells.append("".join(buf).strip())
        return cells

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
            # The exported name is the page's display name now (#88), not the
            # raw capture string: display_name's kept-group rule renders the
            # fixture's glued "alert(1)" as "alert (1)". This updates the #48
            # pin's expected NAME value deliberately -- issue #88 changed the
            # name rule; every escaping assertion below is untouched.
            expected = build.display_name(self.HOSTILE_NAME)
            self.assertNotEqual(expected, self.HOSTILE_NAME)
            escaped = (expected.replace("\\", "\\\\")
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

            # the payload must also survive its own grammar: parsed back as
            # a markdown table -- rows on newlines, cells on unescaped pipes
            # -- every original display text comes back per cell
            table = [line for line in md.split("\n") if line.startswith("|")]
            self.assertGreaterEqual(len(table), 3)
            self.assertEqual(len(self._markdown_cells(table[0])), 13)
            cells = self._markdown_cells(row)
            self.assertEqual(len(cells), 13)
            self.assertEqual(cells[0], expected)
            self.assertEqual(cells[1], "Hostile Lab")
            self.assertEqual(cells[12], "open")
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
            # The name field carries the page's display name now (#88) -- the
            # same value the table and tooltips show; the rawness this pin
            # holds the export to applies to every value the page carries,
            # and every other assertion here is untouched.
            expected = build.display_name(self.HOSTILE_NAME)
            rows = [m for m in exported["models"]
                    if m["name"] == expected]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], expected)
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
        # tooltip appears and vanishes instantly. The bound is page-wide:
        # the copy toast's fade is the same class of motion and is held to
        # the same rule.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        duration = ("getComputedStyle(document.getElementById"
                    "('tip-intelligence')).transitionDuration")
        toast = ("getComputedStyle(document.getElementById"
                 "('toast')).transitionDuration")
        page.emulate_media(reduced_motion="reduce")
        self.assertEqual(page.evaluate(duration), "0s")
        self.assertEqual(page.evaluate(toast), "0s")
        page.emulate_media(reduced_motion="no-preference")
        self.assertEqual(page.evaluate(duration), "0.12s")
        self.assertEqual(page.evaluate(toast), "0.2s")
        page.close()

    # Replay drawCapability's label placement over a rendered chart and return
    # the slot every frontier label MUST occupy under the nearest-clear-slot
    # rule, alongside the labels actually on the page. Queue: frontier points,
    # smartest first (Y is affine in the score, so score-descending order is
    # y-ascending; ties keep row order). Candidates, widths and collision
    # rules mirror the placer exactly -- a measuring text element takes
    # getComputedTextLength() under the same .lbl class so the font metrics
    # match to the pixel.
    #
    # The text rule mirrors assignLabels' narrow path (#85), which REPLACES
    # the plain 34-char name truncation the #84 pin replayed: the compact
    # build-time label (r.label) first, the full AA name re-truncated when
    # the compact form is ambiguous (two rows compacting alike) or its
    # truncated text is already taken on this chart, a numeric suffix when
    # that collides too. This updates the #84 pin deliberately -- issue #85
    # changed the text rule; the placement rule is untouched. The replay runs
    # with no pins and st.sup off, so every replayed label is narrow and the
    # queue IS the whole allocation order. r.label is read from the page's
    # top-level `const DATA` -- a global lexical binding, reachable from
    # page.evaluate -- matched to replay points by name.
    _REPLAY_NEAREST_CLEAR_SLOT = """(chartId) => {
      const svg = document.getElementById(chartId);
      const dom = [...svg.querySelectorAll("text.lbl")].map(t => ({
        x: +t.getAttribute("x"), y: +t.getAttribute("y"),
        text: t.textContent, claimed: false}));
      const pts = [...svg.querySelectorAll("circle.pt")].map(p => {
        const a = p.getAttribute("aria-label") || "";
        return {x: +p.getAttribute("cx"), y: +p.getAttribute("cy"),
                r: p.getAttribute("r"),
                name: a.slice(4, a.lastIndexOf(" on the "))};
      });
      const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
      const T = 20, PY = H - 72;
      const meas = document.createElementNS(svg.namespaceURI, "text");
      meas.setAttribute("class", "lbl");
      svg.appendChild(meas);
      const hits = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x &&
                             a.y < b.y + b.h && a.y + a.h > b.y;
      const boxes = [];
      const queue = pts.filter(p => p.r === "6").map((p, j) => ({p, j}))
        .sort((a, b) => (a.p.y - b.p.y) || (a.j - b.j));
      const trunc = n => n.length > 34 ? n.slice(0, 33) + "\\u2026" : n;
      const labelOf = name => {
        const row = DATA.rows.find(r => r.name === name);
        return (row && row.label) || name;
      };
      const compactCounts = new Map();
      for (const {p} of queue) {
        const c = labelOf(p.name);
        compactCounts.set(c, (compactCounts.get(c) || 0) + 1);
      }
      const taken = new Set();
      const out = [];
      for (const {p} of queue) {
        const compact = labelOf(p.name);
        let text = trunc(compact);
        if (compactCounts.get(compact) > 1 || taken.has(text)) {
          text = trunc(p.name);
          if (taken.has(text)) {
            let n = 2;                      // first free number, queue order
            while (taken.has(text + " (" + n + ")")) n++;
            text = text + " (" + n + ")";
          }
        }
        taken.add(text);
        meas.textContent = text;
        const tw = meas.getComputedTextLength();
        const cands = [];
        for (let dy = -16; dy <= 16; dy += 16) {
          cands.push([p.x + 10, p.y + dy, Math.hypot(10, dy)]);
          cands.push([p.x - tw - 10, p.y + dy, Math.hypot(tw + 10, dy)]);
        }
        cands.sort((a, b) => a[2] - b[2]);
        let chosen = null;
        for (const [bx, by] of cands) {
          const box = {x: bx - 3, y: by - 12, w: tw + 6, h: 15};
          if (box.x < 4 || box.x + box.w > W - 4 ||
              box.y < T || box.y + box.h > T + PY) continue;
          if (boxes.some(q => hits(box, q))) continue;
          if (pts.some(q => q !== p &&
              q.x >= box.x - 7 && q.x <= box.x + box.w + 7 &&
              q.y >= box.y - 7 && q.y <= box.y + box.h + 7)) continue;
          chosen = {x: bx, y: by}; break;
        }
        if (!chosen) continue;                  // refuse-and-drop: no label
        out.push({text, x: chosen.x, y: chosen.y});
        boxes.push({x: chosen.x - 3, y: chosen.y - 12, w: tw + 6, h: 15});
      }
      svg.removeChild(meas);
      return {dom, replay: out, n_pts: pts.length};
    }"""

    def test_capability_labels_take_the_nearest_clear_slot(self):
        # #84: the capability placer walked its candidates in generation
        # order -- right(-16), left(-16), right(0), left(0), right(16),
        # left(16) -- so one blocked slot threw a label to the far side of
        # its dot (a full truncated-label width, ~215px on the live capture)
        # while nearer slots on the SAME side sat clear. The intelligence
        # chart has sorted candidates by distance since 9c74397; the placer
        # must drift a label only as far as the crowd genuinely forces it.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        for chart in ("coding", "agentic", "parameters"):
            with self.subTest(chart=chart):
                res = page.evaluate(self._REPLAY_NEAREST_CLEAR_SLOT,
                                    f"svg-{chart}")
                # a broken page must fail here, saying so -- both sides of
                # the comparison below are vacuously equal on an empty chart
                self.assertGreater(res["n_pts"], 0,
                                   f"{chart} rendered empty")
                self.assertTrue(res["dom"], f"{chart} has no labels")
                unmatched = []
                for want in res["replay"]:
                    hit = next((d for d in res["dom"] if not d["claimed"]
                                and d["text"] == want["text"]
                                and abs(d["x"] - want["x"]) <= 0.5
                                and abs(d["y"] - want["y"]) <= 0.5), None)
                    if hit:
                        hit["claimed"] = True
                    else:
                        unmatched.append(want)
                leftover = [d for d in res["dom"] if not d["claimed"]]
                self.assertEqual(
                    (unmatched, leftover), ([], []),
                    f"labels not at their nearest clear slot on {chart}: "
                    f"{[(w['text'], (w['x'], w['y'])) for w in unmatched]}"
                    f"{[(d['text'], (d['x'], d['y'])) for d in leftover]}")

        # #84's first invariant, same page: a click that does not change
        # which points are drawn must leave every label exactly where it
        # was. Table sort is the page's pure no-op control; a
        # Hide-superseded round trip must restore the identical layout,
        # because the placer is a pure function of the drawn state.
        with self.subTest(phase="no-op clicks"):
            snap = ("charts => Object.fromEntries(charts.map(c => [c, "
                    "Object.fromEntries([...document.querySelectorAll("
                    "`#svg-${c} text.lbl`)].map(t => "
                    "[t.textContent, [t.getAttribute('x'), "
                    "t.getAttribute('y')]]))]))")
            charts = ["coding", "intelligence", "agentic", "parameters"]
            before = page.evaluate(snap, charts)
            # an empty snapshot compares vacuously equal to everything --
            # the page must have rendered labels before any click is judged
            self.assertTrue(any(before[c] for c in charts),
                            "no chart rendered any label; nothing to compare")

            header = page.locator("#tbl th[data-k='ii']")
            header.click()
            self.assertEqual(page.evaluate(snap, charts), before,
                             "a table-sort click moved chart labels")
            header.click()
            self.assertEqual(page.evaluate(snap, charts), before,
                             "the second sort click moved chart labels")

            page.locator("#fSup").click()
            page.locator("#fSup").click()
            self.assertEqual(page.evaluate(snap, charts), before,
                             "a Hide-superseded round trip did not restore "
                             "the identical label layout")
        page.close()

    def test_chart_labels_are_distinct_on_every_chart(self):
        # #85: a chart label identifies exactly one row. Four effort variants
        # of Claude Opus 5.5 shared a 33-char name prefix, so all four
        # frontier rows rendered the identical truncated text on the
        # intelligence chart, and a Codex row's dict-repr effort group ate 28
        # of the 34 label characters. A collision means a reader cannot tell
        # which row a label names, so every chart's rendered label list must
        # be non-empty (the assertion must not pass vacuously on an emptied
        # chart) and all-distinct.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        for chart in ("coding", "intelligence", "agentic", "parameters"):
            with self.subTest(chart=chart):
                labels = page.locator(
                    f"#svg-{chart} text.lbl").all_text_contents()
                self.assertTrue(labels, f"{chart} rendered no labels")
                duplicates = sorted(
                    t for t in set(labels) if labels.count(t) > 1)
                self.assertEqual(
                    duplicates, [],
                    f"duplicate chart labels on {chart}")
        page.close()

    def test_table_name_cells_carry_no_dict_effort_text(self):
        # #88: AA's dict-form effort text must not reach the table -- the
        # accessible twin of the tooltip, and the surface readers who cannot
        # hover get their names from. The pin runs over every rendered name
        # cell, so one dict row in the payload fails it.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        cells = page.locator("#tbl td.name")
        self.assertGreater(cells.count(), 0,
                           "the table rendered no name cells")
        for cell in cells.all_text_contents():
            self.assertNotIn("reasoning_effort", cell)
        page.close()

    def test_the_static_tbody_serves_the_data_without_javascript(self):
        # #97: both tbody elements used to ship empty -- every data row was
        # built client-side, so a visitor with JavaScript disabled got page
        # chrome and no data. build.py now renders both bodies at build time
        # in the page's default state, so the documented accessible twin is
        # reachable without JS.
        page = self.browser.new_page(
            viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        page.goto(build.OUT.as_uri())
        payload = _data_payload(build.OUT.read_text(encoding="utf-8"))

        for table in ("fTable", "tbl"):
            self.assertGreater(
                page.locator(f"#{table} tbody tr").count(), 0,
                f"#{table} shipped an empty tbody -- no data without JS")
        self.assertEqual(
            page.locator("#tbl tbody tr").count(), len(payload["rows"]))
        # The expected lead row comes from the payload through the page's
        # default sort -- Intelligence Index descending, missing values
        # last, stable -- not from assuming payload row 0 leads the render:
        # build_rows' own ordering is a separate concern, and coupling the
        # two would false-red the hourly refresh on a capture whose top
        # model is not its first row.
        lead = sorted(
            payload["rows"],
            key=lambda row: (row["ii"] is None,
                             -(row["ii"] if row["ii"] is not None else 0.0)),
        )[0]
        first_cells = page.locator("#tbl tbody tr").first.locator(
            "td").all_text_contents()
        # The name cell is the name, a trailing space, and a vendor-retired
        # tag when the lead row carries one -- strip the tag's text rather
        # than couple the pin to its presence.
        rendered = first_cells[0]
        if rendered.endswith("vendor-retired"):
            rendered = rendered[: -len("vendor-retired")]
        self.assertEqual(
            rendered, lead["name"] + " ",
            "the static table's first row is not the default sort's top row")
        # an absent value renders as the page's em dash, never blank
        self.assertIn("—", page.locator("#tbl tbody td").all_text_contents())
        # the noscript notice covers the charts, filters and sorting; the
        # tables themselves are static and must say nothing of the sort
        self.assertIn("JavaScript", page.locator("noscript").inner_text())
        page.close()

    # Both tables' tbody DOM, cell-for-cell: className and textContent per
    # td, row order preserved. evaluate() runs even with script execution
    # disabled, so one expression reads both pages the same way.
    _TBODY_DOM = """(tid) => [...document.querySelectorAll(`#${tid} tbody tr`)]
      .map(tr => [...tr.children].map(td => [td.className, td.textContent]))"""

    def _tbody_dom(self, page, table_id):
        return page.evaluate(self._TBODY_DOM, table_id)

    def test_the_static_tbody_matches_the_js_rendered_tbody_cell_for_cell(self):
        # #97's drift guard: the rows build.py renders statically must be
        # exactly the rows the page's own script builds in its default state
        # -- same cells, same classes, same order. Any Python/JS formatter
        # drift fails here cell-for-cell rather than shipping a static table
        # that disagrees with the interactive one.
        on = self.browser.new_page(viewport={"width": 1280, "height": 900})
        off = self.browser.new_page(
            viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        on.goto(build.OUT.as_uri())
        off.goto(build.OUT.as_uri())
        # render()'s most visible act is the filter count line, which the
        # static HTML ships as an em dash -- so a non-em-dash counter proves
        # the initial render() has settled.
        on.wait_for_function(
            "document.getElementById('count').textContent !== '—'")
        for table in ("fTable", "tbl"):
            with self.subTest(table=table):
                self.assertEqual(
                    self._tbody_dom(on, table), self._tbody_dom(off, table))
        on.close()
        off.close()

    def test_footer_carries_a_licence_note_linking_the_licence(self):
        # #69 (page half): the generated page ships under the repo's MIT
        # licence but never said so. The footer now carries the one-line
        # copyright/licence note, linking the licence blob on GitHub.
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(build.OUT.as_uri())
        foot = page.locator(".foot")
        link = foot.locator(
            "a[href='https://github.com/Nitjsefnie/ai-researcher"
            "/blob/main/LICENSE']")
        self.assertEqual(link.count(), 1)
        self.assertEqual(link.inner_text(), "MIT licence")
        text = foot.inner_text()
        self.assertIn("© 2026 Peter Z (Nitjsefnie)", text)
        self.assertIn("MIT licence", text)
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


def _load_perf_budgets():
    """Import scripts/ci/perf_budgets.py by path.

    scripts/ci is not a package and deliberately has no __init__.py --
    it holds standalone CI entry points, not an importable library.
    """
    path = (pathlib.Path(__file__).resolve().parents[1]
            / "scripts" / "ci" / "perf_budgets.py")
    spec = importlib.util.spec_from_file_location("perf_budgets", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["perf_budgets"] = module
    spec.loader.exec_module(module)
    return module


perf_budgets = _load_perf_budgets()


class PerfBudgetTests(unittest.TestCase):
    """The CI gate for issue #109's tighten-only perf ratchet.

    This class runs in the coverage job; the 3x3 matrix --ignores
    tests/test_browser.py, so this is where CI enforces the committed
    budgets in .github/perf-budgets.json on every pull request. Nothing
    about the journeys or the verdict is re-implemented here: the
    journeys come from the harness's own runners
    (scripts/ci/perf_budgets.py) and the verdict from its own gate, so
    this class and `perf_budgets.py --check` share one runner and one
    gate logic and cannot drift on those; the capture behind each is
    deliberately different -- this class's fixed fixture, the CLI's the
    checkout's own.

    The gated page is built from this class's own DETERMINISTIC fixture
    capture (#153), never the ambient data/: budgets measure code cost
    and must be capture-size-invariant (issue #112), but AA's rollout size
    moves the scale underneath a page built from the ambient capture. The
    fixture is byte-identical every run, so the gate judges ONE fixed
    workload against the committed ceilings, whatever AA ships.
    """

    @classmethod
    def setUpClass(cls):
        # The class builds its own page into a temp dir under ROOT and
        # keeps build.OUT pointed there for the class's lifetime -- the
        # journey test navigates build.OUT.as_uri() and gates
        # build.OUT.read_bytes(). The real out/frontier-models.html is
        # never touched (#114); tearDownClass restores the module path.
        # The source stamp is stripped for the build so the bytes this
        # class gates are the canonical stamp-less build, whatever the
        # ambient environment carries. The capture behind the build is
        # the class's deterministic fixture (#153): a fixed synthetic the
        # committed ceilings evaluate, written into the temp dir so the
        # ambient data/ never reaches
        # the gate.
        cls._saved = (build.RAW, build.AGENTS_RAW, build.OUT)
        # The directory outlives this setup -- tearDownClass cleans it up
        # after the browser closes -- so it cannot live in a with.
        cls._page_dir = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
            prefix=".issue-114-perf-", dir=build.ROOT)
        data = pathlib.Path(cls._page_dir.name) / "data"
        data.mkdir()
        (data / "models.json").write_text(
            json.dumps(_probe_models(_PERF_FIXTURE_MODELS)),
            encoding="utf-8")
        (data / "coding-agents.json").write_text(
            json.dumps(_PROBE_AGENTS), encoding="utf-8")
        build.RAW = data / "models.json"
        build.AGENTS_RAW = data / "coding-agents.json"
        build.OUT = pathlib.Path(cls._page_dir.name) / "frontier-models.html"
        saved_stamp = os.environ.pop("AA_SOURCE_COMMIT", None)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
            # The launch is inside the handler's reach too (mirrors
            # BrowserInteractionTests): setUpClass failure skips
            # tearDownClass, so a raise from playwright's start or the
            # launch itself would strand build.OUT at the temp path.
            cls.playwright = sync_playwright().start()
            # A second browser launch, mirroring the harness's recipe over
            # this module's existing discovery: --js-flags=--expose-gc is
            # load-bearing -- the journeys place the load's garbage
            # collection through window.gc(), which the flag provides.
            cls.browser = cls.playwright.chromium.launch(
                executable_path=CHROMIUM_EXECUTABLE,
                headless=True,
                args=["--no-sandbox", "--js-flags=--expose-gc"],
            )
        except BaseException:
            build.RAW, build.AGENTS_RAW, build.OUT = cls._saved
            cls._page_dir.cleanup()
            raise
        finally:
            if saved_stamp is not None:
                os.environ["AA_SOURCE_COMMIT"] = saved_stamp

    @classmethod
    def tearDownClass(cls):
        # Restore the module paths first, mirroring BrowserInteractionTests:
        # a browser-close failure must not leave build.OUT at the temp path.
        build.RAW, build.AGENTS_RAW, build.OUT = cls._saved
        cls._page_dir.cleanup()
        cls.browser.close()
        cls.playwright.stop()

    def test_every_journey_meets_its_committed_budget(self):
        budgets = perf_budgets.load_budgets(
            build.ROOT / ".github" / "perf-budgets.json")
        journeys = perf_budgets.measure_journeys(
            self.browser, build.OUT.as_uri())
        raw = build.OUT.read_bytes()
        measurement = {
            "bytes": {
                "raw": len(raw),
                "gzip": len(gzip.compress(raw, 9, mtime=0)),
                "code_bytes": perf_budgets.code_bytes(raw),
            },
            "journeys": journeys,
        }
        findings = perf_budgets.gate(budgets, measurement)
        self.assertEqual(
            findings, [],
            "the page regressed past its committed performance budgets "
            "(path: head exceeds base) -- make the page meet the budget "
            "again; re-seeding a budget is the lead's explicit call")

    def _fixture_measurement(self, root, models, agents):
        """Build a fixture page under `root` (never out/) and measure it
        through the harness: {code_bytes, gated journey metrics}."""
        raw = root / "models.json"
        agents_raw = root / "coding-agents.json"
        page = root / "frontier-models.html"
        raw.write_text(json.dumps(models), encoding="utf-8")
        agents_raw.write_text(json.dumps(agents), encoding="utf-8")
        old_raw, old_agents, old_out = (
            build.RAW, build.AGENTS_RAW, build.OUT)
        build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, page
        try:
            saved_stamp = os.environ.pop("AA_SOURCE_COMMIT", None)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
            finally:
                if saved_stamp is not None:
                    os.environ["AA_SOURCE_COMMIT"] = saved_stamp
        finally:
            build.RAW, build.AGENTS_RAW, build.OUT = (
                old_raw, old_agents, old_out)
        journeys = perf_budgets.measure_journeys(
            self.browser, page.as_uri())
        gated = {"bytes": perf_budgets.code_bytes(page.read_bytes())}
        for journey, metrics in perf_budgets.GATED_JOURNEY_METRICS.items():
            for metric in metrics:
                gated[f"journeys.{journey}.{metric}"] = \
                    journeys[journey][metric]
        return gated

    def test_row_free_metrics_are_identical_across_capture_sizes(self):
        """Decoupling proof (issue #112): the SAME code built against a
        small (~8 rows) and a large (~60 rows) synthetic capture must
        weigh the same in code bytes and cost the same in hover tooltip
        work -- the two gated metrics that are row-free by construction
        cannot be moved by capture growth. The long-task counts are
        deliberately absent: they are threshold physics (the 60-row
        page's render crosses the 50 ms task threshold, the 8-row
        page's does not), so their decoupling proof is the live
        686 -> 688 capture growth below, not a size fixture."""
        small_models, large_models = _probe_models(6), _probe_models(58)
        with tempfile.TemporaryDirectory(
                prefix=".decouple-small-", dir=build.ROOT) as small_dir:
            with tempfile.TemporaryDirectory(
                    prefix=".decouple-large-", dir=build.ROOT) as large_dir:
                small = self._fixture_measurement(
                    pathlib.Path(small_dir), small_models, _PROBE_AGENTS)
                large = self._fixture_measurement(
                    pathlib.Path(large_dir), large_models, _PROBE_AGENTS)
        row_free = ("bytes", "journeys.hover.dom_nodes_mutated")
        self.assertEqual(
            {k: small[k] for k in row_free},
            {k: large[k] for k in row_free},
            "a row-free gated metric moved with the capture's size")

    def _preceding_capture_blobs(self):
        """The 686-model capture that preceded main's 688 refresh, or
        None on a checkout whose history cannot reach it (shallow CI):
        the fixture proof above carries the property there."""
        result = subprocess.run(  # pylint: disable=subprocess-run-check
            ["git", "show", "875d024^:data/aa-raw-models.json"],
            cwd=str(build.ROOT), capture_output=True, check=False)
        models = result.stdout if result.returncode == 0 else None
        result = subprocess.run(  # pylint: disable=subprocess-run-check
            ["git", "show", "875d024^:data/aa-raw-coding-agents.json"],
            cwd=str(build.ROOT), capture_output=True, check=False)
        agents = result.stdout if result.returncode == 0 else None
        return models, agents

    def test_the_gate_passes_on_the_preceding_capture_without_budget_edit(
            self):
        """Decoupling proof, live repro (issue #112): --check over the
        686-model capture that preceded main's growth passes against the
        committed budgets with no budget edit."""
        models_686, agents_686 = self._preceding_capture_blobs()
        if models_686 is None or agents_686 is None:
            self.skipTest("shallow checkout: the pre-growth capture blob "
                          "is not reachable; the fixture proof carries "
                          "the property")
        with tempfile.TemporaryDirectory(
                prefix=".gate-686-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            (root / "models.json").write_bytes(models_686)
            (root / "coding-agents.json").write_bytes(agents_686)
            old_raw, old_agents = build.RAW, build.AGENTS_RAW
            build.RAW, build.AGENTS_RAW = (root / "models.json",
                                           root / "coding-agents.json")
            try:
                # The class browser is already live (playwright's sync
                # API refuses a second instance in one thread), so the
                # proof drives the harness's own runners against the
                # 686-built page and its own gate -- the same functions
                # `--check` runs, without a second sync_playwright.
                with tempfile.TemporaryDirectory(
                        prefix=".gate-686-build-", dir=build.ROOT) as bld:
                    page = pathlib.Path(bld) / "frontier-models.html"
                    old_out = build.OUT
                    build.OUT = page
                    try:
                        with contextlib.redirect_stdout(io.StringIO()):
                            build.main()
                    finally:
                        build.OUT = old_out
                    measurement = {
                        "bytes": {
                            "code_bytes": perf_budgets.code_bytes(
                                page.read_bytes()),
                        },
                        "journeys": perf_budgets.measure_journeys(
                            self.browser, page.as_uri()),
                    }
            finally:
                build.RAW, build.AGENTS_RAW = old_raw, old_agents
        findings = perf_budgets.gate(
            perf_budgets.load_budgets(
                build.ROOT / ".github" / "perf-budgets.json"), measurement)
        self.assertEqual(
            findings, [],
            "the gate red on a capture whose growth it was rebuilt to "
            "survive -- a budget moved with the data")


# The pin crowd test_pinned_names_stay_labelled_on_every_chart pins on the
# intelligence chart: the audit's count (#27), large enough to exhaust the
# clear slots so the clamp fallback is the only option. A property of the
# test's own fixture -- never of the ambient capture (#153).
PIN_CROWD = 40

# The row count of PerfBudgetTests' deterministic fixture capture (#153).
# Measured on this box, 8 runs: code_bytes 78687 against the committed 79700;
# long_task_count maxima load 1 / filter 1 / sort 1 / hover 0 against the
# committed 2 / 2 / 2 / 1; hover dom_nodes_mutated 32 against the committed
# 40 -- every budget met with margin, the load journey still crossing the
# 50 ms threshold so the long-task family keeps gating. 58 rows (the
# decoupling proof's large size) also passes but occasionally pushes hover's
# single long task onto its budget of 1, so the reference page sits at the
# largest size probed that keeps the tightest budget clear. A property of
# the gate's own page -- never of the ambient capture. Re-measure before
# changing.
_PERF_FIXTURE_MODELS = 40


def _probe_models(count):
    """A deterministic live-like synthetic capture: scores descend as
    costs rise, so the frontier stays compact like the real page's."""
    out = []
    for i in range(count):
        score = round(80.0 - i * 0.04, 2)
        cost = round(0.5 + i * 0.9, 3)
        out.append({
            "name": f"Probe Model {i:04d}",
            "modelCreatorName": "Probe Lab",
            "isOpenWeights": i % 3 == 0,
            "slug": f"probe-model-{i:04d}",
            "intelligenceIndex": score,
            "gdpvalNormalized": 0.4 + (i % 20) * 0.01,
            "parameters": 20 + (i % 40) * 3,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": cost},
                "evaluations": [
                    {"slug": "gdpval-aa",
                     "weightedCostPerTask": round(cost / 10.0, 4)},
                ],
            },
        })
    return out


_PROBE_AGENTS = [
    {"id": "probe-agent-1", "displayLabel": "Probe Agent One",
     "agentName": "Probe Agent One CLI",
     "hostModelSlug": "probe-model-0000",
     "display": {"creator": {"agent": "Probe Agent Lab",
                             "model": "Probe Lab"}},
     "indexScore": 0.64, "mean": {"costUsd": 2.5,
                                  "agentWallTimeSec": 900.0}},
    {"id": "probe-agent-2", "displayLabel": "Probe Agent Two",
     "agentName": "Probe Agent Two CLI",
     "hostModelSlug": "probe-model-0001",
     "display": {"creator": {"agent": "Probe Agent Lab",
                             "model": "Probe Lab"}},
     "indexScore": 0.55, "mean": {"costUsd": 1.9,
                                  "agentWallTimeSec": 700.0}},
]


class BuildProvenanceTests(unittest.TestCase):
    """#49: the footer's provenance — source commit when the build
    environment carries one, and a sha256 over the build's inputs that a
    reader can verify today, by hashing the committed files. The content
    hash covers the two capture files, whole bytes concatenated
    models-then-agents -- exactly what the footer's own inputs note
    names."""

    COMMIT = "e5e10f1c0ffee4215deadbeefcafe0123456789a"

    @staticmethod
    def _foot(html):
        """The footer div's text, and nothing else -- slicing to end-of-file
        would drag in the payload <script> the footer is not responsible
        for."""
        start = html.index('class="foot"')
        return html[start:html.index("<script>", start)]

    @staticmethod
    def _expected_digest(data_dir):
        """The sha256 a reader recomputes from the data directory: the two
        capture files, whole and in that order -- the same rule build.py
        states in the footer's inputs note."""
        digest = hashlib.sha256()
        digest.update((data_dir / "aa-raw-models.json").read_bytes())
        digest.update((data_dir / "aa-raw-coding-agents.json").read_bytes())
        return digest.hexdigest()

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
            foot = self._foot(html)
            self.assertIn(self.COMMIT, foot)
            # the content hash equals an independently computed sha256 over
            # the build's inputs, read straight off the data directory
            self.assertIn(self._expected_digest(build.RAW.parent), foot)

    def test_footer_omits_the_source_commit_when_the_environment_is_unset(self):
        with tempfile.TemporaryDirectory(prefix=".issue-49-build-",
                                         dir=build.ROOT) as tmp:
            output = pathlib.Path(tmp) / "frontier-models.html"
            html = self._build(output).decode("utf-8")

            foot = self._foot(html)
            # the SHA itself is the thing that would render on regression, so
            # its absence -- here and page-wide -- is the absence oracle
            self.assertNotIn(self.COMMIT, foot)
            self.assertNotIn(self.COMMIT, html)
            # the content hash is verifiable today without any workflow
            # change, so it renders with or without the commit
            self.assertIn(self._expected_digest(build.RAW.parent), foot)

    def test_a_malformed_source_commit_renders_no_stamp_and_no_marker_splice(self):
        # AA_SOURCE_COMMIT is build-machine input, so only SHA-shaped values
        # (7-40 hex chars) render. Anything else must be treated exactly like
        # an unset variable -- otherwise a value carrying a template marker
        # would be spliced by the later __CAPTURED__/__DATA__ substitutions.
        malformed = "__CAPTURED__ <script>__DATA__</script>"
        with tempfile.TemporaryDirectory(prefix=".issue-49-build-",
                                         dir=build.ROOT) as tmp:
            output = pathlib.Path(tmp) / "frontier-models.html"
            html = self._build(output, commit=malformed).decode("utf-8")

            foot = self._foot(html)
            self.assertNotIn("Source commit", foot)
            self.assertNotIn(malformed, foot)
            # nothing the env carried survived into the page, spliced or not
            self.assertNotIn("__CAPTURED__", foot)
            self.assertNotIn("__DATA__", foot)
            self.assertNotIn("<script>", foot)

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


class ZeroScoreBrowserTests(unittest.TestCase):
    """Issue #146 in a real browser: a zero capability score is a legal AA
    publication, and the JS fillFrontiers cell for a zero-score frontier row
    must render the em dash the static render shows -- "$Infinity" would
    fail the drift contract and read as a real price. A dedicated class
    exists because this JS path never executes on a normal page (the
    standard capture puts no zero on the frontier), so without coverage
    wiring the JavaScript ratchet reads it as uncovered and reds the
    coverage job.
    """

    @classmethod
    def setUpClass(cls):
        cls._saved = (build.RAW, build.AGENTS_RAW, build.OUT)
        cls._dir = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
            prefix=".issue-146-browser-", dir=build.ROOT)
        data = pathlib.Path(cls._dir.name) / "data"
        data.mkdir()
        # gdpval 0.0 with the fixture's gdpval eval (weightedCostPerTask
        # 0.80 -> measured cost 8.00) puts the page's only model on the
        # agentic frontier carrying a zero score.
        (data / "aa-raw-models.json").write_text(
            json.dumps([test_build.model_fixture(gdpval=0.0)]),
            encoding="utf-8")
        (data / "aa-raw-coding-agents.json").write_text(
            json.dumps([test_build.agent_fixture()]), encoding="utf-8")
        (data / "captured-at.txt").write_text("2026-10-04\n",
                                              encoding="utf-8")
        build.RAW = data / "aa-raw-models.json"
        build.AGENTS_RAW = data / "aa-raw-coding-agents.json"
        build.OUT = pathlib.Path(cls._dir.name) / "frontier-models.html"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(
                executable_path=CHROMIUM_EXECUTABLE,
                headless=True,
                args=["--no-sandbox"])
        except BaseException:
            build.RAW, build.AGENTS_RAW, build.OUT = cls._saved
            cls._dir.cleanup()
            raise
        # The same V8 block-coverage wiring BrowserInteractionTests uses.
        cls._coverage_entries = []
        cls._open_pages = []
        original_new_page = cls.browser.new_page

        def new_page(**kwargs):
            page = original_new_page(**kwargs)
            if kwargs.get("java_script_enabled") is False:
                return page
            session = page.context.new_cdp_session(page)
            session.send("Debugger.enable")
            session.send("Profiler.enable")
            session.send("Profiler.startPreciseCoverage",
                         {"callCount": True, "detailed": True})
            original_close = page.close

            def close(**close_kwargs):
                if (page, session) in cls._open_pages:
                    cls._open_pages.remove((page, session))
                cls._coverage_entries.extend(collect_page_coverage(session))
                return original_close(**close_kwargs)

            page.close = close
            cls._open_pages.append((page, session))
            return page

        cls.browser.new_page = new_page

    @classmethod
    def tearDownClass(cls):
        build.RAW, build.AGENTS_RAW, build.OUT = cls._saved
        for _page, session in list(cls._open_pages):
            try:
                cls._coverage_entries.extend(collect_page_coverage(session))
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        cls._open_pages.clear()
        dump = os.environ.get("JS_COVERAGE_OUT")
        if dump:
            path = pathlib.Path(dump)
            entries = cls._coverage_entries
            if path.exists():
                try:
                    entries = json.loads(
                        path.read_text(encoding="utf-8")) + entries
                except (OSError, json.JSONDecodeError):
                    pass
            path.write_text(json.dumps(entries), encoding="utf-8")
        cls.browser.close()
        cls.playwright.stop()
        cls._dir.cleanup()

    def test_the_zero_score_frontier_cell_is_em_dash(self):
        page = self.browser.new_page()
        try:
            page.goto(build.OUT.as_uri())
            # fillTable/fillFrontiers ran to completion -- a crash in the
            # new JS branch would leave the frontier table empty.
            page.wait_for_selector("#fTable tbody tr")
            # The agentic section, not the agent row's coding section --
            # both rows carry the model text.
            row = page.locator("#fTable tbody tr",
                               has_text="GDPval-AA v2").filter(
                                   has_text="Fixture Model").first
            cells = row.locator("td").all_text_contents()
            # metric | name | creator | score | cost | $/point | weights
            self.assertEqual(cells[3], "0.0")
            self.assertEqual(cells[4], "$8.00")
            self.assertEqual(cells[5], "—")
        finally:
            page.close()
