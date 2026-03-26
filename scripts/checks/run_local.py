import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from check_local import validate_local

apps_root = Path("apps")
errors    = []
warnings  = []

print("\n" + "="*60)
print("  LOCAL FILE & CONFIG VALIDATION")
print("="*60)

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
    validate_local(app_dir, cfg, errors, warnings)

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
    print(f"\n  ✓  All local checks passed")
print("="*60)