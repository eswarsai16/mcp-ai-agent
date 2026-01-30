from langchain_core.tools import tool
from school_api import get_students, create_student, delete_student

# helper function to for class names
def normalize_class_id(class_id: str) -> str:
    class_id = class_id.lower().strip()

    if class_id.startswith("class "):
        return "c" + class_id.split("class ")[1]

    if class_id.isdigit():
        return "c" + class_id

    return class_id

#get
@tool
def fetch_all_students():
    """Get all students from the school database"""
    return get_students()


#post
@tool
def add_student(name: str, class_id: str):
    """Add a new student to the school database. Accepts class like c5 or class 5."""
    normalized_class = normalize_class_id(class_id)
    return create_student(name, normalized_class)


#delete
@tool
def remove_student(student_id: str):
    """Delete a student by student_id. Example: s12"""
    return delete_student(student_id)
