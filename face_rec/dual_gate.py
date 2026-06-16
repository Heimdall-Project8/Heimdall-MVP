import cv2
import face_recognition
from ultralytics import YOLO
import numpy as np
import os

# --- 1. LOAD AI MODELS ---
print("Loading YOLOv8 Nano (CPU Optimized)...")
yolo_model = YOLO("yolov8n.pt") 

# --- 2. LOAD KNOWN FACES ---
KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

known_face_encodings = []
known_face_names = []

print("Loading faces from memory...")
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.endswith(".jpg") or filename.endswith(".png"):
        name = os.path.splitext(filename)[0]
        image_path = os.path.join(KNOWN_FACES_DIR, filename)
        
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if len(encodings) > 0:
            known_face_encodings.append(encodings[0])
            known_face_names.append(name)

print("System ready. Running tracking loop...")

# --- 3. PERSISTENT MEMORY STORAGE ---
# This list holds targets across frames to prevent flickering
tracked_targets = []
process_this_frame = True 

video_capture = cv2.VideoCapture(0)

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # Run YOLO to find all people in the room (Class 0)
    results = yolo_model(frame, classes=0, verbose=False)
    
    # Extract raw boxes from YOLO for this specific frame
    current_yolo_boxes = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            current_yolo_boxes.append((x1, y1, x2, y2))

    # --- HEAVY AI RECOGNITION FRAME ---
    if process_this_frame:
        new_tracked_targets = []
        
        for (x1, y1, x2, y2) in current_yolo_boxes:
            name = "Unknown Intruder"
            abs_face_box = None

            # Crop the person out for the face sniper scan
            crop_img = frame[max(0, y1-50):y2, max(0, x1-50):x2+50]
            
            if crop_img.size > 0:
                rgb_crop = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_crop, model="hog")
                
                if face_locations:
                    face_encodings = face_recognition.face_encodings(rgb_crop, face_locations)
                    
                    # Target the first face found in the crop
                    top, right, bottom, left = face_locations[0]
                    face_encoding = face_encodings[0]

                    # Match check
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.55)
                    if len(known_face_encodings) > 0:
                        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            name = known_face_names[best_match_index]

                    # Calculate exact full-screen coordinates for the face box
                    abs_face_box = (
                        left + max(0, x1-50),
                        top + max(0, y1-50),
                        right + max(0, x1-50),
                        bottom + max(0, y1-50)
                    )

            new_tracked_targets.append({
                'body_box': (x1, y1, x2, y2),
                'face_box': abs_face_box,
                'name': name
            })
        
        tracked_targets = new_tracked_targets

    # --- LIGHTWEIGHT TRACKING (SKIPPED) FRAME ---
    else:
        # We don't run Face Rec here. We map the new YOLO positions to our old identities
        updated_targets = []
        for (x1, y1, x2, y2) in current_yolo_boxes:
            assigned_name = "Analyzing Target..."
            assigned_face_box = None
            
            # Find the closest matching body from the previous frame to carry over the name
            min_distance = float('inf')
            for old_target in tracked_targets:
                ox1, oy1, _, _ = old_target['body_box']
                distance = (x1 - ox1)**2 + (y1 - oy1)**2  # Distance formula
                
                if distance < min_distance and distance < 15000: # Max 120 pixel movement drift
                    min_distance = distance
                    assigned_name = old_target['name']
                    
                    # Move the face box based on how much the body shifted (dx, dy)
                    if old_target['face_box']:
                        dx = x1 - ox1
                        dy = y1 - oy1
                        ol, ot, oright, ob = old_target['face_box']
                        assigned_face_box = (ol + dx, ot + dy, oright + dx, ob + dy)
            
            updated_targets.append({
                'body_box': (x1, y1, x2, y2),
                'face_box': assigned_face_box,
                'name': assigned_name
            })
        tracked_targets = updated_targets

    # Flip the skip-frame switch
    process_this_frame = not process_this_frame

    # --- 4. RENDER GRAPHICS (Runs smoothly every frame) ---
    for target in tracked_targets:
        bx1, by1, bx2, by2 = target['body_box']
        name = target['name']

        # Pick colors and status text based on security clearance
        if name == "Analyzing Target...":
            color = (255, 165, 0)      # Orange
            status_label = "Analyzing..."
        elif "Unknown" in name:
            color = (0, 0, 255)        # Red
            status_label = "CRITICAL: Unknown Intruder"
        else:
            color = (0, 255, 0)        # Green
            status_label = f"Access Granted: {name}"

        # Draw YOLO Body Box
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)
        cv2.putText(frame, status_label, (bx1, by1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Draw Face Box if it was successfully localized
        if target['face_box']:
            fl, ft, fr, fb = target['face_box']
            cv2.rectangle(frame, (fl, ft), (fr, fb), color, 2)
            cv2.rectangle(frame, (fl, fb - 25), (fr, fb), color, cv2.FILLED)
            cv2.putText(frame, name, (fl + 6, fb - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

    cv2.imshow('Dual-AI Security Gate', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()