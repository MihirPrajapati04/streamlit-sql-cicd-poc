import streamlit as st
from faker import Faker

fake = Faker()

st.title("App One — requirements.txt Test")

if st.button("Generate Fake Name"):
    st.write(fake.name())
    st.write(fake.address())
    st.write(fake.email())