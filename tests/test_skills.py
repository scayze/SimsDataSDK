import json

import pytest

from sims4_sdk.skills import (
    ADULT_CURVE, CHILD_CURVE, TODDLER_CURVE, VAMPIRE_LORE_CURVE,
    SkillCurve, SkillCurveError, convert_skill_xp,
)


@pytest.mark.parametrize("curve", [ADULT_CURVE, CHILD_CURVE, TODDLER_CURVE, VAMPIRE_LORE_CURVE])
def test_reference_curve_boundaries(curve):
    for level, threshold in enumerate(curve.thresholds, 1):
        assert convert_skill_xp(threshold, curve).level == level
        if level > 1:
            assert convert_skill_xp(threshold - 0.01, curve).level == level - 1
    assert convert_skill_xp(curve.thresholds[-1] + 100000, curve).level == curve.max_level


def test_unknown_curve_and_100_xp_do_not_imply_assignment():
    unresolved = convert_skill_xp(100)
    assert unresolved.raw_xp == 100
    assert unresolved.level is None and unresolved.status == "unresolved_curve"
    unknown_assignment = convert_skill_xp(100, ADULT_CURVE)
    assert unknown_assignment.level == 1 and unknown_assignment.assigned is None
    floor = convert_skill_xp(100, ADULT_CURVE, assigned=False)
    assert floor.level is None and floor.status == "unassigned"
    assert convert_skill_xp(100, ADULT_CURVE, assigned=True).level == 1


def test_custom_curve_and_serialization():
    curve = SkillCurve("mod", [100, 200, 400], "fixture")
    assert convert_skill_xp(99, curve).status == "below_curve"
    result = convert_skill_xp(200, curve, assigned=True)
    assert json.loads(result.to_json())["curve"]["thresholds"] == [100, 200, 400]
    assert result.to_dict()["level"] == 2


@pytest.mark.parametrize("thresholds", [(), (0, 0), (5, 1), (0, float("nan")), (-1,)])
def test_invalid_curves(thresholds):
    with pytest.raises(SkillCurveError):
        SkillCurve("invalid", thresholds, "fixture")


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_invalid_xp(value):
    with pytest.raises(SkillCurveError):
        convert_skill_xp(value, ADULT_CURVE)
