"""Student portal API. Uses SQLite by default; set DATABASE_URL to use MySQL, e.g.
mysql+pymysql://user:password@localhost/student_portal"""
import os
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import ForeignKey, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

app = Flask(__name__, static_folder="static")
engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///portal.db"))


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    roll_no: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    email: Mapped[str]
    semester: Mapped[int]


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    credit_hours: Mapped[int]


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    marks: Mapped[int | None] = mapped_column(default=None)


def seed():
    with Session(engine) as s:
        if s.scalar(select(Course).limit(1)):
            return
        s.add_all([
            Course(code="CS-201", title="Data Structures and Algorithms", credit_hours=3),
            Course(code="CS-215", title="Object-Oriented Programming", credit_hours=3),
            Course(code="CS-301", title="Database Systems", credit_hours=3),
            Course(code="CS-330", title="Artificial Intelligence", credit_hours=3),
            Course(code="CS-312", title="Web Technologies", credit_hours=3),
        ])
        s.commit()


Base.metadata.create_all(engine)
seed()


def err(msg, code=400):
    return jsonify({"error": msg}), code


@app.get("/api/students")
def list_students():
    with Session(engine) as s:
        rows = s.scalars(select(Student).order_by(Student.roll_no)).all()
        return jsonify([{"id": r.id, "roll_no": r.roll_no, "name": r.name, "email": r.email, "semester": r.semester} for r in rows])


@app.post("/api/students")
def add_student():
    d = request.get_json(silent=True) or {}
    if not all(str(d.get(k, "")).strip() for k in ("roll_no", "name", "email", "semester")):
        return err("Roll number, name, email and semester are required.")
    if "@" not in d["email"]:
        return err("Enter a valid email address.")
    with Session(engine) as s:
        if s.scalar(select(Student).where(Student.roll_no == d["roll_no"].strip())):
            return err("A student with this roll number already exists.", 409)
        st = Student(roll_no=d["roll_no"].strip(), name=d["name"].strip(), email=d["email"].strip(), semester=int(d["semester"]))
        s.add(st)
        s.commit()
        return jsonify({"id": st.id}), 201


@app.delete("/api/students/<int:sid>")
def delete_student(sid):
    with Session(engine) as s:
        st = s.get(Student, sid)
        if not st:
            return err("Student not found.", 404)
        for e in s.scalars(select(Enrollment).where(Enrollment.student_id == sid)):
            s.delete(e)
        s.delete(st)
        s.commit()
        return "", 204


@app.get("/api/courses")
def list_courses():
    with Session(engine) as s:
        return jsonify([{"id": c.id, "code": c.code, "title": c.title, "credit_hours": c.credit_hours} for c in s.scalars(select(Course))])


@app.get("/api/students/<int:sid>/enrollments")
def student_enrollments(sid):
    with Session(engine) as s:
        q = select(Enrollment, Course).join(Course, Course.id == Enrollment.course_id).where(Enrollment.student_id == sid)
        return jsonify([{"id": e.id, "code": c.code, "title": c.title, "credit_hours": c.credit_hours, "marks": e.marks} for e, c in s.execute(q)])


@app.post("/api/students/<int:sid>/enrollments")
def enroll(sid):
    d = request.get_json(silent=True) or {}
    with Session(engine) as s:
        if not s.get(Student, sid) or not s.get(Course, d.get("course_id")):
            return err("Student or course not found.", 404)
        if s.scalar(select(Enrollment).where(Enrollment.student_id == sid, Enrollment.course_id == d["course_id"])):
            return err("Already enrolled in this course.", 409)
        s.add(Enrollment(student_id=sid, course_id=d["course_id"]))
        s.commit()
        return "", 201


@app.patch("/api/enrollments/<int:eid>")
def set_marks(eid):
    marks = (request.get_json(silent=True) or {}).get("marks")
    if not isinstance(marks, int) or not 0 <= marks <= 100:
        return err("Marks must be a whole number from 0 to 100.")
    with Session(engine) as s:
        e = s.get(Enrollment, eid)
        if not e:
            return err("Enrollment not found.", 404)
        e.marks = marks
        s.commit()
        return "", 204


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
