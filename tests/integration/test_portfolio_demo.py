"""Integration tests for the reproducible executable portfolio demo."""

import json

from packages.contracts import (
    canonical_sha256,
)
from packages.portfolio_demo import (
    build_demo_report,
    main,
    render_json,
    render_text,
)


def test_report_is_deterministic():
    first = build_demo_report()
    second = build_demo_report()

    assert first == second

    assert (
        render_json(first)
        == render_json(second)
    )


def test_report_contains_both_controlled_fault_scenarios():
    report = build_demo_report()

    assert [
        scenario["fault_fixture"]
        for scenario in report["scenarios"]
    ] == [
        "tool_selection",
        "parameter_transformation",
    ]


def test_each_scenario_exposes_complete_executable_chain():
    report = build_demo_report()

    expected = {
        "tool_selection": (
            "tool_selection_fault",
            "replace_tool",
        ),
        "parameter_transformation": (
            "parameter_transformation_fault",
            "override_parameter",
        ),
    }

    for scenario in report["scenarios"]:
        diagnosis, repair = expected[
            scenario["fault_fixture"]
        ]

        assert scenario["baseline"]["output"] == 2

        assert (
            scenario["diagnosis"]["status"]
            == "diagnosed"
        )

        assert (
            scenario["diagnosis"]["hypothesis"]
            == diagnosis
        )

        assert (
            scenario["repair"]["kind"]
            == repair
        )

        assert (
            scenario["candidate"]["output"]
            == 12
        )

        assert (
            scenario["source_evaluation"]["outcome"]
            == "PASS"
        )

        assert (
            scenario["verification"]["evaluation_outcome"]
            == "PASS"
        )

        assert (
            scenario["verification"]["outcome"]
            == "VERIFIED"
        )

        assert (
            scenario["eligibility"]["outcome"]
            == "ELIGIBLE"
        )


def test_report_exposes_distinct_verification_lineage():
    report = build_demo_report()

    for scenario in report["scenarios"]:
        assert (
            scenario["source_evaluation"]["execution_id"]
            != scenario["verification"]["execution_id"]
        )

        assert (
            scenario["source_evaluation"]["evaluation_id"]
            != scenario["verification"]["evaluation_id"]
        )


def test_policy_control_proves_verified_does_not_imply_eligible():
    report = build_demo_report()
    control = report["policy_control"]

    assert (
        control["verification_outcome"]
        == "VERIFIED"
    )

    assert (
        control["default_policy"]["outcome"]
        == "ELIGIBLE"
    )

    assert (
        control["restricted_policy"]["outcome"]
        == "INELIGIBLE"
    )

    assert (
        control["default_policy"]["policy_sha256"]
        != control["restricted_policy"]["policy_sha256"]
    )

    assert (
        control["conclusion"]
        == "VERIFIED does not automatically imply ELIGIBLE"
    )


def test_report_hash_binds_report_body():
    report = build_demo_report()

    body = {
        key: value
        for key, value in report.items()
        if key != "report_sha256"
    }

    assert (
        report["report_sha256"]
        == canonical_sha256(body)
    )


def test_json_renderer_is_parseable_and_stable():
    report = build_demo_report()

    rendered = render_json(
        report
    )

    assert json.loads(
        rendered
    ) == report

    assert (
        '"report_sha256"'
        in rendered
    )


def test_text_renderer_is_reviewer_facing():
    report = build_demo_report()

    rendered = render_text(
        report
    )

    assert (
        "Hetren deterministic executable "
        "portfolio demonstration"
        in rendered
    )

    assert (
        "Fixture: tool_selection"
        in rendered
    )

    assert (
        "Fixture: parameter_transformation"
        in rendered
    )

    assert (
        "Verification: VERIFIED"
        in rendered
    )

    assert (
        "Restricted policy: INELIGIBLE"
        in rendered
    )

    assert (
        "Report SHA-256:"
        in rendered
    )


def test_json_cli_surface(capsys):
    result = main(
        ["--format", "json"]
    )

    captured = capsys.readouterr()

    assert result == 0

    payload = json.loads(
        captured.out
    )

    assert (
        payload["report_type"]
        == "HetrenDeterministicPortfolioDemo"
    )


def test_text_cli_surface(capsys):
    result = main(
        ["--format", "text"]
    )

    captured = capsys.readouterr()

    assert result == 0

    assert (
        "VERIFIED does not automatically imply ELIGIBLE"
        in captured.out
    )

    assert (
        "ELIGIBLE is not authorization or deployment approval"
        in captured.out
    )
