import cv2
import pickle
import face_recognition
import numpy as np
import customtkinter as ctk
from PIL import Image
import firebase_admin
from firebase_admin import credentials, db
from supabase import create_client
from datetime import datetime
import threading
from PIL import Image

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
FACE_THRESHOLD = 0.5

class FaceAttendanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. Setup Window
        self.title("Smart Face Attendance System")
        self.geometry("1100x600")

        # 2. Setup Resources
        self.setup_resources()

        self.image_cache = []   # prevent CTkImage garbage-collection

        # 3. Create GUI
        self.create_widgets()

        # 4. State Variables for Logic
        self.counter = 0
        self.current_id = -1
        self.studentInfo = None
        self.is_fetching_data = False 
        
        # 5. Image Holders
        self.current_image_ref = None     # Holds the final CTkImage (Main Thread)
        self.temp_pil_image = None        # Holds the raw downloaded image (Background Thread)
        self.attendance_status = "active" # success, already_marked, error
        self.unknown_detected = False

        # 6. Start Video
        self.process_webcam()

    def setup_resources(self):
        # Supabase
        SUPABASE_URL = "https://ygxgejkfcuqbryizacry.supabase.co"
        # Note: Keep your key secure in production
        SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlneGdlamtmY3VxYnJ5aXphY3J5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NTcyMzMsImV4cCI6MjA4MDMzMzIzM30.9Z6cFhAdli8oGkz1iccoHEASoc_lUfWgj-ALG_wEjl8"
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Firebase
        cred = credentials.Certificate("serviceAccountKey.json")
        try:
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://faceattendacerealtime-f9ac7-default-rtdb.firebaseio.com/"
            })
        except ValueError:
            pass

        # Encodings
        print("Loading Encode file...")
        file = open("EncodeFile.p", 'rb')
        encodeListKnownWithIds = pickle.load(file)
        file.close()
        self.encodeListKnown, self.studentIds = encodeListKnownWithIds
        print("Encode File Loaded")

        self.unknown_image = Image.open("Assets/Unknown.jpg").resize((216, 216))

        # Webcam
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 640)
        self.cap.set(4, 480)

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # --- VIDEO FRAME ---
        self.video_frame = ctk.CTkFrame(self, corner_radius=15)
        self.video_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.video_label = ctk.CTkLabel(self.video_frame, text="")
        self.video_label.pack(expand=True, padx=10, pady=10)

        # --- INFO FRAME ---
        self.info_frame = ctk.CTkFrame(self, width=400, corner_radius=15, fg_color="#2B2B2B")
        self.info_frame.grid(row=0, column=1, padx=20, pady=20, sticky="ns")
        self.info_frame.pack_propagate(False)

        # Image Placeholder
        self.student_img_label = ctk.CTkLabel(self.info_frame, text="Waiting...", 
                                              width=216, height=216, fg_color="#1F1F1F", corner_radius=10)
        self.student_img_label.pack(pady=(40, 20))

        # Text Info
        self.name_label = ctk.CTkLabel(self.info_frame, text="Scan Face", font=("Roboto Medium", 24))
        self.name_label.pack(pady=5)
        self.major_label = ctk.CTkLabel(self.info_frame, text="", font=("Roboto", 16), text_color="gray")
        self.major_label.pack(pady=5)
        self.year_label = ctk.CTkLabel(self.info_frame, text="", font=("Roboto", 16), text_color="gray")
        self.year_label.pack(pady=5)


        # Stats
        self.stats_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.stats_frame.pack(pady=20, fill="x", padx=20)
        self.id_label = ctk.CTkLabel(self.stats_frame, text="ID: --", font=("Roboto", 14))
        self.id_label.pack(side="left", padx=10)
        self.att_label = ctk.CTkLabel(self.stats_frame, text="Total: --", font=("Roboto", 14))
        self.att_label.pack(side="right", padx=10)

        # Status Button
        self.status_button = ctk.CTkButton(self.info_frame, text="System Active", 
                                           fg_color="#3B8ED0", state="disabled", height=50)
        self.status_button.pack(side="bottom", fill="x", padx=20, pady=20)

    def process_webcam(self):
        success, img = self.cap.read()
       
        
        if success:
            imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

            faceCurFrame = face_recognition.face_locations(imgS)
            encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

            # Prevent detecting new faces if we are currently displaying/processing one
            if not self.is_fetching_data and self.counter == 0:
                for encodeFace, faceLoc in zip(encodeCurFrame, faceCurFrame):
                    
                    matches = face_recognition.compare_faces(self.encodeListKnown, encodeFace)
                    faceDis = face_recognition.face_distance(self.encodeListKnown, encodeFace)
                    matchIndex = np.argmin(faceDis)
                    #  Unknown Face Condition
                    if faceDis[matchIndex] > FACE_THRESHOLD:
                      self.show_unknown_face()
                      continue

                    #  Known Face Condition
                    if matches[matchIndex]:
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        id = self.studentIds[matchIndex]

                        # Start Process
                        self.current_id = id
                        self.counter = 1
                        self.status_button.configure(text="Processing...", fg_color="#E1A11D",text_color="white",font=("Roboto Bold",18))
                        
                        self.is_fetching_data = True
                        threading.Thread(target=self.fetch_student_data).start()

            # Handle UI Flow
            if self.counter > 0:
                self.update_attendance_ui()

            # Video Feed Update
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(640, 480))
            
            self.video_label.configure(image=ctk_img)
            self.video_label.image = ctk_img 

        self.after(10, self.process_webcam)

    def fetch_student_data(self):
        """ BACKGROUND THREAD """
        try:
            # 1. Get Text Data
            self.studentInfo = db.reference(f'Students/{self.current_id}').get()
            
            # 2. Get Image Data
            try:
                res = self.supabase.storage.from_("student-images").download(f"Images/{self.current_id}.jpg")
                img_array = np.frombuffer(res, np.uint8)
                img_student_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                img_student_rgb = cv2.cvtColor(img_student_cv, cv2.COLOR_BGR2RGB)
                
                # FIX 1: Use .copy() to ensure data persists after thread dies
                self.temp_pil_image = Image.fromarray(img_student_rgb).copy()
                
            except Exception as e:
                print(f"Image Fetch Error: {e}")
                self.temp_pil_image = None

            # 3. Update DB Logic
            datetimeObject = datetime.strptime(self.studentInfo['last_attendance_time'], "%Y-%m-%d %H:%M:%S")
            secondsElapsed = (datetime.now() - datetimeObject).total_seconds()

            if secondsElapsed > 30:
                ref = db.reference(f'Students/{self.current_id}')
                self.studentInfo['total_attendance'] += 1
                ref.child('total_attendance').set(self.studentInfo['total_attendance'])
                ref.child('last_attendance_time').set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                self.attendance_status = "success"
            else:
                self.attendance_status = "already_marked"
                
        except Exception as e:
            print(f"Data Error: {e}")
            self.attendance_status = "error"
        
        # Release lock
        self.is_fetching_data = False

    def update_attendance_ui(self):
        """ MAIN THREAD """
        
        # Phase 1: Waiting for Thread to finish
        if self.counter == 1:
            if not self.is_fetching_data: # Thread finished
                
                if self.studentInfo:
                    self.name_label.configure(text=self.studentInfo['name'])
                    self.major_label.configure(text=self.studentInfo['major'])
                    self.year_label.configure(text=f"Year: {self.studentInfo.get('year', '--')}")

                    self.id_label.configure(text=f"ID: {self.current_id}")
                    self.att_label.configure(text=f"Total Attendance: {self.studentInfo['total_attendance']}")
                    
                    # FIX 2: Create local variable first, then assign
                    if self.temp_pil_image:
                        new_img = ctk.CTkImage(light_image=self.temp_pil_image, 
                                               dark_image=self.temp_pil_image, 
                                               size=(216, 216))
                        # self.student_img_label.configure(image=new_img, text="")
                        # Keep reference forever to prevent garbage collection
                        self.image_cache.append(new_img)
                        self.current_image_ref = new_img # Keep reference alive
                        self.student_img_label.configure(image=new_img, text="")
                    
                    if self.attendance_status == "success":
                        self.status_button.configure(text="Marked Successfully", fg_color="#2CC985",text_color="white", font=("Roboto Bold", 18))
                    elif self.attendance_status == "already_marked":
                        self.status_button.configure(text="Already Marked", fg_color="#C92C38",text_color="white", font=("Roboto Bold",18))
                
                self.counter += 1 

        # Phase 2: Hold Display
        elif 1 < self.counter < 40:
            self.counter += 1

        # Phase 3: Reset
        else:
            self.counter = 0
            self.studentInfo = None
            self.current_image_ref = None # Clear local ref
            self.temp_pil_image = None
            self.image_cache.clear()
            
            # Reset UI Text
            self.status_button.configure(text="System Active", fg_color="#3B8ED0")
            self.name_label.configure(text="Scan Face")
            self.major_label.configure(text="")
            self.year_label.configure(text="")
            self.id_label.configure(text="ID: ")
            self.att_label.configure(text="Total Attendance: ")
            
            # Reset Image Label safely
            self.student_img_label.configure(image="", text="Waiting...") 

    def show_unknown_face(self):
        if self.counter != 0:
          return  # avoid interrupting if showing another student

        self.unknown_detected = True
        self.counter = 1

    # Update UI
        self.name_label.configure(text="Unknown Face")
        self.major_label.configure(text="Not Found in Database")
        self.id_label.configure(text="ID: --")
        self.att_label.configure(text="Total Attendance: --")
        self.status_button.configure(text="Student Not Found", fg_color="#C92C38",text_color='white',font=("Roboto Bold", 18))

        # Load the unknown person placeholder image
        unknown_ctk_img = ctk.CTkImage( light_image=self.unknown_image,dark_image=self.unknown_image,size=(216,216)
        )

         # Keep reference to avoid garbage collection
        self.image_cache.append(unknown_ctk_img)
        

    # Reset image
        self.student_img_label.configure(image=unknown_ctk_img, text="")

    # Automatically reset after few seconds
        self.after(3000, self.reset_unknown_ui)
    
    def reset_unknown_ui(self):
        self.unknown_detected = False
        self.counter = 0

        self.status_button.configure(text="System Active", fg_color="#3B8ED0")
        self.name_label.configure(text="Scan Face")
        self.major_label.configure(text="")
        self.id_label.configure(text="ID: --")
        self.att_label.configure(text="Total Attendance: --")

        self.student_img_label.configure(image="", text="Waiting...")



            


if __name__ == "__main__":
    app = FaceAttendanceApp()
    app.mainloop()