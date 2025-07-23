import time
from playsound import playsound
import edge_tts
import pygame
import streamlit as st
import os
import google.generativeai as genai
import json
import whisper
import sounddevice as sd
import numpy as np
import wave
from datetime import datetime
import asyncio
from face_memory import register_face, recognize_face
import platform, subprocess
import hashlib

USER_DATA_FILE = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)

def register_user(user_data):
    users = load_users()
    email = user_data["email"]
    if email in users:
        return False, "User already exists."
    users[email] = user_data
    save_users(users)
    return True, "Registration successful! Redirecting to bot...!"

def authenticate(email, password):
    users = load_users()
    hashed_pw = hash_password(password)
    if email in users and users[email]["password"] == hashed_pw:
        return True, users[email]
    return False, None

# Streamlit Page Config
st.set_page_config(page_title="Forget Me Not - Memory Chatbot & Voicebot", page_icon="🧠", layout="wide")
st.markdown(
    """
    <style>
    /* Background: abstract gradient */
    body {
        background: linear-gradient(135deg, #f0f2f5, #e0eafc);
        background-attachment: fixed;
        color: white; /* Default text color */
    }

    /* Streamlit container styling */
    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/cubes.png");
        background-repeat: repeat;
        background-size: auto;
        background-position: center;
        background-attachment: fixed;
        color: white; /* Ensures text inside app is white */
    }

    /* Remove white box styling */
    .element-container, .chat-message {
        background: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🧠 Forget Me Not - Memory Chatbot & Voicebot")

ContinueVoiceChat = False

# Secure API Key Handling
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Please set the Google API key in Streamlit secrets!")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Load Whisper Model
whisper_model = whisper.load_model("base")

# Memory File
# MEMORY_FILE = "memory.json"
def get_memory_file():
    user_email = st.session_state.get("user_email")
    if not user_email:
        return None
    safe_email = user_email.replace("@", "_").replace(".", "_")
    return f"memory_{safe_email}.json"

def load_memories():
    memory_file = get_memory_file()
    if not memory_file or not os.path.exists(memory_file):
        return {}
    with open(memory_file, "r") as file:
        return json.load(file)

def save_memory(key, value):
    memory_file = get_memory_file()
    if not memory_file:
        st.warning("Not logged in. Cannot save memory.")
        return
    memories = load_memories()
    memories[key] = value
    with open(memory_file, "w") as file:
        json.dump(memories, file, indent=4)

def search_memory(query):
    memories = load_memories()
    matches = [f"- {key}: {value}" for key, value in memories.items() if query.lower() in key.lower() or query.lower() in value.lower()]
    return "\n".join(matches) if matches else "I don't remember anything about that. You can tell me, and I'll remember."

def get_time():
    return datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")

def disableVoiceInput():
    global ContinueVoiceChat
    ContinueVoiceChat = False

def record_audio(filename="voice_input.wav", duration=6, sample_rate=44100):
    st.info(f"Recording for {duration} seconds... Speak now!")
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
    sd.wait()
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    st.success("Recording complete!")

def transcribe_audio(filename="voice_input.wav"):
    result = whisper_model.transcribe(filename)
    return result["text"]

def set_reminder(task_name, reminder_time, message):
    print(f"abc: {task_name}, {reminder_time}, {message}")
    if platform.system() == "Windows":
        time_str = reminder_time.strftime("%H:%M")
        print(f"abab: {time_str}")
        bat_path = os.path.abspath(f"{task_name.replace(' ', '_')}_play_alarm.bat")
        with open(bat_path, "w") as f:
            f.write(r'''@echo off
powershell -c "(New-Object Media.SoundPlayer 'C:\Windows\Media\Alarm01.wav').PlaySync();"''')

        ps1_script = f'''
        $wshell = New-Object -ComObject WScript.Shell
        $wshell.Popup("{message}", 10, "{task_name}", 0x1)
        exit
        '''
        ps1_path = os.path.abspath(f"{task_name.replace(' ', '_')}_popup.ps1")
        with open(ps1_path, "w") as file:
            file.write(ps1_script)

        cmd = f'schtasks /Create /SC ONCE /TN "{task_name}" /TR "powershell -ExecutionPolicy Bypass -File {ps1_path} & {bat_path}" /ST {time_str} /F'
        subprocess.run(cmd, shell=True)
        print(f"✅ Reminder set: {task_name} at {time_str}. A sound alarm and popup will show.")
    else:
        print("Reminder setting is currently only supported in Windows.")

async def speak_text(text, filename="assistant_reply.mp3"):
      # Clean up if file exists and isn't in use
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except PermissionError:
            # Try to force unload if pygame is using it
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            time.sleep(0.5)
            os.remove(filename)

    communicate = edge_tts.Communicate(text, voice="en-IN-NeerjaExpressiveNeural")  # You can change the voice
    await communicate.save(filename)
    
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()

    # Wait until the music finishes playing
    while pygame.mixer.music.get_busy():
        time.sleep(1)

    # Clean up and release resources
    pygame.mixer.music.unload()
    pygame.mixer.quit()

SYSTEM_PROMPT = """
You are an AI memory assistant designed to help dementia patients by providing personalized support and assistance. Your role is to facilitate clear communication, provide emotional support, and ensure the safety and well-being of the user. The system leverages advanced speech recognition and machine learning to assist with daily tasks, appointments, and medication schedules. You will also be able to bridge communication gaps between the patient and their caregivers and offer comfort and reassurance through interactive conversations, music, and activities.

Capabilities:
1. **Memory Assistance**: 
   - Remember and retrieve information about daily tasks, appointments, medication schedules, and any relevant details the user shares.
   - When the user asks for help with any of these topics, provide the appropriate information from memory.

2. **Emotional Support**:
   - Offer friendly, engaging, and compassionate conversations to help alleviate feelings of isolation and loneliness.
   - Encourage the user to engage in activities, ask about their emotional state, and provide comfort.

3. **Safety and Independence**:
   - Help the user remain independent by assisting with reminders for critical tasks, medication, and appointments.
   - If the user asks for help regarding safety (such as environmental sensors or home integration), provide helpful guidance.

4. **Music Recommendations**:
   - If the user asks for music recommendations, suggest calming or enjoyable songs that can be found on platforms like YouTube. You can recommend song names.

5. **Activity Suggestions**:
   - Recommend simple, interactive activities that the user can do to stay engaged and entertained, such as drawing, listening to music, simple exercises, or reading.
   - Example Response: "How about we try a fun activity? You could try drawing, doing a short walk around the house, or I can guide you through a mindfulness breathing exercise."

6. **Context Awareness**:
   - Be aware of the context, including any previous interactions, to ensure responses are relevant and personalized.
   - Provide responses that are supportive and considerate, making the user feel heard and cared for.

7. **Response Format**:
   - If storing new memories: start the response with [CALL:store_memory] {"key": "<memory summary>", "value": "<full memory>"}
   - If retrieving memories: start the response with [CALL:retrieve_memory] {"query": "<user query>"}
   - If the user asks for **time**, start the response with [CALL:get_time] as this uses the `get_time` function.
   - if users ask to stop the voice input mode, respond with [CALL:disableVoiceInput] as this calls the `disableVoiceInput` function.
   - If the user asks to set a reminder, respond with: `[CALL:set_reminder] {"task_name": "<title>", "reminder_time": "<HH:MM 24hr>", "message": "<what to remind>"}`
   - If the user asks for **reminders** (such as tasks, medications, or appointments), ensure they are clearly explained, referencing the stored memories.
   - If no memory is found on a specific topic: "I don't remember anything about that. Please tell me, and I'll remember."

8. **Behavior Guidelines**:
   - Provide responses that are **calm**, **reassuring**, and **clear**.
   - Use simple, direct language and repeat information if necessary.
   - Engage the user regularly to avoid isolation, suggest activities, or ask about their feelings or well-being.
   - If you are answering queries related to the current memories, don't ask for confirmation, just say very confidently, this is what I remembered about you.
   User is having a fully belief in you as you have are their memory assistant. asking confirmation will lose that.

Before responding, always check if the user's query relates to stored memories or context, such as daily tasks, medications, appointments, or previous conversations.

If the user asks for **music** or **activities**, offer calming songs and simple, cognitive-friendly activities to keep them engaged and emotionally supported.

Current Memories are: \n
"""

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I'm your memory assistant. What would you like to share or ask?"}]


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:

    # auth_tab = st.tabs(["🔐 Login", "📝 Register"])[0]

    with st.sidebar:
        st.title("🧠 Memory Assistant Login")
        choice = st.radio("Choose:", ["Register", "Login"])

    if choice == "Register":
        with st.form("register_form", clear_on_submit=False):
            st.subheader("Create Account")
            name = st.text_input("Name")
            email = st.text_input("Email")
            age = st.number_input("Age", min_value=0, max_value=120, step=1)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            dementia = st.selectbox("Are you suffering from dementia?", ["Yes", "No"])
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            security_q = st.selectbox("Security Question", [
                "What is your favorite food?",
                "What is your mother's maiden name?",
                "What city were you born in?",
                "What is the name of your first pet?"
            ])
            security_a = st.text_input("Answer to Security Question")
            submit = st.form_submit_button("Register")

            if submit:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                elif not all([name, email, password, confirm_password, security_a]):
                    st.error("Please fill all fields.")
                else:
                    success, msg = register_user({
                        "name": name,
                        "email": email,
                        "age": age,
                        "gender": gender,
                        "dementia": dementia,
                        "password": hash_password(password),
                        "security_question": security_q,
                        "security_answer": security_a
                    })
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_email = email
                        st.session_state.user_profile = {
                            "name": name, "email": email, "age": age, "gender": gender,
                            "dementia": dementia, "password": hash_password(password),
                            "security_question": security_q, "security_answer": security_a
                        }
                        st.success(msg)
                        st.rerun()  # 👈 Refresh to show bot
                    else:
                        st.error(msg)

    elif choice == "Login":
        with st.form("login_form"):
            st.subheader("Welcome Back")
            login_email = st.text_input("Email")
            login_password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")

            if login_btn:
                success, user = authenticate(login_email, login_password)
                if success:
                    st.success("Login successful!")                    
                    st.session_state.authenticated = True
                    st.session_state.user_email = login_email
                    st.session_state.user_profile = user  # ← Save full user profile
                    st.rerun()  # 👈 Refresh to show bot

                else:
                    st.error("Invalid credentials.")
    st.stop()  # prevent further code execution if not logged in


if st.session_state.get("authenticated"):
    user_email = st.session_state.get("user_email")
    if user_email:
        safe_email = user_email.replace("@", "_").replace(".", "_")
        MEMORY_FILE = f"memory_{safe_email}.json"
        
    with st.sidebar:
        user = st.session_state.get("user_profile", {})
        st.markdown("## 👤 Profile Info")
        st.markdown(f"**Name:** {user.get('name')}")
        st.markdown(f"**Email:** {user.get('email')}")
        st.markdown(f"**Age:** {user.get('age')}")
        st.markdown(f"**Gender:** {user.get('gender')}")
        st.markdown(f"**Dementia:** {user.get('dementia')}")
        st.markdown("---")

        if st.button("🚪 Logout"):
            for key in ["authenticated", "user_email", "user_profile"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

user = st.session_state.get("user_profile", {})
st.success(f"👋 Welcome back, {user.get('name', 'User')}!")

memories = load_memories()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask me anything...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    user = st.session_state.get("user_profile", {})
    user_profile_text = f"""
    User Profile:
    - Name: {user.get("name")}
    - Age: {user.get("age")}
    - Gender: {user.get("gender")}
    - Dementia: {user.get("dementia")}
    """
    memory_text = user_profile_text + "\n\n" + "\n".join([f"{key}: {value}" for key, value in memories.items()])

    messages = [{"role": "assistant", "parts": [SYSTEM_PROMPT + memory_text]}] + [
        {"role": msg["role"], "parts": [msg["content"]]} for msg in st.session_state.messages
    ]

    try:
        response = model.generate_content(messages)
        assistant_reply = response.text.strip()

        if assistant_reply.startswith("[CALL:store_memory]"):
            json_data = assistant_reply[len("[CALL:store_memory]"):].strip()
            json_start = json_data.find("{")
            json_end = json_data.rfind("}") + 1
            json_data = json_data[json_start:json_end].strip()
            params = json.loads(json_data)
            save_memory(params.get("key"), params.get("value"))
            natural_reply = assistant_reply[len("[CALL:store_memory]") + len(json_data)+1:].strip()
            assistant_reply = natural_reply if natural_reply else "Got it! I'll remember that."

        elif assistant_reply.startswith("[CALL:retrieve_memory]"):
            json_data = assistant_reply[len("[CALL:retrieve_memory]"):].strip()
            json_start = json_data.find("{")
            json_end = json_data.rfind("}") + 1
            json_data = json_data[json_start:json_end].strip()
            params = json.loads(json_data)
            assistant_reply = search_memory(params.get("query"))

        elif assistant_reply.startswith("[CALL:get_time]"):
            assistant_reply = get_time()

        elif assistant_reply.startswith("[CALL:set_reminder]"):
            json_data = assistant_reply[len("[CALL:set_reminder]"):].strip()
            json_start = json_data.find("{")
            json_end = json_data.rfind("}") + 1
            json_data = json_data[json_start:json_end].strip()
            params = json.loads(json_data)
            reminder_time = datetime.strptime(params.get("reminder_time"), "%H:%M")
            set_reminder(params.get("task_name"), reminder_time, params.get("message"))
            assistant_reply = f"Got it! I’ve set a reminder for '{params.get('task_name')}' at {params.get('reminder_time')}."

    except Exception as e:
        assistant_reply = f"Error: {str(e)}"
        st.error(assistant_reply)

    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    with st.chat_message("assistant"):
        st.markdown(assistant_reply)
        # asyncio.run(speak_text(assistant_reply))
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(speak_text(assistant_reply))

if st.button("🎤 Start Voice Chat"):
    if st.button("🛑 Stop Voice Chat"):
        disableVoiceInput()
    ContinueVoiceChat = True

    async def continuous_voice_chat():
        while ContinueVoiceChat:
            record_audio()
            user_input = transcribe_audio()
            st.success(f"You said: {user_input}")

            if user_input.lower() in ["exit", "stop", "quit"]:
                st.warning("Voice chat stopped.")
                break

            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            memory_text = "\n".join([f"{key}: {value}" for key, value in memories.items()])
            messages = [{"role": "assistant", "parts": [SYSTEM_PROMPT + memory_text]}] + [
                {"role": msg["role"], "parts": [msg["content"]]} for msg in st.session_state.messages
            ]

            try:
                response = model.generate_content(messages)
                assistant_reply = response.text.strip()

                if assistant_reply.startswith("[CALL:store_memory]"):
                    json_data = assistant_reply[len("[CALL:store_memory]"):].strip()
                    json_start = json_data.find("{")
                    json_end = json_data.rfind("}") + 1
                    json_data = json_data[json_start:json_end].strip()
                    params = json.loads(json_data)
                    save_memory(params.get("key"), params.get("value"))
                    natural_reply = assistant_reply[len("[CALL:store_memory]") + len(json_data)+1:].strip()
                    assistant_reply = natural_reply if natural_reply else "Got it! I'll remember that."

                elif assistant_reply.startswith("[CALL:retrieve_memory]"):
                    json_data = assistant_reply[len("[CALL:retrieve_memory]"):].strip()
                    json_start = json_data.find("{")
                    json_end = json_data.rfind("}") + 1
                    json_data = json_data[json_start:json_end].strip()
                    params = json.loads(json_data)
                    assistant_reply = search_memory(params.get("query"))

                elif assistant_reply.startswith("[CALL:get_time]"):
                    assistant_reply = get_time()

                elif "[CALL:disableVoiceInput]" in assistant_reply:
                    disableVoiceInput()
                    assistant_reply = "Disabling Voice Input"

            except Exception as e:
                assistant_reply = f"Error: {str(e)}"
                st.error(assistant_reply)

            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
            with st.chat_message("assistant"):
                st.markdown(assistant_reply)
                await speak_text(assistant_reply)

            time.sleep(1)

    asyncio.run(continuous_voice_chat())

with st.expander("👤 Face Recognition"):
    register_face()
    recognize_face()
