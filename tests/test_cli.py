import csv
import json

import pytest

from jobspy_lite import ScrapeResults
from jobspy_lite.cli import main


def fake_results(monkeypatch, results):
    monkeypatch.setattr(
        "jobspy_lite.cli.scrape_jobs", lambda **kwargs: results
    )


def test_jsonl_to_stdout(monkeypatch, capsys, make_job):
    fake_results(
        monkeypatch,
        ScrapeResults(
            [make_job(site="indeed", min_amount=1)],
            sites=["indeed"],
            filtered_out=2,
            duplicates_removed=1,
        ),
    )

    code = main(["analyst", "--fields", "site,title"])

    printed = capsys.readouterr()
    assert code == 0
    rows = [json.loads(line) for line in printed.out.splitlines()]
    assert rows == [{"site": "indeed", "title": "Data Analyst"}]
    assert "2 jobs filtered out" in printed.err
    assert "1 duplicates merged" in printed.err


def test_csv_file(monkeypatch, capsys, make_job, tmp_path):
    fake_results(
        monkeypatch,
        ScrapeResults([make_job(site="indeed")], sites=["indeed"]),
    )
    path = tmp_path / "jobs.csv"

    code = main(["-o", str(path)])

    assert code == 0
    with path.open(encoding="utf-8", newline="") as saved:
        rows = list(csv.DictReader(saved))
    assert len(rows) == 1
    assert rows[0]["title"] == "Data Analyst"
    assert "1 jobs written to" in capsys.readouterr().err


def test_every_board_failing_exits_1(monkeypatch, make_job):
    fake_results(
        monkeypatch,
        ScrapeResults([], sites=["indeed"], errors={"indeed": "boom"}),
    )
    assert main(["analyst"]) == 1


def test_invalid_argument_exits_2(monkeypatch):
    def failing(**kwargs):
        raise ValueError("Invalid results_wanted: 0")

    monkeypatch.setattr("jobspy_lite.cli.scrape_jobs", failing)
    assert main(["analyst"]) == 2


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("jobspy-lite ")
    assert out.split()[-1][0].isdigit()
