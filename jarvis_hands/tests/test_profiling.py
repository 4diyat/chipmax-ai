"""Tes profiling mikro (Fase 8)."""

from __future__ import annotations

from typing import Any

from jarvis_hands.app import main
from jarvis_hands.profiling import ProfileReport, benchmark_one_euro, run_profile


def test_run_profile_small_iteration() -> None:
    report = run_profile(5)
    assert isinstance(report, ProfileReport)
    assert len(report.results) == 3
    for result in report.results:
        assert result.iterations == 5
        assert result.total_ms >= 0.0
        assert result.per_call_us >= 0.0
    assert report.slowest() is not None
    markdown = report.to_markdown()
    assert "| Benchmark |" in markdown
    assert "One-Euro 2D" in markdown
    assert "Mesin gestur" in markdown
    payload = report.to_dict()
    assert len(payload["results"]) == 3
    assert payload["results"][0]["name"] == "One-Euro 2D"


def test_benchmark_one_euro_returns_result() -> None:
    result = benchmark_one_euro(3)
    assert result.name == "One-Euro 2D"
    assert result.iterations == 3
    assert result.note


def test_profile_cli_prints_table(capsys: Any) -> None:
    assert main(["--profile", "--profile-iterations", "3"]) == 0
    output = capsys.readouterr().out
    assert "One-Euro 2D" in output
    assert "Kursor 2D" in output
    assert "Mesin gestur" in output
