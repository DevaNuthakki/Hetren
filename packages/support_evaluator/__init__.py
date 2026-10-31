"""Evaluator-only data for the Milestone 1 support examples.

Only ``packages/verification/support_verification.py`` may import this
package. ``tests/unit/test_support_evaluator_boundaries.py`` enforces that.
"""

from .catalog import (
    EVALUATOR_FIELD_NAMES,
    EXAMPLES,
    EvidenceCondition,
    ExampleSpec,
    FAULTS,
    FaultDefinition,
    SupportVerdict,
    answer_pairs,
    example,
    fault,
    sensitive_tokens,
)
from .cases import (
    CASE_KINDS,
    CaseTruth,
    FAMILIES,
    HELD_OUT_KINDS,
    LOOKALIKES,
    case_answer_pairs,
)
from .leakage import (
    LeakFinding,
    NEUTRAL_FILE_NAME,
    assert_no_leaks,
    scan_agent_outputs,
    scan_case_content,
    scan_content,
    scan_identifiers,
)
from .registry import (
    NEUTRAL_RUN_ID,
    RunRegistration,
    RunRegistry,
)


__all__ = [
    "CASE_KINDS",
    "CaseTruth",
    "EVALUATOR_FIELD_NAMES",
    "FAMILIES",
    "HELD_OUT_KINDS",
    "LOOKALIKES",
    "case_answer_pairs",
    "scan_case_content",
    "EXAMPLES",
    "EvidenceCondition",
    "ExampleSpec",
    "FAULTS",
    "FaultDefinition",
    "LeakFinding",
    "NEUTRAL_FILE_NAME",
    "NEUTRAL_RUN_ID",
    "RunRegistration",
    "RunRegistry",
    "SupportVerdict",
    "answer_pairs",
    "assert_no_leaks",
    "example",
    "fault",
    "scan_agent_outputs",
    "scan_content",
    "scan_identifiers",
    "sensitive_tokens",
]
