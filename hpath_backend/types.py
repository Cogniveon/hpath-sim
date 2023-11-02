"""Type definitions for the hpath module."""
from typing import NamedTuple


HPathSharedParams = NamedTuple(
    'HPathSharedParams',
    [('sim_hours', float), ('num_reps', int), ('analysis_name', str | None)]
)
"""Shared parameters of a submitted single-scenario or multiple-scenario analysis."""

HPathConfigParams = NamedTuple(
    'HPathConfigParams',
    [('name', str), ('file_name', str), ('config', str), ('file', bytes)]
)
"""Parameters for a single submiited scenario."""
