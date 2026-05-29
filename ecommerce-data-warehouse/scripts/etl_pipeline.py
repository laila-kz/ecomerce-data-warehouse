"""
Standalone ETL pipeline runner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.config import setup_logging
from scripts.extract import extract_bronze_layer
from scripts.load import load_to_mysql
from scripts.scd2 import merge_scd2_dimensions
from scripts.transform import transform_silver_layer

logger = setup_logging()


def run_pipeline(stage: str = "all") -> bool:
    stages = {
        "extract": extract_bronze_layer,
        "transform": transform_silver_layer,
        "load": load_to_mysql,
        "scd2": merge_scd2_dimensions,
    }

    if stage == "all":
        for stage_name in ["extract", "transform", "load", "scd2"]:
            logger.info("Running stage: %s", stage_name)
            if not stages[stage_name]():
                return False
        return True

    if stage not in stages:
        raise ValueError(f"Unknown stage: {stage}")

    return stages[stage]()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Olist ETL pipeline")
    parser.add_argument("--stage", choices=["all", "extract", "transform", "load", "scd2"], default="all")
    args = parser.parse_args()

    success = run_pipeline(args.stage)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()