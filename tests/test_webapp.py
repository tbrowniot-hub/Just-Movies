import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from MovieRipper.webapp.app import create_app


def test_web_status_idle_shape():
    client = TestClient(create_app())
    res = client.get('/api/v1/status')
    assert res.status_code == 200
    payload = res.json()
    assert 'running' in payload
    assert 'step' in payload


def test_web_version_shape():
    client = TestClient(create_app())
    res = client.get('/api/v1/version')
    assert res.status_code == 200
    payload = res.json()
    assert payload['api_version'] == 'v1'
    assert 'app_version' in payload


def test_web_import_endpoint(tmp_path):
    client = TestClient(create_app())
    content = (
        "Title,Release Year,IMDb Url,Barcode,Format,Edition,Index\n"
        "Movie A,2000,https://www.imdb.com/title/tt1234567/,123,DVD,,10\n"
    )
    out = tmp_path / 'index.json'
    res = client.post(
        '/api/v1/import',
        data={'out_path': str(out)},
        files={'csv_file': ('sample.csv', content, 'text/csv')},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload['total_rows'] == 1
    assert payload['eligible'] == 1


def test_queue_page_renders():
    client = TestClient(create_app())
    res = client.get('/queue')
    assert res.status_code == 200


def test_index_load_endpoint(tmp_path):
    client = TestClient(create_app())
    idx = tmp_path / 'movie_index.json'
    idx.write_text(
        '{"items":[{"title":"Movie A","year":2000,"clz_index":10,"imdb_id":"tt1234567"},{"title":"Movie B","year":2001,"clz_index":null,"imdb_id":null}]}',
        encoding='utf-8',
    )
    res = client.post('/api/v1/index/load', json={'path': str(idx), 'eligible_only': True})
    assert res.status_code == 200
    payload = res.json()
    assert payload['total'] == 2
    assert payload['eligible_only'] is True
    assert len(payload['items']) == 1


def test_run_paths_endpoint(tmp_path):
    client = TestClient(create_app())
    queue = tmp_path / 'movie_queue.json'
    config = tmp_path / 'config.json'
    queue.write_text('{"items": []}', encoding='utf-8')
    config.write_text('{}', encoding='utf-8')

    res = client.post(
        '/api/v1/run/paths',
        json={
            'queue_path': str(queue),
            'config_path': str(config),
            'index_path': str(tmp_path / 'movie_index.json'),
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload['queue_exists'] is True
    assert payload['config_exists'] is True
    assert payload['index_exists'] is False
