import json

from shakti_seva.cli import main


def test_fixture_cli_writes_case_and_trace(capsys) -> None:
    exit_code = main(["case", "--fixture"])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["case"]["fixture"] is True
    assert output["case"]["next_step"]["code"] == "urgent_hpd_follow_up"
    assert output["trace_path"].endswith(".jsonl")
