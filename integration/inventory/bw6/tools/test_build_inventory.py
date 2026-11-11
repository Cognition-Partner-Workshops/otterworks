import json
import unittest

from build_inventory import INVENTORY, classification, inventory_data, parse_decisions, readme, wave_plan


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
            expected_class = 'needs-human-decision' if expected else 'straight-conversion'
            self.assertEqual(classification(process, blockers), expected_class)
            self.assertEqual(process['classification'], expected_class)
            self.assertEqual(process['decision_ids'], expected)
            self.assertEqual(process['wave'], waves[process['id']])
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
        self.assertIn('decisions.md#d-12-instruction-intake-xa-scope-ends-before-calls', plan)
        self.assertEqual(plan.count('| needs-human-decision |'), 16)
        self.assertEqual(index.count('| needs-human-decision |'), 16)
        self.assertEqual(plan.count('| straight-conversion |'), 8)
        self.assertEqual(index.count('| straight-conversion |'), 8)
        held = plan.split('## Held for decision')[1].split('## Wave summary')[0]
        self.assertNotIn('straight-conversion', held)
        self.assertNotIn('payments.currency-routing', held)

    def test_empty_decisions_release_all_without_changing_waves(self):
        processes, blockers, waves = inventory_data(self.graph, {})
        self.assertTrue(all(not ids for ids in blockers.values()))
        self.assertTrue(all(classification(p, blockers) == 'straight-conversion' for p in processes))
        self.assertEqual(list(waves.values()).count(3), 3)
        plan = wave_plan(self.graph, {})
        self.assertEqual(plan.count('| straight-conversion |'), 24)
        self.assertNotIn('| needs-human-decision |', plan)

    def test_groundwork_is_not_a_flow_blocker(self):
        plan = wave_plan(self.graph, self.decisions)
        for title in ('Environment credentials', 'Call-process binding', 'HTTP side effects',
                      'Dead-letter ownership', 'Durable subscriber', 'Request schema namespace'):
            self.assertIn('### ' + title, plan)
        self.assertEqual(len(self.decisions), 12)


if __name__ == '__main__':
    unittest.main()
