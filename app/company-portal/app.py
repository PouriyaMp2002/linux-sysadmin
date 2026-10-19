"""Small Linux/NFS lab workload. No authentication: private lab use only."""
import errno
import logging
import os
import re
import secrets
import stat
import time

from flask import (Flask, Request, abort, flash, g, jsonify, redirect,
                   render_template, request, send_file, session, url_for)
from werkzeug.exceptions import HTTPException

ALLOWED = frozenset({'txt', 'pdf', 'csv', 'md', 'docx', 'xlsx'})
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,119}\Z')


def valid_name(name):
    # Reject rather than silently rename; never accept a path or hidden file.
    return (isinstance(name, str) and NAME.fullmatch(name) is not None
            and '..' not in name and name == name.strip()
            and '.' in name and name.rsplit('.', 1)[1].lower() in ALLOWED)


def mount_unescape(value):
    return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)


def nfs_mount_id(path):
    with open('/proc/self/mountinfo', encoding='utf-8') as mounts:
        for line in mounts:
            left, right = line.rstrip().split(' - ', 1)
            fields = left.split()
            if mount_unescape(fields[4]) == path and right.split()[0] in {'nfs', 'nfs4'}:
                return fields[0]
    raise OSError(errno.ENODEV, 'Expected NFS mount is absent')


def storage_fd():
    """Pin the actual mount, not a possibly exposed local mountpoint directory."""
    if 'storage_fd' in g:
        return g.storage_fd
    mount = app.config['DOCUMENT_MOUNT']
    mount_fd = os.open(mount, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if app.config['REQUIRE_NFS']:
            expected = nfs_mount_id(mount)
            with open(f'/proc/self/fdinfo/{mount_fd}', encoding='utf-8') as info:
                actual = dict(line.strip().split(':', 1) for line in info)
            if actual.get('mnt_id', '').strip() != expected:
                raise OSError(errno.ENODEV, 'NFS mount changed while opening storage')
        fd = os.open('documents', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=mount_fd)
        if os.fstat(fd).st_dev != os.fstat(mount_fd).st_dev:
            os.close(fd)
            raise OSError(errno.ENODEV, 'Documents must be on the expected mount')
        g.storage_fd = fd
        return fd
    finally:
        os.close(mount_fd)


def new_staging_file():
    directory = storage_fd()
    name = '.upload-' + secrets.token_hex(16)
    fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory)
    stream = os.fdopen(fd, 'w+b')
    g.setdefault('staging_files', []).append((name, stream))
    return stream


class NFSRequest(Request):
    def _get_file_stream(self, total_content_length, content_type,
                         filename=None, content_length=None):
        # Werkzeug's default may spool to local /tmp. Always stage on NFS.
        return new_staging_file()


app = Flask(__name__)
app.request_class = NFSRequest
secret = os.environ.get('PORTAL_SECRET_KEY', '')
if len(secret) < 32:
    raise RuntimeError('Set PORTAL_SECRET_KEY to a persistent random value of at least 32 characters')
app.config.update(
    SECRET_KEY=secret,
    DOCUMENT_MOUNT=os.path.abspath(os.environ.get('DOCUMENT_MOUNT', '/mnt/company-documents')),
    REQUIRE_NFS=os.environ.get('REQUIRE_NFS', '1') != '0',
    MAX_CONTENT_LENGTH=int(os.environ.get('MAX_UPLOAD_MB', '10')) * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=64 * 1024,
    MAX_FORM_PARTS=8,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
)
if app.config['MAX_CONTENT_LENGTH'] <= 0:
    raise RuntimeError('MAX_UPLOAD_MB must be positive')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app.logger.setLevel(logging.INFO)
if not app.config['REQUIRE_NFS']:
    app.logger.warning('REQUIRE_NFS=0: local TEST MODE; never use on web01')


@app.context_processor
def template_helpers():
    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return session['csrf_token']
    return {'csrf_token': csrf_token, 'extensions': ', '.join(sorted(ALLOWED)),
            'upload_mb': app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)}


@app.before_request
def begin_request():
    g.started = time.monotonic()
    if request.method == 'POST':
        # Check availability before multipart parsing starts writing any bytes.
        storage_fd()
        token = request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        if not expected or not secrets.compare_digest(token, expected):
            abort(400, description='Invalid or missing CSRF token. Reload the page and try again.')


@app.after_request
def finish_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; style-src 'self'; script-src 'none'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
    response.headers['Cache-Control'] = 'no-store'
    app.logger.info('request method=%s path=%r status=%s duration_ms=%.1f peer=%s',
                    request.method, request.path, response.status_code,
                    (time.monotonic() - g.get('started', time.monotonic())) * 1000,
                    request.remote_addr)
    return response


