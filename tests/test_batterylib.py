import pathlib
import subprocess
import sys
from collections import Counter
from fractions import Fraction

import pytest

from batterylib import (
    VSPLITTER_1_OVER_2,
    VSPLITTER_1_OVER_3,
    VSPLITTER_1_OVER_5,
    BalancerDefinition,
    BatteryDefinition,
    MaxDrain,
    NontrivialLine,
    RatedFullSolution,
    calculate_longest_gap,
    generate_reachable_fractions,
    sort_deduplicate,
)

ROOT = pathlib.Path(__file__).parent.parent


# --- sort_deduplicate ---

def test_sort_deduplicate_basic():
    assert sort_deduplicate([3, 1, 2, 1]) == [1, 2, 3]

def test_sort_deduplicate_empty():
    assert sort_deduplicate([]) == []

def test_sort_deduplicate_all_same():
    assert sort_deduplicate([5, 5, 5]) == [5]

def test_sort_deduplicate_no_dupes():
    assert sort_deduplicate([1, 2, 3]) == [1, 2, 3]


# --- VirtualSplitterDefinition.can_be_first ---

def test_can_be_first_without_recycle():
    assert VSPLITTER_1_OVER_2.can_be_first() is True

def test_can_be_first_with_recycle():
    assert VSPLITTER_1_OVER_5.can_be_first() is False


# --- BalancerDefinition.weight_cost ---

def test_weight_cost_single():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    assert bdef.weight_cost() == 10

def test_weight_cost_two_same():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 4), vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_2])
    assert bdef.weight_cost() == 20

def test_weight_cost_mixed():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 6), vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3])
    assert bdef.weight_cost() == 25


# --- BalancerDefinition.is_valid ---

def test_is_valid_single_half():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    assert bdef.is_valid() is True

def test_is_valid_wrong_fraction():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 3), vsplitter_defs=[VSPLITTER_1_OVER_2])
    assert bdef.is_valid() is False

def test_is_valid_recycle_first():
    # 1/5 splitter has RECYCLE, cannot be first
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 5), vsplitter_defs=[VSPLITTER_1_OVER_5])
    assert bdef.is_valid() is False

def test_is_valid_recycle_after_half():
    # 1/2 reduces fraction to 1/2, then 1/5 is valid (current_fraction <= 1/2)
    bdef = BalancerDefinition(
        pass_fraction=Fraction(1, 10),
        vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_5],
    )
    assert bdef.is_valid() is True


# --- BalancerDefinition.__str__ ---

def test_str_single():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    assert str(bdef) == "1/2 = 1/2"

def test_str_repeated():
    bdef = BalancerDefinition(
        pass_fraction=Fraction(1, 4),
        vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_2],
    )
    assert str(bdef) == "1/4 = (1/2)^2"

def test_str_mixed():
    bdef = BalancerDefinition(
        pass_fraction=Fraction(1, 6),
        vsplitter_defs=[VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3],
    )
    assert str(bdef) == "1/6 = 1/2 × 1/3"


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


# --- NontrivialLine.average_power ---

def test_nontrivial_average_power():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    battery = BatteryDefinition(power=3200.0, duration=40.0, name="SC Wuling Battery")
    line = NontrivialLine(balancer_definition=bdef, battery_definition=battery)
    # 1/2 * 3200 * 40 / 2 = 32000
    assert line.average_power(2.0) == pytest.approx(32000.0)


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
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    gap = calculate_longest_gap(bdef)
    assert isinstance(gap, int)
    assert gap > 0

def test_calculate_longest_gap_deterministic():
    bdef = BalancerDefinition(pass_fraction=Fraction(1, 2), vsplitter_defs=[VSPLITTER_1_OVER_2])
    assert calculate_longest_gap(bdef) == calculate_longest_gap(bdef)


# --- Snapshot: CLI output ---

def test_main_cli_snapshot(snapshot):
    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "batterylib.py"), "-c", "50"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert result.stdout == snapshot
