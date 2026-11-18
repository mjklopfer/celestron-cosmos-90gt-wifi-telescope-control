"""Offline session ZIP save/read. Never extracts archives or contacts hardware."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from types import SimpleNamespace
import zipfile

MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024

class MemoryLog:
    def __init__(self, name, data):
        self.path = PurePosixPath(name)
        self.session_name = self.path.as_posix()
        self.data = data
        self.name = self.path.name
        self.parent = self.path.parent
    def open(self, mode='r', encoding=None):
        return io.BytesIO(self.data) if 'b' in mode else io.StringIO(self.data.decode(encoding or 'utf-8'))
    def stat(self):
        return SimpleNamespace(st_size=len(self.data))
    def resolve(self):
        return 'archive-member:' + str(self.path)

def json_log_bytes(data):
    value = json.loads(data.decode('utf-8-sig'))
    if isinstance(value, dict) and 'records' in value:
        value = value['records']
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ValueError('Expected an event, event list, or exported recording JSON.')
    events = []
    for row in value:
        if isinstance(row, dict) and row.get('details_json'):
            row = json.loads(row['details_json'])
        if isinstance(row, dict) and row.get('utc') and row.get('event'):
            events.append(row)
    if not events:
        raise ValueError('JSON contains no timestamped log events; choose an events log or exported recording.')
    return ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events).encode('utf-8')

def archive_logs(source):
    logs = []
    with zipfile.ZipFile(source) as archive:
        members = [m for m in archive.infolist() if not m.is_dir() and PurePosixPath(m.filename).suffix.lower() in ('.json', '.jsonl')]
        if sum(m.file_size for m in members) > MAX_TOTAL:
            raise ValueError('Archive logs exceed the 512 MiB import limit. Open smaller session archives.')
        for member in members:
            path = PurePosixPath(member.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in str(path) or member.file_size > MAX_MEMBER:
                raise ValueError('Unsafe archive path or log file larger than 256 MiB.')
            with archive.open(member) as stream:
                data = stream.read(MAX_MEMBER + 1)
            if len(data) > MAX_MEMBER:
                raise ValueError('Archive log exceeds 256 MiB.')
            if path.suffix.lower() == '.json':
                try:
                    data = json_log_bytes(data)
                except (ValueError, TypeError):
                    continue  # Reports/manifests are retained in ZIP, but are not event streams.
            logs.append(MemoryLog(str(path), data))
    if not logs:
        raise ValueError('ZIP contains no JSON/JSONL event recordings.')
    return logs

def save_logs_zip(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if not root.is_dir():
        raise ValueError('No saved logs directory exists yet.')
    if destination.is_relative_to(root):
        raise ValueError('Save the ZIP outside the logs directory to avoid including earlier archives.')
    files = [p for p in root.rglob('*') if p.is_file() and not p.is_symlink()]
    if not files:
        raise ValueError('No saved log files to archive.')
    fd, temp = tempfile.mkstemp(prefix='.cosmos-logs-', suffix='.zip', dir=destination.parent)
    os.close(fd)
    count = 0
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                remaining = file.stat().st_size
                with file.open('rb') as source, archive.open('logs/' + file.relative_to(root).as_posix(), 'w', force_zip64=True) as target:
                    while remaining:
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        target.write(chunk)
                        remaining -= len(chunk)
                count += 1
        os.replace(temp, destination)
    finally:
        if Path(temp).exists():
            Path(temp).unlink()
    return count
