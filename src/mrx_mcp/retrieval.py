"""Bounded lexical retrieval over integrity-verified, public MRX source pages.

No external model, embedding service, private data, query logging, or disk cache.
A cold search verifies at most 120 new pages; coverage is always explicit. Repeated
searches progressively warm the corpus. Documents refresh after 30 minutes and expire after one hour.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime, timezone
from urllib.parse import quote
import math
import re
import threading
import time

from . import discovery as d

CACHE_SECONDS = 3600
REFRESH_SECONDS = 1800
BATCH_SIZE = 120
MAX_WORKERS = 6
_cache = {}
_lock = threading.RLock()
_build_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
STOP = set('a an the and or to of in on for with is are was be do does how what when my i me can should about it that this getting from why which have has been need different difference compare comparison versus vs'.split())
ALIASES = {'minerals': 'mineral', 'leases': 'lease', 'inherit': 'inheritance', 'inherited': 'inheritance', 'inheriting': 'inheritance',
           'royalties': 'royalty', 'payments': 'payment', 'checks': 'payment',
           'check': 'payment', 'selling': 'sell', 'sale': 'sell', 'sold': 'sell',
           'leasing': 'lease', 'leased': 'lease', 'taxes': 'tax', 'deeds': 'deed',
           'owners': 'owner', 'rights': 'right', 'documents': 'document', 'smaller': 'decline', 'decreasing': 'decline',
           'declining': 'decline', 'decrease': 'decline', 'down': 'decline', 'lower': 'decline'}
STATES = ('alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
          'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois',
          'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana', 'maine', 'maryland',
          'massachusetts', 'michigan', 'minnesota', 'mississippi', 'missouri', 'montana',
          'nebraska', 'nevada', 'new hampshire', 'new jersey', 'new mexico', 'new york',
          'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania',
          'rhode island', 'south carolina', 'south dakota', 'tennessee', 'texas', 'utah',
          'vermont', 'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming')
TOPICS = {'inheritance': ('inheritance', 'probate', 'estate', 'heir'),
          'royalties': ('royalty', 'payment', 'division'),
          'selling': ('sell', 'offer', 'purchase', 'loi'),
          'leasing': ('lease', 'leasing'), 'tax': ('tax',),
          'ownership': ('ownership', 'title', 'deed', 'record')}


def tokens(text):
    return [ALIASES.get(t, t) for t in re.findall(r'[a-z0-9]+', text.lower()) if t not in STOP]


def _key(entry, revision):
    return (entry['url'], entry['sha256'])


def _document(entry, robots, revision):
    page = d.verify_page(entry, robots)
    context = getattr(page, 'source_context', None) or {
        'text': '\n'.join(page.text), 'sections': [], 'source_metadata': [],
        'text_scope': 'document', 'metadata_note': 'Source metadata unavailable.'}
    title = ' '.join(page.title_parts).strip()
    sections = []
    for section in context['sections']:
        item = dict(section)
        # Never invent anchors from headings. Only an actual nonempty HTML id
        # receives a section citation URL; otherwise cite the canonical page.
        item['url'] = entry['url'] + ('#' + quote(item['anchor'], safe='') if item.get('anchor') else '')
        sections.append(item)
    label_text = (title + ' ' + entry['url'] + ' ' + ' '.join(s['title'] for s in sections)).lower().replace('-', ' ')
    label_tokens = set(tokens(label_text))
    jurisdictions = [s for s in STATES if re.search(r'\b' + re.escape(s) + r'\b',
                     label_text.replace('west virginia', '') if s == 'virginia' else label_text)]
    topics = [label for label, terms in TOPICS.items() if label_tokens.intersection(terms)]
    return {'id': entry['url'], 'url': entry['url'], 'canonical_url': entry['url'],
            'title': title, 'text': context['text'], 'sections': sections,
            'source_metadata': context['source_metadata'], 'metadata_note': context['metadata_note'],
            'text_scope': context['text_scope'], 'labels': {'jurisdictions': jurisdictions, 'topics': topics,
                'provenance': 'inferred_from_title_url_and_headings',
                'note': 'Topic mentions, not verified legal applicability; absent labels mean unknown.'},
            'external_sources': sorted(page.external_sources),
            'content_sha256': entry['sha256'], 'manifest_revision': revision,
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'content_is_untrusted_data': True, 'integrity_verified': True}


def _corpus(max_new=BATCH_SIZE, max_seconds=90):
    """Refresh discovery each call, drop removed/changed records, warm a bounded batch."""
    if not 1 <= max_seconds <= 300:
        raise ValueError('max_seconds must be 1–300.')
    if not isinstance(max_new, int) or not 1 <= max_new <= 500:
        raise ValueError('max_new must be 1–500.')
    manifest, robots = d.discovery()  # Never serve cached results if discovery fails.
    revision = str(manifest.get('content_revision', ''))
    entries = manifest['pages']
    keys = {_key(e, revision) for e in entries}
    now = time.monotonic()
    with _lock:
        for key in list(_cache):
            if key not in keys or now - _cache[key][0] >= CACHE_SECONDS:
                del _cache[key]
        missing = [e for e in entries if _key(e, revision) not in _cache]
        refresh = [e for e in entries if _key(e, revision) in _cache
                   and now - _cache[_key(e, revision)][0] >= REFRESH_SECONDS]
    # Skip inaccessible pages even when a previously verified cache entry exists.
    allowed = {e['url'] for e in entries if robots.can_fetch('bingbot', e['url']) and robots.can_fetch(d.USER_AGENT, e['url'])}
    pending = [e for e in missing + refresh if e['url'] in allowed][:max_new]
    failed = []
    completed = set()
    verified_this_batch = 0
    futures = {_executor.submit(_document, e, robots, revision): e for e in pending}
    timed_out = False
    try:
        for future in as_completed(futures, timeout=max_seconds):
            entry = futures[future]
            completed.add(future)
            try:
                document = future.result()
                with _lock:
                    _cache[_key(entry, revision)] = (time.monotonic(), document)
                verified_this_batch += 1
            except Exception:
                # Do not leak arbitrary network response/error data to tools.
                failed.append(entry['url'])
                with _lock:
                    _cache.pop(_key(entry, revision), None)
    except TimeoutError:
        timed_out = True
    finally:
        # Active requests have their own 20-second network timeout. Pending
        # requests are cancelled; no worker writes records after this return.
        for future in futures:
            future.cancel()
            if future not in completed:
                with _lock:
                    _cache.pop(_key(futures[future], revision), None)
    with _lock:
        now = time.monotonic()
        for key in list(_cache):
            if now - _cache[key][0] >= CACHE_SECONDS:
                del _cache[key]
        refresh_due = sum(_key(e, revision) in _cache and e["url"] in allowed
                          and now - _cache[_key(e, revision)][0] >= REFRESH_SECONDS for e in entries)
        documents = [dict(_cache[_key(e, revision)][1], manifest_revision=revision) for e in entries
                     if _key(e, revision) in _cache and e['url'] in allowed]
    return documents, {'manifest_pages': len(entries), 'verified_indexed_pages': len(documents),
        'complete': len(documents) == len(entries), 'unavailable_or_not_yet_indexed': len(entries) - len(documents),
        'verified_this_batch': verified_this_batch, 'refresh_due_pages': refresh_due,
        'failed_this_batch': len(failed), 'failed_urls_this_batch': sorted(failed),
        'scheduled_this_batch': len(pending), 'batch_deadline_reached': timed_out, 'manifest_revision': revision,
        'freshness': 'Discovery checked this request; cached HTML last verified at each document retrieved_at, at most one hour ago.'}


def corpus(max_new=BATCH_SIZE, max_seconds=90):
    # One shared executor and build lane prevent concurrent client requests from
    # multiplying outbound requests or duplicating a corpus build.
    if not _build_lock.acquire(blocking=False):
        raise ValueError('Public search index is warming; retry shortly.')
    try:
        return _corpus(max_new, max_seconds)
    finally:
        _build_lock.release()


def _excerpt(document, query_tokens):
    sections = document['sections']
    if sections:
        section = max(sections, key=lambda s: len(set(tokens(s['title'] + ' ' + s['text'])).intersection(query_tokens)))
        text = section['text'] or section['title']
        citation = section['url']
    else:
        text, citation = document['text'], document['url']
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    best = max(sentences or [''], key=lambda s: len(set(tokens(s)).intersection(query_tokens)))
    return best[:600], citation


def rank(documents, query, limit=10, jurisdiction=None, topic=None):
    """BM25 lexical ranking plus exact title/heading boosts; scores are not confidence."""
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or not tokens(query):
        raise ValueError('query must contain searchable words and be 1–200 characters.')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError('limit must be 1–20.')
    if jurisdiction is not None and (not isinstance(jurisdiction, str) or jurisdiction.lower() not in STATES):
        raise ValueError('jurisdiction must be a supported full lowercase or title-case US state name.')
    if topic is not None and topic not in TOPICS:
        raise ValueError('topic must be inheritance, royalties, selling, leasing, tax, or ownership.')
    filtered = [doc for doc in documents if (not jurisdiction or jurisdiction.lower() in doc['labels']['jurisdictions'])
                and (not topic or topic in doc['labels']['topics'])]
    query_terms = set(tokens(query))
    counts = [Counter(tokens(doc['text'])) for doc in filtered]
    average = sum(sum(c.values()) for c in counts) / max(len(counts), 1) or 1
    frequency = {term: sum(term in c for c in counts) for term in query_terms}
    matches = []
    for doc, count in zip(filtered, counts):
        title = Counter(tokens(doc['title']))
        headings = Counter(tokens(' '.join(s['title'] for s in doc['sections'])))
        score = 0.0
        for term in query_terms:
            tf = count[term]
            idf = math.log(1 + (len(counts) - frequency[term] + .5) / (frequency[term] + .5))
            score += idf * (tf * 2.2 / (tf + 1.2 * (.25 + .75 * sum(count.values()) / average)) if tf else 0)
            score += idf * (2.5 * min(title[term], 1) + min(headings[term], 1))
        archive = bool(re.search(r'/(?:category|tag)/|/page/\d+/', doc['url']) or doc['url'] == d.SITE + '/blog/')
        if archive:
            score *= 0.2
        if score > 0:
            excerpt, citation = _excerpt(doc, query_terms)
            matches.append({'id': doc['id'], 'url': doc['url'], 'title': doc['title'],
                'excerpt': excerpt, 'citation_url': citation, 'score': round(score, 6),
                'ranking_adjustment': 'Archive/listing score multiplied by 0.2 to prefer substantive guides.' if archive else None,
                'labels': doc['labels'], 'source_metadata': doc['source_metadata'],
                'retrieved_at': doc['retrieved_at'], 'content_is_untrusted_data': True})
    return sorted(matches, key=lambda r: (-r['score'], r['url']))[:limit]


def search(query, limit=10, jurisdiction=None, topic=None):
    # Validate before any network requests.
    rank([], query, limit, jurisdiction, topic)
    documents, coverage = corpus()
    return {'results': rank(documents, query, limit, jurisdiction, topic), 'coverage': coverage,
            'matching_method': 'BM25 full-text with title/heading boosts, explicit word aliases and 0.2 archive/listing multiplier; relevance scores are not factual confidence.',
            'filters': {'jurisdiction': jurisdiction, 'topic': topic,
                        'provenance': 'Inferred mentions in titles, URLs and headings; not verified legal applicability.'}}


def read_document(url):
    """Always freshly verify a requested canonical page; IDs are canonical URLs."""
    d.public_url(url)
    manifest, robots = d.discovery()
    entry = next((e for e in manifest['pages'] if e['url'] == url), None)
    if entry is None:
        raise ValueError('Page is not in the current verified public manifest.')
    revision = str(manifest.get('content_revision', ''))
    try:
        document = _document(entry, robots, revision)
    except Exception:
        with _lock:
            _cache.pop(_key(entry, revision), None)
        raise
    with _lock:
        _cache[_key(entry, revision)] = (time.monotonic(), document)
    return document


def warm_index(max_rounds=5, max_seconds=90):
    """Operator prewarm helper, bounded overall corpus-fetch time (discovery extra).

    Returns final explicit coverage. If there is no progress, stop and leave
    unavailable pages for a later retry rather than hammering them.
    """
    if not isinstance(max_rounds, int) or not 1 <= max_rounds <= 20:
        raise ValueError('max_rounds must be 1–20.')
    if not 1 <= max_seconds <= 300:
        raise ValueError('max_seconds must be 1–300.')
    started = time.monotonic()
    coverage = None
    for _ in range(max_rounds):
        remaining = max_seconds - (time.monotonic() - started)
        if remaining < 1:
            break
        _, coverage = corpus(max_seconds=remaining)
        if coverage['complete'] and coverage['refresh_due_pages'] == 0:
            break
        if coverage['verified_this_batch'] == 0:
            break
    return coverage
