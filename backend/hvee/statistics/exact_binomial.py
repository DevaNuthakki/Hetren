"""Deterministic exact-binomial utilities with no third-party dependency."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from math import comb


class ExactBinomialTail(str, Enum):
    """Inclusive binomial tails used by directional exact tests."""

    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"


@dataclass(frozen=True, slots=True)
class ExactPValue:
    """A stable claim key paired with an exact rational p-value."""

    claim_key: str
    value: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.claim_key, str) or not self.claim_key.strip():
            raise ValueError("claim_key must be a non-empty string")
        _require_probability(name="p-value", value=self.value)


@dataclass(frozen=True, slots=True)
class HolmStepDownDecision:
    """One ordered decision from Holm familywise error control."""

    claim_key: str
    rank: int
    raw_p_value: Fraction
    critical_value: Fraction
    adjusted_p_value: Fraction
    rejected: bool


def _require_count(*, name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_probability(*, name: str, value: object) -> Fraction:
    if not isinstance(value, Fraction) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a Fraction between zero and one")
    return value


def _require_binomial_observation(
    *,
    successes: object,
    trials: object,
) -> tuple[int, int]:
    checked_successes = _require_count(name="successes", value=successes)
    checked_trials = _require_count(name="trials", value=trials)
    if checked_trials == 0:
        raise ValueError("trials must be greater than zero")
    if checked_successes > checked_trials:
        raise ValueError("successes cannot exceed trials")
    return checked_successes, checked_trials


def exact_binomial_tail_probability(
    *,
    successes: int,
    trials: int,
    probability: Fraction,
    tail: ExactBinomialTail,
) -> Fraction:
    """Return an inclusive binomial tail using exact integer arithmetic."""

    checked_successes, checked_trials = _require_binomial_observation(
        successes=successes,
        trials=trials,
    )
    checked_probability = _require_probability(
        name="probability",
        value=probability,
    )
    if not isinstance(tail, ExactBinomialTail):
        raise ValueError("tail must be an ExactBinomialTail")

    probability_numerator = checked_probability.numerator
    probability_denominator = checked_probability.denominator
    complement_numerator = probability_denominator - probability_numerator
    denominator = probability_denominator**checked_trials

    if probability_numerator == 0:
        if tail is ExactBinomialTail.LESS_THAN_OR_EQUAL:
            return Fraction(1, 1)
        return Fraction(int(checked_successes == 0), 1)

    if complement_numerator == 0:
        if tail is ExactBinomialTail.GREATER_THAN_OR_EQUAL:
            return Fraction(1, 1)
        return Fraction(int(checked_successes == checked_trials), 1)

    if tail is ExactBinomialTail.LESS_THAN_OR_EQUAL:
        first_count = 0
        final_count = checked_successes
    else:
        first_count = checked_successes
        final_count = checked_trials

    term = (
        comb(checked_trials, first_count)
        * probability_numerator**first_count
        * complement_numerator ** (checked_trials - first_count)
    )
    numerator = term

    for count in range(first_count, final_count):
        term = (
            term
            * (checked_trials - count)
            * probability_numerator
            // ((count + 1) * complement_numerator)
        )
        numerator += term

    return Fraction(numerator, denominator)


def clopper_pearson_lower_bound_scaled(
    *,
    successes: int,
    trials: int,
    confidence_level: Fraction,
    scale: int,
) -> int:
    """Return the conservative scaled one-sided exact lower bound."""

    checked_successes, checked_trials = _require_binomial_observation(
        successes=successes,
        trials=trials,
    )
    checked_confidence = _require_probability(
        name="confidence_level",
        value=confidence_level,
    )
    checked_scale = _require_count(name="scale", value=scale)

    if checked_confidence in (0, 1):
        raise ValueError(
            "confidence_level must be strictly between zero and one"
        )
    if checked_scale == 0:
        raise ValueError("scale must be greater than zero")
    if checked_successes == 0:
        return 0

    alpha = 1 - checked_confidence
    low = 0
    high = checked_scale

    while low <= high:
        midpoint = (low + high) // 2
        tail_probability = exact_binomial_tail_probability(
            successes=checked_successes,
            trials=checked_trials,
            probability=Fraction(midpoint, checked_scale),
            tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
        )
        if tail_probability <= alpha:
            low = midpoint + 1
        else:
            high = midpoint - 1

    return high


def clopper_pearson_upper_bound_scaled(
    *,
    successes: int,
    trials: int,
    confidence_level: Fraction,
    scale: int,
) -> int:
    """Return the conservative scaled one-sided exact upper bound."""

    checked_successes, checked_trials = _require_binomial_observation(
        successes=successes,
        trials=trials,
    )
    checked_confidence = _require_probability(
        name="confidence_level",
        value=confidence_level,
    )
    checked_scale = _require_count(name="scale", value=scale)

    if checked_confidence in (0, 1):
        raise ValueError(
            "confidence_level must be strictly between zero and one"
        )
    if checked_scale == 0:
        raise ValueError("scale must be greater than zero")
    if checked_successes == checked_trials:
        return checked_scale

    alpha = 1 - checked_confidence
    low = 0
    high = checked_scale

    while low <= high:
        midpoint = (low + high) // 2
        tail_probability = exact_binomial_tail_probability(
            successes=checked_successes,
            trials=checked_trials,
            probability=Fraction(midpoint, checked_scale),
            tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
        )
        if tail_probability <= alpha:
            high = midpoint - 1
        else:
            low = midpoint + 1

    return low


def holm_step_down(
    *,
    p_values: Sequence[ExactPValue],
    familywise_alpha: Fraction,
) -> tuple[HolmStepDownDecision, ...]:
    """Apply deterministic Holm step-down control to exact p-values."""

    checked_alpha = _require_probability(
        name="familywise_alpha",
        value=familywise_alpha,
    )
    if checked_alpha in (0, 1):
        raise ValueError(
            "familywise_alpha must be strictly between zero and one"
        )
    if not p_values:
        raise ValueError("p_values must contain at least one claim")
    if any(not isinstance(item, ExactPValue) for item in p_values):
        raise ValueError(
            "p_values must contain only ExactPValue instances"
        )

    claim_keys = [item.claim_key for item in p_values]
    if len(set(claim_keys)) != len(claim_keys):
        raise ValueError("p_values must use unique claim keys")

    ordered = sorted(
        p_values,
        key=lambda item: (item.value, item.claim_key),
    )
    family_size = len(ordered)
    continue_rejecting = True
    running_adjusted = Fraction(0, 1)
    decisions: list[HolmStepDownDecision] = []

    for rank, item in enumerate(ordered, start=1):
        remaining_claims = family_size - rank + 1
        critical_value = checked_alpha / remaining_claims
        adjusted_value = min(
            Fraction(1, 1),
            item.value * remaining_claims,
        )
        running_adjusted = max(running_adjusted, adjusted_value)
        rejected = (
            continue_rejecting and item.value <= critical_value
        )

        if not rejected:
            continue_rejecting = False

        decisions.append(
            HolmStepDownDecision(
                claim_key=item.claim_key,
                rank=rank,
                raw_p_value=item.value,
                critical_value=critical_value,
                adjusted_p_value=running_adjusted,
                rejected=rejected,
            )
        )

    return tuple(decisions)
