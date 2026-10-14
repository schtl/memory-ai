"""Check the deployed services and real local memory storage without cloud calls."""
import json
import os
import uuid
import urllib.request
import urllib.error


def request(url, data=None, headers=None):
    encoded = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=encoded,
        headers={'Content-Type': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    memory_url = os.getenv('MEMORY_URL', 'http://memory:8000')
    user = 'smoke-test-' + str(uuid.uuid4())
    auth = {'Authorization': 'Bearer ' + os.environ['MEMORY_API_KEY']}
    saved_ids = []

    def command(text, user_id=user):
        response = request(memory_url + '/v1/chat/completions',
            {'model': 'memory-ai', 'messages': [{'role': 'user', 'content': text}]},
            {**auth, 'X-OpenWebUI-User-Id': user_id})
        return response['choices'][0]['message']['content']

    try:
        assert request(memory_url + '/health')['status'] == 'ok'
        model_list = request(memory_url + '/v1/models', headers=auth)
        assert any(model['id'] == 'memory-ai' for model in model_list['data'])
        request(os.environ['OPENWEBUI_URL'] + '/health')
        request(os.environ['LITELLM_URL'] + '/health/liveliness', headers={
            'Authorization': 'Bearer ' + os.environ['LITELLM_MASTER_KEY']})
        print('PASS: Open WebUI, memory gateway and LiteLLM respond.')
        try:
            request(memory_url + '/v1/chat/completions',
                {'model': 'memory-ai', 'messages': [{'role': 'user', 'content': '/memories'}]}, auth)
        except urllib.error.HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError('Missing user ID was accepted')
        text = 'Smoke test fact ' + user
        response = command('/remember ' + text)
        memory_id = str(uuid.UUID(response.split('ID: ')[1]))
        saved_ids.append(memory_id)
        assert text in command('/memories')
        assert text not in command('/memories', user_id=user + '-other')
        assert 'No memory' in command('/forget ' + memory_id, user_id=user + '-other')
        assert text in command('/memories')
        assert 'deleted' in command('/forget ' + memory_id)
        saved_ids.remove(memory_id)
        assert text not in command('/memories')
        print('PASS: real embeddings, Qdrant writes, user isolation and deletion.')
        print('Smoke test passed. No external LLM request was made.')
    finally:
        for memory_id in saved_ids:
            command('/forget ' + memory_id)


if __name__ == '__main__':
    main()
