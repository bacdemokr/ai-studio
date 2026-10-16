"""Portable example input contracts, independent of model output."""
import csv
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GoalExamplesTests(unittest.TestCase):
    def test_sample_files_and_numeric_gpu_ranking(self):
        examples = json.loads((ROOT / 'src/goal-examples.json').read_text())
        self.assertEqual(len({item['id'] for item in examples}), len(examples))
        for item in examples:
            if item.get('document'):
                self.assertTrue((ROOT / 'scenario' / item['document']).is_file())
        stores = next(item for item in examples if item['id'] == 'stores')
        self.assertIs(stores.get('requiredDocument'), True)
        gpu = next(item for item in examples if item['id'] == 'gpu')
        with (ROOT / 'scenario' / gpu['document']).open(newline='') as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 11)
        self.assertEqual(len({row['product'] for row in rows}), 11)
        self.assertTrue(all(int(row['max_single_gpu_tdp_w']) > 0 for row in rows))
        top = sorted(rows, key=lambda row: -int(row['max_single_gpu_tdp_w']))[:5]
        self.assertEqual([(row['product'], int(row['max_single_gpu_tdp_w'])) for row in top], [
            ('Vera Rubin NVL72', 2300), ('HGX Rubin NVL8', 2300),
            ('GB300 NVL72', 1400), ('GB200 NVL72', 1200), ('GB200 NVL4', 1200)])


if __name__ == '__main__':
    unittest.main()
