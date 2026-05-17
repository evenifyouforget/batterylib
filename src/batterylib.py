import argparse
from collections import Counter
from dataclasses import dataclass
import itertools
import functools
from enum import Enum
import heapq
from fractions import Fraction
from rich.console import Console
import typing

console = Console(soft_wrap=True)
print = console.print

class TurnAction(Enum):
    """
    An action that a virtual splitter can take on a turn.
    """
    PASS = 1
    DISCARD = 2
    RECYCLE = 3

@dataclass(order=True)
class VirtualSplitterDefinition:
    """
    Defines the behaviour of a combination of possibly multiple splitters and convergers.
    """
    pass_fraction: Fraction
    cycle: list[TurnAction]
    weight_cost: int

    def __hash__(self) -> int:
        return hash((self.pass_fraction, tuple(self.cycle), self.weight_cost))

    def can_be_first(self) -> bool:
        """
        Whether this virtual splitter achieves its advertised fraction when placed first.
        """
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

T = typing.TypeVar('T')

def sort_deduplicate(items: list[T]) -> list[T]:
    """
    Sort a list and remove duplicates.
    """
    items = sorted(items)
    result = []
    for item in items:
        if not result or item != result[-1]:
            result.append(item)
    return result

@dataclass(order=True)
class BalancerDefinition:
    """
    A sequence of virtual splitter definitions that produces an advertised fraction.
    """
    pass_fraction: Fraction
    vsplitter_defs: list[VirtualSplitterDefinition]

    def weight_cost(self) -> int:
        """
        The total weight cost of this balancer definition, as the sum of the weight costs of its virtual splitters.
        """
        return sum(vsplitter.weight_cost for vsplitter in self.vsplitter_defs)
    
    def __hash__(self) -> int:
        return hash((self.pass_fraction, tuple(self.vsplitter_defs)))

    def normalize_in_place(self) -> None:
        """
        Attempt to reorder the vsplitters optimally, based on simple rules.
        """
        num_1_over_2 = sum(1 for vsplitter in self.vsplitter_defs if vsplitter == VSPLITTER_1_OVER_2)
        num_1_over_3 = sum(1 for vsplitter in self.vsplitter_defs if vsplitter == VSPLITTER_1_OVER_3)
        others = [vsplitter for vsplitter in self.vsplitter_defs if vsplitter not in (VSPLITTER_1_OVER_2, VSPLITTER_1_OVER_3)]
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
        """
        Whether this balancer definition is valid, i.e. whether the advertised fraction is actually achieved by the sequence of virtual splitters.
        """
        current_fraction = 1
        for vsplitter in self.vsplitter_defs:
            if not vsplitter.can_be_first() and current_fraction > Fraction(1, 2):
                return False
            current_fraction *= vsplitter.pass_fraction
        return current_fraction == self.pass_fraction

    def __str__(self) -> str:
        bits = []
        def submit_vsplitter(vsplitter: VirtualSplitterDefinition | None, last: list[VirtualSplitterDefinition | None] = [None], last_count: list[int] = [0]) -> None:
            if vsplitter != last[0]:
                # Flush
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
    """
    A balancer definition annotated with actual configuration details like battery power and duration.
    """
    maximum_safe_power: float
    average_power: float
    definition: BalancerDefinition

@dataclass(order=True, frozen=True)
class BatteryDefinition:
    """
    A battery definition with a given power and duration.
    """
    power: float
    duration: float
    name: str

@dataclass(order=True)
class MaxDrain:
    """
    Maximum drain analysis result for a balancer definition with a given power demand.
    """
    demand: float
    max_drain: float
    def __add__(self, other: 'MaxDrain') -> 'MaxDrain':
        return MaxDrain(demand=self.demand + other.demand, max_drain=self.max_drain + other.max_drain)

