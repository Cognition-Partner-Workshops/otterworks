import json
import unittest

from build_inventory import INVENTORY, inventory_data, parse_decisions, readme, wave_plan


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((INVENTORY / 'graph.json').read_text())
        cls.decisions = parse_decisions((INVENTORY / 'decisions.md').read_text())

    def test_decision_parser_normal_empty_and_error(self):
        self.assertEqual(parse_decisions(''), {})
        text = '## D-01 Example question\n\n**Affected processes:** `payments.example`.\n\n**Decision:** \n'
        parsed = parse_decisions(text)
        self.assertTrue(parsed['D-01']['open'])
        self.assertEqual(parsed['D-01']['slug'], 'd-01-example-question')
        self.assertEqual(parsed['D-01']['processes'], ['payments.example'])
        self.assertFalse(parse_decisions(text.rstrip() + ' approved\n')['D-01']['open'])
        with self.assertRaisesRegex(ValueError, 'missing affected'):
            parse_decisions('## D-01 Invalid\n')
        with self.assertRaisesRegex(ValueError, 'duplicate decision'):
            parse_decisions(text + text)
        with self.assertRaisesRegex(ValueError, 'unknown affected process'):
            inventory_data(self.graph, parsed)

    def test_source_derived_wave_slots_and_blockers(self):
        processes, blockers, waves = inventory_data(self.graph, self.decisions)
        self.assertEqual(len(processes), 24)
        self.assertEqual([list(waves.values()).count(w) for w in (1, 2, 3)], [9, 12, 3])
        for process in processes:
            name = process['label']
            expected = [d for d, value in self.decisions.items() if name in value['processes'] and value['open']]
            self.assertEqual(blockers[name], expected)
            self.assertTrue({'D-09', 'D-11', 'D-23', 'D-24', 'D-25'} <= set(blockers[name]))
        for edge in self.graph['edges']:
            if edge['kind'] == 'call_process':
                self.assertEqual(waves[edge['from']], 3)
                self.assertEqual(waves[edge['to']], 2)

    def test_documents_cover_all_processes_and_full_anchors(self):
        plan = wave_plan(self.graph, self.decisions)
        index = readme(self.graph, self.decisions)
        self.assertEqual(len([line for line in plan.splitlines() if line.startswith('| `')]), 24)
        self.assertEqual(len([line for line in index.splitlines() if line.startswith('| `')]), 24)
        for identifier, decision in self.decisions.items():
            target = f'decisions.md#{decision["slug"]}'
            self.assertIn(target, plan)
            self.assertIn(target, index)
            self.assertTrue(decision['slug'].startswith(identifier.lower() + '-'))
        self.assertIn('decisions.md#d-09-transaction-and-acknowledgement-boundary', plan)
        self.assertEqual(plan.count('| needs-human-decision |'), 24)
        self.assertEqual(index.count('| needs-human-decision |'), 24)


if __name__ == '__main__':
    unittest.main()
