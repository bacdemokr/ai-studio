"""Resource links are optional and are hidden unless startup verifies them."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import resource_links


PAGE = '''<a href="https://unrelated.example/">Unrelated</a>
<details id="studio-resources" class="studio-resources">
  <summary>Resources</summary>
  <nav>
    <a data-bac-resource href="https://good.example/" target="_blank">Good</a>
    <a data-bac-resource href="https://bad.example/" target="_blank">Bad</a>
  </nav>
</details>
'''


class ResourceLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.page = Path(self.temp.name) / 'index.html'
        self.page.write_text(PAGE, encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_only_verified_links_remain(self):
        kept = resource_links.filter_page(
            self.page, checker=lambda url: url == 'https://good.example/')
        result = self.page.read_text(encoding='utf-8')
        self.assertEqual(kept, ['https://good.example/'])
        self.assertIn('https://good.example/', result)
        self.assertNotIn('https://bad.example/', result)
        self.assertIn('https://unrelated.example/', result)

    def test_resource_menu_is_hidden_when_no_link_is_verified(self):
        self.assertEqual(resource_links.filter_page(self.page, checker=lambda _url: False), [])
        result = self.page.read_text(encoding='utf-8')
        self.assertNotIn('id="studio-resources"', result)
        self.assertIn('https://unrelated.example/', result)

    def test_check_errors_hide_links_without_blocking_startup(self):
        def unavailable(_url):
            raise TimeoutError('offline')
        self.assertEqual(resource_links.filter_page(self.page, checker=unavailable), [])
        self.assertNotIn('id="studio-resources"', self.page.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
