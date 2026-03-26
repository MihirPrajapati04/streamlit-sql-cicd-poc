import json
import sys
import os
from pathlib import Path
import snowflake.connector

sys.path.append(str(Path(__file__).parent))
from check_snowflake_infra import (
    check_database, check_schema,
    check_warehouse, check_stage, check_compute_pool
)

apps_root = Path("apps")
errors    = []
warnings  = []


def get_cursor():
    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        role      = os.environ["SNOWFLAKE_ROLE"],
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"],
    )
    return conn, conn.cursor()


print("\n" + "="*60)
print("  SNOWFLAKE INFRASTRUCTURE CHECKS")
print("="*60)

try:
    conn, cursor = get_cursor()
    print("\n  ✓ Connected to Snowflake successfully")

    for app_dir in sorted(apps_root.iterdir()):
        if not app_dir.is_dir():
            continue
        config_path = app_dir / "app_config.json"
        if not config_path.exists():
            continue
        with open(config_path) as f:
            cfg = json.load(f)

        db        = cfg["database"]
        schema    = cfg["schema"]
        stage     = cfg["stage"]
        warehouse = cfg["query_warehouse"]
        runtime   = cfg["runtime"]
        app_name  = app_dir.name

        print(f"\n  [{app_name}]")

        db_ok = check_database(cursor, db, app_name, errors, warnings)
        if db_ok:
            check_schema(cursor, db, schema, app_name, errors, warnings)
            check_stage(cursor, db, schema, stage, app_name, errors, warnings)
        check_warehouse(cursor, warehouse, app_name, errors, warnings)

        if runtime == "container":
            compute_pool = cfg.get("compute_pool", "")
            check_compute_pool(cursor, compute_pool, app_name, errors, warnings)

    cursor.close()
    conn.close()

except Exception as e:
    errors.append(f"Could not connect to Snowflake — {e}")
    print(f"\n  ✗ Snowflake connection failed: {e}")

print("\n" + "="*60)
print("  SUMMARY")
print("="*60)

if warnings:
    print(f"\n  ⚠  {len(warnings)} warning(s):\n")
    for w in warnings:
        print(f"     ⚠  {w}")

if errors:
    print(f"\n  ✗  Validation FAILED — {len(errors)} error(s):\n")
    for e in errors:
        print(f"     ✗  {e}")
    sys.exit(1)
else:
    print(f"\n  ✓  All infrastructure checks passed")
print("="*60)