import sys
import types
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path


def install_rich_stub():
    rich = types.ModuleType("rich")
    console = types.ModuleType("rich.console")

    class Console:
        def __init__(self, *args, **kwargs):
            pass

        def print(self, *args, **kwargs):
            pass

    console.Console = Console
    sys.modules.setdefault("rich", rich)
    sys.modules.setdefault("rich.console", console)


install_rich_stub()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import batterylib as b  # noqa: E402


class UtilityTests(unittest.TestCase):
    def test_sort_deduplicate_returns_sorted_unique_values(self):
        self.assertEqual(b.sort_deduplicate([3, 1, 2, 3, 1]), [1, 2, 3])

    def test_max_drain_adds_demand_and_drain(self):
        self.assertEqual(
            b.MaxDrain(demand=10, max_drain=25) + b.MaxDrain(demand=5, max_drain=7),
            b.MaxDrain(demand=15, max_drain=32),
        )


class BalancerDefinitionTests(unittest.TestCase):
    def test_weight_cost_sums_virtual_splitters(self):
        definition = b.BalancerDefinition(
            pass_fraction=Fraction(1, 6),
            vsplitter_defs=[b.VSPLITTER_1_OVER_2, b.VSPLITTER_1_OVER_3],
        )

        self.assertEqual(definition.weight_cost(), 25)

    def test_normalize_places_first_required_splitter_before_recycler(self):
        definition = b.BalancerDefinition(
            pass_fraction=Fraction(1, 10),
            vsplitter_defs=[b.VSPLITTER_1_OVER_5, b.VSPLITTER_1_OVER_2],
        )

        definition.normalize_in_place()

        self.assertEqual(definition.vsplitter_defs[0], b.VSPLITTER_1_OVER_2)
        self.assertEqual(definition.vsplitter_defs[1], b.VSPLITTER_1_OVER_5)

    def test_is_valid_rejects_recycler_as_first_splitter(self):
        definition = b.BalancerDefinition(
            pass_fraction=Fraction(1, 5),
            vsplitter_defs=[b.VSPLITTER_1_OVER_5],
        )

        self.assertFalse(definition.is_valid())

    def test_string_compacts_repeated_splitters(self):
        definition = b.BalancerDefinition(
            pass_fraction=Fraction(1, 4),
            vsplitter_defs=[b.VSPLITTER_1_OVER_2, b.VSPLITTER_1_OVER_2],
        )

        self.assertEqual(str(definition), "1/4 = (1/2)^2")


class SolverTests(unittest.TestCase):
    def test_generate_reachable_fractions_respects_output_and_weight_limits(self):
        definitions = b.generate_reachable_fractions(Fraction(1, 3), 25)
        rendered = [str(definition) for definition in definitions]

        self.assertEqual(rendered, ["1/3 = 1/3", "1/4 = (1/2)^2", "1/6 = 1/2 × 1/3"])
        self.assertTrue(all(definition.pass_fraction <= Fraction(1, 3) for definition in definitions))
        self.assertTrue(all(definition.weight_cost() <= 25 for definition in definitions))

    def test_calculate_longest_gap_for_simple_balancers(self):
        one_half = b.BalancerDefinition(
            pass_fraction=Fraction(1, 2),
            vsplitter_defs=[b.VSPLITTER_1_OVER_2],
        )
        one_quarter = b.BalancerDefinition(
            pass_fraction=Fraction(1, 4),
            vsplitter_defs=[b.VSPLITTER_1_OVER_2, b.VSPLITTER_1_OVER_2],
        )

        self.assertEqual(b.calculate_longest_gap(one_half), 3)
        self.assertEqual(b.calculate_longest_gap(one_quarter), 4)


class PowerModelTests(unittest.TestCase):
    def test_nontrivial_line_average_power_uses_fraction_and_tick_duration(self):
        line = b.NontrivialLine(
            balancer_definition=b.BalancerDefinition(
                pass_fraction=Fraction(1, 2),
                vsplitter_defs=[b.VSPLITTER_1_OVER_2],
            ),
            battery_definition=b.BatteryDefinition(power=3200, duration=40, name="SC Wuling"),
        )

        self.assertEqual(line.average_power(seconds_per_tick=2), 32000)

    def test_full_solution_average_power_includes_trivial_lines(self):
        battery = b.BatteryDefinition(power=1100, duration=40, name="HC Valley")
        line = b.NontrivialLine(
            balancer_definition=b.BalancerDefinition(
                pass_fraction=Fraction(1, 2),
                vsplitter_defs=[b.VSPLITTER_1_OVER_2],
            ),
            battery_definition=battery,
        )
        solution = b.RatedFullSolution(
            maximum_safe_power=5000,
            trivial_lines=Counter({battery: 2}),
            nontrivial_lines=[line],
        )

        self.assertEqual(solution.average_power(seconds_per_tick=2), 13200)
        self.assertEqual(solution.weight_cost(), 10)


if __name__ == "__main__":
    unittest.main()
