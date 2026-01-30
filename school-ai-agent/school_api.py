import requests

BASE_URL = "http://localhost:3000/api"

#get
def get_students():
    res = requests.get(f"{BASE_URL}/students")
    res.raise_for_status()
    return res.json()

#post
def create_student(name: str, class_id: str):
    #Get all students
    students = get_students()["data"]

    #Extract numeric part of student_id
    max_id = 0
    for s in students:
        sid = s["student_id"]
        if sid.startswith("s"):
            try:
                num = int(sid[1:])
                max_id = max(max_id, num)
            except ValueError:
                pass

    #Create next ID
    new_student_id = f"s{max_id + 1}"

    payload = {
        "student_id": new_student_id,
        "name": name,
        "class_id": class_id
    }

    res = requests.post(f"{BASE_URL}/students", json=payload)
    res.raise_for_status()
    return res.json()

#delete   
def delete_student(student_id: str):
    res = requests.delete(f"{BASE_URL}/students/{student_id}")
    res.raise_for_status()
    return res.json()
