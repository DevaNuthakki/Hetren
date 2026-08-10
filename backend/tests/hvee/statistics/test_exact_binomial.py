from fractions import Fraction

import pytest

from hvee.statistics import (
    ExactBinomialTail,
    ExactPValue,
    clopper_pearson_lower_bound_scaled,
    clopper_pearson_upper_bound_scaled,
    exact_binomial_tail_probability,
    holm_step_down,
)


def test_exact_tails_use_rational_arithmetic() -> None:
    assert exact_binomial_tail_probability(
        successes=1,
        trials=2,
        probability=Fraction(1, 3),
        tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
    ) == Fraction(5, 9)

    assert exact_binomial_tail_probability(
        successes=1,
        trials=2,
        probability=Fraction(1, 3),
        tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
    ) == Fraction(8, 9)


def test_lower_bound_is_conservative_on_the_requested_grid() -> None:
    scale = 1_000_000
    bound = clopper_pearson_lower_bound_scaled(
        successes=8,
        trials=10,
        confidence_level=Fraction(95, 100),
        scale=scale,
    )
    alpha = Fraction(5, 100)

    assert exact_binomial_tail_probability(
        successes=8,
        trials=10,
        probability=Fraction(bound, scale),
        tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
    ) <= alpha

    assert exact_binomial_tail_probability(
        successes=8,
        trials=10,
        probability=Fraction(bound + 1, scale),
        tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
    ) > alpha


def test_upper_bound_is_conservative_on_the_requested_grid() -> None:
    scale = 1_000_000
    bound = clopper_pearson_upper_bound_scaled(
        successes=2,
        trials=10,
        confidence_level=Fraction(95, 100),
        scale=scale,
    )
    alpha = Fraction(5, 100)

    assert exact_binomial_tail_probability(
        successes=2,
        trials=10,
        probability=Fraction(bound, scale),
        tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
    ) <= alpha

    assert exact_binomial_tail_probability(
        successes=2,
        trials=10,
        probability=Fraction(bound - 1, scale),
        tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
    ) > alpha


def test_exact_bound_endpoints_are_explicit() -> None:
    assert clopper_pearson_lower_bound_scaled(
        successes=0,
        trials=10,
        confidence_level=Fraction(95, 100),
        scale=1_000_000,
    ) == 0

    assert clopper_pearson_upper_bound_scaled(
        successes=10,
        trials=10,
        confidence_level=Fraction(95, 100),
        scale=1_000_000,
    ) == 1_000_000


def test_holm_stops_after_first_non_rejection() -> None:
    decisions = holm_step_down(
        p_values=(
            ExactPValue("third", Fraction(4, 100)),
            ExactPValue("first", Fraction(1, 100)),
            ExactPValue("second", Fraction(3, 100)),
        ),
        familywise_alpha=Fraction(5, 100),
    )

    assert [decision.claim_key for decision in decisions] == [
        "first",
        "second",
        "third",
    ]
    assert [decision.rejected for decision in decisions] == [
        True,
        False,
        False,
    ]
    assert [
        decision.adjusted_p_value for decision in decisions
    ] == [
        Fraction(3, 100),
        Fraction(6, 100),
        Fraction(6, 100),
    ]


def test_holm_ties_use_claim_key_and_accept_exact_equality() -> None:
    decisions = holm_step_down(
        p_values=(
            ExactPValue("b", Fraction(1, 40)),
            ExactPValue("a", Fraction(1, 40)),
        ),
        familywise_alpha=Fraction(1, 20),
    )

    assert [
        (decision.claim_key, decision.rank)
        for decision in decisions
    ] == [
        ("a", 1),
        ("b", 2),
    ]
    assert all(decision.rejected for decision in decisions)


@pytest.mark.parametrize(
    ("successes", "trials"),
    [(-1, 1), (0, 0), (2, 1), (True, 1)],
)
def test_binomial_observations_reject_invalid_counts(
    successes: int,
    trials: int,
) -> None:
    with pytest.raises(ValueError):
        exact_binomial_tail_probability(
            successes=successes,
            trials=trials,
            probability=Fraction(1, 2),
            tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
        )


def test_holm_rejects_duplicate_claim_keys() -> None:
    with pytest.raises(ValueError, match="unique claim keys"):
        holm_step_down(
            p_values=(
                ExactPValue("same", Fraction(1, 100)),
                ExactPValue("same", Fraction(2, 100)),
            ),
            familywise_alpha=Fraction(5, 100),
        )
