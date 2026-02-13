$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

python -m MovieRipper build-queue --index ".\MovieRipper\movie_index.json" --out ".\MovieRipper\movie_queue.json"
