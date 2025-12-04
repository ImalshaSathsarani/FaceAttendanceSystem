import cv2
import face_recognition
import pickle
import os
from supabase import create_client


SUPABASE_URL = "https://ygxgejkfcuqbryizacry.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlneGdlamtmY3VxYnJ5aXphY3J5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NTcyMzMsImV4cCI6MjA4MDMzMzIzM30.9Z6cFhAdli8oGkz1iccoHEASoc_lUfWgj-ALG_wEjl8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)



#Importing student images 
folderPath = 'Images'
pathList = os.listdir(folderPath)
# print(pathList)
imgList = []
studentIds = []
for path in pathList:
    imgList.append(cv2.imread(os.path.join(folderPath,path)))
    studentIds.append(os.path.splitext(path)[0])

    fileName = f'{folderPath}/{path}'
    upload_path = f"Images/{path}"  
    # bucket = storage.bucket()
    # blob = bucket.blob(fileName)
    # blob.upload_from_filename(fileName)
    with open(fileName, "rb") as f:
      supabase.storage.from_("student-images").upload(upload_path, f)

    # print(path)
    # print(os.path.splitext(path)[0])
print(studentIds)

def findEncodings(imagesList):
   encodeList = []
   for img in imagesList:
       img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
       encode = face_recognition.face_encodings(img)[0]
       encodeList.append(encode)

   return encodeList
print("Encoding Starting ...")
encodeListKnown = findEncodings(imgList)
encodeListKnownWithIds = [encodeListKnown, studentIds]
print("Encoding Complete")

file = open("EncodeFile.p", "wb")
pickle.dump(encodeListKnownWithIds, file)
file.close()
print("File Saved")
