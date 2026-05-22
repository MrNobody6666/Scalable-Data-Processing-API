"""
join_service.py
===============
Out-of-core data join using DuckDB.

DuckDB reads the CSV files via its built-in scanner, performs an INNER JOIN,
and streams the result straight to an output CSV.  The `memory_limit` is
capped at 200 MB so we comfortably stay below the 256 MB hard ceiling.

Usage (standalone test):
    python join_service.py
"""

import logging
import os
import shutil
import time
import uuid

import duckdb

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_USERS = os.path.join(BASE_DIR, "users.csv")
DEFAULT_TRANSACTIONS = os.path.join(BASE_DIR, "transactions.csv")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "result.csv")


def perform_join(
    users_path: str = DEFAULT_USERS,
    transactions_path: str = DEFAULT_TRANSACTIONS,
    output_path: str = DEFAULT_OUTPUT,
    memory_limit: str = "200MB",
) -> dict:
    """
    Execute an out-of-core INNER JOIN between users and transactions.

    Parameters
    ----------
    users_path : str
        Path to users.csv.
    transactions_path : str
        Path to transactions.csv.
    output_path : str
        Destination for the joined result.
    memory_limit : str
        DuckDB memory budget (e.g. '200MB').

    Returns
    -------
    dict
        Metadata about the completed join:
        ``{ "rows": int, "output_path": str, "duration_seconds": float }``
    """
    logger.info("Starting out-of-core join ...")
    logger.info("  users         : %s", users_path)
    logger.info("  transactions  : %s", transactions_path)
    logger.info("  output        : %s", output_path)
    logger.info("  memory_limit  : %s", memory_limit)

    start = time.perf_counter()

    # Create an in-process DuckDB connection (no persistent database file)
    con = duckdb.connect(database=":memory:")

    temp_dir = os.path.join(BASE_DIR, f"duckdb_tmp_{uuid.uuid4().hex}")
    try:
        # Enforce the memory ceiling
        con.execute(f"SET memory_limit = '{memory_limit}'")
        # Allow DuckDB to spill to disk when memory is tight
        con.execute(f"SET temp_directory = '{temp_dir.replace(os.sep, '/')}'")
        # Reduce memory overhead
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 2")
        
        # Perform the join and write the output in one streaming query.
        # DuckDB's CSV scanner reads data lazily -- it never materialises
        # both entire files in RAM at once.
        query = f"""
            COPY (
                SELECT
                    u.user_id,
                    u.name,
                    u.email,
                    u.age,
                    u.city,
                    t.transaction_id,
                    t.amount,
                    t.date,
                    t.category
                FROM read_csv_auto('{users_path.replace(os.sep, "/")}')       AS u
                JOIN read_csv_auto('{transactions_path.replace(os.sep, "/")}') AS t
                  ON u.user_id = t.user_id
            ) TO '{output_path.replace(os.sep, "/")}' (HEADER, DELIMITER ',');
        """

        con.execute(query)

        # Grab the row count from the output file via DuckDB itself
        row_count = con.execute(
            f"SELECT count(*) FROM read_csv_auto('{output_path.replace(os.sep, '/')}')"
        ).fetchone()[0]
    finally:
        con.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    duration = time.perf_counter() - start
    result_meta = {
        "rows": row_count,
        "output_path": output_path,
        "duration_seconds": round(duration, 2),
    }

    logger.info("Join complete in %.2fs -- %s rows written.", duration, f"{row_count:,}")
    return result_meta


# ---------------------------------------------------------------------------
# Quick standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    meta = perform_join()
    print(meta)
