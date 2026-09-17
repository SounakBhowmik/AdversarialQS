"""Command-line entry points; no notebook or repository-relative imports required."""

import argparse
import logging
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .config import AttackSpec, ExperimentConfig, load_config
from .experiments.output import write_run
from .experiments.sweeps import attack_scenarios, defense_scenarios, sensitivity_scenarios


def main() -> None:
    """Run a baseline, selected attack grid, defense grid or fixed-seed reproduction."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["simulate", "attack-sweep", "defense-sweep", "sensitivity-sweep", "reproduce"],
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--suite",
        choices=["phase", "target", "timing", "iq", "frequency", "composite", "all"],
        default="phase",
    )
    args = parser.parse_args()
    config = load_config(args.config) if args.config else ExperimentConfig()
    baseline = ("baseline", replace(config, attack=AttackSpec(kind="none")))
    if args.command == "simulate":
        scenarios = [("simulation", config)]
    elif args.command == "attack-sweep":
        scenarios = [baseline] + attack_scenarios(config, args.suite)
    elif args.command == "defense-sweep":
        scenarios = defense_scenarios(config)
    elif args.command == "sensitivity-sweep":
        scenarios = sensitivity_scenarios(config)
    else:
        scenarios = (
            [baseline]
            + attack_scenarios(config, "phase")
            + attack_scenarios(config, "target")
            + defense_scenarios(config)
        )
    output = args.output or Path("outputs") / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        write_run(scenarios, output)
    except FileExistsError:
        parser.error(f"Output directory already exists: {output}. Choose a new path.")
    logging.info("Completed: %s", output)
