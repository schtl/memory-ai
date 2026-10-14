"""Check the real installed FastEmbed registry without downloading a model."""
import ast
from pathlib import Path
import re

from fastembed import TextEmbedding


def configured_constants():
    root = Path(__file__).resolve().parents[1]
    source = root / 'app.py'
    if not source.exists():
        source = root / 'memory-service' / 'app.py'
    constants = {}
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                        'DEFAULT_EMBEDDING_MODEL', 'EMBEDDING_DIMENSION'):
                    constants[target.id] = ast.literal_eval(node.value)
    return constants


def test_default_model_is_registered_in_real_fastembed():
    settings = configured_constants()
    supported = {entry['model']: entry for entry in TextEmbedding.list_supported_models()}
    model_name = settings['DEFAULT_EMBEDDING_MODEL']
    assert model_name in supported, f'{model_name} is unsupported by installed FastEmbed'
    assert supported[model_name]['dim'] == settings['EMBEDDING_DIMENSION']


def test_compose_uses_the_same_supported_model():
    root = Path(__file__).resolve().parents[1]
    compose = (root / 'compose.yaml').read_text()
    match = re.search(r'^\s+EMBEDDING_MODEL:\s*(\S+)\s*$', compose, re.MULTILINE)
    assert match is not None
    assert match.group(1) == configured_constants()['DEFAULT_EMBEDDING_MODEL']
