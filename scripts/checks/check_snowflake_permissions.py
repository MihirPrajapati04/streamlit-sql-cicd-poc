def check_role_permissions(cursor, db, schema, warehouse, role, app_name, errors, warnings):
    print(f"\n    Checking permissions for role '{role}'...")

    checks = [
        {
            "sql":       f"SHOW GRANTS ON DATABASE {db}",
            "privilege": "USAGE",
            "label":     f"USAGE on DATABASE {db}",
            "error_msg": f"does not have USAGE on database '{db}'"
        },
        {
            "sql":       f"SHOW GRANTS ON SCHEMA {db}.{schema}",
            "privilege": "USAGE",
            "label":     f"USAGE on SCHEMA {db}.{schema}",
            "error_msg": f"does not have USAGE on schema '{db}.{schema}'"
        },
        {
            "sql":       f"SHOW GRANTS ON SCHEMA {db}.{schema}",
            "privilege": "CREATE STREAMLIT",
            "label":     f"CREATE STREAMLIT on SCHEMA {db}.{schema}",
            "error_msg": f"does not have CREATE STREAMLIT on schema '{db}.{schema}'"
        },
        {
            "sql":       f"SHOW GRANTS ON SCHEMA {db}.{schema}",
            "privilege": "CREATE STAGE",
            "label":     f"CREATE STAGE on SCHEMA {db}.{schema}",
            "error_msg": f"does not have CREATE STAGE on schema '{db}.{schema}'"
        },
        {
            "sql":       f"SHOW GRANTS ON WAREHOUSE {warehouse}",
            "privilege": "USAGE",
            "label":     f"USAGE on WAREHOUSE {warehouse}",
            "error_msg": f"does not have USAGE on warehouse '{warehouse}'"
        },
    ]

    for check in checks:
        try:
            cursor.execute(check["sql"])
            grants  = cursor.fetchall()
            granted = any(
                row[1] == check["privilege"] and row[5].upper() == role.upper()
                for row in grants
            )
            if granted:
                print(f"      ✓ {check['label']} — granted to {role}")
            else:
                errors.append(f"{app_name}: DEPLOY_ROLE '{role}' {check['error_msg']}")
                print(f"      ✗ {check['label']} — NOT granted to {role}")
        except Exception as e:
            warnings.append(f"{app_name}: could not verify {check['label']} — {e}")
            print(f"      ⚠ could not verify {check['label']} — {e}")