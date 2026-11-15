"""Coordinate access to the adapter's single stream across copies of this app."""
import functools
import hashlib
import os
from pathlib import Path
import tempfile


class EndpointBusy(ConnectionError):
    pass


class EndpointLease:
    def __init__(self, host, port):
        root = Path(tempfile.gettempdir()) / ('cosmos-control-locks-' + str(getattr(os, 'getuid', lambda: 'user')()))
        root.mkdir(mode=0o700, exist_ok=True)
        key = hashlib.sha256(f'{host}:{port}'.encode()).hexdigest()
        self.path = root / (key + '.lock')
        self.file = None
        self.endpoint = f'{host}:{port}'

    def acquire(self):
        self.file = self.path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.file.close()
            self.file = None
            raise EndpointBusy(f'{self.endpoint} is already in use by another operation or copy of this application. '
                               'Disconnect or close that connection first.') from error
        return self

    def release(self):
        if self.file:
            try:
                if os.name == 'nt':
                    import msvcrt
                    self.file.seek(0)
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.file.close()
                self.file = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()


def exclusive_endpoint(operation):
    @functools.wraps(operation)
    def wrapped(host, port=2000, *args, **kwargs):
        with EndpointLease(host, port):
            return operation(host, port, *args, **kwargs)
    return wrapped
