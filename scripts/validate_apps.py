import json
import sys
import os
from pathlib import Path
import snowflake.connector

# ── Required for ALL apps regardless of runtime ──────────────────────────────
REQUIRED_FILES = ["streamlit_app.py", "app_config.json"]

COMMON_REQUIRED_KEYS = [
    "app_name",
    "database",
    "schema",
    "stage",
    "main_file",
    "query_warehouse",
    "runtime"
]

CONTAINER_REQUIRED_KEYS = ["runtime_name", "compute_pool"]
VALID_RUNTIMES           = ["warehouse", "container"]
VALID_RUNTIME_NAMES      = ["SYSTEM$ST_CONTAINER_RUNTIME_PY3_11"]


# ── Snowflake connection ──────────────────────────────────────────────────────
def get_snowflake_cursor():
    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        role      = os.environ["SNOWFLAKE_ROLE"],
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"],
    )
    return conn, conn.cursor()


# ══════════════════════════════════════════════════════════════════════════════
# SNOWFLAKE SIDE CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_database(cursor, db, app_name, errors, warnings):
    print(f"\n    Checking database '{db}'...")
    try:
        cursor.execute(f"SHOW DATABASES LIKE '{db}'")
        result = cursor.fetchall()
        if not result:
            errors.append(f"{app_name}: database '{db}' does not exist or is not accessible")
            print(f"      ✗ database '{db}' — NOT FOUND")
            return False
        else:
            print(f"      ✓ database '{db}' exists")
            return True
    except Exception as e:
        errors.append(f"{app_name}: error checking database '{db}' — {e}")
        print(f"      ✗ error checking database — {e}")
        return False


def check_schema(cursor, db, schema, app_name, errors, warnings):
    print(f"\n    Checking schema '{db}.{schema}'...")
    try:
        cursor.execute(f"SHOW SCHEMAS LIKE '{schema}' IN DATABASE {db}")
        result = cursor.fetchall()
        if not result:
            errors.append(f"{app_name}: schema '{schema}' does not exist in database '{db}'")
            print(f"      ✗ schema '{schema}' — NOT FOUND in {db}")
            return False
        else:
            print(f"      ✓ schema '{db}.{schema}' exists")
            return True
    except Exception as e:
        errors.append(f"{app_name}: error checking schema '{db}.{schema}' — {e}")
        print(f"      ✗ error checking schema — {e}")
        return False


def check_warehouse(cursor, warehouse, app_name, errors, warnings):
    print(f"\n    Checking warehouse '{warehouse}'...")
    try:
        cursor.execute(f"SHOW WAREHOUSES LIKE '{warehouse}'")
        result = cursor.fetchall()
        if not result:
            errors.append(f"{app_name}: warehouse '{warehouse}' does not exist or is not accessible")
            print(f"      ✗ warehouse '{warehouse}' — NOT FOUND")
            return False
        else:
            # Check warehouse state (index 3 is state in SHOW WAREHOUSES)
            wh_state = result[0][3]
            if wh_state in ("STARTED", "SUSPENDED", "RESIZING"):
                print(f"      ✓ warehouse '{warehouse}' exists — state: {wh_state}")
            else:
                warnings.append(
                    f"{app_name}: warehouse '{warehouse}' is in unexpected state '{wh_state}'"
                )
                print(f"      ⚠ warehouse '{warehouse}' — unexpected state: {wh_state}")
            return True
    except Exception as e:
        errors.append(f"{app_name}: error checking warehouse '{warehouse}' — {e}")
        print(f"      ✗ error checking warehouse — {e}")
        return False


def check_stage(cursor, db, schema, stage, app_name, errors, warnings):
    print(f"\n    Checking stage '{db}.{schema}.{stage}'...")
    try:
        cursor.execute(f"SHOW STAGES LIKE '{stage}' IN SCHEMA {db}.{schema}")
        result = cursor.fetchall()
        if not result:
            warnings.append(
                f"{app_name}: stage '{stage}' does not exist yet — "
                f"it will be created automatically during deploy"
            )
            print(f"      ⚠ stage '{stage}' — does not exist yet (will be created on deploy)")
        else:
            print(f"      ✓ stage '{db}.{schema}.{stage}' already exists")
    except Exception as e:
        errors.append(f"{app_name}: error checking stage '{db}.{schema}.{stage}' — {e}")
        print(f"      ✗ error checking stage — {e}")


