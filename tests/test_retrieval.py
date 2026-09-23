"""Retrieval evaluation with source-grounded miniature mineral-owner guides."""
import unittest
from unittest.mock import patch
from urllib.robotparser import RobotFileParser
from mrx_mcp import discovery as d, retrieval as r


def robot():
    obj = RobotFileParser()
    obj.parse(['User-agent: *', 'Allow: /'])
    return obj


def fixture(slug, title, heading, text, state='Texas'):
    url = d.SITE + '/blog/' + slug + '/'
    html = (f'<html><head><title>{title}</title><link rel="canonical" href="{url}"></head>'
            f'<body><nav>Sell royalty lease tax probate</nav><main><h1>{title}</h1>'
            f'<h2 id="next-step">{state}: {heading}</h2><p>{text}</p></main></body></html>').encode()
    entry = {'url': url, 'sha256': d.content_hash(html)}
    with patch.object(d, 'get', return_value=({}, html)):
        doc = r._document(entry, robot(), 'evaluation')
    return entry, doc, html


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        r._cache.clear()
        self.fixtures = [
            fixture('a', 'Inherited mineral rights', 'Probate records', 'An heir inheriting mineral ownership should gather probate documents and the recorded deed.'),
            fixture('b', 'Missing royalty payments', 'Payment statements', 'If royalty checks stopped arriving, compare the payment statement with the operator contact records.'),
            fixture('c', 'Evaluate an offer', 'Purchase agreement', 'Selling minerals requires comparing the offer and purchase agreement before deciding to sell.', 'Oklahoma'),
            fixture('d', 'Oil and gas lease terms', 'Lease negotiation', 'A lease bonus and royalty clause have different purposes. Review the leasing document.')]

    def test_realistic_questions_rank_expected_guides(self):
        docs = [x[1] for x in self.fixtures]
        for query, expected in [
            ('I inherited minerals what probate documents do I need?', 0),
            ('My royalty checks stopped arriving', 1),
            ('Should I sell after receiving a purchase offer?', 2),
            ('What does the lease bonus mean?', 3)]:
            with self.subTest(query=query):
                results = r.rank(docs, query)
                self.assertEqual(results[0]['url'], self.fixtures[expected][0]['url'])
                self.assertTrue(results[0]['excerpt'])
                self.assertIn('#next-step', results[0]['citation_url'])
        self.assertEqual(r.rank(docs, 'offer', jurisdiction='Texas'), [])
        self.assertEqual(r.rank(docs, 'purchase', jurisdiction='Oklahoma', topic='selling')[0]['url'], self.fixtures[2][0]['url'])

    def test_declining_payment_question_and_archive_penalty(self):
        _, answer, _ = fixture('why-did-my-royalty-check-go-down', 'Why Did My Mineral Royalty Check Go Down?', 'Payment changes', 'A lower royalty check can reflect production, price, timing, deductions, or ownership changes.')
        _, distractor, _ = fixture('fees', 'Fees for a No-Obligation Mineral Assessment', 'Payment cards', 'Royalty statements can contain payment and account information. No payment card is required for an assessment.')
        results = r.rank([distractor, answer], 'Why are royalty checks getting smaller?')
        self.assertEqual(results[0]['url'], answer['url'])
        _, archive, _ = fixture('category/inherited-mineral-rights/page/2', 'Inherited Mineral Rights', 'Inherited mineral rights', 'Inherited mineral rights articles and resources.')
        # Topic pagination also exists outside /blog/ on the live site.
        archive['url'] = d.SITE + '/inherited-mineral-rights/page/2/'
        archive['id'] = archive['url']
        docs = [archive, self.fixtures[0][1]]
        results = r.rank(docs, 'inherited mineral rights')
        self.assertEqual(results[0]['url'], self.fixtures[0][0]['url'])
        archive_result = next(x for x in results if x['url'] == archive['url'])
        self.assertIn('multiplied by 0.2', archive_result['ranking_adjustment'])

    def test_visible_content_metadata_and_real_anchors(self):
        result = d.source_context('''<html><head><title>Page</title><script type="application/ld+json">{"@graph":[{"@type":"BlogPosting","author":{"@type":"Person","name":"Jane Example"},"datePublished":"2025-01-02"}]}</script></head><body><nav>navigation phrase</nav><main><h1>Guide</h1><h2 id="records">Records</h2><p>Public evidence.</p><p hidden>Hidden phrase</p><p aria-hidden="true">Aria phrase</p><div style="display:none"><p>CSS phrase</p></div><time datetime="2025-01-03">January 3</time><h2>No ID</h2><p>Next step</p></main><footer>Footer phrase</footer></body></html>''')
        self.assertIn('Public evidence.', result['text'])
        for excluded in ['navigation phrase', 'Hidden phrase', 'Aria phrase', 'CSS phrase', 'Footer phrase', 'Jane Example']:
            self.assertNotIn(excluded, result['text'])
        self.assertEqual(result['sections'][1]['anchor'], 'records')
        self.assertIsNone(result['sections'][2]['anchor'])
        published = next(m for m in result['source_metadata'] if m['field'] == 'datePublished')
        self.assertEqual(published['provenance'], 'json_ld')
        self.assertFalse(any(m['field'] == 'reviewedBy' for m in result['source_metadata']))

    def test_partial_coverage_cache_reuse_and_changed_hash(self):
        entries = [x[0] for x in self.fixtures]
        by_url = {e['url']: html for e, _, html in self.fixtures}
        def get(url, media):
            return {}, by_url[url]
        manifest = {'pages': entries, 'content_revision': 'evaluation'}
        with patch.object(d, 'discovery', return_value=(manifest, robot())), patch.object(d, 'get', side_effect=get) as fetch:
            _, coverage = r.corpus(max_new=2)
            self.assertFalse(coverage['complete'])
            self.assertEqual(coverage['verified_indexed_pages'], 2)
            _, coverage = r.corpus(max_new=2)
            self.assertTrue(coverage['complete'])
            self.assertEqual(fetch.call_count, 4)
            r.corpus()
            self.assertEqual(fetch.call_count, 4)
            entries[0]['sha256'] = '0' * 64
            _, coverage = r.corpus()
            self.assertFalse(coverage['complete'])
            self.assertEqual(coverage['failed_this_batch'], 1)
            self.assertEqual(coverage['verified_indexed_pages'], 3)

    def test_removed_page_blocked_robots_and_discovery_failure(self):
        entry, document, html = self.fixtures[0]
        manifest = {'pages': [entry], 'content_revision': 'evaluation'}
        with patch.object(d, 'discovery', return_value=(manifest, robot())), patch.object(d, 'get', return_value=({}, html)):
            self.assertTrue(r.search('probate')['coverage']['complete'])
        blocked = RobotFileParser()
        blocked.parse(['User-agent: *', 'Disallow: /'])
        with patch.object(d, 'discovery', return_value=(manifest, blocked)):
            self.assertEqual(r.search('probate')['results'], [])
        with patch.object(d, 'discovery', side_effect=ValueError('offline')):
            with self.assertRaises(ValueError):
                r.search('probate')
        with patch.object(d, 'discovery', return_value=({'pages': [], 'content_revision': 'new'}, robot())):
            self.assertEqual(r.search('probate')['results'], [])
            self.assertEqual(r._cache, {})
            with self.assertRaises(ValueError):
                r.read_document(entry['url'])

    def test_invalid_queries_are_rejected_before_network(self):
        with patch.object(d, 'discovery') as network:
            for kwargs in [dict(query=''), dict(query='???'), dict(query='x'*201),
                           dict(query='probate', limit=21), dict(query='probate', jurisdiction='Atlantis'),
                           dict(query='probate', topic='guaranteed returns')]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    r.search(**kwargs)
            network.assert_not_called()

    def test_actual_crawler_robots_and_serial_build_lane(self):
        entry, _, html = self.fixtures[0]
        crawler_block = RobotFileParser()
        crawler_block.parse(['User-agent: MRX-Content-Discovery', 'Disallow: /', '', 'User-agent: *', 'Allow: /'])
        with patch.object(d, 'get', return_value=({}, html)) as network:
            with self.assertRaises(ValueError):
                d.verify_page(entry, crawler_block)
            network.assert_not_called()
        r._build_lock.acquire()
        try:
            with patch.object(d, 'discovery') as network:
                with self.assertRaisesRegex(ValueError, 'warming'):
                    r.corpus()
                network.assert_not_called()
        finally:
            r._build_lock.release()

    def test_revision_only_change_reuses_identical_bytes(self):
        entry, _, html = self.fixtures[0]
        manifest = {'pages': [entry], 'content_revision': 'one'}
        with patch.object(d, 'discovery', return_value=(manifest, robot())), patch.object(d, 'get', return_value=({}, html)) as network:
            r.corpus()
            manifest['content_revision'] = 'two'
            documents, coverage = r.corpus()
            self.assertTrue(coverage['complete'])
            self.assertEqual(network.call_count, 1)
            self.assertEqual(documents[0]['manifest_revision'], 'two')

    def test_refresh_ahead_prioritizes_missing_and_evicts_failed_refresh(self):
        entries = [x[0] for x in self.fixtures]
        by_url = {e['url']: html for e, _, html in self.fixtures}
        manifest = {'pages': entries, 'content_revision': 'evaluation'}
        with patch.object(d, 'discovery', return_value=(manifest, robot())), patch.object(d, 'get', side_effect=lambda url, media: ({}, by_url[url])):
            r.corpus()
            for key, (_, doc) in list(r._cache.items()):
                r._cache[key] = (r.time.monotonic() - 1801, doc)
            missing = entries[-1]
            r._cache.pop(r._key(missing, 'evaluation'))
            documents, coverage = r.corpus(max_new=1)
            self.assertTrue(coverage['complete'])
            self.assertEqual(coverage['refresh_due_pages'], 3)
            self.assertLess(r.time.monotonic() - r._cache[r._key(missing, 'evaluation')][0], 10)
            by_url[entries[0]['url']] += b'unapproved change'
            documents, coverage = r.corpus(max_new=1)
            self.assertFalse(coverage['complete'])
            self.assertEqual(coverage['failed_this_batch'], 1)
            self.assertNotIn(entries[0]['url'], [doc['url'] for doc in documents])

    def test_warmer_continues_complete_coverage_until_refresh_drained(self):
        coverage = [dict(complete=True, refresh_due_pages=2, verified_this_batch=2),
                    dict(complete=True, refresh_due_pages=0, verified_this_batch=2)]
        with patch.object(r, 'corpus', side_effect=[([], c) for c in coverage]) as corpus:
            result = r.warm_index()
            self.assertEqual(corpus.call_count, 2)
            self.assertEqual(result['refresh_due_pages'], 0)

    def test_expired_cache_cannot_survive_failed_reverification(self):
        entry, document, _ = self.fixtures[0]
        r._cache[r._key(entry, 'evaluation')] = (r.time.monotonic() - 3601, document)
        with patch.object(d, 'discovery', return_value=({'pages': [entry], 'content_revision': 'evaluation'}, robot())), patch.object(d, 'verify_page', side_effect=ValueError('unavailable')):
            documents, coverage = r.corpus()
            self.assertEqual(documents, [])
            self.assertFalse(coverage['complete'])
            self.assertEqual(r._cache, {})

    def test_fresh_read_rejects_changed_bytes(self):
        entry, _, html = self.fixtures[0]
        with patch.object(d, 'discovery', return_value=({'pages': [entry]}, robot())), patch.object(d, 'get', return_value=({}, html + b'changed')):
            with self.assertRaises(ValueError):
                r.read_document(entry['url'])


if __name__ == '__main__':
    unittest.main()
