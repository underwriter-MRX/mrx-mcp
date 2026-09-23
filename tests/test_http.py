import os
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient
from mrx_mcp.http import create_app


class HttpTests(unittest.TestCase):
    def test_rejects_bad_public_origin(self):
        for origin in ['http://example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?x=1', 'https://example.com#x']:
            with self.subTest(origin=origin), patch.dict(os.environ, {'MRX_MCP_PUBLIC_ORIGIN': origin}):
                with self.assertRaises(ValueError):
                    create_app()

    def test_health_and_rebinding_protection(self):
        with patch.dict(os.environ, {'MRX_MCP_PUBLIC_ORIGIN': 'https://mcp.example.com'}):
            with TestClient(create_app(), base_url='https://mcp.example.com') as client:
                result = client.get('/health')
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json()['read_only'])
                self.assertEqual(result.headers['x-robots-tag'], 'noindex')
                headers = {'Accept': 'application/json, text/event-stream'}
                body = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}}
                result = client.post('/mcp', json=body, headers=headers)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['result']['serverInfo']['name'], 'mrx-public')
                result = client.post('/mcp', json=body, headers={**headers, 'Host': 'evil.example'})
                self.assertEqual(result.status_code, 421)
                result = client.post('/mcp', json=body, headers={**headers, 'Origin': 'https://evil.example'})
                self.assertEqual(result.status_code, 403)
