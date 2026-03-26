import os
import json
import sys
import snowflake.connector
from pathlib import Path

# ── Environment: dev | uat | prod ────────────────────────────────────────────
ENVIRONMENT = os.environ.get("SNOWFLAKE_ENV", "dev").lower()
VALID_ENVS  = ["dev", "uat", "prod"]

if ENVIRONMENT not in VALID_ENVS:
    print(f"✗ Invalid SNOWFLAKE_ENV '{ENVIRONMENT}'. Must be one of: {VALID_ENVS}")
    sys.exit(1)

print(f"\n  Environment: {ENVIRONMENT.upper()}")

# ── Snowflake connection ──────────────────────────────────────────────────────
conn = snowflake.connector.connect(
    account   = os.environ["SNOWFLAKE_ACCOUNT"],
    user      = os.environ["SNOWFLAKE_USER"],
    password  = os.environ["SNOWFLAKE_PASSWORD"],
    role      = os.environ["SNOWFLAKE_ROLE"],
    warehouse = os.environ["SNOWFLAKE_WAREHOUSE"],
)
cursor = conn.cursor()


def run_sql(sql: str, description: str = ""):
    print(f"\n▶ {description or sql[:80]}")
    try:
        cursor.execute(sql)
        result = cursor.fetchall()
        print(f"  ✓ Done. {result}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        raise


def upload_file_to_stage(local_path: str, stage_path: str):
    abs_path = Path(local_path).resolve()
    put_sql  = f"""
        PUT file://{abs_path} {stage_path}
        AUTO_COMPRESS = FALSE
        OVERWRITE = TRUE
    """
    print(f"\n▶ Uploading {abs_path.name} → {stage_path}")
    cursor.execute(put_sql)
    result = cursor.fetchall()
    print(f"  ✓ {result}")


def deploy_app(app_dir: Path):
    config_path = app_dir / "app_config.json"
    if not config_path.exists():
        print(f"  ⚠ Skipping {app_dir.name} — no app_config.json found.")
        return

    with open(config_path) as f:
        cfg = json.load(f)

    # ── Resolve database for current environment ──────────────
    databases = cfg.get("databases", {})
    db = databases.get(ENVIRONMENT)
    if not db:
        print(f"  ⚠ Skipping {app_dir.name} — no database configured for env '{ENVIRONMENT}'")
        return

    schema    = cfg["schema"]
    stage     = cfg["stage"]
    app_name  = cfg["app_name"]
    main_file = cfg["main_file"]
    warehouse = cfg["query_warehouse"]
    runtime   = cfg.get("runtime", "warehouse")
    stage_ref = f"@{db}.{schema}.{stage}/app"

    print(f"\n{'='*60}")
    print(f"  Deploying : {app_name}")
    print(f"  Env       : {ENVIRONMENT.upper()}")
    print(f"  Database  : {db}")
    print(f"  Runtime   : {runtime}")
    print(f"{'='*60}")

    # 1. Create stage
    run_sql(
        f"CREATE STAGE IF NOT EXISTS {db}.{schema}.{stage}",
        f"Ensure stage {stage}"
    )

    # 2. Grant stage access
    run_sql(
        f"GRANT READ, WRITE ON STAGE {db}.{schema}.{stage} TO ROLE {os.environ['SNOWFLAKE_ROLE']}",
        f"Grant READ, WRITE on stage {stage}"
    )

    # 3. Upload app files
    app_files = [
        p for p in app_dir.iterdir()
        if p.is_file() and p.name != "app_config.json"
    ]
    for file_path in app_files:
        upload_file_to_stage(str(file_path), stage_ref)

    # 4. CREATE OR REPLACE STREAMLIT
    if runtime == "container":
        runtime_name = cfg["runtime_name"]
        compute_pool = cfg["compute_pool"]
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

    # 5. Publish LIVE VERSION
    run_sql(
        f"ALTER STREAMLIT {db}.{schema}.{app_name} ADD LIVE VERSION FROM LAST",
        f"Publish LIVE VERSION for {app_name}"
    )

    # 6. Grant usage to end users
    viewer_role = cfg.get("viewer_role", "PUBLIC")
    run_sql(
        f"GRANT USAGE ON STREAMLIT {db}.{schema}.{app_name} TO ROLE {viewer_role}",
        f"Grant USAGE on {app_name} to {viewer_role}"
    )

    print(f"\n  ✅ {app_name} deployed to {ENVIRONMENT.upper()} successfully!\n")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    apps_root   = Path("apps")
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
    print(f"  Environment : {ENVIRONMENT.upper()}")
    print(f"  ✅ Deployed : {deployed}")
    print(f"  ✗  Failed  : {failed}")
    print("="*60)

    if failed:
        sys.exit(1)