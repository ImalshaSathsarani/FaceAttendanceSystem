import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred,{
    'databaseURL':"https://faceattendacerealtime-f9ac7-default-rtdb.firebaseio.com/"
})

ref = db.reference('Students')

data = {
    "321654":{
        "name":"Imalsha Sathsarani",
        "major":"Software Engineering",
        "starting_year":2023,
        "total_attendance":6,
        "standing":"G",
        "year":3,
        "last_attendance_time":"2025-12-03 00:54:34"
    },
    "852741":{
        "name":"Student 1",
        "major":"Economics",
        "starting_year":2022,
        "total_attendance":12,
        "standing":"B",
        "year":4,
        "last_attendance_time":"2025-12-03 00:54:34"
    },
    "963852":{
        "name":"Student 2",
        "major":"Physics",
        "starting_year":2021,
        "total_attendance":7,
        "standing":"G",
        "year":4,
        "last_attendance_time":"2025-12-03 00:54:34"
    }
}

for key, value in data.items():
    ref.child(key).set(value)
