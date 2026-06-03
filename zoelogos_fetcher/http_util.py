"""Shared HTTP helpers with retry, backoff, and polite delays."""
from __future__ import annotations
import os, sys, time, json, urllib.request, urllib.parse, urllib.error

DEBUG = bool(os.environ.get('ZOE_DEBUG'))


def http_get_json(url: str, headers: dict = None, max_retries: int = 3,
                  timeout: int = 30) -> dict:
    """GET a URL and parse JSON. Returns {} on persistent failure."""
    headers = headers or {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Zoe.Logos-Graph/3.0'
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if DEBUG:
                print(f'  HTTP {e.code} on {url[:120]}', file=sys.stderr)
            if e.code in (429, 503):
                time.sleep(min(60, 2 ** (attempt + 2)))
                continue
            if 500 <= e.code < 600 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {}
        except Exception as e:
            if DEBUG:
                print(f'  ERR {e} on {url[:120]}', file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {}
    return {}


def http_get_text(url: str, headers: dict = None, max_retries: int = 3,
                  timeout: int = 30) -> str:
    """GET a URL and return text. Returns '' on persistent failure."""
    headers = headers or {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Zoe.Logos-Graph/3.0'
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', errors='ignore')
        except urllib.error.HTTPError as e:
            if DEBUG:
                print(f'  HTTP {e.code} on {url[:120]}', file=sys.stderr)
            if e.code in (429, 503):
                time.sleep(min(60, 2 ** (attempt + 2)))
                continue
            return ''
        except Exception as e:
            if DEBUG:
                print(f'  ERR {e} on {url[:120]}', file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return ''
    return ''
