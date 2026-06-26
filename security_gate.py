import customtkinter as ctk
import cv2
import face_recognition
from ultralytics import YOLO
import numpy as np
from PIL import Image, ImageTk
import threading
import time
import os
from datetime import datetime
from pymongo import MongoClient

# --- 1. GLOBAL STATE & THEME ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LATEST_FRAME = None
FRAME_LOCK = threading.Lock()

# Toggle switches to control what the AI looks for
SCAN_MODE = "FACE" 
QR_RESULT = None

# --- 2. MONGODB CONFIGURATION ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "SecuritySystem"
COLLECTION_NAME = "incidents"

try:
    print("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = mongo_client[DB_NAME]
    incident_collection = db[COLLECTION_NAME]
    pre_approval_collection = db["pre_approvals"]
    print("MongoDB Connected Successfully.")
except Exception as e:
    print(f"MongoDB Connection Failed: {e}")
    incident_collection = None
    pre_approval_collection = None

def async_db_log(payload, is_tailgate=False):
    if incident_collection is None: return
    try:
        incident_collection.insert_one(payload)
        if is_tailgate:
            print(f"[!!! TAILGATE ALARM !!!] {payload['metrics']['intruder_count']} Intruders followed {payload['resident_compromised']}!")
        else:
            print(f"[DB LOG] Saved {payload['incident_type']}: {payload['identity']}")
    except Exception as e:
        pass

# --- 3. LOAD AI MODELS & FACES ---
print("Loading YOLOv8 Nano...")
yolo_model = YOLO("yolov8n.pt") 

KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
known_face_encodings = []
known_face_names = []

print("Loading facial embeddings...")
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.endswith(".npy"):
        name = os.path.splitext(filename)[0]
        file_path = os.path.join(KNOWN_FACES_DIR, filename)
        known_face_encodings.append(np.load(file_path))
        known_face_names.append(name)

print(f"System ready. Loaded {len(known_face_names)} profiles instantly.")

# --- 4. BACKGROUND AI ENGINE ---
def run_ai_engine():
    global LATEST_FRAME, known_face_encodings, known_face_names, SCAN_MODE, QR_RESULT
    cap = cv2.VideoCapture(0)
    qr_detector = cv2.QRCodeDetector() 
    
    tracked_targets = []
    process_this_frame = True 
    active_logs = {}
    COOLDOWN_SECONDS = 30  

    last_authorized_time = None
    last_authorized_name = "None"
    last_tailgate_log_time = datetime.min
    TAILGATE_TIME_WINDOW, TAILGATE_DISTANCE_LIMIT, TAILGATE_COOLDOWN = 5.0, 250, 10.0
    MATCH_DISTANCE_THRESHOLD = 15000 
    
    while True:
        for _ in range(2): cap.grab()
        ret, frame = cap.read()
        if not ret: continue
        
        frame = cv2.resize(frame, (640, 480))

        # ==========================================
        # QR SCANNING LOGIC 
        # ==========================================
        if SCAN_MODE == "QR":
            data, bbox, _ = qr_detector.detectAndDecode(frame)
            
            if bbox is not None and len(bbox) > 0:
                pts = bbox[0].astype(int)
                for i in range(len(pts)):
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i+1) % len(pts)]), (0, 255, 255), 3)
                    
            if data and QR_RESULT is None:
                # STRIP WHITESPACE OFF THE END OF THE QR CODE
                clean_data = data.strip()
                QR_RESULT = clean_data
                print(f"\n[SYSTEM] Successfully locked onto QR Code: '{clean_data}'")

            with FRAME_LOCK:
                LATEST_FRAME = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            continue

        elif SCAN_MODE == "PROCESSING":
            # The UI is querying MongoDB. Stop running AI and just push the empty camera feed.
            with FRAME_LOCK:
                LATEST_FRAME = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            continue
        # ==========================================

        results = yolo_model(frame, classes=0, conf=0.5, iou=0.3, verbose=False)
        current_yolo_boxes = [(int(x1), int(y1), int(x2), int(y2)) for r in results for x1, y1, x2, y2 in r.boxes.xyxy]
        
        new_tracked_targets = []
        claimed_old_targets = set()
        active_names_in_frame = set() 

        for (x1, y1, x2, y2) in current_yolo_boxes:
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            
            matched_old_target, min_distance = None, float('inf')
            matched_index = -1
            
            for i, old_target in enumerate(tracked_targets):
                if i in claimed_old_targets: continue 
                ox1, oy1, ox2, oy2 = old_target['body_box']
                ocenter_x, ocenter_y = (ox1 + ox2) // 2, (oy1 + oy2) // 2
                distance = (center_x - ocenter_x)**2 + (center_y - ocenter_y)**2
                
                if distance < min_distance and distance < MATCH_DISTANCE_THRESHOLD:
                    min_distance = distance
                    matched_old_target = old_target
                    matched_index = i

            if matched_old_target:
                claimed_old_targets.add(matched_index) 
                assigned_name, assigned_face_box = matched_old_target['name'], matched_old_target['face_box']
                if assigned_face_box:
                    dx, dy = x1 - matched_old_target['body_box'][0], y1 - matched_old_target['body_box'][1]
                    assigned_face_box = (assigned_face_box[0]+dx, assigned_face_box[1]+dy, assigned_face_box[2]+dx, assigned_face_box[3]+dy)
            else:
                assigned_name = "Analyzing Target..." if process_this_frame else "Unknown Intruder"
                assigned_face_box = None

            if process_this_frame and assigned_name in ["Analyzing Target...", "Unknown Intruder"]:
                crop_img = frame[max(0, y1-50):y2, max(0, x1-50):x2+50]
                if crop_img.size > 0:
                    rgb_crop = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                    face_locations = face_recognition.face_locations(rgb_crop, model="hog")
                    if face_locations:
                        face_encodings = face_recognition.face_encodings(rgb_crop, face_locations)
                        top, right, bottom, left = face_locations[0]
                        matches = face_recognition.compare_faces(known_face_encodings, face_encodings[0], tolerance=0.65)
                        if len(known_face_encodings) > 0:
                            face_distances = face_recognition.face_distance(known_face_encodings, face_encodings[0])
                            best_match_index = np.argmin(face_distances)
                            if matches[best_match_index]: assigned_name = known_face_names[best_match_index]
                            else: assigned_name = "Unknown Intruder"
                        else: assigned_name = "Unknown Intruder"
                        assigned_face_box = (left + max(0, x1-50), top + max(0, y1-50), right + max(0, x1-50), bottom + max(0, y1-50))

            if assigned_name not in ["Analyzing Target...", "Unknown Intruder"]:
                if assigned_name in active_names_in_frame:
                    assigned_name = "Unknown Intruder"
                else:
                    active_names_in_frame.add(assigned_name)

            new_tracked_targets.append({'body_box': (x1, y1, x2, y2), 'face_box': assigned_face_box, 'name': assigned_name})
        
        tracked_targets = new_tracked_targets
        process_this_frame = not process_this_frame

        current_time = datetime.now()
        auth_positions, unknown_positions = [], []

        for target in tracked_targets:
            bx1, by1, bx2, by2 = target['body_box']
            raw_name = target['name']
            if raw_name == "Analyzing Target...": continue
            
            center_x, center_y = (bx1 + bx2) // 2, (by1 + by2) // 2
            
            if raw_name == "Unknown Intruder": 
                unknown_positions.append((center_x, center_y, target['body_box'], target['face_box']))
            elif not raw_name.startswith("BLACKLIST_"):
                auth_positions.append((center_x, center_y, raw_name))
                last_authorized_time, last_authorized_name = current_time, raw_name
            
            should_log = raw_name not in active_logs or (current_time - active_logs[raw_name]).total_seconds() > COOLDOWN_SECONDS
            if should_log and incident_collection is not None:
                status = "CRITICAL_BLACKLIST_BREACH" if raw_name.startswith("BLACKLIST_") else ("CRITICAL_BREACH" if raw_name == "Unknown Intruder" else "AUTHORIZED_ACCESS")
                inc_type = "BLACKLISTED_ENTRY" if raw_name.startswith("BLACKLIST_") else "STANDARD_ENTRY"
                payload = {"timestamp": current_time, "incident_type": inc_type, "identity": raw_name.replace("BLACKLIST_", ""), "clearance_status": status, "bounding_boxes": {"body": target['body_box'], "face": target['face_box']}}
                threading.Thread(target=async_db_log, args=(payload, False)).start()
                active_logs[raw_name] = current_time

            color = (0, 0, 255) if "Unknown" in raw_name or "BLACKLIST" in raw_name else ((255, 165, 0) if "Analyzing" in raw_name else (0, 255, 0))
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)
            cv2.putText(frame, raw_name.replace("BLACKLIST_", ""), (bx1, by1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if target['face_box']:
                fl, ft, fr, fb = target['face_box']
                cv2.rectangle(frame, (fl, ft), (fr, fb), color, 2)
                cv2.rectangle(frame, (fl, fb - 25), (fr, fb), color, cv2.FILLED)
                cv2.putText(frame, raw_name.replace("BLACKLIST_", ""), (fl + 6, fb - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

        if incident_collection is not None and (current_time - last_tailgate_log_time).total_seconds() > TAILGATE_COOLDOWN:
            tailgate_triggered = False
            for ax, ay, resident_name in auth_positions:
                tailgating_intruders = []
                min_distance = float('inf')
                for ux, uy, u_body, u_face in unknown_positions:
                    distance = ((ax - ux)**2 + (ay - uy)**2)**0.5
                    if distance < TAILGATE_DISTANCE_LIMIT:
                        tailgating_intruders.append({"body": u_body, "face": u_face})
                        min_distance = min(min_distance, distance)
                
                if tailgating_intruders:
                    tailgate_triggered = True
                    payload = {"timestamp": current_time, "date_string": current_time.strftime("%Y-%m-%d %H:%M:%S"), "incident_type": "TAILGATING_SPATIAL", "clearance_status": "HIGH_ALERT_BREACH", "resident_compromised": resident_name, "metrics": {"intruder_count": len(tailgating_intruders), "closest_distance_pixels": round(min_distance, 1), "time_delta_seconds": 0.0}, "intruders_data": tailgating_intruders}
                    threading.Thread(target=async_db_log, args=(payload, True)).start()
                    last_tailgate_log_time = current_time
                    break

            if not tailgate_triggered and last_authorized_time and unknown_positions:
                time_delta = (current_time - last_authorized_time).total_seconds()
                if 0 < time_delta <= TAILGATE_TIME_WINDOW:
                    tailgating_intruders = [{"body": u[2], "face": u[3]} for u in unknown_positions]
                    tailgate_triggered = True
                    payload = {"timestamp": current_time, "date_string": current_time.strftime("%Y-%m-%d %H:%M:%S"), "incident_type": "TAILGATING_TEMPORAL", "clearance_status": "HIGH_ALERT_BREACH", "resident_compromised": last_authorized_name, "metrics": {"intruder_count": len(tailgating_intruders), "closest_distance_pixels": None, "time_delta_seconds": round(time_delta, 2)}, "intruders_data": tailgating_intruders}
                    threading.Thread(target=async_db_log, args=(payload, True)).start()
                    last_tailgate_log_time = current_time

        with FRAME_LOCK:
            LATEST_FRAME = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

# --- 5. MODERN KIOSK APPLICATION ---
class SecurityKioskApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Security Gate")
        self.geometry("900x700")
        
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both")

        self.build_idle_screen()
        self.build_menu_screen()
        self.build_visiting_help_screen()
        self.build_vendor_screen()
        self.build_visitor_screen()
        self.build_status_screen()
        
        self.update_video_feed()
        self.show_screen(self.idle_frame)

    def show_screen(self, frame_to_show):
        for frame in [self.idle_frame, self.menu_frame, self.visiting_help_frame, self.vendor_frame, self.visitor_frame, self.status_frame]:
            frame.pack_forget()
        frame_to_show.pack(expand=True, fill="both")

    def build_idle_screen(self):
        self.idle_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        ctk.CTkLabel(self.idle_frame, text="Scanning for Approved Residents...", font=("Helvetica", 24, "bold")).pack(pady=20)
        self.video_canvas_idle = ctk.CTkLabel(self.idle_frame, text="")
        self.video_canvas_idle.pack(pady=10)
        ctk.CTkButton(self.idle_frame, text="Other Access", font=("Helvetica", 18), height=50, width=200, command=lambda: self.show_screen(self.menu_frame)).pack(pady=30)

    def build_menu_screen(self):
        self.menu_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        ctk.CTkLabel(self.menu_frame, text="Select Access Type", font=("Helvetica", 28, "bold")).pack(pady=60)
        ctk.CTkButton(self.menu_frame, text="Visiting Help Setup", font=("Helvetica", 20), height=60, width=300, command=lambda: self.show_screen(self.visiting_help_frame)).pack(pady=15)
        ctk.CTkButton(self.menu_frame, text="Delivery / Vendor", font=("Helvetica", 20), height=60, width=300, command=lambda: self.show_screen(self.vendor_frame)).pack(pady=15)
        ctk.CTkButton(self.menu_frame, text="Visitor", font=("Helvetica", 20), height=60, width=300, command=lambda: self.show_screen(self.visitor_frame)).pack(pady=15)
        ctk.CTkButton(self.menu_frame, text="Back to Camera", font=("Helvetica", 18), fg_color="#b30000", hover_color="#800000", height=50, width=200, command=self.return_to_home).pack(pady=40)

    def build_visiting_help_screen(self):
        self.visiting_help_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        ctk.CTkLabel(self.visiting_help_frame, text="New Help Setup", font=("Helvetica", 24, "bold")).pack(pady=10)
        self.video_canvas_setup = ctk.CTkLabel(self.visiting_help_frame, text="")
        self.video_canvas_setup.pack(pady=10)
        self.flat_entry = ctk.CTkEntry(self.visiting_help_frame, placeholder_text="Enter Flat No.", font=("Helvetica", 16), width=250, height=40)
        self.flat_entry.pack(pady=10)
        self.name_entry = ctk.CTkEntry(self.visiting_help_frame, placeholder_text="Enter Name", font=("Helvetica", 16), width=250, height=40)
        self.name_entry.pack(pady=10)
        ctk.CTkButton(self.visiting_help_frame, text="Capture & Register Face", font=("Helvetica", 18), height=50, width=250, command=self.submit_help_request).pack(pady=10)
        ctk.CTkButton(self.visiting_help_frame, text="Cancel", font=("Helvetica", 16), fg_color="#b30000", hover_color="#800000", command=lambda: self.show_screen(self.menu_frame)).pack(pady=10)

    def build_vendor_screen(self):
        self.vendor_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        ctk.CTkLabel(self.vendor_frame, text="Vendor / Delivery Access", font=("Helvetica", 28, "bold")).pack(pady=40)
        ctk.CTkLabel(self.vendor_frame, text="Enter Destination Flat Number:", font=("Helvetica", 18)).pack(pady=(20, 0))
        self.vendor_flat_entry = ctk.CTkEntry(self.vendor_frame, placeholder_text="e.g. 402", font=("Helvetica", 20), width=300, height=50, border_color="#555555", border_width=2)
        self.vendor_flat_entry.pack(pady=(5, 20))
        ctk.CTkButton(self.vendor_frame, text="Check Pre-Approval", font=("Helvetica", 20), height=60, width=300, command=self.check_vendor_approval).pack(pady=10)
        ctk.CTkLabel(self.vendor_frame, text="— OR —", font=("Helvetica", 16)).pack(pady=10)
        ctk.CTkButton(self.vendor_frame, text="Request Access from Resident", font=("Helvetica", 18), height=50, width=300, fg_color="#cc7000", hover_color="#b35f00", command=lambda: self.trigger_approval_wait(self.vendor_flat_entry.get(), "Vendor")).pack(pady=10)
        ctk.CTkButton(self.vendor_frame, text="Back", font=("Helvetica", 16), fg_color="#b30000", hover_color="#800000", command=lambda: self.show_screen(self.menu_frame)).pack(pady=30)

    def build_visitor_screen(self):
        self.visitor_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        ctk.CTkLabel(self.visitor_frame, text="Visitor Entry", font=("Helvetica", 28, "bold")).pack(pady=40)
        ctk.CTkButton(self.visitor_frame, text="Scan QR Code", font=("Helvetica", 20), height=60, width=300, command=self.start_qr_scan).pack(pady=10)
        ctk.CTkLabel(self.visitor_frame, text="— OR —", font=("Helvetica", 16)).pack(pady=10)
        ctk.CTkLabel(self.visitor_frame, text="Enter Destination Flat Number:", font=("Helvetica", 18)).pack(pady=(10, 0))
        self.visitor_flat_entry = ctk.CTkEntry(self.visitor_frame, placeholder_text="e.g. 402", font=("Helvetica", 20), width=300, height=50, border_color="#555555", border_width=2)
        self.visitor_flat_entry.pack(pady=(5, 10))
        ctk.CTkButton(self.visitor_frame, text="Request Access Now", font=("Helvetica", 20), height=60, width=300, command=lambda: self.trigger_approval_wait(self.visitor_flat_entry.get(), "Visitor")).pack(pady=10)
        ctk.CTkButton(self.visitor_frame, text="Back", font=("Helvetica", 16), fg_color="#b30000", hover_color="#800000", command=lambda: self.show_screen(self.menu_frame)).pack(pady=30)

    def build_status_screen(self):
        self.status_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.status_msg = ctk.CTkLabel(self.status_frame, text="Awaiting...", font=("Helvetica", 24, "bold"))
        self.status_msg.pack(pady=30)
        self.video_canvas_status = ctk.CTkLabel(self.status_frame, text="")
        self.video_canvas_status.pack(pady=10)
        ctk.CTkButton(self.status_frame, text="Return to Home", font=("Helvetica", 18), command=self.return_to_home).pack(pady=20)

    def update_video_feed(self):
        with FRAME_LOCK:
            if LATEST_FRAME is not None:
                img = Image.fromarray(LATEST_FRAME)
                imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(500, 375))
                self.video_canvas_idle.configure(image=imgtk)
                self.video_canvas_setup.configure(image=imgtk)
                self.video_canvas_status.configure(image=imgtk)
        self.after(30, self.update_video_feed)

    def return_to_home(self):
        global SCAN_MODE
        SCAN_MODE = "FACE"
        self.show_screen(self.idle_frame)

    def submit_help_request(self):
        flat = self.flat_entry.get()
        name = self.name_entry.get()
        if not flat or not name:
            self.status_msg.configure(text="Error: Please enter both Name and Flat No.", text_color="red")
            self.show_screen(self.status_frame)
            return

        with FRAME_LOCK:
            if LATEST_FRAME is None: return
            frame_to_scan = LATEST_FRAME.copy()

        face_locations = face_recognition.face_locations(frame_to_scan, model="hog")
        if not face_locations:
            self.status_msg.configure(text="Error: No face detected.\nPlease look directly at the camera.", text_color="red")
            self.show_screen(self.status_frame)
            return

        face_encodings = face_recognition.face_encodings(frame_to_scan, face_locations)
        new_encoding = face_encodings[0]
        
        file_name = f"{name}_{flat}"
        file_path = os.path.join("known_faces", f"{file_name}.npy")
        np.save(file_path, new_encoding)

        global known_face_encodings, known_face_names
        known_face_encodings.append(new_encoding)
        known_face_names.append(file_name)
        
        self.status_msg.configure(text=f"Face Added Successfully!\nIdentity saved as: {file_name}", text_color="#00FF00")
        self.show_screen(self.status_frame)
        self.after(4000, self.return_to_home)

    def check_vendor_approval(self):
        flat = self.vendor_flat_entry.get()
        if not flat:
            self.status_msg.configure(text="Error: Please enter a Flat Number.", text_color="red")
            self.show_screen(self.status_frame)
            return
            
        if pre_approval_collection is not None:
            match = pre_approval_collection.find_one({"flat": flat})
            if match:
                self.status_msg.configure(text=f"✅ Pre-Approval Found for Flat {flat}.\nACCESS GRANTED.", text_color="#00FF00")
            else:
                self.status_msg.configure(text=f"❌ No active pre-approvals for Flat {flat}.\nPlease Request Access.", text_color="#FF0000")
        else:
            self.status_msg.configure(text="Database connection offline.", text_color="red")
            
        self.show_screen(self.status_frame)
        self.after(4000, self.return_to_home)
            
    def trigger_approval_wait(self, flat, access_type):
        if not flat:
            self.status_msg.configure(text="Error: Please enter a Flat Number.", text_color="red")
            self.show_screen(self.status_frame)
            return

        if pre_approval_collection is None:
            self.status_msg.configure(text="Database connection offline.", text_color="red")
            self.show_screen(self.status_frame)
            return

        request_payload = {"flat": flat, "type": access_type, "status": "pending", "timestamp": datetime.now()}
        result = pre_approval_collection.insert_one(request_payload)
        request_id = result.inserted_id

        self.status_msg.configure(text=f"Request Sent to Flat {flat}.\nAwaiting Resident Approval...", text_color="white")
        self.show_screen(self.status_frame)
        threading.Thread(target=self.poll_for_approval, args=(request_id,), daemon=True).start()

    def poll_for_approval(self, request_id):
        max_attempts = 30
        for _ in range(max_attempts):
            time.sleep(2)
            req = pre_approval_collection.find_one({"_id": request_id})
            if not req: continue
            if req["status"] == "approved":
                self.after(0, lambda: self.status_msg.configure(text="✅ ACCESS GRANTED by Resident!", text_color="#00FF00"))
                self.after(4000, self.return_to_home)
                return
            elif req["status"] == "denied":
                self.after(0, lambda: self.status_msg.configure(text="❌ ACCESS DENIED by Resident.", text_color="#FF0000"))
                self.after(4000, self.return_to_home)
                return
        self.after(0, lambda: self.status_msg.configure(text="Request Timed Out.\nResident did not respond.", text_color="orange"))
        pre_approval_collection.update_one({"_id": request_id}, {"$set": {"status": "expired"}})
        self.after(4000, self.return_to_home)

    def start_qr_scan(self):
        global SCAN_MODE, QR_RESULT
        SCAN_MODE = "QR"
        QR_RESULT = None
        self.status_msg.configure(text="Hold QR Code up to the Camera...", text_color="white")
        self.show_screen(self.status_frame)
        self.poll_for_qr()

    def poll_for_qr(self):
        global QR_RESULT, SCAN_MODE
        if SCAN_MODE != "QR": return 

        if QR_RESULT is not None:
            scanned_token = QR_RESULT
            SCAN_MODE = "PROCESSING"  # INSTANTLY shut down the camera logic so it doesn't spam!
            QR_RESULT = None 
            
            if pre_approval_collection is not None:
                # Query DB with the stripped, mathematically clean string
                match = pre_approval_collection.find_one({"token": scanned_token, "status": "active"})
                
                if match:
                    flat = match.get("flat", "Unknown")
                    name = match.get("visitor_name", "Guest")
                    self.status_msg.configure(text=f"✅ Welcome {name}!\nApproved for Flat {flat}.\nACCESS GRANTED.", text_color="#00FF00")
                    pre_approval_collection.update_one({"_id": match["_id"]}, {"$set": {"status": "used"}})
                    
                    payload = {"timestamp": datetime.now(), "incident_type": "QR_ENTRY", "identity": f"{name} (QR)", "clearance_status": "AUTHORIZED_ACCESS"}
                    threading.Thread(target=async_db_log, args=(payload, False)).start()
                else:
                    self.status_msg.configure(text="❌ Invalid, Fake, or Expired QR Code.\nACCESS DENIED.", text_color="#FF0000")
            else:
                self.status_msg.configure(text="Database offline. Cannot verify QR.", text_color="red")

            # Wait 4 seconds for the person to read the giant text, then reset automatically
            self.after(4000, self.return_to_home)
            return

        self.after(100, self.poll_for_qr) 

if __name__ == "__main__":
    ai_thread = threading.Thread(target=run_ai_engine, daemon=True)
    ai_thread.start()
    app = SecurityKioskApp()
    app.mainloop()