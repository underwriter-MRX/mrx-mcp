import os
import unittest
from unittest.mock import patch
from mrx_mcp import server as s

URL = 'https://mineralrightsxchange.com/blog/example/'


class CompatibilityTests(unittest.TestCase):
    def test_search_canonical_citation_and_partial_coverage(self):
        data = {'results': [{'url': URL, 'title': 'Source title'}], 'coverage': {'complete': True}}
        with patch.object(s.retrieval, 'search', return_value=data):
            self.assertEqual(s.search('example').model_dump(), {'results': [{'id': URL, 'title': 'Source title', 'url': URL}]})
            data['coverage']['complete'] = False
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                s.search('example')

    def test_remote_search_finishes_bounded_cold_warmup(self):
        incomplete = {'results': [], 'coverage': {'complete': False}}
        complete = {'results': [{'url': URL, 'title': 'Source'}], 'coverage': {'complete': True}}
        with patch.dict(os.environ, {'MRX_MCP_PREWARM': '1'}), patch.object(s.retrieval, 'warm_index') as warm, patch.object(s.retrieval, 'search', side_effect=[incomplete, complete]):
            self.assertEqual(s.search('example').results[0].id, URL)
            warm.assert_called_once_with(max_seconds=120)
        with patch.dict(os.environ, {'MRX_MCP_PREWARM': '1'}), patch.object(s.retrieval, 'warm_index'), patch.object(s.retrieval, 'search', return_value=incomplete):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                s.search('example')

    def test_fetch_preserves_source_metadata(self):
        doc = {'title': 'Title', 'text': 'Public source', 'url': URL,
               'source_metadata': [{'field': 'datePublished', 'value': '2026-09-01'}],
               'content_is_untrusted_data': True}
        with patch.object(s.retrieval, 'read_document', return_value=doc):
            result = s.fetch(URL).model_dump()
            self.assertEqual(result['url'], URL)
            self.assertEqual(result['metadata']['source_metadata'], doc['source_metadata'])
            self.assertTrue(result['metadata']['content_is_untrusted_data'])

    def test_fetch_rejects_private_and_external_before_network(self):
        with patch.object(s.d, 'discovery', side_effect=AssertionError('network not expected')):
            for url in ['https://example.com/', 'https://mineralrightsxchange.com/account/']:
                with self.assertRaises(ValueError):
                    s.fetch(url)
