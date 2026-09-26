"""Mocked API checks; no network requests or real Dune result claims."""

import json
from pathlib import Path
import pytest

from gasopt.config import load_config
from gasopt.data import dune


def test_api_downloads_all_pages_and_records_execution(tmp_path, monkeypatch):
    calls = []
    def fake_request(path, body=None):
        calls.append((path, body))
        if path == 'sql/execute':
            return {'execution_id': 'TEST123'}
        if path.endswith('/status'):
            return {'state': 'QUERY_STATE_COMPLETED', 'execution_ended_at': '2026-09-23T12:00:00Z'}
        if 'offset=0' in path:
            return {'result': {'rows': [{'day': '2025-01-01', 'slot': 1}],
                               'metadata': {'total_row_count': 2}}, 'next_offset': 1}
        return {'result': {'rows': [{'day': '2025-01-01', 'slot': 2}], 'metadata': {'total_row_count': 2}}}
    monkeypatch.setattr(dune, 'dune_request', fake_request)
    output = tmp_path / 'SYNTHETIC_API_RESPONSE.csv'
    sidecar = dune.extract('SELECT synthetic_fixture', load_config(), 'slots', output)
    assert len(dune.pd.read_csv(output)) == 2
    meta = json.loads(sidecar.read_text())
    assert meta['source_reference'] == 'TEST123'
    assert len(calls) == 4
    assert sum(path == 'sql/execute' for path, _ in calls) == 1
    with pytest.raises(ValueError, match='mismatch'):
        dune.extract('DIFFERENT QUERY', load_config(), 'slots', output, execution_id='TEST123')


def test_api_refuses_incomplete_pages(tmp_path, monkeypatch):
    def fake_request(path, body=None):
        if path == 'sql/execute':
            return {'execution_id': 'TEST123'}
        if path.endswith('/status'):
            return {'state': 'QUERY_STATE_COMPLETED', 'execution_ended_at': '2026-09-23T12:00:00Z'}
        return {'result': {'rows': [], 'metadata': {'total_row_count': 2}}}
    monkeypatch.setattr(dune, 'dune_request', fake_request)
    output = tmp_path / 'SYNTHETIC_API_RESPONSE.csv'
    with pytest.raises(RuntimeError, match='Incomplete Dune pagination'):
        dune.extract('SELECT synthetic_fixture', load_config(), 'slots', output)
    assert not output.exists()


def test_no_credential_fails_without_network(monkeypatch):
    monkeypatch.delenv('DUNE_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='DUNE_API_KEY'):
        dune.dune_request('sql/execute', {'sql': 'SELECT 1'})
