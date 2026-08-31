import json

import pytest

import airidl.cli as cli


@pytest.mark.parametrize(("overall", "expected_exit"), [("pass", 0), ("fail", 3)])
def test_doctor_json_exit_code(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    overall: str,
    expected_exit: int,
) -> None:
    report = {
        "schema": "airidl.doctor/v1",
        "profile": "portable-ci",
        "overall": overall,
        "checks": [],
    }
    monkeypatch.setattr(cli, "collect_report", lambda _profile: report)
    exit_code = cli.main(["doctor", "--json", "--profile", "portable-ci"])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == report
    assert exit_code == expected_exit
