import pathlib
import subprocess
import sys
from fractions import Fraction

import pytest

from batterylib import (
    VSPLITTER_1_OVER_2,
    VSPLITTER_1_OVER_3,
    VSPLITTER_1_OVER_5,
    VSPLITTER_1_OVER_7,
    BalancerDefinition,
    BatteryDefinition,
    MaxDrain,
    NontrivialLine,
    calculate_longest_gap,
    generate_reachable_fractions,
    sort_deduplicate,
)

ROOT = pathlib.Path(__file__).parent.parent


# --- sort_deduplicate ---


@pytest.mark.parametrize(
    "input,expected",
    [
        ([3, 1, 2, 1], [1, 2, 3]),
        ([], []),
        ([5, 5, 5], [5]),
        ([1, 2, 3], [1, 2, 3]),
        ([2, 2, 3, 1, 3], [1, 2, 3]),
    ],
)
def test_sort_deduplicate(input, expected):
    assert sort_deduplicate(input) == expected


# --- VirtualSplitterDefinition.can_be_first ---


@pytest.mark.parametrize(
    "vsplitter,expected",
    [
        (VSPLITTER_1_OVER_2, True),
        (VSPLITTER_1_OVER_3, True),
        (VSPLITTER_1_OVER_5, False),
        (VSPLITTER_1_OVER_7, False),
    ],
)
def test_can_be_first(vsplitter, expected):
    assert vsplitter.can_be_first() is expected


# --- BalancerDefinition.weight_cost ---


@pytest.mark.parametrize(
    "bdef,expected",
    [
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2]
            ),
            10,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 3), vsplitter_defs=[VSPLITTER_1_OVER_3]
            ),
            15,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 4),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_2],
            ),
            20,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 6),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3],
            ),
            25,
        ),
    ],
)
def test_weight_cost(bdef, expected):
    assert bdef.weight_cost() == expected


# --- BalancerDefinition.is_valid ---


@pytest.mark.parametrize(
    "bdef,expected",
    [
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2]
            ),
            True,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 3), vsplitter_defs=[VSPLITTER_1_OVER_3]
            ),
            True,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 4),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_2],
            ),
            True,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 3), vsplitter_defs=[VSPLITTER_1_OVER_2]
            ),
            False,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 5), vsplitter_defs=[VSPLITTER_1_OVER_5]
            ),
            False,
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 10),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_5],
            ),
            True,
        ),
    ],
)
def test_balancer_is_valid(bdef, expected):
    assert bdef.is_valid() is expected


# --- BalancerDefinition.__str__ ---


@pytest.mark.parametrize(
    "bdef,expected",
    [
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2]
            ),
            "1/2 = 1/2",
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 3), vsplitter_defs=[VSPLITTER_1_OVER_3]
            ),
            "1/3 = 1/3",
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 4),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_2],
            ),
            "1/4 = (1/2)^2",
        ),
        (
            BalancerDefinition(
                pass_fraction=Fraction(1, 6),
                vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3],
            ),
            "1/6 = 1/2 × 1/3",
        ),
    ],
)
def test_balancer_str(bdef, expected):
    assert str(bdef) == expected


# --- MaxDrain.__add__ ---


def test_max_drain_add():
    a = MaxDrain(demand=100.0, max_drain=1000.0)
    b = MaxDrain(demand=200.0, max_drain=2000.0)
    result = a + b
    assert result.demand == pytest.approx(300.0)
    assert result.max_drain == pytest.approx(3000.0)


def test_max_drain_add_identity():
    zero = MaxDrain(demand=0.0, max_drain=0.0)
    b = MaxDrain(demand=50.0, max_drain=500.0)
    assert (zero + b) == b


# --- NontrivialLine.average_power + is_valid ---

_SC = BatteryDefinition(power=3200.0, duration=40.0, name="SC Wuling Battery")


@pytest.mark.parametrize(
    "bdef,battery,spt,expected_avg,expected_valid",
    [
        # 1/2: 0.5 >= min(1, 2/40)=0.05 → NOT valid
        (
            BalancerDefinition(Fraction(1, 2), [VSPLITTER_1_OVER_2]),
            _SC,
            2.0,
            32000.0,
            False,
        ),
        # 1/32=(1/2)^5: 0.03125 < 0.05 → valid; avg = (1/32)*3200*40/2 = 2000.0
        (
            BalancerDefinition(Fraction(1, 32), [VSPLITTER_1_OVER_2] * 5),
            _SC,
            2.0,
            2000.0,
            True,
        ),
    ],
)
def test_nontrivial_line(bdef, battery, spt, expected_avg, expected_valid):
    line = NontrivialLine(balancer_definition=bdef, battery_definition=battery)
    assert line.average_power(spt) == pytest.approx(expected_avg)
    assert line.is_valid(spt) is expected_valid


# --- generate_reachable_fractions ---


def test_generate_reachable_fractions_includes_half():
    results = generate_reachable_fractions(Fraction(1, 2), 10)
    assert any(r.pass_fraction == Fraction(1, 2) for r in results)


def test_generate_reachable_fractions_respects_max_output():
    results = generate_reachable_fractions(Fraction(1, 3), 10)
    assert all(r.pass_fraction <= Fraction(1, 3) for r in results)


def test_generate_reachable_fractions_all_valid():
    results = generate_reachable_fractions(Fraction(1, 2), 30)
    assert all(r.is_valid() for r in results)


# --- calculate_longest_gap ---


def test_calculate_longest_gap_returns_positive_int():
    bdef = BalancerDefinition(
        pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2]
    )
    gap = calculate_longest_gap(bdef)
    assert isinstance(gap, int)
    assert gap > 0


def test_calculate_longest_gap_deterministic():
    bdef = BalancerDefinition(
        pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2]
    )
    assert calculate_longest_gap(bdef) == calculate_longest_gap(bdef)


# --- Snapshot: CLI output ---


@pytest.mark.parametrize("weight_cost", [50, 80, 90])
def test_main_cli_snapshot(snapshot, weight_cost):
    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "batterylib.py"), "-c", str(weight_cost)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert result.stdout == snapshot
