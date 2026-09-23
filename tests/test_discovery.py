import hashlib
import json
import unittest
from unittest.mock import patch, Mock
from urllib.robotparser import RobotFileParser
from mrx_mcp import discovery as d, server as s

URL = d.SITE + "/blog/example/"
HTML = (f'<html><head><title>Example</title><link rel="canonical" href="{URL}">'
        '</head><body><main><h1>Example</h1><p>Public guide.</p>'
        '<script>secret_script()</script></main></body></html>').encode()


def robots():
    r = RobotFileParser()
    r.parse(["User-agent: *", "Disallow: /account/"])
    return r


class SecurityTests(unittest.TestCase):
    def test_reject_nonpublic_urls(self):
        paths = ["//account/", "/account/", "/staff/", "/api/status/", "/drafts/a/",
                 "/owner-intake/", "/oauth/consent/", "/uploads/a/", "/thank-you/",
                 "/x/../account/", "/%61ccount/", "/blog/x/?", "/blog/x/#",
                 "/blog/x/?key=a", "/blog/x/#test", "/blog\\x/", "/blog/x/\n"]
        for url in [d.SITE + p for p in paths] + ["https://evil.test/", "http://mineralrightsxchange.com/",
                    "https://mineralrightsxchange.com.evil.test/", "https://user@mineralrightsxchange.com/",
                    "https://mineralrightsxchange.com:443/", "https://127.0.0.1/"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                d.public_url(url)
        self.assertEqual(d.public_url(URL), URL)

    def test_response_size_and_redirects(self):
        response = Mock(status=200, headers={"Content-Type": "text/html"})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"x" * (d.MAX_BODY + 1)
        with patch.object(d, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with self.assertRaises(ValueError):
                d.request(URL)
        self.assertIsNone(d.NoRedirect().redirect_request(None, None, 302, None, None, "http://127.0.0.1/"))

    def test_content_type_and_status(self):
        for status, content_type in [(302, "text/html"), (403, "text/html"), (200, "application/json")]:
            with patch.object(d, "request", return_value=(status, {"content-type": content_type}, HTML)):
                with self.assertRaises(ValueError):
                    d.get(URL, ["text/html"])

    def test_hash_mismatch_and_injection_rejected(self):
        entry = {"url": URL, "sha256": hashlib.sha256(HTML).hexdigest()}
        for body in [HTML.replace(b"Public guide", b"Changed guide"), HTML + b"<script>injection()</script>"]:
            with patch.object(d, "get", return_value=({}, body)), self.assertRaises(ValueError):
                d.verify_page(entry, robots())
        self.assertEqual(d.content_hash(b"a<!--email_off-->b<!--/email_off-->"), hashlib.sha256(b"ab").hexdigest())

    def test_canonical_noindex_refresh_and_robots(self):
        cases = [HTML.replace(URL.encode(), (d.SITE + "/wrong/").encode()),
                 HTML.replace(b"</head>", b'<meta name="robots" content="noindex"></head>'),
                 HTML.replace(b"</head>", b'<meta http-equiv="refresh" content="0;url=/account/"></head>')]
        for body in cases:
            with patch.object(d, "get", return_value=({}, body)), self.assertRaises(ValueError):
                d.verify_page({"url": URL, "sha256": d.content_hash(body)}, robots())
        with patch.object(d, "get", return_value=({"X-Robots-Tag": "noindex"}, HTML)), self.assertRaises(ValueError):
            d.verify_page({"url": URL, "sha256": d.content_hash(HTML)}, robots())
        blocked = robots()
        blocked.parse(["User-agent: *", "Disallow: /"])
        with self.assertRaises(ValueError):
            d.verify_page({"url": URL, "sha256": d.content_hash(HTML)}, blocked)

    def test_verified_read_excludes_scripts(self):
        manifest = {"pages": [{"url": URL, "sha256": d.content_hash(HTML)}], "content_revision": "fixture"}
        with patch.object(s, "inventory", return_value=(manifest, robots())), patch.object(d, "get", return_value=({}, HTML)):
            read = s.read_page(URL)
            self.assertIn("Public guide.", read["text"])
            self.assertNotIn("secret_script", read["text"])
            self.assertTrue(read["content_is_untrusted_data"])
            self.assertEqual(read["canonical_url"], URL)
            with self.assertRaises(ValueError):
                s.read_page(d.SITE + "/blog/not-in-manifest/")

    def test_search_limits_labels_and_cache_fail_closed(self):
        manifest = {"pages": [{"url": URL}], "content_revision": "fixture"}
        with patch.object(s, "inventory", return_value=(manifest, robots())):
            self.assertEqual(s.mrx_search_guides("example", 1)["results"][0]["url_label"], "example")
            for query, limit in [("", 1), ("a" * 201, 1), ("x", 21), ("x", 0), ("???", 1)]:
                with self.assertRaises(ValueError):
                    s.mrx_search_guides(query, limit)
        with patch.object(s, "_cache", (manifest, robots())), patch.object(s, "_cache_at", 0), patch.object(d, "discovery", side_effect=ValueError("offline")):
            with self.assertRaises(ValueError):
                s.inventory()
            self.assertIsNone(s._cache)

    def test_manifest_rejects_duplicates_and_private_entries(self):
        m = {"version": 2, "origin": d.SITE, "hash_policy": "sha256-html-approved-cloudflare-transport-v1",
             "pages": [{"url": URL, "sha256": "a" * 64}],
             "indexnow": {"key": "fixture-test-key", "key_location": d.SITE + "/indexnow-key.txt"}}
        with patch.object(d, "get", return_value=({}, json.dumps(m).encode())):
            self.assertEqual(d.manifest()["pages"][0]["url"], URL)
        m["pages"] *= 2
        with patch.object(d, "get", return_value=({}, json.dumps(m).encode())), self.assertRaises(ValueError):
            d.manifest()
        m["pages"] = [{"url": d.SITE + "/account/", "sha256": "a" * 64}]
        with patch.object(d, "get", return_value=({}, json.dumps(m).encode())), self.assertRaises(ValueError):
            d.manifest()

    def test_sitemap_manifest_disagreement_rejected(self):
        m = {"pages": [{"url": URL}], "content_revision": "fixture"}
        index = ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                 '<sitemap><loc>' + d.SITE + '/sitemap-pages.xml</loc></sitemap></sitemapindex>').encode()
        segment = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   '<url><loc>' + d.SITE + '/wrong/</loc></url></urlset>').encode()
        responses = [({}, ('Sitemap: ' + d.SITE + '/sitemap_index.xml').encode()), ({}, index), ({}, segment)]
        with patch.object(d, "manifest", return_value=m), patch.object(d, "get", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "disagree"):
                d.discovery()

    def test_public_links_exclude_private_and_external(self):
        p = d.Page()
        p.feed('<a href="/account/">Private</a><a href="/blog/example/">Guide</a>'
               '<a href="https://example.com/">Source</a><a href="/blog/example/?key=x">Query</a>')
        self.assertEqual(p.public_links, {URL})
        self.assertEqual(p.external_sources, {"https://example.com/"})


if __name__ == "__main__":
    unittest.main()
