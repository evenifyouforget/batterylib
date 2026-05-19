import argparse
from collections import Counter
import itertools

from rich.console import Console

from .algorithms import calculate_longest_gap, generate_reachable_fractions, sort_deduplicate
from .models import BatteryDefinition, MaxDrain, NontrivialLine, RatedBalancer, RatedFullSolution

console = Console(soft_wrap=True)
print = console.print


def old_main():
    parser = argparse.ArgumentParser(
        description="Calculate Endfield-style battery balancers"
    )

    parser.add_argument(
        "-p",
        "--battery-power",
        type=float,
        default=3200,
        help="Power produced by the battery in watts",
    )
    parser.add_argument(
        "-d",
        "--battery-duration",
        type=float,
        default=40,
        help="How many seconds a battery lasts for",
    )
    parser.add_argument(
        "-b",
        "--base-power",
        type=float,
        default=3400,
        help="Power provided by always-on generators",
    )
    parser.add_argument(
        "-s",
        "--storage-energy",
        type=float,
        default=1e5,
        help="Max storage of the depot in joules",
    )
    parser.add_argument(
        "-t",
        "--seconds-per-tick",
        type=float,
        default=2,
        help="Belt speed as seconds per item",
    )
    parser.add_argument(
        "-c",
        "--max-weight-cost",
        type=int,
        default=100,
        help="Limit how complex solutions can be in abstract units",
    )
    parser.add_argument(
        "-m",
        "--safety-margin",
        type=float,
        default=0.01,
        help="Reduce fractional generator ratings by this much",
    )

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

    print(
        f"[bold green]# Found {len(bdefs)} distinct balancer solutions. Now calculating real power ratings...[/bold green]"
    )

    rated_balancers = []
    safety_multiplier = 1 - args.safety_margin
    full_power = (
        safety_multiplier
        * args.battery_power
        * args.battery_duration
        / args.seconds_per_tick
    )
    for bdef in bdefs:
        average_power = full_power * bdef.pass_fraction + args.base_power
        longest_gap = calculate_longest_gap(bdef)
        maximum_safe_power = (
            safety_multiplier
            * min(
                args.storage_energy
                / max(
                    longest_gap * args.seconds_per_tick - args.battery_duration, 1e-10
                ),
                args.battery_power
                * args.battery_duration
                / (longest_gap * args.seconds_per_tick),
            )
            + args.base_power
        )
        rated_balancers.append(
            RatedBalancer(
                maximum_safe_power=maximum_safe_power,
                average_power=average_power,
                definition=bdef,
            )
        )
    rated_balancers.sort()

    print("[bold green]# All solutions:[/bold green]")
    for rated_balancer in rated_balancers:
        print(
            f"""[cyan]Safe for {rated_balancer.maximum_safe_power:.1f} W\t(actual average {rated_balancer.average_power:.1f} W):\t{rated_balancer.definition}[/cyan]"""
        )


