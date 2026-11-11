import unittest
from collections import Counter

from build_graph import Graph, markdown


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = Graph().build()

    def test_source_inventory(self):
        nodes = {n['id']: n for n in self.graph['nodes']}
        self.assertEqual(sum(n['type'] == 'process' for n in nodes.values()), 24)
        kinds = Counter(e['kind'] for e in self.graph['edges'])
        self.assertEqual(kinds['call_process'], 12)
        self.assertEqual(kinds['fault_to'], 24)
        for edge in self.graph['edges']:
            self.assertIn(edge['from'], nodes)
            self.assertIn(edge['to'], nodes)
            if edge['kind'] == 'call_process':
                self.assertFalse(edge['name_matches'])
                self.assertEqual(edge['declared_name'], 'halvergate.' + edge['called_name'])
                self.assertEqual(edge['citations'], [nodes[edge['to']]['citation']])
        self.assertEqual(self.graph['summary']['producer_consumer_matches'], [])
        self.assertEqual(len(self.graph['summary']['profile_differences']), 1)
        starter = nodes['jms:HB.STATEMENT.DROP']
        self.assertTrue(starter['non_jms_starter'])
        self.assertIsNone(starter['destination_type'])

    def test_empty_graph_summary(self):
        graph = Graph().document()
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])
        self.assertTrue(all(not value for value in graph['summary'].values()))

    def test_diagram_and_tables(self):
        document = markdown(self.graph)
        self.assertEqual(document.count('subgraph domain'), 5)
        self.assertEqual(document.count('-. "call (name mismatch)" .->'), 12)
        self.assertIn('["${screening.url} (dev v1 / prod v2)"]', document)
        self.assertIn('24 processes configure a fault to HB.UNDLV and 24 reference EmsConnection.', document)
        self.assertIn('22 processes reference LedgerJdbc;', document)
        self.assertIn('`payments.currency-routing`, `statements-documents.pdf-request`', document)
        rows = [line for line in document.splitlines() if line.startswith('| `')]
        self.assertEqual(len(rows), len(self.graph['edges']))


if __name__ == '__main__':
    unittest.main()
