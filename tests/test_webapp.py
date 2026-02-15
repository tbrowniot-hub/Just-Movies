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
