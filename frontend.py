import streamlit as st
import hmac
import requests


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

# Set up the chat page layout
st.title("Apstra Assistant")
st.caption('This is a prototype of a LangChain powered Apstra Assistant.')
st.warning('This tool can make changes to your Apstra environment. Please use with caution.')

# Initialize chat history in session state if not already initialized
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

with st.sidebar:
    st.title('Apstra Assistant')
    app_backend = st.text_input('Backend URL:', 'https://h3npgsr3cehhdgxdyh4wkbiawa0doaij.lambda-url.us-east-2.on.aws')
    apstra_url = st.text_input('Apstra URL:', "https://apstra-954fc41c-a5c9-4994-8b70-79f578dafe33.aws.apstra.com")
    username = st.text_input('Apstra username:', 'admin')
    password = st.text_input('Apstra password:', type='password')

# Display chat history
for chat in st.session_state["chat_history"]:
    st.write(f"**{chat['role']}:** {chat['content']}")

# Check if all required parameters are provided
if app_backend and apstra_url and username and password:
    # Display a text input box for the chat
    user_message = st.text_input("Your Message", placeholder="Does any blueprint have active anomalies?")

    # Send the message when the user presses Enter or clicks Send
    if st.button("Send") and user_message:
        # Prepare the payload for the POST request
        payload = {
            "apstra_url": apstra_url,
            "username": username,
            "password": password,
            "message": user_message
        }

        # Send the POST request
        try:
            response = requests.post(f"{app_backend}/chat", json=payload)
            if response.status_code == 200:
                response_data = response.json()

                # Append user and assistant messages to chat history
                st.session_state["chat_history"].append({"role": "You", "content": user_message})
                st.session_state["chat_history"].append(
                    {"role": "Apstra Assistant", "content": response_data.get("response", "No response from server")})
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Error: {str(e)}")