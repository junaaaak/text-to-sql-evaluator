-- School database used by the text-to-SQL benchmark.

CREATE TABLE departments (
    dept_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,   -- e.g. 'Computer Science'
    building   TEXT NOT NULL
);

CREATE TABLE students (
    student_id     INTEGER PRIMARY KEY,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    gender         TEXT NOT NULL CHECK (gender IN ('M', 'F')),
    dept_id        INTEGER NOT NULL REFERENCES departments(dept_id),
    year_of_study  INTEGER NOT NULL CHECK (year_of_study BETWEEN 1 AND 4),
    city           TEXT NOT NULL,
    email          TEXT,                -- NULL when the student has not provided one
    date_of_birth  TEXT NOT NULL        -- ISO date 'YYYY-MM-DD'
);

CREATE TABLE courses (
    course_id   INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,   -- e.g. 'CS101'
    title       TEXT NOT NULL,
    dept_id     INTEGER NOT NULL REFERENCES departments(dept_id),
    credits     INTEGER NOT NULL,
    instructor  TEXT NOT NULL,
    semester    TEXT NOT NULL CHECK (semester IN ('Fall', 'Spring'))
);

-- One row per student enrolled in a course. score is NULL when the exam has not been graded yet.
CREATE TABLE marks (
    mark_id     INTEGER PRIMARY KEY,
    student_id  INTEGER NOT NULL REFERENCES students(student_id),
    course_id   INTEGER NOT NULL REFERENCES courses(course_id),
    score       REAL CHECK (score BETWEEN 0 AND 100),
    exam_date   TEXT NOT NULL,          -- ISO date 'YYYY-MM-DD'
    UNIQUE (student_id, course_id)
);
