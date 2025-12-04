import sys
import cv2
import pickle
import face_recognition
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QImage, QPixmap, QFont
from PyQt5.QtCore import QTimer, Qt

import firebase_admin
from firebase_admin import credentials, db
from supabase import create_client

# ----------------------- Firebase & Supabase Setup -----------------------
SUPABASE_URL = "https://ygxgejkfcuqbryizacry.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlneGdlamtmY3VxYnJ5aXphY3J5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NTcyMzMsImV4cCI6MjA4MDMzMzIzM30.9Z6cFhAdli8oGkz1iccoHEASoc_lUfWgj-ALG_wEjl8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://faceattendacerealtime-f9ac7-default-rtdb.firebaseio.com/"
})

# ----------------------- Load Known Faces -----------------------
print("Loading Encode file...")
with open("EncodeFile.p", 'rb') as file:
    encodeListKnownWithIds = pickle.load(file)
encodeListKnown, studentIds = encodeListKnownWithIds
print("Encode File Loaded")

# ----------------------- PyQt5 UI -----------------------
class FaceAttendanceUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face Attendance System")
        self.resize(1100, 600)

        # Layouts
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # Camera Feed
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(640, 480)
        self.camera_label.setStyleSheet("border: 2px solid black;")
        main_layout.addWidget(self.camera_label)

        # Right panel - student info
        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel)

        # Labels for student info
        self.name_label = QLabel("Name: -")
        self.attendance_label = QLabel("Attendance: -")
        self.year_label = QLabel("Year: -")
        self.status_label = QLabel("Status: Waiting...")
        self.student_photo = QLabel()
        self.student_photo.setFixedSize(216, 216)
        self.student_photo.setStyleSheet("border: 1px solid gray;")

        for widget in [self.name_label, self.attendance_label, self.year_label, self.status_label]:
            widget.setFont(QFont("Arial", 16))
            right_panel.addWidget(widget)

        right_panel.addWidget(self.student_photo)
        right_panel.addStretch()

        # OpenCV Camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 640)
        self.cap.set(4, 480)

        # Timer to grab frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        # State
        self.counter = 0
        self.modeType = 0
        self.current_id = None
        self.student_info = None
        self.imgStudent = None

    def update_frame(self):
        success, frame = self.cap.read()
        if not success:
            return

        # Resize & convert
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Face detection & recognition
        face_locations = face_recognition.face_locations(rgb_small_frame)
        encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for encodeFace, faceLoc in zip(encodings, face_locations):
            matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
            faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
            matchIndex = np.argmin(faceDis)

            if matches[matchIndex]:
                self.current_id = studentIds[matchIndex]
                self.counter = 1  # start loading
                self.load_student_info()

        # Show camera feed
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        qimg = QImage(rgb_frame.data, w, h, 3 * w, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(qimg))

    def load_student_info(self):
        # Load student info from Firebase
        self.student_info = db.reference(f'Students/{self.current_id}').get()
        if not self.student_info:
            return

        # Load student image from Supabase
        res = supabase.storage.from_("student-images").download(f"Images/{self.current_id}.jpg")
        img_array = np.frombuffer(res, np.uint8)
        self.imgStudent = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        self.imgStudent = cv2.resize(self.imgStudent, (216, 216))
        self.display_student_info()

    def display_student_info(self):
        # Check last attendance
        last_time = datetime.strptime(self.student_info['last_attendance_time'], "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.now() - last_time).total_seconds()

        if elapsed > 30:
            # Update attendance
            ref = db.reference(f'Students/{self.current_id}')
            self.student_info['total_attendance'] += 1
            ref.child('total_attendance').set(self.student_info['total_attendance'])
            ref.child('last_attendance_time').set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.status_label.setText("Status: Marked ✔")
        else:
            self.status_label.setText("Status: Already Marked ❌")

        # Update labels
        self.name_label.setText(f"Name: {self.student_info['name']}")
        self.attendance_label.setText(f"Attendance: {self.student_info['total_attendance']}")
        self.year_label.setText(f"Year: {self.student_info['year']}")

        # Convert OpenCV image to QImage
        rgb_img = cv2.cvtColor(self.imgStudent, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        qimg = QImage(rgb_img.data, w, h, 3 * w, QImage.Format_RGB888)
        self.student_photo.setPixmap(QPixmap.fromImage(qimg))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FaceAttendanceUI()
    window.show()
    sys.exit(app.exec_())
