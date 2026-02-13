$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

python -m MovieRipper run-queue --queue ".\MovieRipper\movie_queue.json"
