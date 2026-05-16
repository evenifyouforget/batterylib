# batterylib

Endfield-style battery balancer solvers.

## Developer Guide

Install requirements:

```sh
uv venv
TODO
```

Run the program:

```sh
python3 src/batterylib.py
```

Run tests:

```sh
TODO
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
- Battery income comes from elsewhere and is stashed in the depot (battery income decoupled from usage)

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

## Math behind the solvers

### Part 1: Longest Drought Analysis

### Part 2: Maximum Drain Analysis

**This is not yet implemented.**