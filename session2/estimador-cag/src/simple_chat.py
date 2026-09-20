from dotenv import load_dotenv
from openai import OpenAI
import os
import streamlit as st

from utils import get_absolute_path

st.title("ChatGPT-like clone")

# client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
load_dotenv(f"{get_absolute_path()}/.env")

client = OpenAI()

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = os.getenv('LLM_MODEL', 'gpt-4.1-nano')

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})