@dataclass(order=True)
class NontrivialLine:
    """
    A nontrivial line, annotated with balancer definition and battery definition.
    """
    balancer_definition: BalancerDefinition
    battery_definition: BatteryDefinition
    def average_power(self, seconds_per_tick: float) -> float:
        return self.balancer_definition.pass_fraction * self.battery_definition.power * self.battery_definition.duration / seconds_per_tick
    def is_valid(self, seconds_per_tick: float) -> bool:
        """
        Returns true if this line can achieve its advertised average power, and is not a degenerate edge case.
        """
        return 0 < self.balancer_definition.pass_fraction < min(1, seconds_per_tick / self.battery_definition.duration)

@dataclass(order=True)
class RatedFullSolution:
    """
    A full solution, which may contain multiple trivial and nontrivial lines.
    """
    maximum_safe_power: float
    trivial_lines: Counter[BatteryDefinition, int]
    nontrivial_lines: list[NontrivialLine]
    def average_power(self, seconds_per_tick: float) -> float:
        return sum(line.average_power(seconds_per_tick) for line in self.nontrivial_lines) + sum(battery.power * count for battery, count in self.trivial_lines.items())
    def weight_cost(self) -> int:
        return sum(line.balancer_definition.weight_cost() for line in self.nontrivial_lines)

def generate_reachable_fractions(max_output: Fraction, max_weight_cost: int) -> list[BalancerDefinition]:
    """
    Use Dijkstra's algorithm to enumerate balancer definitions that fit in a maximum weight cost.
    """
    results = []
    nextq = [(0, Fraction(1, 1))]
    bw = {}
    seen = set()
    while nextq:
        cost_so_far, fraction_so_far = heapq.heappop(nextq)
        if cost_so_far > max_weight_cost:
            break
        if fraction_so_far in seen:
            continue
        seen.add(fraction_so_far)
        # Submit solution
        if fraction_so_far <= max_output:
            vdefs = []
            current_fraction = fraction_so_far
            while current_fraction in bw:
                vdef = bw[current_fraction]
                vdefs.append(vdef)
                current_fraction /= vdef.pass_fraction
            results.append(BalancerDefinition(pass_fraction=fraction_so_far, vsplitter_defs=list(vdefs)))
        # Generate outgoing edges
        for vsplitter_def in ALL_VSPLITTER_DEFS:
            new_fraction = fraction_so_far * vsplitter_def.pass_fraction
            new_cost = cost_so_far + vsplitter_def.weight_cost
            heapq.heappush(nextq, (new_cost, new_fraction))
            if new_fraction not in bw:
                bw[new_fraction] = vsplitter_def
    # Normalize and validate results
    for result in results:
        result.normalize_in_place()
    results = [result for result in results if result.is_valid()]
    return results

@functools.cache
def calculate_longest_gap(bdef: BalancerDefinition) -> int:
    """
    Calculate the longest gap (number of turns between final output being reached).
    """
    vdefs = [VSPLITTER_IDENTITY] + bdef.vsplitter_defs + [VSPLITTER_IDENTITY]
    turn_index = [0] * len(vdefs)
    buffer = [0] * len(vdefs)
    longest_gap = 0
    num_cycles = 0
    current_drought = 0
    # Start counting on cycle 2, stop counting on cycle 5
    while True:
        # count a cycle when all turn index are 0 (same internal state as start)
        if not any(turn_index):
            num_cycles += 1
            if num_cycles == 5:
                break
        if num_cycles >= 2:
            current_drought += 1
        if buffer[-1]:
            # Output is reached
            longest_gap = max(longest_gap, current_drought)
            current_drought = 0
            buffer[-1] = 0
        # Simulate a tick
        for i in range(len(vdefs) - 1)[::-1]:
            if not buffer[i]:
                continue
            action = vdefs[i].cycle[turn_index[i]]
            if action == TurnAction.PASS:
                buffer[i] -= 1
                buffer[i + 1] += 1
            elif action == TurnAction.DISCARD:
                buffer[i] -= 1
            turn_index[i] = (turn_index[i] + 1) % len(vdefs[i].cycle)
        buffer[0] = 1
    return longest_gap

