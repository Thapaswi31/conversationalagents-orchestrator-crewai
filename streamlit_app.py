import streamlit as st
import requests
from uuid import uuid4

API_URL = "http://localhost:8000"

st.title("Conversational Agent")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Call FastAPI backend
    with st.spinner("Agent is thinking..."):
        response = requests.post(
            f"{API_URL}/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": prompt,
            },
        )
        data = response.json()
        reply = data["reply"]

    # Show assistant reply
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)