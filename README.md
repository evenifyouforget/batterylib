# batterylib

Endfield-style battery balancer solvers.

## Developer Guide

Install requirements:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

Run the program:

```sh
uv run batterylib
```

Run the legacy solver:

```sh
uv run batterylib-old
```

Run tests:

```sh
uv run pytest
```

Run linters:

```sh
prek run --all-files
```

## Architecture: Specializing for Endfield

**Currently batterylib is under-specialized. This will be changed in a future update to match what we say here.**

There are three main reasons to specialize:

- If we try to be extremely general, usage becomes clunky as users must specify common values again ex. that SC Wuling Battery = 3200W for 40s
- The most powerful solvers must make many assumptions about the game.
- Actually, we made several important assumptions already, such as splitters taking turns rather than being randomized, or that we need to consume batteries to generate power in the first place.

Endfield assumptions include:

- A baseline 200W is provided, without spending any batteries.
- Belts run at 0.5 items/s. (in other words, 1 interval = 2s).
- Belts run slightly slow offline
- The safety factor is usually increased further for user comfort (ex. assuming belts run at 99% speed rather than 99.7%)
- By convention, the depot is used as a source for batteries (1 full belt), which then optionally passes through a balancer network, then to a thermal bank as a sink
- If using a balancer, the source is not shared with any other line (each line has an independent 1 full belt of source pressure)
- Thermal bank consumes a battery, then generates the specified power for the specified duration
- Thermal bank will not consume more batteries if it is already busy producing power
- Thermal bank has a buffer capacity of 50, so it can take more batteries even if currently busy
- By convention, balancers are not used if it would provide batteries faster than the thermal bank can consume them, or at exactly the rate of consumption (ex. 1/20 balancer for 40s power generation is redundant)
- A line with no balancer will always supply its thermal bank, and limit its battery consumption by backpressure (ex. for 40s power generation, equivalent to 1/20 balancer)
- Since a line with no balancer always supplies the power without any gaps, no safety factor is applied here (ex. 3200W x 40s battery will contribute exactly 3200W instead of 3200W x 0.99)
- A certain palette of battery types are available to choose from (see section below)
- A line source always provides the same type of item
- In the case of multiple lines, each source can have a different type of item
- The factory has energy reserves with a capacity of 100kJ
- If more power is currently supplied than demand, energy reserves charge by the difference
- If energy reserves are already at the maximum, excess power is wasted safely
- If less power is currently supplied than demand, energy reserves drain by the difference
- If energy reserves reach 0, power outage occurs (failure scenario), energy does not drain into negatives
- Power outage does not stop these battery lines from functioning; power can be restored automatically
- Splitters can have 2 or 3 outputs, and take turns between their outputs
- Convergers are like splitters but just the inverse
- Splitters and convergers run at belt speed (but without the offline speed reduction)
- "Discarding" batteries means returning them to the depot without using them; there is no spend overall
- "Recycling" batteries means feeding a splitter output backwards to a converger, so that battery gets another attempt to pass through the remainder of the balancer
- Battery income comes from elsewhere and is stashed in the depot (battery income decoupled from usage)
- The problem domain is around 3000W to 7000W of demand
- Power demand is stable and a known constant, but may vary between users depending on their setup
- The rating of a configuration is the maximum power demand it can safely support without causing a power outage
- The goal of optimization is generally to achieve a safe power supply (rating > actual demand) while spending less batteries than would be the case with only fully-supplied lines

### Offline belt speed

Source: [Your Offline Factory Is Broken (Here's Why)](https://www.youtube.com/watch?v=LxjNrCya1aI)

68 items are lost over (according to them) 12 hours. This would mean belts are 0.3% slower than their advertised speed.

### Available batteries (thermal bank recipes)

- Originium Ore: 50W for 8s
- LC Valley Battery: 220W for 40s
- SC Valley Battery: 420W for 40s
- HC Valley Battery: 1100W for 40s
- LC Wuling Battery: 1600W for 40s
- SC Wuling Battery: 3200W for 40s

Default configuration should use only the strongest battery (SC Wuling Battery). Users can opt-in to allowing other battery types.

It is notable that the strongest battery is capable of over-charging the reserves: 128kJ is more than the reserves of 100kJ. Excess energy would be wasted. This is the main reason why average power analysis alone isn't enough to determine ratings.

## Math behind the solvers

### Part 1: Longest Drought Analysis

Using only 1/2 splitters and 1/3 splitters, the cycle is extremely regular: on for X time, off for Y time, repeat. With a single line, if we charge reserves to max in the on time, and don't drain reserves fully in the off time, we're safe.

However, in all more complex cases such as the 3/4 virtual splitter (1/2 -> 1/2 but you only discard 1 in 4 rather than 3 in 4), the cycle will not be even. This motivates "longest drought" as a means of analysis: the worst case is determined by the longest off time in the cycle.

- Longest drought: Maximum contiguous off period = Y
- Longest gap: Maximum time between a battery reaching the thermal bank = X + Y

It is easy to calculate the longest gap first, which does not depend on the specific battery being used. Knowing the specific battery, the longest drought can then be calculated.

Longest gap can be determined in complex cases by just simulating the balancer. This is the most accurate method.

### Part 2: Maximum Drain Analysis

Lines with no balancers are referred to interchangeably as always-on lines or fully-supplied lines. They are a special case that can be handled separately. Here we call them trivial lines.

In the case of multiple nontrivial lines, the situation seems complicated - the rating may depend on the phase difference between the lines, the lines may have different cycle lengths, and the charge-discharge graph may appear as a complicated dance.

To make this problem tractable, we need to make lines composable in some simple linear way. We do this with maximum drain.

Consider this simple example:

> Line A: 1100 W for 40 seconds, then nothing for 360 seconds (400 seconds cycle)

Obviously the average power is 110W. If we fix the power demand at 110 W (assuming no 200 W base): The maximum drain is 360s × 110W = 39600J. Our energy reserves need to be at least this big; if we have, say, only 30000J of reserves, we will have a power outage.

We might try formatting this as

> f([(power, on time, off time)]) = (demand, maximum drain)

so

> f([(1100W, 40s, 360s)]) = (110W, 39600J)

Now we have a linear composition possible: f(A + B) = f(A) + f(B). This works perfectly well on complex cases.

> f([(3200W, 40s, 24s), (1100W, 40s, 216s)]) = (2000W, 48000J) + (171.875W, 37125J) = (2171.875W, 85125J)

You can imagine, of the 2171.875W total power demand, 2000W is supplied by section A, and 171.875W is supplied by section B. Section A needs reserve capacity of at least 48000J. Section B needs reserve capacity of at least 37125J. Section A and B can charge and discharge on independent cycles. We are virtually splitting our main reserves and power generation.

Suppose we did this initial calculation, and the maximum drain of the combined system is more than the main reserves. Fortunately, all of this was linear, so we can take our initial guess and immediately jump to the correct solution. Supposing the main reserves are actually 50000J, we can calculate: 2171.875W × 50000J / 85125J = 1275.69750367W.

So the final result looks something like:

> Rating = Base 200W + Trivial supply + Safety factor × Nontrivial supply
>
> Nontrivial supply = min(Average power, Maximum drain corrected safe demand)
