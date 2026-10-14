"""HTTP regression tests: real FastAPI and in-memory Qdrant, no external calls."""
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

os.environ.setdefault('MEMORY_API_KEY', 'test-memory-key')
os.environ.setdefault('LITELLM_MASTER_KEY', 'test-upstream-key')
os.environ.setdefault('LITELLM_URL', 'http://mock-provider')
os.environ.setdefault('QDRANT_URL', 'http://unused')


class DeterministicEmbeddings:
    """Replace model downloads; matching text receives matching unit vectors."""
    def __init__(self, **kwargs):
        pass

    def embed(self, texts):
        for text in texts:
            result = np.zeros(384, dtype=np.float32)
            result[1 if 'unrelated' in text else 0] = 1
            yield result


@pytest.fixture
def gateway(monkeypatch):
    # Stub only the heavyweight model import; Qdrant and HTTP remain real.
    monkeypatch.setitem(sys.modules, 'fastembed', SimpleNamespace(TextEmbedding=DeterministicEmbeddings))
    source = Path(__file__).resolve().parents[1] / 'app.py'
    if not source.exists():
        source = source.parent / 'memory-service' / 'app.py'
    spec = importlib.util.spec_from_file_location('gateway_under_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'QdrantClient', lambda **kwargs:
        QdrantClient(':memory:', force_disable_check_same_thread=True))
    monkeypatch.setattr(module, 'SEND_MEMORY', True)
    calls = []
    mode = {'status': 200, 'offline': False}

    def provider(request):
        calls.append(request)
        if mode['offline']:
            raise httpx.ConnectError('Offline', request=request)
        if mode['status'] != 200:
            return httpx.Response(mode['status'], json={'error': 'provider-sensitive-details'})
        body = json.loads(request.content)
        if body.get('stream'):
            data = {'choices': [{'index': 0, 'delta': {'content': 'Mock answer'}}]}
            return httpx.Response(200, text='data: ' + json.dumps(data) + '\n\ndata: [DONE]\n\n',
                                  headers={'content-type': 'text/event-stream'})
        return httpx.Response(200, json={'choices': [
            {'message': {'role': 'assistant', 'content': 'Mock answer'}, 'finish_reason': 'stop'}]})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kwargs:
        real_async_client(transport=httpx.MockTransport(provider), **kwargs))
    with TestClient(module.app) as client:
        yield SimpleNamespace(client=client, module=module, calls=calls, mode=mode)


def headers(user='alice'):
    result = {'Authorization': 'Bearer ' + os.environ['MEMORY_API_KEY']}
    if user is not None:
        result['X-OpenWebUI-User-Id'] = user
    return result


def post(gateway, text, user='alice', **kwargs):
    body = {'model': 'memory-ai', 'messages': [{'role': 'user', 'content': text}], **kwargs}
    return gateway.client.post('/v1/chat/completions', headers=headers(user), json=body)


def reply(response):
    assert response.status_code == 200, response.text
    return response.json()['choices'][0]['message']['content']


def save(gateway, text, user='alice'):
    return reply(post(gateway, '/remember ' + text, user)).split('ID: ')[1]


def test_health_and_model_listing(gateway):
    assert gateway.client.get('/health').json() == {'status': 'ok'}
    assert gateway.client.get('/v1/models').status_code == 401
    response = gateway.client.get('/v1/models', headers=headers(None))
    assert response.json()['data'][0]['id'] == 'memory-ai'


def test_authentication_and_required_user_id(gateway):
    assert gateway.client.post('/v1/chat/completions', json={}).status_code == 401
    assert post(gateway, 'Hello', user=None).status_code == 403
    assert not gateway.calls


def test_store_list_and_delete_without_provider_calls(gateway):
    memory_id = save(gateway, 'I teach Java.')
    assert memory_id in reply(post(gateway, '/memories'))
    assert 'I teach Java.' in reply(post(gateway, '/memories'))
    assert 'deleted' in reply(post(gateway, '/forget ' + memory_id))
    assert reply(post(gateway, '/memories')) == 'No saved memories.'
    assert not gateway.calls


