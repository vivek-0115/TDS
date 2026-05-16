from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Load CSV data
students_data = []

with open("q-fastapi.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        students_data.append({
            "studentId": int(row["studentId"]),
            "class": row["class"]
        })


@app.get("/api")
def get_students(class_: list[str] | None = Query(default=None, alias="class")):
    
    if class_:
        filtered = [
            student for student in students_data
            if student["class"] in class_
        ]
    else:
        filtered = students_data

    return {
        "students": filtered
    }