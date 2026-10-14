"""Dependency-free tests for domain configuration and Apache generation."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('apache_generator', ROOT / 'scripts' / 'generate_apache.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class ApacheGeneratorTests(unittest.TestCase):
    def test_domain_and_default_certificate_paths(self):
        domain, certificate, files = generator.render_configs({'PUBLIC_DOMAIN': 'ai.example.org'})
        self.assertEqual((domain, certificate), ('ai.example.org', 'ai.example.org'))
        self.assertIn('ServerName ai.example.org', files['memory-ai.conf'])
        self.assertIn('/etc/letsencrypt/live/ai.example.org/fullchain.pem', files['memory-ai.conf'])
        self.assertIn('upgrade=websocket', files['memory-ai.conf'])
        self.assertIn('${APACHE_LOG_DIR}', files['memory-ai.conf'])
        self.assertNotIn('{{', files['memory-ai.conf'])

    def test_existing_certificate_directory(self):
        _, certificate, files = generator.render_configs({
            'PUBLIC_DOMAIN': 'ai.example.org', 'APACHE_CERTIFICATE_NAME': 'example.org'})
        self.assertEqual(certificate, 'example.org')
        self.assertIn('/live/example.org/privkey.pem', files['memory-ai.conf'])
        self.assertIn('https://ai.example.org', files['memory-ai.conf'])

    def test_rejects_invalid_domains_and_injection(self):
        for domain in ['', 'localhost', 'https://ai.example.org', 'ai.example.org:443',
                       'ai.example.org/path', '*.example.org', '127.0.0.1', '-ai.example.org',
                       'ai_.example.org', 'ai.example.org\nProxyRequests On', 'a' * 64 + '.at']:
            with self.subTest(domain=domain):
                with self.assertRaises(ValueError):
                    generator.render_configs({'PUBLIC_DOMAIN': domain})

    def test_rejects_certificate_path_traversal(self):
        with self.assertRaises(ValueError):
            generator.render_configs({'PUBLIC_DOMAIN': 'ai.example.org',
                                      'APACHE_CERTIFICATE_NAME': '../../private'})

    def test_env_quotes_comments_and_unrelated_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            env.write_text('PUBLIC_DOMAIN="AI.EXAMPLE.ORG" # domain\n'
                           'APACHE_CERTIFICATE_NAME=\nCLOUD_API_KEY=secret\n')
            settings = generator.read_settings(env)
            self.assertNotIn('CLOUD_API_KEY', settings)
            self.assertEqual(generator.render_configs(settings)[0], 'ai.example.org')

    def test_duplicate_and_expansion_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            env.write_text('PUBLIC_DOMAIN=ai.example.org\nPUBLIC_DOMAIN=other.example.org\n')
            with self.assertRaises(ValueError):
                generator.read_settings(env)
            with self.assertRaises(ValueError):
                generator.render_configs({'PUBLIC_DOMAIN': '${OTHER_DOMAIN}'})

    def test_writes_files_and_regenerates_after_domain_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env, output = root / '.env', root / 'generated'
            env.write_text('PUBLIC_DOMAIN=ai.example.org\n')
            generator.generate(env, output)
            self.assertEqual(len(list(output.iterdir())), 2)
            env.write_text('PUBLIC_DOMAIN=tutor.example.org\n')
            generator.generate(env, output)
            for file in output.iterdir():
                self.assertNotIn('ai.example.org', file.read_text())
                self.assertIn('tutor.example.org', file.read_text())

    def test_invalid_configuration_does_not_overwrite_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env, output = root / '.env', root / 'generated'
            env.write_text('PUBLIC_DOMAIN=ai.example.org\n')
            generator.generate(env, output)
            original = (output / 'memory-ai.conf').read_bytes()
            env.write_text('PUBLIC_DOMAIN=invalid\n')
            with self.assertRaises(ValueError):
                generator.generate(env, output)
            self.assertEqual((output / 'memory-ai.conf').read_bytes(), original)

    def test_cli_reports_error_without_printing_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            env.write_text('PUBLIC_DOMAIN=invalid\nCLOUD_API_KEY=very-secret\n')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/generate_apache.py'),
                '--env-file', str(env), '--output-dir', str(Path(directory) / 'output')],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('very-secret', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
