import streamlit as st
import pandas as pd
import os 

st.title("App One — Native Snowflake Connection Test")
st.write(f"SNOWFLAKE_ENV_ID: {os.environ['SNOWFLAKE_ENV_ID']}")

# ── Native connection — no credentials needed ──────────────────
conn = st.connection("snowflake")

st.subheader("Raw Table Data")

st.write(f"SNOWFLAKE_ENV_ID: {os.environ['SNOWFLAKE_ENV_ID']}")
df = conn.query(
    "SELECT * FROM STREAMLIT_APP.STREAMLIT_APP_POC.TEST_EMPLOYEES"
)
st.dataframe(df)

st.subheader("Department wise Average Salary")

df_agg = conn.query("""
    SELECT 
        DEPARTMENT,
        COUNT(*)        AS HEADCOUNT,
        AVG(SALARY)     AS AVG_SALARY,
        MAX(SALARY)     AS MAX_SALARY
    FROM STREAMLIT_APP.STREAMLIT_APP_POC.TEST_EMPLOYEES
    GROUP BY DEPARTMENT
    ORDER BY AVG_SALARY DESC
""")
st.dataframe(df_agg)

st.subheader("Filter by City")

cities = conn.query(
    "SELECT DISTINCT CITY FROM STREAMLIT_APP.STREAMLIT_APP_POC.TEST_EMPLOYEES"
)
selected_city = st.selectbox("Select City", cities["CITY"].tolist())

df_filtered = conn.query(
    f"SELECT * FROM STREAMLIT_APP.STREAMLIT_APP_POC.TEST_EMPLOYEES WHERE CITY = '{selected_city}'"
)
st.dataframe(df_filtered)

st.divider()
st.subheader("Current Session Context — Before Role Switch")

context = conn.query("""
    SELECT 
        CURRENT_USER()      AS CURRENT_USER,
        CURRENT_ROLE()      AS CURRENT_ROLE,
        CURRENT_WAREHOUSE() AS CURRENT_WAREHOUSE,
        CURRENT_DATABASE()  AS CURRENT_DATABASE,
        CURRENT_SCHEMA()    AS CURRENT_SCHEMA
""")
st.dataframe(context)

# ── Switch to SYSADMIN and query ANALYTICS DB ─────────────────
st.divider()
st.subheader("ANALYTICS.ANALYTICS.DIM_CUSTOMERS — via SYSADMIN")

try:
    session = conn.session()
    session.use_role("SYSADMIN")
    session.use_warehouse("COMPUTE_WH")

    st.subheader("Current Session Context — After Role Switch")
    context_after = conn.query("""
        SELECT 
            CURRENT_USER()      AS CURRENT_USER,
            CURRENT_ROLE()      AS CURRENT_ROLE,
            CURRENT_WAREHOUSE() AS CURRENT_WAREHOUSE,
            CURRENT_DATABASE()  AS CURRENT_DATABASE,
            CURRENT_SCHEMA()    AS CURRENT_SCHEMA
    """)
    st.dataframe(context_after)

    df_customers = conn.query("""
        SELECT * FROM ANALYTICS.ANALYTICS.DIM_CUSTOMERS
        LIMIT 100
    """)
    st.success("Query successful — SYSADMIN has access to DIM_CUSTOMERS")
    st.dataframe(df_customers)

except Exception as e:
    st.error(f"Query failed — {str(e)}")
    st.warning("Possible reasons: SYSADMIN not granted to DEPLOY_ROLE, or SYSADMIN has no access to ANALYTICS DB")