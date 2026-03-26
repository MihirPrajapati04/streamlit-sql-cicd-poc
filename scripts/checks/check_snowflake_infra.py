def check_database(cursor, db, app_name, errors, warnings):
    print(f"\n    Checking database '{db}'...")
    try:
        cursor.execute(f"SHOW DATABASES LIKE '{db}'")
        result = cursor.fetchall()
        if not result:
            errors.append(f"{app_name}: database '{db}' does not exist or is not accessible")
            print(f"      ✗ database '{db}' — NOT FOUND")
            return False
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
            errors.append(
                f"{app_name}: warehouse '{warehouse}' does not exist or is not accessible"
            )
            print(f"      ✗ warehouse '{warehouse}' — NOT FOUND")
            return False
        col_names = [desc[0].lower() for desc in cursor.description]
        row       = dict(zip(col_names, result[0]))
        wh_state  = row.get("state", "UNKNOWN")
        wh_size   = row.get("size", "UNKNOWN")
        if wh_state in ("STARTED", "SUSPENDED", "RESIZING"):
            print(f"      ✓ warehouse '{warehouse}' exists — size: {wh_size}, state: {wh_state}")
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
                f"will be created automatically during deploy"
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
        col_names  = [desc[0].lower() for desc in cursor.description]
        row        = dict(zip(col_names, result[0]))
        pool_state = row.get("state", "UNKNOWN")
        pool_size  = row.get("instance_family", "UNKNOWN")
        if pool_state in ("ACTIVE", "IDLE"):
            print(f"      ✓ compute pool '{compute_pool}' — size: {pool_size}, state: {pool_state}")
        elif pool_state == "STARTING":
            warnings.append(
                f"{app_name}: compute pool '{compute_pool}' is still STARTING — "
                f"may not be ready when the app deploys"
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