"""
src/db_v2.py
------------
Compatibility wrapper — re-exports the canonical v2 schema from src/db.py.

DO NOT add new schema definitions here.
All schema is canonical in src/db.py.

This file exists only so that older import paths
    from src.db_v2 import get_connection, ...
continue to work without modification.
"""
from src.db import (          # noqa: F401  (re-export everything used externally)
    get_connection,
    init_db,
    DEFAULT_DB_PATH,
    SCHEMA,
    VIEWS,
    compute_profile_level,
    update_all_profile_levels,
)

# Legacy alias — some scripts import SCHEMA_V2 from here
SCHEMA_V2 = SCHEMA
SCHEMA_V1 = SCHEMA   # no separate v1 schema in current codebase
