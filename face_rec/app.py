import cv2
import face_recognition
import numpy as np
import os

# --- 1. SETUP STORAGE & MEMORY ---
KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

known_face_encodings = []
known_face_names = []

print("Booting system and loading face embeddings from disk...")
# Automatically load every saved mathematical vector profile
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.endswith(".npy"):  # Look for NumPy binary files instead of images
        name = os.path.splitext(filename)[0]
        file_path = os.path.join(KNOWN_FACES_DIR, filename)
        
        # Fast direct load: No image decoding or AI parsing required on boot
        encoding = np.load(file_path)
        
        known_face_encodings.append(encoding)
        known_face_names.append(name)

print(f"System ready. Loaded {len(known_face_names)} profiles instantly.")
print("-----------------------------------------")
print("HOTKEYS:")
print("[r] - Register a new face embedding from the live feed")
print("[q] - Quit system")
print("-----------------------------------------")

# --- 2. INITIALIZE CAMERA ---
video_capture = cv2.VideoCapture(0)

face_locations = []
face_encodings = []
face_names = []
process_this_frame = True

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # OPTIMIZATION 1: Resize frame to 1/4 size
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # OPTIMIZATION 2: Skip-frame logic
    if process_this_frame:
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
            name = "Unknown"

            if len(known_face_encodings) > 0:
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = known_face_names[best_match_index]

            face_names.append(name)

    process_this_frame = not process_this_frame

    # --- 3. DISPLAY RESULTS ---
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4

        color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

    cv2.imshow('Video', frame)

    # --- 4. KEYBOARD CONTROLS ---
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        break
    
    elif key == ord('r'):
        # --- REGISTRATION MODE ---
        print("\n[!] Registration Triggered.")
        
        ret, reg_frame = video_capture.read()
        rgb_reg_frame = cv2.cvtColor(reg_frame, cv2.COLOR_BGR2RGB)
        
        print("Scanning for face...")
        reg_locations = face_recognition.face_locations(rgb_reg_frame, model="hog")
        
        if len(reg_locations) == 0:
            print("[X] Failed: No face detected. Try again.")
        elif len(reg_locations) > 1:
            print("[X] Failed: Multiple faces detected. Please stand alone.")
        else:
            print("[✓] Face locked.")
            name = input(">> ENTER NAME FOR THIS USER: ")
            
            if name.strip():
                # Extract the 128-point math encoding array
                reg_encoding = face_recognition.face_encodings(rgb_reg_frame, reg_locations)[0]
                
                # 1. Add them to live memory so they are recognized instantly
                known_face_encodings.append(reg_encoding)
                known_face_names.append(name)
                
                # 2. Save the array to disk as a binary file instead of saving the raw picture
                save_path = os.path.join(KNOWN_FACES_DIR, f"{name}.npy")
                np.save(save_path, reg_encoding)
                
                print(f"[✓] Success! Vector embedding for {name} has been secured to disk.")
            else:
                print("[X] Registration cancelled.")
        
        print("Resuming live feed...\n")

video_capture.release()
cv2.destroyAllWindows()