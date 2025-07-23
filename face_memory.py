import os
import json
import cv2
from deepface import DeepFace
import streamlit as st

# ========== CONFIG ==========
BASE_FACE_FOLDER = "faces"
os.makedirs(BASE_FACE_FOLDER, exist_ok=True)

# ========== HELPERS ==========

def get_safe_email():
    email = st.session_state.get("user_email", "default")
    return email.replace("@", "_").replace(".", "_")

def get_memory_file():
    safe_email = get_safe_email()
    return os.path.join(BASE_FACE_FOLDER, f"face_memory_{safe_email}.json")

def get_face_folder():
    safe_email = get_safe_email()
    folder = os.path.join(BASE_FACE_FOLDER, safe_email)
    os.makedirs(folder, exist_ok=True)
    return folder

def save_face_memory(name, memory, img_path):
    memory_file = get_memory_file()
    data = {}
    if os.path.exists(memory_file):
        with open(memory_file, "r") as f:
            data = json.load(f)

    data[name] = {
        "image_path": img_path,
        "memory": memory
    }

    with open(memory_file, "w") as f:
        json.dump(data, f, indent=4)

# ========== REGISTER FACE ==========

def register_face():
    st.subheader("📸 Register a New Face")
    name = st.text_input("Enter the person's name:")
    memory = st.text_area("What should I remember about them?")

    if st.button("Capture Face"):
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            st.error("❌ Failed to capture image. Make sure your webcam is working.")
            return

        face_folder = get_face_folder()
        img_path = os.path.join(face_folder, f"{name}.jpg")
        cv2.imwrite(img_path, frame)
        save_face_memory(name, memory, img_path)
        st.success(f"✅ Saved memory for {name}!")

# ========== RECOGNIZE FACE ==========

def recognize_face():
    st.subheader("🔍 Recognize a Familiar Face")

    if st.button("Scan Face"):
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            st.error("❌ Failed to capture image.")
            return

        temp_path = "temp_face.jpg"
        cv2.imwrite(temp_path, frame)

        memory_file = get_memory_file()
        if not os.path.exists(memory_file):
            st.warning("⚠️ No faces registered yet for this user.")
            return

        with open(memory_file, "r") as f:
            data = json.load(f)

        for name, info in data.items():
            try:
                result = DeepFace.verify(temp_path, info["image_path"], enforce_detection=False)
                if result.get("verified"):
                    st.success(f"✅ This is **{name}**.\n\n**Memory**: {info['memory']}")
                    return
            except Exception as e:
                st.error(f"⚠️ Error comparing faces: {str(e)}")

        st.info("😕 Sorry, I don't recognize this face.")
