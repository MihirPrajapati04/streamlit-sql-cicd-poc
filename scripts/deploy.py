import os
import json
import sys
import snowflake.connector
from pathlib import Path

# ── Load global Snowflake connection config ──────────────────────────────────
with open("snowflake_config.json") as f:
    sf_config = json.load(f)

conn = snowflake.connector.connect(
    account=sf_config["account"],
    user=sf_config["user"],
    password=os.environ["SNOWFLAKE_PASSWORD"],   # injected from GitHub Secret
    role=sf_config["role"],
    warehouse=sf_config["warehouse"],
)
cursor = conn.cursor()


def run_sql(sql: str, description: str = ""):
    """Execute a SQL statement and print result."""
    print(f"\n▶ {description or sql[:80]}")
    try:
        cursor.execute(sql)
        result = cursor.fetchall()
        print(f"  ✓ Done. {result}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        raise


def upload_file_to_stage(local_path: str, stage_path: str):
    """
    Upload a single file to a Snowflake stage using PUT over SQL.
    """
    # PUT requires a file:// URI
    abs_path = Path(local_path).resolve()
    put_sql = f"""
        PUT file://{abs_path} {stage_path}
        AUTO_COMPRESS = FALSE
        OVERWRITE = TRUE
    """
    print(f"\n▶ Uploading {abs_path.name} → {stage_path}")
    cursor.execute(put_sql)
    result = cursor.fetchall()
    print(f"  ✓ {result}")


def deploy_app(app_dir: Path):
    """Full deploy flow for a single Streamlit app using SQL only."""

    config_path = app_dir / "app_config.json"
    if not config_path.exists():
        print(f"  ⚠ Skipping {app_dir.name} — no app_config.json found.")
        return

    with open(config_path) as f:
        cfg = json.load(f)

    db          = cfg["database"]
    schema      = cfg["schema"]
    stage       = cfg["stage"]
    app_name    = cfg["app_name"]
    main_file   = cfg["main_file"]
    warehouse   = cfg["query_warehouse"]
    runtime     = cfg.get("runtime", "warehouse")   # "warehouse" or "container"
    stage_ref   = f"@{db}.{schema}.{stage}/app"

    print(f"\n{'='*60}")
    print(f"  Deploying: {app_name}  ({runtime} runtime)")
    print(f"{'='*60}")

    # # 1. Ensure database/schema exist (optional guard)
    # run_sql(f"CREATE DATABASE IF NOT EXISTS {db}", f"Ensure DB {db}")
    # run_sql(f"CREATE SCHEMA IF NOT EXISTS {db}.{schema}", f"Ensure schema {schema}")

    # 2. Create or replace the stage
    run_sql(
        f"CREATE STAGE IF NOT EXISTS {db}.{schema}.{stage}",
        f"Ensure stage {stage}"
    )

    # 3. Upload all app files to the stage
    app_files = [
        p for p in app_dir.iterdir()
        if p.is_file() and p.name != "app_config.json"
    ]
    for file_path in app_files:
        upload_file_to_stage(str(file_path), stage_ref)

    # 4. CREATE OR REPLACE the STREAMLIT object using SQL
    if runtime == "container":
        runtime_name  = cfg["runtime_name"]
        compute_pool  = cfg["compute_pool"]
        create_sql = f"""
            CREATE OR REPLACE STREAMLIT {db}.{schema}.{app_name}
                FROM '{stage_ref}'
                MAIN_FILE = '{main_file}'
                RUNTIME_NAME = '{runtime_name}'
                COMPUTE_POOL = {compute_pool}
                QUERY_WAREHOUSE = {warehouse}
        """
    else:
        create_sql = f"""
            CREATE OR REPLACE STREAMLIT {db}.{schema}.{app_name}
                FROM '{stage_ref}'
                MAIN_FILE = '{main_file}'
                QUERY_WAREHOUSE = {warehouse}
        """

    run_sql(create_sql, f"CREATE OR REPLACE STREAMLIT {app_name}")

    # 5. Push code to LIVE VERSION (required for USAGE-privilege users)
    run_sql(
        f"ALTER STREAMLIT {db}.{schema}.{app_name} ADD LIVE VERSION FROM LAST",
        f"Publish LIVE VERSION for {app_name}"
    )

    print(f"\n  ✅ {app_name} deployed successfully!\n")


# ── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    apps_root = Path("apps")

    # Optional: deploy only specific apps passed as CLI args
    # e.g. python scripts/deploy.py app_one app_three
    target_apps = sys.argv[1:] if len(sys.argv) > 1 else None

    deployed, failed = [], []

    for app_dir in sorted(apps_root.iterdir()):
        if not app_dir.is_dir():
            continue
        if target_apps and app_dir.name not in target_apps:
            continue

        try:
            deploy_app(app_dir)
            deployed.append(app_dir.name)
        except Exception as e:
            print(f"\n  ✗ {app_dir.name} FAILED: {e}")
            failed.append(app_dir.name)

    cursor.close()
    conn.close()

    print("\n" + "="*60)
    print(f"  ✅ Deployed:  {deployed}")
    print(f"  ✗  Failed:   {failed}")
    print("="*60)

    if failed:
        sys.exit(1)   # Fail the CI job if any app failed