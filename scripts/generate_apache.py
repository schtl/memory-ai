#!/usr/bin/env python3
"""Generate Apache configuration from .env without modifying the web server."""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import shlex
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KEYS = {'PUBLIC_DOMAIN', 'APACHE_CERTIFICATE_NAME'}


def read_settings(path):
    settings = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, raw = line.partition('=')
        key = key.strip()
        if not separator or key not in KEYS:
            continue
        if key in settings:
            raise ValueError(f'Duplicate {key} in .env, line {number}')
        try:
            parts = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise ValueError(f'Invalid quoting for {key}, line {number}') from None
        if len(parts) > 1:
            raise ValueError(f'{key} must contain a single literal value')
        settings[key] = parts[0] if parts else ''
    return settings


def validate_hostname(value, key):
    # Accept literal ASCII DNS names only. Reject URLs, paths and config injection.
    value = value.lower()
    if not value or len(value) > 253 or '.' not in value:
        raise ValueError(f'{key} must be a full DNS hostname, for example ai.example.org')
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if not re.fullmatch(label + r'(?:\.' + label + r')+', value):
        raise ValueError(f'{key} must be a hostname without scheme, port, path or wildcard')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError(f'{key} must be a DNS hostname, not an IP address')


def render_configs(settings):
    domain = validate_hostname(settings.get('PUBLIC_DOMAIN', ''), 'PUBLIC_DOMAIN')
    certificate_name = validate_hostname(
        settings.get('APACHE_CERTIFICATE_NAME') or domain, 'APACHE_CERTIFICATE_NAME')
    templates = PROJECT_ROOT / 'proxy' / 'apache' / 'templates'
    files = {}
    for filename in ('memory-ai-http.conf', 'memory-ai.conf'):
        text = (templates / (filename + '.tpl')).read_text(encoding='utf-8')
        text = text.replace('{{DOMAIN}}', domain).replace('{{CERTIFICATE_NAME}}', certificate_name)
        if '{{' in text or '}}' in text:
            raise ValueError(f'Unresolved placeholder in {filename}')
        files[filename] = text
    return domain, certificate_name, files


def generate(env_file, output_dir):
    domain, certificate_name, files = render_configs(read_settings(env_file))
    # Validate and render everything before creating files.
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in files.items():
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    dir=output_dir, prefix='.apache-', delete=False) as temporary:
                temporary.write(text)
                temporary_path = Path(temporary.name)
            os.chmod(temporary_path, 0o644)
            os.replace(temporary_path, output_dir / filename)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return domain, certificate_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=PROJECT_ROOT / '.env')
    parser.add_argument('--output-dir', type=Path, default=PROJECT_ROOT / 'generated' / 'apache')
    args = parser.parse_args()
    try:
        domain, certificate_name = generate(args.env_file, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(f'Generated Apache configuration for https://{domain}')
    print(f'Certificate directory: /etc/letsencrypt/live/{certificate_name}')
    print(f'Files: {args.output_dir / "memory-ai-http.conf"}')
    print(f'       {args.output_dir / "memory-ai.conf"}')
    print('No Apache files were installed, no certificates issued and no services restarted.')


if __name__ == '__main__':
    main()
