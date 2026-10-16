import unittest
from research_citations import unsupported_citations, bounded_sources


class CitationTests(unittest.TestCase):
    def test_later_paper_is_not_rejected_when_earlier_excerpts_fill_context(self):
        sources = [{'url': f'https://arxiv.org/abs/2606.{10000+i}', 'text': 'x' * 1393} for i in range(6)]
        bounded = bounded_sources(sources)
        self.assertLessEqual(sum(len(s['text']) for s in bounded), 6000)
        self.assertEqual(unsupported_citations(sources[-1]['url'], bounded), [])
        self.assertEqual(unsupported_citations('https://arxiv.org/abs/2606.99999', bounded), ['https://arxiv.org/abs/2606.99999'])

    def test_revision_adds_observed_sources_without_repeating_context(self):
        initial = [{'url': f'https://example.com/{i}', 'text': 'a' * 1600} for i in range(6)]
        revision = [{'url': 'https://example.com/revision', 'text': 'New observed evidence.'}]
        bounded = bounded_sources(bounded_sources(initial) + initial + revision)
        self.assertEqual(len(bounded), 7)
        self.assertLessEqual(sum(len(s['text']) for s in bounded), 6000)
        self.assertEqual(unsupported_citations(revision[0]['url'], bounded), [])

    def test_actual_source_and_returned_links_are_allowed(self):
        sources = [{'url': 'http://example.com/news/', 'text': '[Story](https://example.com/story?q=1).'}]
        self.assertEqual(unsupported_citations('See https://example.com/news#today and https://example.com/story?q=1.', sources), [])

    def test_invented_path_or_changed_query_is_not_a_source(self):
        sources = [{'url': 'https://example.com/news', 'text': 'A factual excerpt.'}]
        self.assertEqual(unsupported_citations('See https://example.com/acquisition', sources), ['https://example.com/acquisition'])
        self.assertEqual(unsupported_citations('https://example.com/news?year=2026', sources), ['https://example.com/news?year=2026'])

    def test_non_url_text_is_not_claimed_to_be_fact_checked(self):
        self.assertEqual(unsupported_citations('This is a potentially unsupported claim.', []), [])

    def test_arxiv_paper_representations_preserve_retrieved_evidence(self):
        # Live drone research retrieved the PDF but cited its abstract page.
        for paper in ('2309.12825', '0706.0001v2'):
            with self.subTest(paper=paper):
                sources = [{'url': 'https://arxiv.org/pdf/' + paper + '.pdf', 'text': 'Research excerpt.'}]
                answer = 'https://arxiv.org/abs/' + paper + ' https://arxiv.org/html/' + paper + '#S1'
                self.assertEqual(unsupported_citations(answer, sources), [])

    def test_arxiv_normalization_does_not_allow_other_papers_or_versions(self):
        sources = [{'url': 'https://arxiv.org/pdf/2309.12825v1', 'text': 'Version one.'}]
        for url in ('https://arxiv.org/abs/2309.12826v1',
                    'https://arxiv.org/abs/2309.12825v2',
                    'https://arxiv.org/abs/2309.12825',
                    'https://arxiv.org/abs/2309.12825v1?download=1',
                    'https://arxiv.org/abs/2309.12825v1/other',
                    'https://arxiv.org.example.com/abs/2309.12825v1'):
            with self.subTest(url=url):
                self.assertEqual(unsupported_citations(url, sources), [url])

    def test_balanced_parentheses_in_real_article_urls_are_preserved(self):
        url='https://en.wikipedia.org/wiki/Python_(programming_language)'
        self.assertEqual(unsupported_citations('[Python]('+url+').', [{'url':url,'text':'Python'}]), [])
