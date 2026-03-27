import json
import sys
import os
from pathlib import Path
import snowflake.connector

_scripts = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_scripts))
sys.path.append(str(Path(__file__).parent))
from config_expand import expand_env_templates
from check_snowflake_permissions import check_role_permissions

apps_root   = Path("apps")
errors      = []
warnings    = []
deploy_role = os.environ["SNOWFLAKE_ROLE"]
ENVIRONMENT = os.environ.get("SNOWFLAKE_ENV", "dev").upper()


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
print(f"  SNOWFLAKE PERMISSION CHECKS — {ENVIRONMENT}")
print(f"  SNOWFLAKE_ENV_ID: {os.environ.get('SNOWFLAKE_ENV_ID', '(not set)')}")
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
        app_name = app_dir.name
        with open(config_path) as f:
            cfg = json.load(f)

        try:
            db = expand_env_templates(cfg["database"])
        except (KeyError, ValueError) as e:
            errors.append(f"{app_name}: could not resolve database from app_config — {e}")
            print(f"\n  [{app_name}]")
            print(f"      ✗ database template — {e}")
            continue

        expected = os.environ.get("SNOWFLAKE_DB")
        if expected and db != expected:
            errors.append(
                f"{app_name}: expanded database '{db}' does not match SNOWFLAKE_DB '{expected}'"
            )
            print(f"\n  [{app_name}]")
            print(f"      ✗ database mismatch: {db} vs SNOWFLAKE_DB {expected}")
            continue
        schema    = cfg["schema"]
        warehouse = cfg["query_warehouse"]

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