def test_user_separation_and_cross_user_delete_denied(gateway):
    alice = save(gateway, 'Alice private fact')
    save(gateway, 'Bob private fact', user='bob')
    assert 'Bob' not in reply(post(gateway, '/memories'))
    assert 'Alice' not in reply(post(gateway, '/memories', user='bob'))
    assert 'No memory' in reply(post(gateway, '/forget ' + alice, user='bob'))
    assert alice in reply(post(gateway, '/memories'))
    post(gateway, 'Recall my preferences')
    body = gateway.calls[-1].content.decode()
    assert 'Alice private fact' in body and 'Bob private fact' not in body


@pytest.mark.parametrize('command', ['/remember', '/remember ' + 'x' * 2001, '/forget invalid'])
def test_invalid_memory_commands_do_not_write_or_call_provider(gateway, command):
    assert 'Usage:' in reply(post(gateway, command))
    assert reply(post(gateway, '/memories')) == 'No saved memories.'
    assert not gateway.calls


def test_pagination_lists_more_than_one_page(gateway):
    for number in range(101):
        save(gateway, f'Fact {number}')
    assert reply(post(gateway, '/memories')).count('ID: ') == 101


def test_memory_retrieval_respects_threshold_and_deletion(gateway):
    memory_id = save(gateway, 'Relevant preference')
    post(gateway, 'Recall preference')
    assert 'Relevant preference' in gateway.calls[-1].content.decode()
    post(gateway, 'unrelated question')
    assert 'Relevant preference' not in gateway.calls[-1].content.decode()
    post(gateway, '/forget ' + memory_id)
    post(gateway, 'Recall preference')
    assert 'Relevant preference' not in gateway.calls[-1].content.decode()


def test_disabled_memory_and_filtered_history(gateway, monkeypatch):
    save(gateway, 'Stored private fact')
    monkeypatch.setattr(gateway.module, 'SEND_MEMORY', False)
    messages = [
        {'role': 'user', 'content': '/remember Stored private fact'},
        {'role': 'assistant', 'content': 'Saved locally'},
        {'role': 'user', 'content': '/memories'},
        {'role': 'assistant', 'content': 'Stored private fact'},
        {'role': 'user', 'content': 'Normal question'},
    ]
    post(gateway, '', messages=messages, user='alice')
    outbound = json.loads(gateway.calls[-1].content)
    assert outbound['messages'] == messages[-1:]


def test_identity_headers_and_metadata_are_not_forwarded(gateway):
    response = gateway.client.post('/v1/chat/completions',
        headers={**headers(), 'X-OpenWebUI-User-Email': 'private@example.org'},
        json={'model': 'memory-ai', 'messages': [{'role': 'user', 'content': 'Hello'}],
              'metadata': {'private': 'value'}, 'user': 'alice', 'temperature': 0.2})
    assert response.status_code == 200
    upstream = gateway.calls[-1]
    body = json.loads(upstream.content)
    assert 'metadata' not in body and 'user' not in body
    assert body['temperature'] == 0.2
    assert 'x-openwebui-user-id' not in upstream.headers
    assert 'private@example.org' not in str(upstream.headers)
    assert upstream.headers['authorization'] == 'Bearer ' + os.environ['LITELLM_MASTER_KEY']


def test_local_and_upstream_streaming(gateway):
    response = post(gateway, '/memories', stream=True)
    assert 'No saved memories.' in response.text and 'data: [DONE]' in response.text
    assert not gateway.calls
    response = post(gateway, 'Hello', stream=True)
    assert 'Mock answer' in response.text and 'data: [DONE]' in response.text


def test_upstream_errors_are_sanitized(gateway):
    gateway.mode['status'] = 429
    response = post(gateway, 'Hello')
    assert response.status_code == 429
    assert 'provider-sensitive-details' not in response.text
    gateway.mode['offline'] = True
    assert post(gateway, 'Hello').status_code == 502


@pytest.mark.parametrize('body', [
    {'model': 'memory-ai', 'messages': []},
    {'model': 'unknown', 'messages': [{'role': 'user', 'content': 'Hello'}]},
    {'model': 'memory-ai', 'messages': [{'role': 'system', 'content': 'Hello'}]},
])
def test_invalid_requests_are_rejected(gateway, body):
    assert gateway.client.post('/v1/chat/completions', headers=headers(), json=body).status_code == 400
    assert not gateway.calls
