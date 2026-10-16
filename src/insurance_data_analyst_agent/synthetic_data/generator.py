from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DATASET_VERSION = "synthetic-v1"
SEED = 20260904

PROVINCES = ["QC", "ON", "BC", "AB"]
LINES_OF_BUSINESS = [
    "commercial_property",
    "commercial_auto",
    "general_liability",
]

PolicyRow = tuple[str, str, str, int, float]
ExposureRow = tuple[str, str, int, float]
ClaimRow = tuple[str, str, int, str, float]


def generate_synthetic_rows(
    seed: int = SEED,
    policies_per_segment_year: int = 30,
) -> tuple[list[PolicyRow], list[ExposureRow], list[ClaimRow]]:
    """Generate deterministic synthetic rows, independent of the database."""
    rng = random.Random(seed)

    policy_rows: list[PolicyRow] = []
    exposure_rows: list[ExposureRow] = []
    claim_rows: list[ClaimRow] = []

    policy_number = 1
    claim_number = 1

    for year in range(2023, 2026):
        for province in PROVINCES:
            for lob in LINES_OF_BUSINESS:
                for _ in range(policies_per_segment_year):
                    policy_id = f"P-{policy_number:06d}"
                    premium = round(rng.uniform(3_000, 25_000), 2)
                    exposure_units = round(rng.uniform(0.8, 1.2), 4)

                    policy_rows.append((policy_id, province, lob, year, premium))
                    exposure_rows.append(
                        (f"E-{policy_number:06d}", policy_id, year, exposure_units)
                    )

                    base_frequency = 0.10 if lob == "commercial_property" else 0.07
                    qc_adjustment = 0.05 if province == "QC" else 0.00
                    year_adjustment = 0.06 if year == 2025 else 0.00

                    if rng.random() < base_frequency + qc_adjustment + year_adjustment:
                        severity = rng.uniform(5_000, 45_000)
                        claim_rows.append(
                            (
                                f"C-{claim_number:06d}",
                                policy_id,
                                year,
                                "property_damage",
                                round(severity, 2),
                            )
                        )
                        claim_number += 1

                    policy_number += 1

    return policy_rows, exposure_rows, claim_rows


def create_synthetic_database(
    database_path: Path,
    seed: int = SEED,
    policies_per_segment_year: int = 30,
) -> None:
    policy_rows, exposure_rows, claim_rows = generate_synthetic_rows(
        seed, policies_per_segment_year
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS claims;
            DROP TABLE IF EXISTS exposure;
            DROP TABLE IF EXISTS policies;

            CREATE TABLE policies (
                policy_id TEXT PRIMARY KEY,
                province TEXT NOT NULL,
                line_of_business TEXT NOT NULL,
                underwriting_year INTEGER NOT NULL,
                written_premium REAL NOT NULL CHECK (written_premium > 0)
            );

            CREATE TABLE exposure (
                exposure_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                exposure_year INTEGER NOT NULL,
                exposure_units REAL NOT NULL CHECK (exposure_units > 0),
                FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
            );

            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                claim_year INTEGER NOT NULL,
                claim_type TEXT NOT NULL,
                paid_amount REAL NOT NULL CHECK (paid_amount >= 0),
                FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
            );
            """
        )

        connection.executemany(
            """
            INSERT INTO policies (
                policy_id, province, line_of_business,
                underwriting_year, written_premium
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            policy_rows,
        )

        connection.executemany(
            """
            INSERT INTO exposure (
                exposure_id, policy_id, exposure_year, exposure_units
            )
            VALUES (?, ?, ?, ?)
            """,
            exposure_rows,
        )

        connection.executemany(
            """
            INSERT INTO claims (
                claim_id, policy_id, claim_year, claim_type, paid_amount
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            claim_rows,
        )
