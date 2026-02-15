import json

from MovieRipper.clz_index import build_index


def test_import_master_schema_fields(tmp_path):
    csv_path = tmp_path / "master.csv"
    out_path = tmp_path / "index.json"
    csv_path.write_text(
        "Title,Release Year,IMDb Url,Barcode,Format,Edition,Index\nMovie A,2000,https://www.imdb.com/title/tt1234567/,123,DVD,,10\n",
        encoding="utf-8",
    )
    index = build_index(str(csv_path), str(out_path))
    saved = json.loads(out_path.read_text(encoding="utf-8"))

    assert index["schema_version"] == "movie_index_v2"
    assert "generated_at" in index
    assert index["items"] == index["search"]
    assert saved["schema_version"] == "movie_index_v2"
