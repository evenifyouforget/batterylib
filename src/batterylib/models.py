from collections import Counter
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import typing


class TurnAction(Enum):
    PASS = 1
    DISCARD = 2
    RECYCLE = 3


@dataclass(order=True)
class VirtualSplitterDefinition:
    pass_fraction: Fraction
    cycle: list[TurnAction]
    weight_cost: int

    def __hash__(self) -> int:
        return hash((self.pass_fraction, tuple(self.cycle), self.weight_cost))

    def can_be_first(self) -> bool:
        return TurnAction.RECYCLE not in self.cycle


VSPLITTER_IDENTITY = VirtualSplitterDefinition(
    pass_fraction=Fraction(1, 1),
    cycle=[TurnAction.PASS],
    weight_cost=999999,
)
VSPLITTER_1_OVER_2 = VirtualSplitterDefinition(
    pass_fraction=Fraction(1, 2),
    cycle=[TurnAction.PASS] + [TurnAction.DISCARD],
    weight_cost=10,
)
VSPLITTER_1_OVER_3 = VirtualSplitterDefinition(
    pass_fraction=Fraction(1, 3),
    cycle=[TurnAction.PASS] + [TurnAction.DISCARD] * 2,
    weight_cost=15,
)
VSPLITTER_2_OVER_3 = VirtualSplitterDefinition(
    pass_fraction=Fraction(2, 3),
    cycle=[TurnAction.PASS] * 2 + [TurnAction.DISCARD],
    weight_cost=30,
)
VSPLITTER_3_OVER_4 = VirtualSplitterDefinition(
    pass_fraction=Fraction(3, 4),
    cycle=[TurnAction.PASS] * 3 + [TurnAction.DISCARD],
    weight_cost=35,
)
VSPLITTER_5_OVER_6 = VirtualSplitterDefinition(
    pass_fraction=Fraction(5, 6),
    cycle=[TurnAction.PASS] * 5 + [TurnAction.DISCARD],
    weight_cost=40,
)
VSPLITTER_7_OVER_8 = VirtualSplitterDefinition(
    pass_fraction=Fraction(7, 8),
    cycle=[TurnAction.PASS] * 7 + [TurnAction.DISCARD],
    weight_cost=50,
)
VSPLITTER_11_OVER_12 = VirtualSplitterDefinition(
    pass_fraction=Fraction(11, 12),
    cycle=[TurnAction.PASS] * 11 + [TurnAction.DISCARD],
    weight_cost=60,
)
VSPLITTER_1_OVER_5 = VirtualSplitterDefinition(
    pass_fraction=Fraction(1, 5),
    cycle=[TurnAction.PASS] + [TurnAction.RECYCLE] + [TurnAction.DISCARD] * 4,
    weight_cost=50,
)
VSPLITTER_1_OVER_7 = VirtualSplitterDefinition(
    pass_fraction=Fraction(1, 7),
    cycle=[TurnAction.PASS] + [TurnAction.RECYCLE] + [TurnAction.DISCARD] * 6,
    weight_cost=60,
)

ALL_VSPLITTER_DEFS = [
    VSPLITTER_1_OVER_2,
    VSPLITTER_1_OVER_3,
    VSPLITTER_2_OVER_3,
    VSPLITTER_3_OVER_4,
    VSPLITTER_5_OVER_6,
    VSPLITTER_7_OVER_8,
    VSPLITTER_11_OVER_12,
    VSPLITTER_1_OVER_5,
    VSPLITTER_1_OVER_7,
]

T = typing.TypeVar("T")


