import ast
import asyncio
import importlib.util
import logging
import types
import unittest
import urllib.parse
from pathlib import Path

spec = importlib.util.spec_from_file_location('web_compat', Path(__file__).with_name('web_compat.py'))
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)

SOURCE = '''def create_origin_only_middleware():
    @web.middleware
    async def origin_only_middleware(request, handler):
        if 'Sec-Fetch-Site' in request.headers:
            sec_fetch_site = request.headers['Sec-Fetch-Site']
            if sec_fetch_site == 'cross-site':
                return web.Response(status=403)
        if request.headers.get('Origin') == 'http://untrusted.example':
            return web.Response(status=403)
        return await handler(request)
    return origin_only_middleware
'''


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.source = compat.patch_source(SOURCE)
        namespace = {'web': types.SimpleNamespace(middleware=lambda f: f, Response=lambda status=200: types.SimpleNamespace(status=status))}
        exec(compile(self.source, '<origin middleware>', 'exec'), namespace)
        self.middleware = namespace['create_origin_only_middleware']()

    def status(self, method='GET', path='/', mode='navigate', dest='document', site='cross-site', origin=None):
        headers = {'Sec-Fetch-Site': site, 'Sec-Fetch-Mode': mode, 'Sec-Fetch-Dest': dest}
        if origin:
            headers['Origin'] = origin
        request = types.SimpleNamespace(method=method, path=path, headers=headers)
        async def handler(request):
            return types.SimpleNamespace(status=200)
        return asyncio.run(self.middleware(request, handler)).status

    def test_landing_page_navigation(self):
        self.assertEqual(self.status(), 200)

    def test_api_post_and_embeds_still_blocked(self):
        for options in ({'method': 'POST', 'path': '/prompt'}, {'path': '/object_info'},
                        {'path': '/index.html'}, {'mode': 'cors', 'dest': 'empty'}, {'dest': 'iframe'}):
            with self.subTest(options=options):
                self.assertEqual(self.status(**options), 403)

    def test_origin_guard_preserved(self):
        self.assertEqual(self.status(origin='http://untrusted.example'), 403)
        self.assertEqual(self.status(site='same-origin', path='/object_info'), 200)

    def test_idempotence_and_fail_closed(self):
        self.assertEqual(compat.patch_source(self.source), self.source)
        with self.assertRaises(ValueError):
            compat.patch_source('different upstream code')


if __name__ == '__main__':
    unittest.main()
