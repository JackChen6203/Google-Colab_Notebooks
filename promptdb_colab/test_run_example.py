import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('run_example', ROOT / 'run_example.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ExecutionGraphTests(unittest.TestCase):
    def test_muted_nodes_do_not_leave_dangling_execution_links(self):
        source = json.loads((ROOT / 'examples/workflows/Krea2_PromptDB_Example.json').read_text(encoding='utf-8'))
        graph, metadata = runner.prepare(source)
        self.assertEqual(len(metadata['nodes']), 37)
        self.assertEqual(metadata['links'], source['links'])
        self.assertEqual(graph['21']['inputs']['width'], 256)
        self.assertEqual(graph['22']['inputs']['steps'], 2)
        self.assertEqual(graph['24']['inputs']['images'], ['23', 0])
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value, list):
                    self.assertIn(value[0], graph)
        for muted in (n for n in source['nodes'] if n.get('mode') in (2, 4)):
            self.assertNotIn(str(muted['id']), graph)


if __name__ == '__main__':
    unittest.main()
