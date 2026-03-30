import streamlit as st
from faker import Faker
import os 

fake = Faker()

st.title("App One — pyproject.toml Test")
st.write(f"SNOWFLAKE_ENV_ID: {os.environ['SNOWFLAKE_ENV_ID']}")
st.write(f"SNOWFLAKE_ENV: {os.environ['SNOWFLAKE_ENV']}")



st.write("This app uses the wrhs runtime. ")
st.write("It has a pyproject.toml file for dependencies, but no environment.yml.")
st.write("This tests that the deployment process correctly handles pyproject.toml without environment.yml for a warehouse runtime app.")

if st.button("Generate Fake Company"):
    st.write(fake.company())
    st.write(fake.catch_phrase())
    st.write(fake.bs())
    st.write(fake.address())