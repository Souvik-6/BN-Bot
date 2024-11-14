import PIL.Image
import openai
from dotenv import load_dotenv
import time
import logging
import streamlit as st
import os
import json
from datetime import datetime
from streamlit_feedback import streamlit_feedback
from streamlit_option_menu import option_menu

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up front end configuration
st.set_page_config(
    page_title="Bachelor of Nursing Info Buddy",
    page_icon=":books:",
    layout="centered",
    initial_sidebar_state="collapsed"
)

#Setting up the password login thing
import hmac
import streamlit as st


def check_password():
    """Returns `True` if the user had a correct password."""

    def login_form():
        """Form with widgets to collect user information"""
        with st.form("Credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log in", on_click=password_entered)

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in st.secrets[
            "passwords"
        ] and hmac.compare_digest(
            st.session_state["password"],
            st.secrets.passwords[st.session_state["username"]],
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the username or password.
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    # Return True if the username + password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show inputs for username + password.
    login_form()
    if "password_correct" in st.session_state:
        st.error("😕 User not known or password incorrect")
    return False


if not check_password():
    st.stop()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()
model = "gpt-4o-mini"
assistant_id = os.getenv("ASSISTANT_ID")

# Initialize session state variables
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "thread_count" not in st.session_state:
    st.session_state.thread_count = 0
if "current_chat" not in st.session_state:
    st.session_state.current_chat = None

def save_feedback_to_file(feedback_data):
    """Save feedback to a JSON file with timestamp and thread information"""
    try:
        feedback_dir = "feedback"
        os.makedirs(feedback_dir, exist_ok=True)
        
        feedback_file = os.path.join(feedback_dir, f"feedback_{datetime.now().strftime('%Y%m')}.json")
        
        # Enhance feedback data
        feedback_data.update({
            "timestamp": datetime.now().isoformat(),
            "thread_id": st.session_state.thread_id,
            "chat_alias": st.session_state.chat_history[st.session_state.thread_id]["alias"]
        })
        
        # Load or create feedback data
        if os.path.exists(feedback_file):
            with open(feedback_file, "r", encoding="utf-8") as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []
        
        # Save feedback
        data.append(feedback_data)
        with open(feedback_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        
        logger.info(f"Feedback saved successfully: {feedback_data['feedback']}")
        return True
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        return False

def start_new_chat():
    """Initialize a new chat thread"""
    try:
        chat_thread = client.beta.threads.create()
        st.session_state.thread_id = chat_thread.id
        st.session_state.messages = []
        st.session_state.thread_count += 1
        alias = f"Chat {st.session_state.thread_count}"
        st.session_state.chat_history[chat_thread.id] = {
            "alias": alias,
            "messages": []
        }
        st.session_state.current_chat = chat_thread.id
        return chat_thread.id
    except Exception as e:
        logger.error(f"Error creating new chat: {str(e)}")
        st.error("Failed to create new chat. Please try again.")
        return None

def process_assistant_response(messages_container, prompt):
    """Process and display assistant response"""
    try:
        # Create message in thread
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt
        )
        
        # Create and run the assistant
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=assistant_id,
            instructions="Answer using provided file knowledge. Use **bold** or _underline_ for extra info."
        )
        
        with st.spinner("Assistant is thinking..."):
            while True:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    messages = client.beta.threads.messages.list(
                        thread_id=st.session_state.thread_id,
                        order="desc",
                        limit=1
                    )
                    
                    response = messages.data[0].content[0].text.value
                    return response, run.id
                
                elif run_status.status == "failed":
                    st.error("Failed to generate response. Please try again.")
                    return None, None
                
                time.sleep(0.5)
                
    except Exception as e:
        logger.error(f"Error processing assistant response: {str(e)}")
        st.error(f"An error occurred: {str(e)}")
        return None, None

def main():
    # Add logo
    try:
        image = PIL.Image.open('IHM_NEW_fixed.png')
        st.sidebar.image(image, use_column_width=True)
        st.logo(image, size="large")
    except Exception as e:
        logger.error(f"Error loading logo: {str(e)}")
    
    # App title and containers
    header_container = st.container()
    messages_container = st.container()
    input_container = st.container()
    
    with header_container:
        st.title("📚🔎 BN Buddy")
        st.write("_Ask me anything related to Bachelor of Nursing_")
    
    # Initialize chat if needed
    if not st.session_state.thread_id:
        start_new_chat()
    
    # Sidebar chat history
    with st.sidebar:
        st.write("**Chat History**")
        if st.session_state.chat_history:
            selected_chat = option_menu(
                menu_title=None,
                options=[data["alias"] for data in st.session_state.chat_history.values()],
                icons=["chat-dots"] * len(st.session_state.chat_history),
                menu_icon="cast",
                default_index=list(st.session_state.chat_history.keys()).index(st.session_state.current_chat),
            )
            
            for thread_id, data in st.session_state.chat_history.items():
                if data["alias"] == selected_chat:
                    st.session_state.current_chat = thread_id
                    st.session_state.messages = data["messages"]
                    break

        if st.button("Start New Chat"):
            start_new_chat()
            st.rerun()
    
    # Display messages
    with messages_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Fixed chat input
    with input_container:
        st.markdown('<div class="chat-input">', unsafe_allow_html=True)
        cols = st.columns([8, 1])
        with cols[0]:
            prompt = st.chat_input("Questions go here", key="chat_input")
        with cols[1]:
            if st.button("🗑️", key="delete_chat", help="Delete current chat"):
                if st.session_state.current_chat in st.session_state.chat_history:
                    del st.session_state.chat_history[st.session_state.current_chat]
                    if st.session_state.current_chat == st.session_state.thread_id:
                        start_new_chat()
                    st.session_state.current_chat = st.session_state.thread_id
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Handle chat input and response
    if prompt:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.chat_history[st.session_state.thread_id]["messages"] = st.session_state.messages
        
        with messages_container.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with messages_container.chat_message("assistant"):
            response, run_id = process_assistant_response(messages_container, prompt)
            
            if response:
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.chat_history[st.session_state.thread_id]["messages"] = st.session_state.messages
                
                # Add feedback
                with st.container():
                    st.markdown('<div class="feedback-container">', unsafe_allow_html=True)
                    feedback_key = f"feedback_{run_id}_{int(time.time())}"
                    feedback_response = streamlit_feedback(
                        feedback_type="thumbs",
                        optional_text_label="Please provide an explanation",
                        key=feedback_key
                    )
                    
                    if feedback_response:
                        feedback_data = {
                            "user_message": prompt,
                            "assistant_response": response,
                            "feedback": feedback_response
                        }
                        
                        if save_feedback_to_file(feedback_data):
                            st.toast("Thank you for your feedback! 🙏", icon="✨")
                        else:
                            st.error("Failed to save feedback. Please try again.")
                    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()