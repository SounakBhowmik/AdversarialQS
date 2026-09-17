"""Artifact writing is isolated from scientific simulation and refuses run reuse."""

import hashlib
import importlib.metadata
import json
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..config import ExperimentConfig
from ..plotting import plot_results
from .runner import identifiability_control, run_scenario


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_run(scenarios: list[tuple[str, ExperimentConfig]], output: Path) -> Path:
    """Create a new run directory, write auditable artifacts and mark completion last."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": dict(
            sorted(
                (distribution.metadata["Name"], distribution.version)
                for distribution in importlib.metadata.distributions()
            )
        ),
    }
    manifest = {
        "schema_version": 1,
        "source_sha256": {
            str(path.relative_to(Path(__file__).resolve().parents[1])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(Path(__file__).resolve().parents[1].rglob("*.py"))
        },
        "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "environment": environment,
        "scenarios": [name for name, _ in scenarios],
    }
    _json(output / "manifest.json", manifest)
    runs = []
    try:
        for name, config in scenarios:
            logging.info(
                "Running %s: seed=%s, shots=%s, attack=%s/%s",
                name,
                config.seed,
                config.shots_per_setting,
                config.attack.kind,
                config.attack.profile,
            )
            run = run_scenario(config, name)
            runs.append(run)
            directory = output / name
            directory.mkdir()
            (directory / "resolved_config.yaml").write_text(
                yaml.safe_dump(run["config"], sort_keys=False)
            )
            run["results"].to_csv(directory / "results.csv", index=False)
            for key in (
                "summary",
                "detector",
                "roc",
                "calibration",
                "kernel_diagnostics",
                "seeds",
                "training_diagnostics",
            ):
                _json(directory / f"{key}.json", run[key])
            with (directory / "audit.jsonl").open("w") as handle:
                for item in run["audit"]:
                    handle.write(json.dumps(item, allow_nan=False) + "\n")
            np.savez_compressed(
                directory / "states.npz", clean=run["states_clean"], attacked=run["states_attacked"]
            )
            _json(directory / "runtime.json", {"seconds": run["runtime_seconds"]})
        pd.concat([r["results"] for r in runs]).to_csv(output / "results.csv", index=False)
        control = identifiability_control(scenarios[0][1])
        _json(output / "identifiability.json", control)
        if not control["equivalent"]:
            raise RuntimeError("Identifiability control failed")
        fixed = next((r for r in runs if r["name"] == "fixed"), None)
        overhead = (
            {
                r["name"]: {
                    estimator: r["summary"][f"clean/{estimator}"]["rmse_tesla"]
                    - fixed["summary"][f"clean/{estimator}"]["rmse_tesla"]
                    for estimator in (
                        "maximum_likelihood",
                        "linear",
                        "rbf_krr",
                        "mlp",
                        "tomography_krr",
                        "oracle_upper_bound",
                    )
                }
                for r in runs
            }
            if fixed
            else {}
        )
        _json(output / "clean_accuracy_overhead_tesla.json", overhead)
        plot_results(runs, output)
        manifest.update(
            {
                "status": "complete",
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "runtime_seconds": sum(r["runtime_seconds"] for r in runs),
                "files": {
                    str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(output.rglob("*"))
                    if p.is_file() and p.name != "manifest.json"
                },
            }
        )
    except Exception as exc:
        manifest.update({"status": "failed", "error": str(exc)})
        _json(output / "manifest.json", manifest)
        raise
    _json(output / "manifest.json", manifest)
    return output
