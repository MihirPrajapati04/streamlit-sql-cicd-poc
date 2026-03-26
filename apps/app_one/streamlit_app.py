import streamlit as st
from faker import Faker

fake = Faker()

st.title("App Two — pyproject.toml Test")
st.write("This app uses the wrhs runtime. ")
st.write("It has a pyproject.toml file for dependencies, but no environment.yml.")

if st.button("Generate Fake Company"):
    st.write(fake.company())
    st.write(fake.catch_phrase())