def check_compute_pool(cursor, compute_pool, app_name, errors, warnings):
    print(f"\n    Checking compute pool '{compute_pool}'...")
    try:
        cursor.execute(f"SHOW COMPUTE POOLS LIKE '{compute_pool}'")
        result = cursor.fetchall()
        if not result:
            errors.append(
                f"{app_name}: compute pool '{compute_pool}' does not exist or is not accessible"
            )
            print(f"      ✗ compute pool '{compute_pool}' — NOT FOUND")
            return False
        else:
            # index 4 is state in SHOW COMPUTE POOLS
            pool_state = result[0][4]
            if pool_state in ("ACTIVE", "IDLE"):
                print(f"      ✓ compute pool '{compute_pool}' exists — state: {pool_state}")
            elif pool_state == "STARTING":
                warnings.append(
                    f"{app_name}: compute pool '{compute_pool}' is still STARTING — "
                    f"it may not be ready when the app deploys"
                )
                print(f"      ⚠ compute pool '{compute_pool}' — state: STARTING (may not be ready)")
            else:
                errors.append(
                    f"{app_name}: compute pool '{compute_pool}' is in state '{pool_state}' — "
                    f"must be ACTIVE or IDLE to deploy"
                )
                print(f"      ✗ compute pool '{compute_pool}' — bad state: {pool_state}")
            return True
    except Exception as e:
        errors.append(f"{app_name}: error checking compute pool '{compute_pool}' — {e}")
        print(f"      ✗ error checking compute pool — {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ROLE / PERMISSION CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_role_permissions(cursor, db, schema, warehouse, role, app_name, errors, warnings):
    print(f"\n    Checking permissions for role '{role}'...")

    # ── USAGE on database ─────────────────────────────────────
    try:
        cursor.execute(f"""
            SHOW GRANTS ON DATABASE {db}
        """)
        grants = cursor.fetchall()
        # Each row: (created_on, privilege, granted_on, name, granted_to, grantee_name, ...)
        db_usage_granted = any(
            row[1] == "USAGE" and row[5].upper() == role.upper()
            for row in grants
        )
        if db_usage_granted:
            print(f"      ✓ USAGE on DATABASE {db} — granted to {role}")
        else:
            errors.append(
                f"{app_name}: DEPLOY_ROLE '{role}' does not have USAGE on database '{db}'"
            )
            print(f"      ✗ USAGE on DATABASE {db} — NOT granted to {role}")
    except Exception as e:
        warnings.append(f"{app_name}: could not verify USAGE on database '{db}' — {e}")
        print(f"      ⚠ could not verify USAGE on database — {e}")

    # ── USAGE on schema ───────────────────────────────────────
    try:
        cursor.execute(f"SHOW GRANTS ON SCHEMA {db}.{schema}")
        grants = cursor.fetchall()
        schema_usage_granted = any(
            row[1] == "USAGE" and row[5].upper() == role.upper()
            for row in grants
        )
        if schema_usage_granted:
            print(f"      ✓ USAGE on SCHEMA {db}.{schema} — granted to {role}")
        else:
            errors.append(
                f"{app_name}: DEPLOY_ROLE '{role}' does not have USAGE on schema '{db}.{schema}'"
            )
            print(f"      ✗ USAGE on SCHEMA {db}.{schema} — NOT granted to {role}")
    except Exception as e:
        warnings.append(f"{app_name}: could not verify USAGE on schema '{db}.{schema}' — {e}")
        print(f"      ⚠ could not verify USAGE on schema — {e}")

    # ── CREATE STREAMLIT on schema ────────────────────────────
    try:
        cursor.execute(f"SHOW GRANTS ON SCHEMA {db}.{schema}")
        grants = cursor.fetchall()
        create_st_granted = any(
            row[1] == "CREATE STREAMLIT" and row[5].upper() == role.upper()
            for row in grants
        )
        if create_st_granted:
            print(f"      ✓ CREATE STREAMLIT on SCHEMA {db}.{schema} — granted to {role}")
        else:
            errors.append(
                f"{app_name}: DEPLOY_ROLE '{role}' does not have "
                f"CREATE STREAMLIT on schema '{db}.{schema}'"
            )
            print(f"      ✗ CREATE STREAMLIT on SCHEMA {db}.{schema} — NOT granted to {role}")
    except Exception as e:
        warnings.append(f"{app_name}: could not verify CREATE STREAMLIT on schema — {e}")
        print(f"      ⚠ could not verify CREATE STREAMLIT on schema — {e}")

    # ── CREATE STAGE on schema ────────────────────────────────
    try:
        cursor.execute(f"SHOW GRANTS ON SCHEMA {db}.{schema}")
        grants = cursor.fetchall()
        create_stage_granted = any(
            row[1] == "CREATE STAGE" and row[5].upper() == role.upper()
            for row in grants
        )
        if create_stage_granted:
            print(f"      ✓ CREATE STAGE on SCHEMA {db}.{schema} — granted to {role}")
        else:
            errors.append(
                f"{app_name}: DEPLOY_ROLE '{role}' does not have "
                f"CREATE STAGE on schema '{db}.{schema}'"
            )
            print(f"      ✗ CREATE STAGE on SCHEMA {db}.{schema} — NOT granted to {role}")
    except Exception as e:
        warnings.append(f"{app_name}: could not verify CREATE STAGE on schema — {e}")
        print(f"      ⚠ could not verify CREATE STAGE on schema — {e}")

    # ── USAGE on warehouse ────────────────────────────────────
    try:
        cursor.execute(f"SHOW GRANTS ON WAREHOUSE {warehouse}")
        grants = cursor.fetchall()
        wh_usage_granted = any(
            row[1] == "USAGE" and row[5].upper() == role.upper()
            for row in grants
        )
        if wh_usage_granted:
            print(f"      ✓ USAGE on WAREHOUSE {warehouse} — granted to {role}")
        else:
            errors.append(
                f"{app_name}: DEPLOY_ROLE '{role}' does not have "
                f"USAGE on warehouse '{warehouse}'"
            )
            print(f"      ✗ USAGE on WAREHOUSE {warehouse} — NOT granted to {role}")
    except Exception as e:
        warnings.append(f"{app_name}: could not verify USAGE on warehouse '{warehouse}' — {e}")
        print(f"      ⚠ could not verify USAGE on warehouse — {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL FILE CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def validate_local(app_dir: Path, cfg: dict, errors: list, warnings: list):
    app_name = app_dir.name

    # ── Required files ────────────────────────────────────────
    print(f"\n    Required files:")
    for required_file in REQUIRED_FILES:
        if not (app_dir / required_file).exists():
            errors.append(f"{app_name}: missing required file '{required_file}'")
            print(f"      ✗ {required_file} — MISSING")
        else:
            print(f"      ✓ {required_file}")

    # ── Common required keys ──────────────────────────────────
    print(f"\n    Common config keys:")
    for key in COMMON_REQUIRED_KEYS:
        if key not in cfg:
            errors.append(f"{app_name}: app_config.json missing required key '{key}'")
            print(f"      ✗ {key} — MISSING")
        elif not str(cfg[key]).strip():
            errors.append(f"{app_name}: app_config.json key '{key}' is empty")
            print(f"      ✗ {key} — EMPTY")
        else:
            print(f"      ✓ {key} = {cfg[key]}")

    # ── runtime value ─────────────────────────────────────────
    runtime = cfg.get("runtime", "")
    if runtime not in VALID_RUNTIMES:
        errors.append(
            f"{app_name}: invalid runtime '{runtime}'. Must be one of: {VALID_RUNTIMES}"
        )
        return False

    # ── main_file is .py and exists ───────────────────────────
    main_file = cfg.get("main_file", "")
    if not main_file.endswith(".py"):
        errors.append(f"{app_name}: main_file '{main_file}' must be a .py file")
    elif not (app_dir / main_file).exists():
        errors.append(f"{app_name}: main_file '{main_file}' does not exist in app folder")
        print(f"      ✗ main_file '{main_file}' not found in folder")
    else:
        print(f"      ✓ main_file '{main_file}' exists")

    # ── streamlit_app.py not empty ────────────────────────────
    app_py = app_dir / "streamlit_app.py"
    if app_py.exists() and app_py.stat().st_size == 0:
        errors.append(f"{app_name}: streamlit_app.py is empty")
        print(f"      ✗ streamlit_app.py is empty")

    # ── Runtime specific local checks ─────────────────────────
    print(f"\n    Runtime-specific checks ({runtime}):")

    if runtime == "warehouse":
        if not (app_dir / "environment.yml").exists():
            warnings.append(
                f"{app_name}: no environment.yml — "
                f"warehouse runtime uses environment.yml for dependencies"
            )
            print(f"      ⚠ environment.yml not found — recommended for warehouse runtime")
        else:
            print(f"      ✓ environment.yml found")
        for key in CONTAINER_REQUIRED_KEYS:
            if key in cfg:
                warnings.append(
                    f"{app_name}: key '{key}' is not needed for warehouse runtime"
                )
                print(f"      ⚠ '{key}' found but not needed for warehouse runtime")

    elif runtime == "container":
        for key in CONTAINER_REQUIRED_KEYS:
            if key not in cfg:
                errors.append(
                    f"{app_name}: container runtime requires '{key}' in app_config.json"
                )
                print(f"      ✗ {key} — MISSING (required for container runtime)")
            elif not str(cfg[key]).strip():
                errors.append(f"{app_name}: '{key}' is empty")
                print(f"      ✗ {key} — EMPTY")

        runtime_name = cfg.get("runtime_name", "")
        if runtime_name not in VALID_RUNTIME_NAMES:
            errors.append(
                f"{app_name}: invalid runtime_name '{runtime_name}'. "
                f"Must be one of: {VALID_RUNTIME_NAMES}"
            )
            print(f"      ✗ runtime_name '{runtime_name}' is invalid")
        else:
            print(f"      ✓ runtime_name is valid")

        has_dep_file = (
            (app_dir / "requirements.txt").exists() or
            (app_dir / "pyproject.toml").exists()
        )
        if not has_dep_file:
            warnings.append(
                f"{app_name}: no requirements.txt or pyproject.toml found — "
                f"recommended for container runtime"
            )
            print(f"      ⚠ no requirements.txt or pyproject.toml found")
        else:
            dep = "requirements.txt" if (app_dir / "requirements.txt").exists() else "pyproject.toml"
            print(f"      ✓ dependency file found — {dep}")

        if (app_dir / "environment.yml").exists():
            warnings.append(
                f"{app_name}: environment.yml is not used by container runtime"
            )
            print(f"      ⚠ environment.yml found but not used by container runtime")

    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    apps_root = Path("apps")
    errors    = []
    warnings  = []
    deploy_role = os.environ["SNOWFLAKE_ROLE"]

    print("\n" + "="*60)
    print("  STEP 1 — LOCAL FILE & CONFIG VALIDATION")
    print("="*60)

    # collect valid configs first for Snowflake checks
    valid_configs = {}
    for app_dir in sorted(apps_root.iterdir()):
        if not app_dir.is_dir():
            continue
        print(f"\n  [{app_dir.name}]")
        config_path = app_dir / "app_config.json"
        if not config_path.exists():
            errors.append(f"{app_dir.name}: app_config.json missing")
            continue
        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{app_dir.name}: app_config.json is not valid JSON — {e}")
            continue

        ok = validate_local(app_dir, cfg, errors, warnings)
        if ok:
            valid_configs[app_dir.name] = cfg

    # ── Snowflake checks ──────────────────────────────────────
    print("\n" + "="*60)
    print("  STEP 2 — SNOWFLAKE INFRASTRUCTURE & PERMISSION CHECKS")
    print("="*60)

    try:
        conn, cursor = get_snowflake_cursor()
        print("\n  ✓ Connected to Snowflake successfully")

        for app_name, cfg in valid_configs.items():
            db        = cfg["database"]
            schema    = cfg["schema"]
            stage     = cfg["stage"]
            warehouse = cfg["query_warehouse"]
            runtime   = cfg["runtime"]

            print(f"\n  [{app_name}]")

            # ── Infrastructure checks ─────────────────────────
            print(f"\n  Infrastructure:")
            db_ok = check_database(cursor, db, app_name, errors, warnings)
            if db_ok:
                check_schema(cursor, db, schema, app_name, errors, warnings)
                check_stage(cursor, db, schema, stage, app_name, errors, warnings)
            check_warehouse(cursor, warehouse, app_name, errors, warnings)

            # ── Container only: compute pool ──────────────────
            if runtime == "container":
                compute_pool = cfg.get("compute_pool", "")
                check_compute_pool(cursor, compute_pool, app_name, errors, warnings)

            # ── Permission checks ─────────────────────────────
            print(f"\n  Permissions (role: {deploy_role}):")
            check_role_permissions(
                cursor, db, schema, warehouse,
                deploy_role, app_name, errors, warnings
            )

        cursor.close()
        conn.close()

    except Exception as e:
        errors.append(f"Could not connect to Snowflake — {e}")
        print(f"\n  ✗ Snowflake connection failed: {e}")

    # ── Final summary ─────────────────────────────────────────
    print("\n" + "="*60)
    print("  FINAL SUMMARY")
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
        print(f"\n  ✓  All checks passed")
        if warnings:
            print(f"  ⚠  {len(warnings)} warning(s) — review recommended")
    print("="*60)