import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'node' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExampleTests(unittest.TestCase):
    def test_all_original_node_types_and_links(self):
        workflow = json.loads((ROOT / 'examples/workflows/Krea2_PromptDB_Example.json').read_text(encoding='utf-8'))
        self.assertEqual(len(workflow['nodes']), 37)
        counts = Counter(n['type'] for n in workflow['nodes'])
        self.assertEqual(counts['PromptDB'], 17)
        self.assertEqual(counts['LayerUtility: TextJoinV2'], 6)
        self.assertEqual(counts['Krea2CastPick'], 1)
        ids = {n['id'] for n in workflow['nodes']}
        links = {link[0] for link in workflow['links']}
        for link in workflow['links']:
            self.assertIn(link[1], ids)
            self.assertIn(link[3], ids)
        for node in workflow['nodes']:
            for port in node.get('inputs', []):
                if port.get('link') is not None:
                    self.assertIn(port['link'], links)

    def test_every_prompt_selection_resolves(self):
        db = json.loads((ROOT / 'examples/prompts_krea2.json').read_text(encoding='utf-8'))
        workflow = json.loads((ROOT / 'examples/workflows/Krea2_PromptDB_Example.json').read_text(encoding='utf-8'))
        for node in workflow['nodes']:
            if node['type'] == 'PromptDB':
                category, name, text, database = node['widgets_values']
                self.assertIn(name, db[category])
                self.assertEqual(text, '')
                self.assertEqual(database, 'krea2')

    def test_join_and_cast_nodes(self):
        join = load('text_join').TextJoinV2()
        self.assertEqual(join.text_join(text_1='A', text_2='SKIP', text_3='B'), ('A, B',))
        cast = load('cast_compat').Krea2CastPick()
        self.assertEqual(cast.pick('Walking [[krea_own_expr]]', 'An adult traveler', 'Smile'), ('Walking ', 'An adult traveler', ''))


if __name__ == '__main__':
    unittest.main()