@dataclass(order=True)
class BalancerDefinition:
    pass_fraction: Fraction
    vsplitter_defs: list[VirtualSplitterDefinition]

    def weight_cost(self) -> int:
        return sum(vsplitter.weight_cost for vsplitter in self.vsplitter_defs)

    def __hash__(self) -> int:
        return hash((self.pass_fraction, tuple(self.vsplitter_defs)))

    def normalize_in_place(self) -> None:
        num_1_over_2 = sum(
            1 for vsplitter in self.vsplitter_defs if vsplitter == VSPLITTER_1_OVER_2
        )
        num_1_over_3 = sum(
            1 for vsplitter in self.vsplitter_defs if vsplitter == VSPLITTER_1_OVER_3
        )
        others = [
            vsplitter
            for vsplitter in self.vsplitter_defs
            if vsplitter not in (VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3)
        ]
        result = []
        if any(not vsplitter.can_be_first() for vsplitter in others):
            if num_1_over_2 > 0:
                result.append(VSPLITTER_1_OVER_2)
                num_1_over_2 -= 1
            elif num_1_over_3 > 0:
                result.append(VSPLITTER_1_OVER_3)
                num_1_over_3 -= 1
            others.sort(key=lambda vsplitter: vsplitter.can_be_first())
        result.extend(others)
        result.extend([VSPLITTER_1_OVER_2] * num_1_over_2)
        result.extend([VSPLITTER_1_OVER_3] * num_1_over_3)
        self.vsplitter_defs = result

    def is_valid(self) -> bool:
        current_fraction = 1
        for vsplitter in self.vsplitter_defs:
            if not vsplitter.can_be_first() and current_fraction > Fraction(1, 2):
                return False
            current_fraction *= vsplitter.pass_fraction
        return current_fraction == self.pass_fraction

    def __str__(self) -> str:
        bits = []

        def submit_vsplitter(
            vsplitter: VirtualSplitterDefinition | None,
            last: list[VirtualSplitterDefinition | None] = [None],
            last_count: list[int] = [0],
        ) -> None:
            if vsplitter != last[0]:
                if last_count[0] > 1:
                    bits.append(f"({last[0].pass_fraction})^{last_count[0]}")
                elif last_count[0] == 1:
                    bits.append(f"{last[0].pass_fraction}")
                last[0] = None
                last_count[0] = 0
            if vsplitter is not None:
                last[0] = vsplitter
                last_count[0] += 1

        for vsplitter in self.vsplitter_defs:
            submit_vsplitter(vsplitter)
        submit_vsplitter(None)
        return f"{self.pass_fraction} = " + " × ".join(bits)


@dataclass(order=True)
class RatedBalancer:
    maximum_safe_power: float
    average_power: float
    definition: BalancerDefinition


@dataclass(order=True, frozen=True)
class BatteryDefinition:
    power: float
    duration: float
    name: str


@dataclass(order=True)
class MaxDrain:
    demand: float
    max_drain: float

    def __add__(self, other: "MaxDrain") -> "MaxDrain":
        return MaxDrain(
            demand=self.demand + other.demand,
            max_drain=self.max_drain + other.max_drain,
        )


@dataclass(order=True)
class NontrivialLine:
    balancer_definition: BalancerDefinition
    battery_definition: BatteryDefinition

    def average_power(self, seconds_per_tick: float) -> float:
        return (
            self.balancer_definition.pass_fraction
            * self.battery_definition.power
            * self.battery_definition.duration
            / seconds_per_tick
        )

    def is_valid(self, seconds_per_tick: float) -> bool:
        return (
            0
            < self.balancer_definition.pass_fraction
            < min(1, seconds_per_tick / self.battery_definition.duration)
        )


@dataclass(order=True)
class RatedFullSolution:
    maximum_safe_power: float
    trivial_lines: Counter[BatteryDefinition, int]
    nontrivial_lines: list[NontrivialLine]

    def average_power(self, seconds_per_tick: float) -> float:
        return sum(
            line.average_power(seconds_per_tick) for line in self.nontrivial_lines
        ) + sum(battery.power * count for battery, count in self.trivial_lines.items())

    def weight_cost(self) -> int:
        return sum(
            line.balancer_definition.weight_cost() for line in self.nontrivial_lines
        )
