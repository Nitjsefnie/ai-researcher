"""AA coding-agent flight record extraction."""
import json
import unittest

from test_fetch_aa import agent_payload, agent_row, fetch_aa


class CodingAgentRowsTests(unittest.TestCase):
    def test_extracts_rows_carrying_a_paired_score_and_cost(self):
        rows = [agent_row(f"Agent - Model {i}") for i in range(25)]

        got = fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertEqual(len(got), 25)
        self.assertEqual(got[0]["indexScore"], 0.64)
        self.assertEqual(got[0]["mean"]["costUsd"], 1.5)

    def test_marker_strings_between_rows_are_skipped(self):
        payload = fetch_aa.coding_agent_rows(
            agent_payload([agent_row(f"A - {i}") for i in range(21)]))

        self.assertTrue(all(isinstance(r, dict) for r in payload))

    def test_rows_are_collected_from_every_array_not_just_the_biggest(self):
        # AA splits highlighted and remaining rows across arrays.
        highlighted = agent_payload([agent_row(f"H - {i}") for i in range(10)])
        rest = agent_payload([agent_row(f"R - {i}") for i in range(3)],
                             key="benchmarkRows")

        got = fetch_aa.coding_agent_rows(highlighted + rest)

        self.assertEqual(len(got), 13)

    def test_an_array_starting_with_a_back_reference_is_not_skipped(self):
        # benchmarkRows can start with an RSC back-reference.
        rows = [agent_row(f"A - {i}") for i in range(13)]
        body = json.dumps(rows, separators=(",", ":"))[1:-1]
        payload = ('{"benchmarkRows":["$d:props:children:1:props:rows:0",'
                   + body + ']}')

        self.assertEqual(len(fetch_aa.coding_agent_rows(payload)), 13)

    def test_a_row_reachable_twice_is_counted_once(self):
        rows = [agent_row(f"A - {i}") for i in range(13)]
        doubled = agent_payload(rows) + agent_payload(rows, key="benchmarkRows")

        self.assertEqual(len(fetch_aa.coding_agent_rows(doubled)), 13)

    def test_overlapping_arrays_union_rather_than_replace(self):
        highlights = agent_payload([agent_row(f"H - {i}") for i in range(10)])
        full = agent_payload([agent_row(f"F - {i}") for i in range(58)])

        got = fetch_aa.coding_agent_rows(highlights + full)

        self.assertEqual(len(got), 68)

    def test_rows_without_a_cost_do_not_count_toward_the_floor(self):
        rows = [agent_row(f"A - {i}", cost=None) for i in range(58)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("schema changed", str(caught.exception))

    def test_a_collapsed_table_exits_rather_than_publishing_a_stub(self):
        rows = [agent_row(f"A - {i}") for i in range(fetch_aa.CODING_ROW_FLOOR - 1)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("schema changed", str(caught.exception))

    def test_the_highlighted_selection_alone_is_enough(self):
        rows = [agent_row(f"A - {i}") for i in range(10)]

        self.assertEqual(len(fetch_aa.coding_agent_rows(agent_payload(rows))), 10)