def old_main():
    parser = argparse.ArgumentParser(
        description="Calculate Endfield-style battery balancers"
    )

    parser.add_argument("-p","--battery-power", type=float, default=3200, help="Power produced by the battery in watts")
    parser.add_argument("-d","--battery-duration", type=float, default=40, help="How many seconds a battery lasts for")
    parser.add_argument("-b","--base-power", type=float, default=3400, help="Power provided by always-on generators")
    parser.add_argument("-s","--storage-energy", type=float, default=1e5, help="Max storage of the depot in joules")
    parser.add_argument("-t","--seconds-per-tick", type=float, default=2, help="Belt speed as seconds per item")
    parser.add_argument("-c", "--max-weight-cost", type=int, default=100, help="Limit how complex solutions can be in abstract units")
    parser.add_argument("-m","--safety-margin", type=float, default=0.01, help="Reduce fractional generator ratings by this much")

    args = parser.parse_args()

    print(f"""[bold green]# Starting calculation with parameters:[/bold green]
- Battery power: {args.battery_power} W
- Battery duration: {args.battery_duration} s
- Base power: {args.base_power} W
- Storage energy: {args.storage_energy} J
- Seconds per tick: {args.seconds_per_tick} s
- Max weight cost: {args.max_weight_cost}
- Safety margin: {args.safety_margin * 100} %""")

    max_output_fraction = args.seconds_per_tick / args.battery_duration
    bdefs = generate_reachable_fractions(max_output_fraction, args.max_weight_cost)

    print(f"[bold green]# Found {len(bdefs)} distinct balancer solutions. Now calculating real power ratings...[/bold green]")

    rated_balancers = []
    safety_multiplier = 1 - args.safety_margin
    full_power = safety_multiplier * args.battery_power * args.battery_duration / args.seconds_per_tick
    for bdef in bdefs:
        average_power = full_power * bdef.pass_fraction + args.base_power
        longest_gap = calculate_longest_gap(bdef)
        maximum_safe_power = safety_multiplier * min(
            args.storage_energy / max(longest_gap * args.seconds_per_tick - args.battery_duration, 1e-10),
            args.battery_power * args.battery_duration / (longest_gap * args.seconds_per_tick)
        ) + args.base_power
        rated_balancers.append(RatedBalancer(maximum_safe_power=maximum_safe_power, average_power=average_power, definition=bdef))
    rated_balancers.sort()

    print(f"[bold green]# All solutions:[/bold green]")
    for rated_balancer in rated_balancers:
        print(f"""[cyan]Safe for {rated_balancer.maximum_safe_power:.1f} W\t(actual average {rated_balancer.average_power:.1f} W):\t{rated_balancer.definition}[/cyan]""")

