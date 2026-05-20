import functools
import heapq
import typing
from fractions import Fraction

from .models import (
    ALL_VSPLITTER_DEFS,
    VSPLITTER_IDENTITY,
    BalancerDefinition,
    TurnAction,
)

T = typing.TypeVar("T")


def sort_deduplicate(items: list[T]) -> list[T]:
    items = sorted(items)
    result = []
    for item in items:
        if not result or item != result[-1]:
            result.append(item)
    return result


def generate_reachable_fractions(
    max_output: Fraction, max_weight_cost: int
) -> list[BalancerDefinition]:
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
        if fraction_so_far <= max_output:
            vdefs = []
            current_fraction = fraction_so_far
            while current_fraction in bw:
                vdef = bw[current_fraction]
                vdefs.append(vdef)
                current_fraction /= vdef.pass_fraction
            results.append(
                BalancerDefinition(
                    pass_fraction=fraction_so_far, vsplitter_defs=list(vdefs)
                )
            )
        for vsplitter_def in ALL_VSPLITTER_DEFS:
            new_fraction = fraction_so_far * vsplitter_def.pass_fraction
            new_cost = cost_so_far + vsplitter_def.weight_cost
            heapq.heappush(nextq, (new_cost, new_fraction))
            if new_fraction not in bw:
                bw[new_fraction] = vsplitter_def
    for result in results:
        result.normalize_in_place()
    results = [result for result in results if result.is_valid()]
    return results


@functools.cache
def calculate_longest_gap(bdef: BalancerDefinition) -> int:
    vdefs = [VSPLITTER_IDENTITY] + bdef.vsplitter_defs + [VSPLITTER_IDENTITY]
    turn_index = [0] * len(vdefs)
    buffer = [0] * len(vdefs)
    longest_gap = 0
    num_cycles = 0
    current_drought = 0
    while True:
        if not any(turn_index):
            num_cycles += 1
            if num_cycles == 5:
                break
        if num_cycles >= 2:
            current_drought += 1
        if buffer[-1]:
            longest_gap = max(longest_gap, current_drought)
            current_drought = 0
            buffer[-1] = 0
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
