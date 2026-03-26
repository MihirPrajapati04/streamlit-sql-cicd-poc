import json
import sys
import os
from pathlib import Path
import snowflake.connector

sys.path.append(str(Path(__file__).parent))
from check_snowflake_permissions import check_role_permissions

apps_root   = Path("apps")
errors      = []
warnings    = []
deploy_role = os.environ["SNOWFLAKE_ROLE"]


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
print("  SNOWFLAKE PERMISSION CHECKS")
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
        warehouse = cfg["query_warehouse"]
        app_name  = app_dir.name

        print(f"\n  [{app_name}]")

        check_role_permissions(
            cursor, db, schema, warehouse,
            deploy_role, app_name, errors, warnings
        )

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
    print(f"\n  ✓  All permission checks passed")
print("="*60)