def main():
    parser = argparse.ArgumentParser(
        description="Calculate Endfield-style battery balancers"
    )

    parser.add_argument("-l","--max-nontrivial-lines", type=int, default=2, help="Max number of nontrivial lines in a solution")
    parser.add_argument("-L","--max-trivial-lines", type=int, default=3, help="Max number of trivial lines per battery type in a solution")
    parser.add_argument("-b","--base-power", type=float, default=200, help="Power provided by always-on generators")
    parser.add_argument("-s","--storage-energy", type=float, default=1e5, help="Max storage of the depot in joules")
    parser.add_argument("-t","--seconds-per-tick", type=float, default=2, help="Belt speed as seconds per item")
    parser.add_argument("-c","--max-weight-cost", type=int, default=60, help="Limit how complex solutions can be in abstract units")
    parser.add_argument("-m","--safety-margin", type=float, default=0.01, help="Reduce fractional generator ratings by this much")
    parser.add_argument("-P","--penalty-for-weight", type=float, default=1, help="1 weight unit of complexity is treated as this many watts of loss")

    args = parser.parse_args()

    BATTERY_TYPES = [
        BatteryDefinition(power=1100, duration=40, name="HC Valley Battery"),
        BatteryDefinition(power=3200, duration=40, name="SC Wuling Battery"),
    ]

    trivial_combinations = []
    for counts in itertools.product(*[range(args.max_trivial_lines + 1)] * len(BATTERY_TYPES)):
        battery_to_count = Counter({battery: count for battery, count in zip(BATTERY_TYPES, counts) if count > 0})
        base_power = args.base_power + sum(battery.power * count for battery, count in battery_to_count.items())
        trivial_combinations.append((base_power, battery_to_count))

    print(f"[bold green]# Found {len(trivial_combinations)} distinct trivial line combinations.[/bold green]")

    max_output_fraction = args.seconds_per_tick / max(battery.duration for battery in BATTERY_TYPES)
    bdefs = generate_reachable_fractions(max_output_fraction, args.max_weight_cost)

    print(f"[bold green]# Found {len(bdefs)} distinct balancer definitions.[/bold green]")

    multi_lines = []
    for num_nontrivial_lines in range(1, args.max_nontrivial_lines + 1):
        for bdef_list in itertools.combinations_with_replacement(bdefs, num_nontrivial_lines):
            if sum(bdef.weight_cost() for bdef in bdef_list) > args.max_weight_cost:
                continue
            for battery_list in itertools.product(*[BATTERY_TYPES] * num_nontrivial_lines):
                nontrivial_lines = [NontrivialLine(balancer_definition=bdef, battery_definition=battery) for bdef, battery in zip(bdef_list, battery_list)]
                # Max drain analysis
                max_drains = []
                for line in nontrivial_lines:
                    average_power = line.average_power(args.seconds_per_tick)
                    longest_gap = calculate_longest_gap(line.balancer_definition) * args.seconds_per_tick
                    max_drain = average_power * (longest_gap - line.battery_definition.duration)
                    max_drains.append(MaxDrain(demand=average_power, max_drain=max_drain))
                total_max_drain = sum(max_drains, MaxDrain(demand=0, max_drain=0))
                rating = total_max_drain.demand
                if total_max_drain.max_drain > args.storage_energy:
                    scale_factor = args.storage_energy / total_max_drain.max_drain
                    rating *= scale_factor
                rating *= 1 - args.safety_margin
                multi_lines.append((rating, nontrivial_lines))
    
    print(f"[bold green]# Found {len(multi_lines)} nontrivial line combinations.[/bold green]")

    multi_lines = sort_deduplicate(multi_lines)

    print(f"[bold green]# Found {len(multi_lines)} distinct nontrivial line combinations.[/bold green]")

    full_solutions = []
    for rating, nontrivial_lines in multi_lines:
        for base_power, trivial_lines in trivial_combinations:
            full_solutions.append(RatedFullSolution(maximum_safe_power=base_power + rating, trivial_lines=trivial_lines, nontrivial_lines=nontrivial_lines))
    
    print(f"[bold green]# Found {len(full_solutions)} distinct full solutions.[/bold green]")

    full_solutions.sort(key=lambda solution: (solution.maximum_safe_power, solution.average_power(args.seconds_per_tick) + args.penalty_for_weight * solution.weight_cost()))

    print(f"[bold green]# All solutions:[/bold green]")
    for full_solution in full_solutions:
        inner_bits = []
        for battery, count in full_solution.trivial_lines.items():
            inner_bits.append(f"{battery.name} × {count}")
        for line in full_solution.nontrivial_lines:
            inner_bits.append(f"{line.battery_definition.name} × {line.balancer_definition}")
        bits = [
            "[cyan]",
            f"Safe for {full_solution.maximum_safe_power:.1f} W\t",
            f"(actual average {full_solution.average_power(args.seconds_per_tick) + args.base_power:.1f} W,\ttotal weight cost {full_solution.weight_cost()}):\t",
            ",\t".join(inner_bits),
            "[/cyan]",
        ]
        print("".join(bits))

if __name__ == "__main__":
    main()