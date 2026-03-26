import json
from pathlib import Path

REQUIRED_FILES          = ["streamlit_app.py", "app_config.json"]
COMMON_REQUIRED_KEYS    = [
    "app_name", "schema", "stage",
    "main_file", "query_warehouse", "runtime"
]
CONTAINER_REQUIRED_KEYS = ["runtime_name", "compute_pool"]
VALID_RUNTIMES          = ["warehouse", "container"]
VALID_RUNTIME_NAMES     = ["SYSTEM$ST_CONTAINER_RUNTIME_PY3_11"]
VALID_ENVS              = ["dev", "uat", "prod"]


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

    # ── databases block ───────────────────────────────────────
    print(f"\n    Databases per environment:")
    databases = cfg.get("databases", {})
    if not databases:
        errors.append(f"{app_name}: app_config.json missing 'databases' block")
        print(f"      ✗ databases — MISSING")
    else:
        for env in VALID_ENVS:
            if env not in databases:
                errors.append(f"{app_name}: databases block missing env '{env}'")
                print(f"      ✗ databases.{env} — MISSING")
            elif not str(databases[env]).strip():
                errors.append(f"{app_name}: databases.{env} is empty")
                print(f"      ✗ databases.{env} — EMPTY")
            else:
                print(f"      ✓ databases.{env} = {databases[env]}")

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
        print(f"      ✗ main_file '{main_file}' — NOT FOUND in folder")
    else:
        print(f"      ✓ main_file '{main_file}' exists")

    # ── streamlit_app.py not empty ────────────────────────────
    app_py = app_dir / "streamlit_app.py"
    if app_py.exists() and app_py.stat().st_size == 0:
        errors.append(f"{app_name}: streamlit_app.py is empty")
        print(f"      ✗ streamlit_app.py is empty")

    # ── Runtime specific checks ───────────────────────────────
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
                warnings.append(f"{app_name}: key '{key}' is not needed for warehouse runtime")
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
            warnings.append(f"{app_name}: environment.yml is not used by container runtime")
            print(f"      ⚠ environment.yml found but not used by container runtime")

    return True