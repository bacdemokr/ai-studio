import unittest
from research_citations import unsupported_citations


class CitationTests(unittest.TestCase):
    def test_actual_source_and_returned_links_are_allowed(self):
        sources = [{'url': 'http://example.com/news/', 'text': '[Story](https://example.com/story?q=1).'}]
        self.assertEqual(unsupported_citations('See https://example.com/news#today and https://example.com/story?q=1.', sources), [])

    def test_invented_path_or_changed_query_is_not_a_source(self):
        sources = [{'url': 'https://example.com/news', 'text': 'A factual excerpt.'}]
        self.assertEqual(unsupported_citations('See https://example.com/acquisition', sources), ['https://example.com/acquisition'])
        self.assertEqual(unsupported_citations('https://example.com/news?year=2026', sources), ['https://example.com/news?year=2026'])

    def test_non_url_text_is_not_claimed_to_be_fact_checked(self):
        self.assertEqual(unsupported_citations('This is a potentially unsupported claim.', []), [])

    def test_balanced_parentheses_in_real_article_urls_are_preserved(self):
        url='https://en.wikipedia.org/wiki/Python_(programming_language)'
        self.assertEqual(unsupported_citations('[Python]('+url+').', [{'url':url,'text':'Python'}]), [])
