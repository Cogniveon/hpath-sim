"""Configuration settings for the hpath-sim app."""

import os


REDIS_HOST = 'redis'
"""Hostname for the Redis server."""

REDIS_PORT = 6379
"""Port for the Redis server, default 6379 for unaltered Docker container
(https://hub.docker.com/_/redis)."""

PORT = 5000
"""Port to host this server on (internal port)."""

DB_PATH = os.path.join(os.path.dirname(__file__), "db/hpath.db")
print(DB_PATH)
"""Path to the simulation job store, a SQLite database."""

# During development, we may wish to start with a clean database upon
# every launch.  For production, set this to True.
DB_PERSISTENCE = False
# DB_PERSISTENCE = True
"""If false, builds a new empty database upon app launch. If true, use
the existing database if found."""
