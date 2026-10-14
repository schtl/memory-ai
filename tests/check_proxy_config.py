"""Check the resolved production configuration without starting containers."""
import json
import subprocess


def main():
    result = subprocess.run([
        'docker', 'compose', '-f', 'compose.yaml', '-f', 'compose.proxy.yaml',
        'config', '--format', 'json',
    ], check=True, capture_output=True, text=True)
    config = json.loads(result.stdout)
    services = config['services']
    for name, service in services.items():
        if name != 'proxy':
            assert not service.get('ports'), f'{name} must not publish a host port'
    published = sorted((int(port['published']), port.get('protocol', 'tcp'))
                       for port in services['proxy']['ports'])
    assert published == [(80, 'tcp'), (443, 'tcp')], published
    assert config['networks']['frontend']['internal'] is True
    assert 'backend' not in services['proxy']['networks']
    assert 'frontend' in services['openwebui']['networks']
    assert services['openwebui']['environment']['WEBUI_URL'].startswith('https://')
    print('PASS: only proxy ports 80/443 are published; application services stay internal.')


if __name__ == '__main__':
    main()
