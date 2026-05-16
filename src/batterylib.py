import argparse
from dataclasses import dataclass
from enum import Enum
import heapq
from fractions import Fraction
from rich import print

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

@dataclass(order=True)
class BalancerDefinition:
    """
    A sequence of virtual splitter definitions that produces an advertised fraction.
    """
    pass_fraction: Fraction
    vsplitter_defs: list[VirtualSplitterDefinition]

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

def calculate_longest_drought(bdef: BalancerDefinition) -> int:
    """
    Calculate the longest drought (number of turns between final output being reached).
    """
    vdefs = [VSPLITTER_IDENTITY] + bdef.vsplitter_defs + [VSPLITTER_IDENTITY]
    turn_index = [0] * len(vdefs)
    buffer = [0] * len(vdefs)
    longest_drought = 0
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
            longest_drought = max(longest_drought, current_drought)
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
    return longest_drought

def main():
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
        longest_drought = calculate_longest_drought(bdef)
        maximum_safe_power = safety_multiplier * min(
            args.storage_energy / max(longest_drought * args.seconds_per_tick - args.battery_duration, 1e-10),
            args.battery_power * args.battery_duration / (longest_drought * args.seconds_per_tick)
        ) + args.base_power
        rated_balancers.append(RatedBalancer(maximum_safe_power=maximum_safe_power, average_power=average_power, definition=bdef))
    rated_balancers.sort()

    print(f"[bold green]# All solutions:[/bold green]")
    for rated_balancer in rated_balancers:
        print(f"""[cyan]Safe for {rated_balancer.maximum_safe_power:.1f} W\t(actual average {rated_balancer.average_power:.1f} W):\t{rated_balancer.definition}[/cyan]""")

if __name__ == "__main__":
    main()