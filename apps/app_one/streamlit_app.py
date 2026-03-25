import streamlit as st
from faker import Faker

fake = Faker()

st.title("App Two — pyproject.toml Test")

if st.button("Generate Fake Company"):
    st.write(fake.company())
    st.write(fake.catch_phrase())