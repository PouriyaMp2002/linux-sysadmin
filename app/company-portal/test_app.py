"""Local behavior tests only; do not contact or modify any homelab server."""
import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('PORTAL_SECRET_KEY', 'local-test-key-only-not-for-deployment-12345')
from app import app, nfs_mount_id, valid_name


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.docs = self.root / 'documents'
        self.docs.mkdir()
        self.old = {key: app.config[key] for key in
                    ('TESTING', 'REQUIRE_NFS', 'DOCUMENT_MOUNT', 'MAX_CONTENT_LENGTH')}
        app.config.update(TESTING=True, REQUIRE_NFS=False,
                          DOCUMENT_MOUNT=str(self.root), MAX_CONTENT_LENGTH=1024 * 1024)
        self.client = app.test_client()
        page = self.client.get('/')
        self.token = re.search(rb'name="csrf_token" value="([a-f0-9]+)"', page.data)[1].decode()

    def tearDown(self):
        app.config.update(self.old)
        self.temp.cleanup()

    def upload(self, name='lab-test.txt', content=b'hello NFS\n', token=None):
        return self.client.post('/upload', data={
            'csrf_token': self.token if token is None else token,
            # Preserve a literal backslash through MIME quoted-string decoding.
            'file': (io.BytesIO(content), name.replace('\\', '\\\\'))})

    def test_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Company Internal Portal', response.data)

    def test_existing_documents_listed(self):
        (self.docs / 'existing.pdf').write_bytes(b'example')
        self.assertIn(b'existing.pdf', self.client.get('/').data)

    def test_upload_download_delete(self):
        content = b'round trip contents\n'
        self.assertEqual(self.upload(content=content).status_code, 303)
        self.assertEqual((self.docs / 'lab-test.txt').read_bytes(), content)
        response = self.client.get('/download/lab-test.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, content)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        response.close()
        confirmation = self.client.get('/delete/lab-test.txt')
        self.assertIn(b'Confirm delete', confirmation.data)
        self.assertTrue((self.docs / 'lab-test.txt').exists())
        response = self.client.post('/delete/lab-test.txt', data={'csrf_token': self.token})
        self.assertEqual(response.status_code, 303)
        self.assertFalse((self.docs / 'lab-test.txt').exists())

    def test_duplicate_preserves_original(self):
        self.upload(content=b'original')
        self.assertEqual(self.upload(content=b'replacement').status_code, 409)
        self.assertEqual((self.docs / 'lab-test.txt').read_bytes(), b'original')
        self.assertFalse(list(self.docs.glob('.upload-*')))

    def test_invalid_upload_names(self):
        for name in ('../escape.txt', '/tmp/escape.txt', 'folder/a.txt',
                     'a\\b.txt', '.hidden.txt', 'bad..txt', 'a.html', 'a.py',
                     'a.txt ', 'a\n.txt', 'café.txt', 'x' * 121 + '.txt', ''):
            with self.subTest(name=name):
                self.assertEqual(self.upload(name=name).status_code, 400)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_allowlist_case_and_spaces(self):
        self.assertEqual(self.upload(name='Meeting Notes.PDF').status_code, 303)
        self.assertTrue(valid_name('Meeting Notes.PDF'))

    def test_download_and_delete_paths_rejected(self):
        for method in ('/download/', '/delete/'):
            for path in ('../outside.txt', 'nested/file.txt', '.hidden.txt', 'a.py'):
                self.assertEqual(self.client.get(method + path).status_code, 400)

    def test_upload_requires_csrf(self):
        self.assertEqual(self.upload(token='wrong').status_code, 400)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_cross_session_token_rejected(self):
        other = app.test_client()
        response = other.post('/upload', data={'csrf_token': self.token,
                              'file': (io.BytesIO(b'no'), 'cross.txt')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_delete_requires_csrf(self):
        (self.docs / 'keep.txt').write_bytes(b'keep')
        response = self.client.post('/delete/keep.txt', data={'csrf_token': 'bad'})
        self.assertEqual(response.status_code, 400)
        self.assertTrue((self.docs / 'keep.txt').exists())

    def test_missing_file(self):
        self.assertEqual(self.client.get('/download/absent.txt').status_code, 404)
        self.assertEqual(self.client.get('/delete/absent.txt').status_code, 404)

    def test_upload_size_limit(self):
        response = self.upload(content=b'x' * (1024 * 1024))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_large_upload_never_uses_local_tempfile(self):
        # Crosses Werkzeug's usual 500 KB spooling threshold.
        with patch('tempfile.TemporaryFile', side_effect=AssertionError('Local spool used')):
            content = b'x' * 700000
            self.assertEqual(self.upload(content=content).status_code, 303)
        self.assertEqual((self.docs / 'lab-test.txt').read_bytes(), content)
        self.assertFalse(list(self.docs.glob('.upload-*')))

    def test_empty_file_allowed(self):
        self.assertEqual(self.upload(content=b'').status_code, 303)
        self.assertEqual((self.docs / 'lab-test.txt').stat().st_size, 0)

    def test_no_file_rejected(self):
        self.assertEqual(self.client.post('/upload', data={
            'csrf_token': self.token}).status_code, 400)

    def test_multiple_files_rejected_and_cleaned(self):
        response = self.client.post('/upload', data={'csrf_token': self.token, 'file': [
            (io.BytesIO(b'1'), 'one.txt'), (io.BytesIO(b'2'), 'two.txt')]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_symlink_not_followed_or_listed(self):
        outside = self.root / 'outside.txt'
        outside.write_bytes(b'private')
        (self.docs / 'link.txt').symlink_to(outside)
        self.assertNotIn(b'link.txt', self.client.get('/').data)
        self.assertEqual(self.client.get('/download/link.txt').status_code, 400)
        self.assertEqual(self.client.post('/delete/link.txt', data={
            'csrf_token': self.token}).status_code, 400)
        self.assertEqual(self.upload(name='link.txt').status_code, 409)
        self.assertEqual(outside.read_bytes(), b'private')

    def test_fifo_rejected_without_blocking(self):
        os.mkfifo(self.docs / 'pipe.txt')
        self.assertEqual(self.client.get('/download/pipe.txt').status_code, 400)

    def test_missing_storage_fails_ready_but_not_health(self):
        self.docs.rmdir()
        self.assertEqual(self.client.get('/ready').status_code, 503)
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 503)
        self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(self.docs.exists())

    def test_non_nfs_mount_rejected_without_local_fallback(self):
        app.config['REQUIRE_NFS'] = True
        self.assertEqual(self.client.get('/ready').status_code, 503)
        self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_mount_identity_race_fails_closed(self):
        app.config['REQUIRE_NFS'] = True
        with patch('app.nfs_mount_id', return_value='0'):
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_documents_symlink_rejected(self):
        self.docs.rmdir()
        target = self.root / 'elsewhere'
        target.mkdir()
        self.docs.symlink_to(target)
        self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(list(target.iterdir()), [])

    def test_readiness_real_write_read_and_cleanup(self):
        response = self.client.get('/ready')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ready')
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_permission_error_returns_503(self):
        with patch('app.new_staging_file', side_effect=PermissionError('simulated read-only NFS')):
            self.assertEqual(self.client.get('/ready').status_code, 503)
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'unavailable or unwritable', response.data)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_disk_full_does_not_publish(self):
        with patch('app.os.fsync', side_effect=OSError(28, 'simulated disk full')):
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_publish_failure_does_not_claim_success(self):
        with patch('app.os.link', side_effect=OSError(5, 'simulated NFS error')):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'Uploaded lab-test.txt', response.data)
        self.assertEqual(list(self.docs.iterdir()), [])

    def test_security_headers_and_cookie(self):
        client = app.test_client()
        response = client.get('/')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("script-src 'none'", response.headers['Content-Security-Policy'])
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])

    def test_hidden_staging_not_listed(self):
        (self.docs / '.upload-leftover').write_bytes(b'interrupted')
        (self.docs / 'ignored.exe').write_bytes(b'unlisted')
        self.assertNotIn(b'.upload-leftover', self.client.get('/').data)
        self.assertNotIn(b'ignored.exe', self.client.get('/').data)

    def test_mountinfo_parsing(self):
        data = '100 1 0:12 / /mnt/test\\040space rw - nfs4 10.0.2.12:/srv/company-data rw\n'
        with patch('builtins.open', return_value=io.StringIO(data)):
            self.assertEqual(nfs_mount_id('/mnt/test space'), '100')


if __name__ == '__main__':
    unittest.main(verbosity=2)
