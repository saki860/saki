"""Exercise app response functions without starting Streamlit or calling Google."""
import ast
from pathlib import Path
import random
import unittest
from types import SimpleNamespace
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
APPS = ('streamlit_app.py', 'streamlit_app (1).py', 'streamlit_app_complete.py')


def load_app(filename, outcomes):
    tree = ast.parse((ROOT / filename).read_text())
    # Load real functions and the diagnostic helper, excluding top-level UI effects.
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             or isinstance(n, ast.ImportFrom) and n.module == 'gemini_errors']
    results = iter(outcomes)
    def generate(*args, **kwargs):
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)
    sdk = SimpleNamespace(configure=lambda **kw: None,
                          GenerativeModel=lambda name: SimpleNamespace(generate_content=generate))
    scope = dict(genai=sdk, List=List, Dict=Dict, Tuple=Tuple, random=random)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), scope)
    return scope


def respond(scope):
    if 'generate_ai_response_gemini' in scope:
        return scope['generate_ai_response_gemini']('hello', 0, 'listening', [], 'secret-key', 'listening')
    return scope['gemini_response']('hello', [], 'secret-key', 0, 'listening', '傾聴モード')


class ResponseTests(unittest.TestCase):
    def test_quota_is_not_hidden_by_later_missing_model(self):
        for filename in APPS:
            with self.subTest(app=filename):
                result = respond(load_app(filename, [RuntimeError('429 quota exhausted'),
                    RuntimeError('404 model not found'), RuntimeError('404 model not found')]))
                self.assertIn('利用上限', result)
                self.assertIn('429', result)
                self.assertIn('404', result)

    def test_successful_fallback_returns_answer(self):
        for filename in APPS:
            with self.subTest(app=filename):
                self.assertEqual(respond(load_app(filename, [RuntimeError('503 unavailable'), 'answer'])), 'answer')

    def test_first_model_success(self):
        for filename in APPS:
            with self.subTest(app=filename):
                self.assertEqual(respond(load_app(filename, ['answer'])), 'answer')

    def test_credentials_and_request_text_are_not_exposed(self):
        for filename in APPS:
            with self.subTest(app=filename):
                error = RuntimeError('403 secret-key private consultation')
                result = respond(load_app(filename, [error, error, error]))
                self.assertIn('APIキー', result)
                self.assertIn('403', result)
                self.assertNotIn('secret-key', result)
                self.assertNotIn('private consultation', result)

    def test_summary_diagnostics_are_safe(self):
        for filename in APPS:
            with self.subTest(app=filename):
                scope = load_app(filename, [RuntimeError('429 secret-key private consultation')])
                fn = scope.get('generate_conversation_summary', scope.get('make_summary'))
                result = fn([], 'secret-key')
                self.assertIn('利用上限', result)
                self.assertNotIn('secret-key', result)
                self.assertNotIn('private consultation', result)

    def test_unknown_error_has_no_raw_exception_text(self):
        for filename in APPS:
            with self.subTest(app=filename):
                error = RuntimeError('private consultation')
                result = respond(load_app(filename, [error, error, error]))
                self.assertIn('不明', result)
                self.assertNotIn('private consultation', result)

    def test_sdk_http_status_is_used(self):
        class QuotaError(Exception):
            code = 429
        for filename in APPS:
            with self.subTest(app=filename):
                error = QuotaError('no status in message')
                result = respond(load_app(filename, [error, error, error]))
                self.assertIn('利用上限', result)

if __name__ == '__main__':
    unittest.main()
