import streamlit as st
import hmac
import requests


st.title("Apstra Assistant")


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.
else:
    st.caption('This is a prototype of a LangChain powered Apstra Assistant.')
    st.warning('This tool can make changes to your Apstra environment. Please use with caution.')

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.sidebar:
    st.title('Apstra Assistant')
    app_backend = st.text_input('Backend URL:', 'https://h3npgsr3cehhdgxdyh4wkbiawa0doaij.lambda-url.us-east-2.on.aws')
    apstra_url = st.text_input('Apstra URL:', "https://apstra-954fc41c-a5c9-4994-8b70-79f578dafe33.aws.apstra.com")
    username = st.text_input('Apstra username:', 'admin')
    password = st.text_input('Apstra password:', type='password')

example_messages = [
    "Does any blueprint have active anomalies?",
    "List all blueprints and the total number of active anomalies in each blueprint.",
    "List all systems associated with the blueprint 'Test Blueprint'."
]

def generate_motd():
    first_msg = "Here are a few questions you can try:\n"
    return first_msg + "\n ".join([f"- {message}" for message in example_messages])

if app_backend and apstra_url and username and password:
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(generate_motd())

    if prompt := st.chat_input("How may I assist your today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        payload = {
            "apstra_url": apstra_url,
            "username": username,
            "password": password,
            "message": prompt
        }

        with st.chat_message("assistant"):
            try:
                resp = requests.post(f"{app_backend}/chat", json=payload)
                if resp.status_code == 200:
                    resp_data = resp.json()["response"]

                st.session_state.messages.append(
                    {"role": "assistant", "content": resp_data["output"]}
                )
            except:
                st.error(f"Error: {resp.status_code} - {resp.text}")
                st.session_state.messages.append(
                    {"role": "assistant", "content": "An error occurred. Please try again."}
                )
                st.rerun()