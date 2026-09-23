"""Public-only MRX discovery; derived from the first-party verified discovery engine.
No notifications, credentials, private records, subprocesses, or arbitrary origins.
"""
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser

SITE = "https://mineralrightsxchange.com"
MAX_BODY = 5_000_000
USER_AGENT = "MRX-Content-Discovery/1.0"
PRIVATE = re.compile(r"/(?:api|account|staff|admin|owner-intake|knowledge|staged|drafts|auth|oauth|login|dashboard|uploads|documents)(?:/|$)|/thank-you(?:/|$)", re.I)


def public_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Expected a canonical public MRX URL.")
    u = urlsplit(value)
    if (u.geturl() != value or u.scheme != "https" or u.netloc != "mineralrightsxchange.com"
            or u.query or u.fragment or "?" in value or "#" in value
            or not re.fullmatch(r"/[a-zA-Z0-9_./~-]*", u.path)
            or "//" in u.path or any(p in (".", "..") for p in u.path.split("/"))
            or PRIVATE.search(u.path)):
        raise ValueError("Only canonical public MRX URLs without queries or fragments are allowed.")
    return value


def request(url):
    public_url(url)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    try:
        response = build_opener(NoRedirect()).open(req, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("Response exceeds the discovery size limit.")
        return response.status, dict(response.headers.items()), body

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def get(url, media):
    status, headers, body = request(url)
    content_type = next((v for k, v in headers.items() if k.lower() == 'content-type'), '').lower()
    if status != 200 or not any(m in content_type for m in media):
        raise ValueError(f'Discovery fetch failed: {url}, HTTP {status}, type {content_type}')
    return headers, body

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals = []
        self.noindex = False
        self.refresh = False
        self.text = []
        self.hidden = 0
        self.h1_count = 0
        self.title_parts = []
        self.in_title = False
        self.external_sources = set()
        self.public_links = set()
        self.descriptions = []
        self.schema_text = []
        self.in_schema = False
        self.main_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            try:
                self.public_links.add(public_url(urljoin(SITE + '/', a['href'])))
            except ValueError:
                pass
        if tag == 'title':
            self.in_title = True
        if tag == 'h1':
            self.h1_count += 1
        if tag == 'main':
            self.main_count += 1
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.in_schema = True
        if tag == 'a' and a.get('href', '').startswith('https://'):
            host = urlsplit(a['href']).hostname
            if host and host != 'mineralrightsxchange.com':
                self.external_sources.add(a['href'])
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'link' and a.get('rel', '').lower() == 'canonical':
            self.canonicals.append(a.get('href'))
        if tag == 'meta':
            if a.get('name', '').lower() == 'description':
                self.descriptions.append(a.get('content', ''))
            if a.get('name', '').lower() in ('robots', 'googlebot', 'bingbot'):
                self.noindex |= bool(re.search(r'\b(noindex|none)\b', a.get('content', ''), re.I))
            self.refresh |= a.get('http-equiv', '').lower() == 'refresh'

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'script':
            self.in_schema = False
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_schema:
            self.schema_text.append(data)
        if not self.hidden and data.strip():
            self.text.append(data.strip())

def manifest():
    _, body = get(SITE + '/crawler-manifest.json', ['application/json'])
    data = json.loads(body)
    if data.get('version') != 2 or data.get('origin') != SITE or data.get('hash_policy') != 'sha256-html-approved-cloudflare-transport-v1':
        raise ValueError('Unsupported MRX manifest.')
    pages = data.get('pages')
    if not isinstance(pages, list) or not 1 <= len(pages) <= 10000:
        raise ValueError('Manifest needs 1–10000 public pages.')
    seen = set()
    for entry in pages:
        url = public_url(entry['url'])
        if not url.endswith('/') or url in seen or not re.fullmatch('[a-f0-9]{64}', entry['sha256']):
            raise ValueError('Invalid or duplicate manifest page.')
        seen.add(url)
    ownership = data['indexnow']
    if not re.fullmatch('[a-zA-Z0-9-]{8,128}', ownership['key']):
        raise ValueError('Invalid ownership key.')
    if ownership['key_location'] != SITE + '/indexnow-key.txt':
        raise ValueError('Unexpected ownership-key location.')
    return data

def discovery():
    data = manifest()
    _, robot_bytes = get(SITE + '/robots.txt', ['text/plain'])
    robots_text = robot_bytes.decode('utf-8')
    if SITE + '/sitemap_index.xml' not in robots_text:
        raise ValueError('robots.txt does not advertise the canonical sitemap.')
    robots = RobotFileParser()
    robots.parse(robots_text.splitlines())
    _, xml = get(SITE + '/sitemap_index.xml', ['xml'])
    root = ET.fromstring(xml)
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = set()
    segments = root.findall('s:sitemap/s:loc', ns)
    if not 1 <= len(segments) <= 20:
        raise ValueError('Invalid sitemap index.')
    for loc in segments:
        url = public_url(loc.text)
        if not re.fullmatch(re.escape(SITE) + r'/sitemap-[a-z]+\.xml', url) or 'staged' in url:
            raise ValueError('Unexpected sitemap segment.')
        _, body = get(url, ['xml'])
        for item in ET.fromstring(body).findall('s:url/s:loc', ns):
            urls.add(public_url(item.text))
    if urls != {entry['url'] for entry in data['pages']}:
        raise ValueError('Live sitemap and crawler manifest disagree; deployment may be incomplete or cached.')
    for path in ['/llms.txt', '/llms-full.txt']:
        _, body = get(SITE + path, ['text/plain'])
        text = body.decode('utf-8')
        if not text.strip() or SITE not in text:
            raise ValueError('LLM discovery file is empty or lacks canonical MRX references.')
        for url in re.findall(r'https://mineralrightsxchange\.com[^\s\)\]>"\']*', text):
            public_url(url + '/' if url == SITE else url)
    return data, robots

def content_hash(body):
    # Only these exact transport comments are ignored; all content/injections remain.
    body = body.replace(b'<!--email_off-->', b'').replace(b'<!--/email_off-->', b'')
    # Captured existing Cloudflare analytics footer, pinned byte-for-byte. Unknown
    # scripts or changed analytics configuration fail closed for review.
    approved = 'a7d7b1207343bf240dc3bf89442b597d9a3609888ede71e183e4ff7c9b18f290'
    def transport(match):
        return b'' if hashlib.sha256(match.group()).hexdigest() == approved else match.group()
    body = re.sub(rb'<script type="module" src="https://static\.cloudflareinsights\.com/beacon\.min\.js/[^>]+></script>\n', transport, body)
    def security_transport(match):
        fragment = match.group()
        normalized = re.sub(rb"r:'[a-f0-9]{16}',t:'[A-Za-z0-9+/=]+'", b"r:'RAY',t:'TIME'", fragment)
        approved_jsd = '016660f3823e7f69cbe84c7b6e6e3219103232ab0ac3cf4094bb7a48cfffef36'
        return b'' if hashlib.sha256(normalized).hexdigest() == approved_jsd else fragment
    body = re.sub(rb'<script>\(function\(\)\{function c\(\).*?</script>', security_transport, body)
    # OTTO's Cloudflare Worker injects a fixed runtime client plus an eight-byte
    # per-request identifier. The runtime is transport, not authored page
    # content. Ignore it only when the request id is the sole normalized field
    # and the remaining client is the independently pinned production version.
    def searchatlas_transport(match):
        fragment = match.group()
        normalized = re.sub(rb"REQ_ID: '[a-f0-9]{8}'", b"REQ_ID: 'REQUEST'", fragment)
        approved_otto = '801ae29b635c9a26b2ceac00a751acd2ff3b3def61fe5072f276cb96c0f80caa'
        return b'' if hashlib.sha256(normalized).hexdigest() == approved_otto else fragment
    body = re.sub(
        rb"<script>\(function\(\)\{\s+'use strict';\s+const OTTO_CONFIG = \{.*?</script>\n?",
        searchatlas_transport,
        body,
        flags=re.S,
    )
    # Search Atlas toggles only the boolean worker-status value in this exact
    # transport marker. Preserve fail-closed hashing for every other marker.
    body = re.sub(
        rb'<meta name="otto" content="uuid=e4bab8bb-717e-480c-8dea-1de1b8596eb7; '
        rb'type=cloudflare; enabled=(?:true|false);">',
        b'',
        body,
    )
    return hashlib.sha256(body).hexdigest()

def verify_page(entry, robots):
    url = entry['url']
    if not robots.can_fetch('bingbot', url) or not robots.can_fetch(USER_AGENT, url):
        raise ValueError('Public retrieval crawler is blocked by robots.txt.')
    headers, body = get(url, ['text/html'])
    if content_hash(body) != entry['sha256']:
        raise ValueError('Live HTML differs from the published manifest; retry after cache/deployment convergence.')
    parsed = Page()
    parsed.feed(body.decode('utf-8'))
    parsed.source_context = source_context(body.decode('utf-8'))
    xrobots = ' '.join(v for k, v in headers.items() if k.lower() == 'x-robots-tag')
    if parsed.canonicals != [url] or parsed.noindex or parsed.refresh or re.search(r'\b(noindex|none)\b', xrobots, re.I):
        raise ValueError('Live page is noncanonical, noindex, or a redirect.')
    return parsed

class SourceContent(HTMLParser):
    """Extract semantic public content; CSS rendering is not inferred."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.blocks = []
        self.main_blocks = []
        self.sections = []
        self.metadata = []
        self.jsonld = []
        self.script = None
        self.heading = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hidden = (any(x[1] for x in self.stack) or tag in ('script', 'style', 'noscript', 'nav', 'footer', 'template')
                  or 'hidden' in a or a.get('aria-hidden', '').lower() == 'true'
                  or bool(re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden)', a.get('style', ''), re.I)))
        if tag not in self.VOID:
            self.stack.append((tag, hidden))
        if tag == 'script' and a.get('type', '').lower() == 'application/ld+json':
            self.script = []
        if tag in ('h1', 'h2', 'h3', 'h4') and not hidden:
            self.heading = {'level': int(tag[1]), 'title': '', 'anchor': a.get('id'), 'text': ''}
            self.sections.append(self.heading)
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or '').lower()
            if key in ('author', 'article:published_time', 'article:modified_time') and a.get('content'):
                self.metadata.append({'field': key, 'value': a['content'], 'provenance': 'html_meta'})
        if tag == 'time' and not hidden and a.get('datetime'):
            self.metadata.append({'field': 'time', 'value': a['datetime'], 'provenance': 'html_time', 'meaning': 'unspecified'})

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            try:
                self.jsonld.append(json.loads(''.join(self.script)))
            except (ValueError, TypeError):
                pass
            self.script = None
        if self.heading is not None and tag in ('h1', 'h2', 'h3', 'h4'):
            self.heading = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        if self.script is not None:
            self.script.append(value)
        if any(x[1] for x in self.stack) or not value.strip():
            return
        text = ' '.join(value.split())
        self.blocks.append(text)
        in_main = any(x[0] in ('main', 'article') for x in self.stack)
        if in_main:
            self.main_blocks.append(text)
        if self.heading is not None:
            self.heading['title'] += (' ' if self.heading['title'] else '') + text
        elif self.sections:
            self.sections[-1]['text'] += (' ' if self.sections[-1]['text'] else '') + text

    def result(self):
        def walk(value):
            if isinstance(value, list):
                for item in value:
                    yield from walk(item)
            elif isinstance(value, dict):
                types = value.get('@type', [])
                if isinstance(types, str):
                    types = [types]
                if any(t in ('Article', 'BlogPosting', 'NewsArticle', 'ScholarlyArticle', 'WebPage') for t in types):
                    for key in ('datePublished', 'dateModified', 'author', 'reviewedBy', 'lastReviewed'):
                        if key in value:
                            yield {'field': key, 'value': value[key], 'provenance': 'json_ld', 'schema_type': types}
                yield from walk(value.get('@graph', []))
                yield from walk(value.get('mainEntity', []))
        return {'text': '\n'.join(self.main_blocks or self.blocks),
                'text_scope': 'main_or_article' if self.main_blocks else 'document_without_navigation',
                'sections': self.sections, 'source_metadata': self.metadata + list(walk(self.jsonld)),
                'metadata_note': 'Source-attributed values, not independently verified authorship, review, or freshness.'}


def source_context(html):
    parser = SourceContent()
    parser.feed(html)
    return parser.result()