@app.teardown_request
def close_storage(_error):
    directory = g.get('storage_fd')
    for name, stream in g.get('staging_files', []):
        try:
            stream.close()
        except OSError:
            app.logger.exception('Failed closing upload staging stream')
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass
        except OSError:
            app.logger.exception('Failed removing NFS staging file %s', name)
    if directory is not None:
        os.close(directory)


@app.errorhandler(OSError)
def storage_error(error):
    app.logger.exception('Document storage operation failed: %s', error)
    message = ('Document storage is unavailable or unwritable. Check the NFS mount, '
               'storage01, free space, and UID/GID 2500 permissions. '
               'If a write was interrupted, verify the file list before retrying.')
    if request.path == '/ready':
        return jsonify(status='not ready', error=message), 503
    return render_template('index.html', error=message), 503


@app.errorhandler(HTTPException)
def http_error(error):
    message = error.description
    if error.code == 413:
        message = 'Upload is too large. The entire request must fit within the configured upload limit.'
    return render_template('index.html', error=message), error.code


@app.get('/health')
def health():
    # Liveness intentionally does not touch NFS or create a session.
    return jsonify(status='ok'), 200


@app.get('/ready')
def ready():
    directory = storage_fd()
    os.listdir(directory)
    probe = new_staging_file()
    probe.write(b'readiness\n')
    probe.flush()
    os.fsync(probe.fileno())
    probe.seek(0)
    if probe.read() != b'readiness\n':
        raise OSError(errno.EIO, 'Storage readback failed')
    name, _ = g.staging_files[-1]
    probe.close()
    os.unlink(name, dir_fd=directory)
    g.staging_files.pop()
    return jsonify(status='ready', storage='readable and writable'), 200


@app.get('/')
def index():
    directory = storage_fd()
    files = []
    for name in os.listdir(directory):
        if not valid_name(name):
            continue
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:  # Concurrent delete is harmless.
            continue
        if stat.S_ISREG(info.st_mode):
            files.append({'name': name, 'size': info.st_size})
    files.sort(key=lambda f: f['name'].lower())
    return render_template('index.html', files=files)


@app.post('/upload')
def upload():
    uploads = request.files.getlist('file')
    if len(uploads) != 1 or len(request.files) != 1:
        abort(400, description='Select exactly one document.')
    document = uploads[0]
    name = document.filename
    if not valid_name(name):
        abort(400, description='Invalid filename or extension. Use 1–120 ASCII characters, '
              'start with a letter or digit, and use only letters, digits, spaces, dots, '
              'hyphens and underscores. Paths, double dots and hidden files are rejected.')
    directory = storage_fd()
    stream = document.stream
    stream.flush()
    os.fsync(stream.fileno())
    staging = next(n for n, s in g.staging_files if s is stream)
    try:
        # Same-filesystem hard link publishes a complete file atomically and
        # fails if ANY entry already has this name (including a symlink).
        os.link(staging, name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False)
    except FileExistsError:
        abort(409, description='A file with this name already exists. Rename your document.')
    app.logger.info('upload completed filename=%r bytes=%s', name, os.fstat(stream.fileno()).st_size)
    flash(f'Uploaded {name}.')
    return redirect(url_for('index'), code=303)


def checked_file(name):
    if not valid_name(name):
        abort(400, description='Invalid filename or extension.')
    directory = storage_fd()
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=directory)
    except FileNotFoundError:
        abort(404, description='Document not found.')
    except OSError as error:
        if error.errno == errno.ELOOP:
            abort(400, description='Symbolic links are not documents.')
        raise
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        abort(400, description='Only regular documents are supported.')
    return fd


@app.get('/download/<path:name>')
def download(name):
    stream = os.fdopen(checked_file(name), 'rb')
    try:
        response = send_file(stream, as_attachment=True, download_name=name,
                             mimetype='application/octet-stream', conditional=False)
        response.content_length = os.fstat(stream.fileno()).st_size
        response.call_on_close(stream.close)
        return response
    except Exception:
        stream.close()
        raise


@app.get('/delete/<path:name>')
def confirm_delete(name):
    os.close(checked_file(name))
    return render_template('index.html', confirm=name)


@app.post('/delete/<path:name>')
def delete(name):
    os.close(checked_file(name))
    # unlink never follows a replaced symlink. Storage writers are trusted.
    try:
        os.unlink(name, dir_fd=storage_fd())
    except FileNotFoundError:
        abort(404, description='Document not found.')
    app.logger.info('delete completed filename=%r', name)
    flash(f'Deleted {name}.')
    return redirect(url_for('index'), code=303)