def main():
    parser = argparse.ArgumentParser(
        description="Calculate Endfield-style battery balancers"
    )

    parser.add_argument(
        "-l",
        "--max-nontrivial-lines",
        type=int,
        default=2,
        help="Max number of nontrivial lines in a solution",
    )
    parser.add_argument(
        "-L",
        "--max-trivial-lines",
        type=int,
        default=3,
        help="Max number of trivial lines per battery type in a solution",
    )
    parser.add_argument(
        "-b",
        "--base-power",
        type=float,
        default=200,
        help="Power provided by always-on generators",
    )
    parser.add_argument(
        "-s",
        "--storage-energy",
        type=float,
        default=1e5,
        help="Max storage of the depot in joules",
    )
    parser.add_argument(
        "-t",
        "--seconds-per-tick",
        type=float,
        default=2,
        help="Belt speed as seconds per item",
    )
    parser.add_argument(
        "-c",
        "--max-weight-cost",
        type=int,
        default=60,
        help="Limit how complex solutions can be in abstract units",
    )
    parser.add_argument(
        "-m",
        "--safety-margin",
        type=float,
        default=0.01,
        help="Reduce fractional generator ratings by this much",
    )
    parser.add_argument(
        "-P",
        "--penalty-for-weight",
        type=float,
        default=1,
        help="1 weight unit of complexity is treated as this many watts of loss",
    )

    args = parser.parse_args()

    BATTERY_TYPES = [
        BatteryDefinition(power=1100, duration=40, name="HC Valley Battery"),
        BatteryDefinition(power=3200, duration=40, name="SC Wuling Battery"),
    ]

    trivial_combinations = []
    for counts in itertools.product(
        *[range(args.max_trivial_lines + 1)] * len(BATTERY_TYPES)
    ):
        battery_to_count = Counter(
            {
                battery: count
                for battery, count in zip(BATTERY_TYPES, counts)
                if count > 0
            }
        )
        base_power = args.base_power + sum(
            battery.power * count for battery, count in battery_to_count.items()
        )
        trivial_combinations.append((base_power, battery_to_count))

    print(
        f"[bold green]# Found {len(trivial_combinations)} distinct trivial line combinations.[/bold green]"
    )

    max_output_fraction = args.seconds_per_tick / max(
        battery.duration for battery in BATTERY_TYPES
    )
    bdefs = generate_reachable_fractions(max_output_fraction, args.max_weight_cost)

    print(
        f"[bold green]# Found {len(bdefs)} distinct balancer definitions.[/bold green]"
    )

    multi_lines = []
    for num_nontrivial_lines in range(1, args.max_nontrivial_lines + 1):
        for bdef_list in itertools.combinations_with_replacement(
            bdefs, num_nontrivial_lines
        ):
            if sum(bdef.weight_cost() for bdef in bdef_list) > args.max_weight_cost:
                continue
            for battery_list in itertools.product(
                *[BATTERY_TYPES] * num_nontrivial_lines
            ):
                nontrivial_lines = [
                    NontrivialLine(balancer_definition=bdef, battery_definition=battery)
                    for bdef, battery in zip(bdef_list, battery_list)
                ]
                max_drains = []
                for line in nontrivial_lines:
                    average_power = line.average_power(args.seconds_per_tick)
                    longest_gap = (
                        calculate_longest_gap(line.balancer_definition)
                        * args.seconds_per_tick
                    )
                    max_drain = average_power * (
                        longest_gap - line.battery_definition.duration
                    )
                    max_drains.append(
                        MaxDrain(demand=average_power, max_drain=max_drain)
                    )
                total_max_drain = sum(max_drains, MaxDrain(demand=0, max_drain=0))
                rating = total_max_drain.demand
                if total_max_drain.max_drain > args.storage_energy:
                    scale_factor = args.storage_energy / total_max_drain.max_drain
                    rating *= scale_factor
                rating *= 1 - args.safety_margin
                multi_lines.append((rating, nontrivial_lines))

    print(
        f"[bold green]# Found {len(multi_lines)} nontrivial line combinations.[/bold green]"
    )

    multi_lines = sort_deduplicate(multi_lines)

    print(
        f"[bold green]# Found {len(multi_lines)} distinct nontrivial line combinations.[/bold green]"
    )

    full_solutions = []
    for rating, nontrivial_lines in multi_lines:
        for base_power, trivial_lines in trivial_combinations:
            full_solutions.append(
                RatedFullSolution(
                    maximum_safe_power=base_power + rating,
                    trivial_lines=trivial_lines,
                    nontrivial_lines=nontrivial_lines,
                )
            )

    print(
        f"[bold green]# Found {len(full_solutions)} distinct full solutions.[/bold green]"
    )

    full_solutions.sort(
        key=lambda solution: (
            solution.maximum_safe_power,
            solution.average_power(args.seconds_per_tick)
            + args.penalty_for_weight * solution.weight_cost(),
        )
    )

    print("[bold green]# All solutions:[/bold green]")
    for full_solution in full_solutions:
        inner_bits = []
        for battery, count in full_solution.trivial_lines.items():
            inner_bits.append(f"{battery.name} × {count}")
        for line in full_solution.nontrivial_lines:
            inner_bits.append(
                f"{line.battery_definition.name} × {line.balancer_definition}"
            )
        bits = [
            "[cyan]",
            f"Safe for {full_solution.maximum_safe_power:.1f} W\t",
            f"(actual average {full_solution.average_power(args.seconds_per_tick) + args.base_power:.1f} W,\ttotal weight cost {full_solution.weight_cost()}):\t",
            ",\t".join(inner_bits),
            "[/cyan]",
        ]
        print("".join(bits))
