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

# Streamlit Page Config
st.set_page_config(page_title="Forget Me Not - Memory Chatbot & Voicebot", page_icon="🧠", layout="wide")
st.markdown(
    """
    <style>
    /* Background: abstract gradient */
    body {
        /* background: linear-gradient(135deg, #f0f2f5, #e0eafc); */
        background-color: #008c8c !important;
        background-attachment: fixed;
    }
    /* Streamlit container styling */
    .stApp {
        background-color: #008c8c;
        background-image: url("https://www.transparenttextures.com/patterns/argyle.png");
        background-repeat: repeat;
        background-size: auto;
        background-position: center;
        background-attachment: fixed;
    }
    /* Optional: round corners and semi-transparent chat bubbles */
    .element-container, .chat-message {
        border-radius: 12px;
        padding: 10px;
    }
      /* Header background color */
    header[data-testid="stHeader"] {
    background-color: #008c8c !important;
    background-image: url("https://www.transparenttextures.com/patterns/argyle.png");
    background-repeat: repeat;
    background-size: auto;
    background-position: center;
    background-attachment: fixed;
    }
    /* Footer background color */
    div[data-testid="stBottomBlockContainer"] {
        background-color: #008c8c !important;
        background-image: url("https://www.transparenttextures.com/patterns/argyle.png");
        background-repeat: repeat;
        background-size: auto;
        background-position: center;
        background-attachment: fixed;
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
MEMORY_FILE = "memory.json"

def load_memories():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as file:
            return json.load(file)
    return {}

def save_memory(key, value):
    memories = load_memories()
    memories[key] = value
    with open(MEMORY_FILE, "w") as file:
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
    if platform.system() == "Windows":
        time_str = reminder_time.strftime("%H:%M")
        bat_path = os.path.abspath(f"{task_name.replace(' ', '_')}_play_alarm.bat")
        with open(bat_path, "w") as f:
            f.write(r'''@echo off
powershell -c "(New-Object Media.SoundPlayer 'C:\Windows\Media\Alarm01.wav').PlaySync();"''')

        ps1_script = f'''
        $wshell = New-Object -ComObject WScript.Shell
        $wshell.Popup("{message}", 10, "{task_name}", 0x1)
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

memories = load_memories()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask me anything...")
if user_input:
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
