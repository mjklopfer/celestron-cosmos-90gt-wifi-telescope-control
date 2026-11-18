"""Offline bridge JSONL export; never connects to a telescope or replays motion.

python -m export_recording events.jsonl track.csv --select positions --format csv
Selections: packets (raw Wi-Fi AUX traffic), positions (measured encoders), both.
Status/gap events are retained in every selection. Active logs export a bounded
snapshot of already-written bytes; queued unwritten events are not included.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from bridge_decode import describe_aux

COLUMNS = ('record_type', 'source_session', 'source_line', 'export_time', 'utc', 'monotonic_seconds', 'event',
           'direction', 'axis', 'encoder_counts', 'raw_angle_degrees',
           'source_node_hex', 'destination_node_hex', 'command_hex', 'payload_hex',
           'frame_hex', 'interpretation', 'message', 'details_json')


def recording_files(source):
    source = Path(source)
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise ValueError('Select an events.jsonl file or a logs folder.')
    files = ([source / 'events.jsonl'] if (source / 'events.jsonl').is_file() else [])
    files += sorted(source.glob('*/events.jsonl'))
    if not files:
        raise ValueError('No events.jsonl recordings found in this folder.')
    return files


def parse_timestamp(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    return stamp.astimezone(dt.timezone.utc)  # Naive inputs use this system's local zone.


def recording_bounds(source):
    stamps = []
    files = recording_files(source)
    for file in files:
        with file.open('r', encoding='utf-8') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    if event.get('utc'):
                        stamps.append(parse_timestamp(event['utc']))
                except (ValueError, TypeError):
                    continue
    if not stamps:
        raise ValueError('No timestamped events found.')
    return {'first': min(stamps).isoformat(), 'last': max(stamps).isoformat(), 'sessions': len(files)}


def export_recording(source, destination, selection='both', format='csv',
                     start=None, end=None, time_format='local'):
    """Export a snapshot. Range is start-inclusive/end-exclusive; never replay motion."""
    source, destination = Path(source), Path(destination)
    if selection not in ('packets', 'positions', 'both') or format not in ('csv', 'json'):
        raise ValueError('Select packets, positions or both, and CSV or JSON.')
    if time_format not in ('local', 'unix'):
        raise ValueError('Time format must be local or unix.')
    start = parse_timestamp(start) if isinstance(start, str) else start
    end = parse_timestamp(end) if isinstance(end, str) else end
    if start and end and end <= start:
        raise ValueError('End must be after start.')
    files = recording_files(source)
    if any(file.resolve() == destination.resolve() for file in files):
        raise ValueError('Choose an export filename different from the original log.')
    records, warnings, snapshots = [], [], []
    for file in files:
        with file.open('rb') as stream:
            snapshot = stream.read(file.stat().st_size)
        session = file.parent.name + '/' + file.name
        snapshots.append({'session': session, 'bytes': len(snapshot), 'sha256': hashlib.sha256(snapshot).hexdigest()})
        lines = snapshot.splitlines(keepends=True)
        for number, line in enumerate(lines, 1):
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError) as error:
                if number == len(lines) and not line.endswith(b'\n'):
                    warnings.append(f'{session}: incomplete final log line omitted from active-file snapshot.')
                    break
                raise ValueError(f'Invalid log record in {session} at line {number}') from error
            stamp = parse_timestamp(event['utc']) if event.get('utc') else None
            if stamp and ((start and stamp < start) or (end and stamp >= end)):
                continue
            kind = event.get('event', '')
            packet = kind == 'bridge_packet'
            position = kind in ('bridge_values', 'motor_values')
            if (packet and selection == 'positions') or (position and selection == 'packets'):
                continue
            row = dict.fromkeys(COLUMNS, '')
            export_time = (stamp.timestamp() if time_format == 'unix' else stamp.astimezone().isoformat()) if stamp else ''
            row.update(record_type='packet' if packet else 'position' if position else 'status',
                       source_session=session, source_line=number, export_time=export_time,
                       utc=event.get('utc', ''), monotonic_seconds=event.get('monotonic', ''), event=kind,
                       message=event.get('message', ''), details_json=json.dumps(event, ensure_ascii=False))
            if position:
                row.update(axis={16: 'azimuth', 17: 'elevation'}.get(event.get('axis'), str(event.get('axis', ''))),
                           encoder_counts=event.get('encoder', ''), raw_angle_degrees=event.get('angle', ''))
            elif packet:
                raw = event.get('hex', '')
                row.update(direction=event.get('direction', ''), frame_hex=raw)
                try:
                    frame = bytes.fromhex(raw)
                    if len(frame) < 6:
                        raise ValueError('short frame')
                    row.update(source_node_hex=f'0x{frame[2]:02X}', destination_node_hex=f'0x{frame[3]:02X}',
                               command_hex=f'0x{frame[4]:02X}', payload_hex=frame[5:-1].hex(' ').upper(),
                               interpretation=event.get('interpretation') or describe_aux(frame))
                except ValueError:
                    row['interpretation'] = 'Invalid raw frame; retained without decoding'
            records.append(row)
    # UTC orders sessions; equal timestamps preserve source order. Monotonic clocks
    # cannot safely be compared across different machines or boot sessions.
    records.sort(key=lambda row: parse_timestamp(row['utc']) if row['utc'] else dt.datetime.max.replace(tzinfo=dt.timezone.utc))
    metadata = dict(schema_version=1, selection=selection,
                    exported_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    source_file=source.name, source_snapshots=snapshots,
                    snapshot_bytes=sum(item['bytes'] for item in snapshots), records=len(records), warnings=warnings,
                    time_format=time_format, local_timezone='exporting computer local zone with per-event UTC offset',
                    start_inclusive=start.isoformat() if start else None,
                    end_exclusive=end.isoformat() if end else None,
                    coordinate_system='raw motor encoder; not aligned sky coordinates',
                    timing='bridge observation timestamps; not hardware execution time',
                    coverage='snapshot of written log only; inspect status records for gaps and reconnects')
    time_column = 'timestamp_unix_seconds_utc' if time_format == 'unix' else 'timestamp_local_iso8601'
    metadata['timestamp_field'] = time_column
    columns = tuple(time_column if col == 'export_time' else col for col in COLUMNS)
    for row in records:
        row[time_column] = row.pop('export_time')
    if format == 'json':
        destination.write_text(json.dumps({'metadata': metadata, 'records': records}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    else:
        with destination.open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerow({'record_type': 'export_metadata', 'details_json': json.dumps(metadata, ensure_ascii=False)})
            writer.writerows(records)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='events.jsonl or logs folder containing session folders')
    parser.add_argument('destination', type=Path, help='Output CSV or JSON filename')
    parser.add_argument('--select', choices=('packets', 'positions', 'both'), default='both')
    parser.add_argument('--format', choices=('csv', 'json'), default='csv')
    parser.add_argument('--start', help='Inclusive ISO timestamp; offset recommended; naive means local')
    parser.add_argument('--end', help='Exclusive ISO timestamp; offset recommended; naive means local')
    parser.add_argument('--time-format', choices=('local', 'unix'), default='local')
    args = parser.parse_args()
    print(json.dumps(export_recording(args.source, args.destination, args.select, args.format, args.start, args.end, args.time_format), indent=2))


if __name__ == '__main__':
    main()
