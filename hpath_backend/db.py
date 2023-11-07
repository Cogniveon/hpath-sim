"""Defines SQLite commands and initialises the database for the histopathology simulator
backend."""
import os
import sqlite3 as sql
from datetime import datetime

import pandas as pd

from conf import DB_PATH, DB_PERSISTENCE
from .types import HPathConfigParams, HPathSharedParams

# NOTE: ALWAYS USE TRANSACTIONS WHEN UPDATING DATABASE

SQL_PERSIST = " IF NOT EXISTS" if DB_PERSISTENCE else ""

SQL_INIT = f"""\
BEGIN TRANSACTION;
{"DROP TABLE IF EXISTS analyses;" if not DB_PERSISTENCE else ""}
{"DROP TABLE IF EXISTS scenarios;" if not DB_PERSISTENCE else ""}
CREATE TABLE{SQL_PERSIST} "analyses" (
        "analysis_id"    INTEGER,
        "analysis_name"  TEXT NOT NULL,
        PRIMARY KEY("analysis_id" AUTOINCREMENT)
);
CREATE TABLE{SQL_PERSIST} "scenarios" (
        "scenario_id"    INTEGER,
        "scenario_name"  TEXT NOT NULL,
        "analysis_id"   INTEGER,
        "created"       REAL NOT NULL,
        "completed"     REAL,
        "num_reps"      INTEGER NOT NULL,
        "done_reps"     INTEGER NOT NULL DEFAULT 0,
        "results"       TEXT,
        "file_name"     TEXT,
        "file"  BLOB,
        FOREIGN KEY("analysis_id") REFERENCES "analyses"("analysis_id"),
        PRIMARY KEY("scenario_id" AUTOINCREMENT)
);
DELETE FROM sqlite_sequence;
COMMIT;
"""  # Generated from sqlitebrowser
"""SQLite command for initialising the database."""

SQL_LIST_SCENARIOS = """\
SELECT
    scenario_id,
    scenario_name,
    analyses.analysis_id as analysis_id,
    analysis_name,
    created,
    completed,
    num_reps,
    done_reps,
    file_name
FROM scenarios
LEFT JOIN analyses ON scenarios.analysis_id = analyses.analysis_id
"""
"""SQLite command for listing the scenarios."""

SQL_SCENARIO_RESULTS = """\
SELECT
    scenario_id,
    scenario_name,
    analysis_id,
    results
FROM scenarios
WHERE scenario_id = ?
"""
"""SQLite command for fetching a single scenario's result."""

SQL_INSERT_ANALYSIS = """\
INSERT INTO analyses(analysis_name)
VALUES(?)
"""
"""SQLite command for creating a new multi-scenario analysis."""

SQL_INSERT_SCENARIO = """\
INSERT INTO scenarios(scenario_name, analysis_id, created, num_reps, file_name, file)
VALUES(?,?,?,?,?,?)
"""
"""SQLite command for creating a new simulation scenario."""

SQL_UPDATE_PROGRESS = """\
UPDATE scenarios
SET done_reps = num_reps
WHERE scenario_id = ?
"""
"""SQLite command for incrementing the progress counter."""

SQL_SAVE_RESULT = """\
UPDATE scenarios
SET
    completed = ?,
    results = ?
WHERE scenario_id = ?
"""
"""SQLite command for saving simulation results to database."""

SQL_CLEAR = """\
BEGIN TRANSACTION;
DELETE FROM analyses;
DELETE FROM scenarios;
DELETE FROM sqlite_sequence;
COMMIT;
"""
"""Clear all database tables."""


def submit_scenario(
    name: str,
    analysis_id: int | None,
    num_reps: int,
    file_name: str, file: bytes,
    *,
    cur: sql.Cursor
) -> int:
    """Submit a scenario and return the new scenario ID."""
    cur.execute(
        SQL_INSERT_SCENARIO,
        (
            name,
            analysis_id,
            # Convert LOCAL time to UNIX time, WHICH IS ALWAYS UTC-BASED
            datetime.now().timestamp(),
            num_reps,
            file_name,
            file
        )
    )
    scenario_id = cur.lastrowid
    return scenario_id


def submit_scenarios(
    configs: list[HPathConfigParams],
    params: HPathSharedParams
) -> list[int]:
    """Submit a list of scenarios as a single transaction, i.e. failure will rollback the
    entire transaction.

    Connected to endpoint `submit/` on the REST server.
    """
    with sql.connect(DB_PATH) as conn:
        cur = conn.cursor()
        scenario_ids: list[int] = []

        try:
            # If multi-scenario analysis:
            if len(configs) > 1 and params.analysis_name is not None:
                cur.execute(SQL_INSERT_ANALYSIS, (params.analysis_name, ))
                analysis_id = cur.lastrowid
            else:
                analysis_id = None

            for config in configs:
                scenario_id = submit_scenario(
                    config.name,
                    analysis_id=analysis_id,
                    num_reps=1,
                    file_name=config.file_name,
                    file=config.file,
                    cur=cur
                )
                scenario_ids.append(scenario_id)

            conn.commit()
            return scenario_ids
        except sql.Error as err:
            if conn.in_transaction():
                conn.rollback()
            raise err


def update_progress(scenario_id: int):
    """Increment the done_reps counter for the scenario with the given ID."""
    try:
        with sql.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(SQL_UPDATE_PROGRESS, (scenario_id, ))
    except sql.Error as err:
        raise err


def save_result(scenario_id: int, result_json: str):
    """Save the results JSON to database for the scenario with the given ID."""
    try:
        with sql.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                SQL_SAVE_RESULT,
                (
                    datetime.now().timestamp(),  # SET completed = ?
                    result_json,  # results = ?
                    scenario_id   # WHERE scenario_id = ?
                )
            )
    except sql.Error as err:
        raise err


def list_scenarios() -> pd.DataFrame:
    """Get the list of scenarios and convert to a dict for input to a Dash AG Grid.

    Connected to endpoint `scenarios/` on the REST server.
    """
    try:
        with sql.connect(DB_PATH) as conn:
            df = pd.read_sql(SQL_LIST_SCENARIOS, conn)
            return df
    except sql.Error as err:
        raise err


def results_scenario(scenario_id: int) -> pd.DataFrame:
    """Return the results of a scenario task."""
    try:
        with sql.connect(DB_PATH) as conn:
            df = pd.read_sql(SQL_SCENARIO_RESULTS, conn, params=(scenario_id, ))
            return df
    except sql.Error as err:
        raise err


def init():
    """Initialise the database, adding the required tables if missing."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sql.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.executescript(SQL_INIT)
            conn.commit()
    except sql.Error as err:
        raise err

def clear():
    """Clear all database tables."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sql.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.executescript(SQL_CLEAR)
            conn.commit()
    except sql.Error as err:
        raise err
