from flask_sqlalchemy import SQLAlchemy
from . import db


class CourseContent(db.Model):
    __tablename__ = 'course_content'

    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(255), nullable=False)
    chapter_title = db.Column(db.String(255), nullable=False)
    section_title = db.Column(db.String(255))
    planned_hours = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    video_link = db.Column(db.String(255))

    def __repr__(self):
        return f'<CourseContent {self.course_name}>'


class Option(db.Model):
    __tablename__ = 'options'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    option_label = db.Column(db.String(1), nullable=False)  # 选项标识，如 'A', 'B'
    option_text = db.Column(db.Text, nullable=False)  # 选项内容

    def __repr__(self):
        return f'<Option {self.option_label}: {self.option_text[:20]}>'


class Flows(db.Model):
    __tablename__ = 'flows'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    step_label = db.Column(db.String(1), nullable=False)  # 选项标识，如 'A', 'B'
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    step_text = db.Column(db.Text, nullable=False)  # 选项内容

    def __repr__(self):
        return f'<Option {self.step_label}: {self.step_text[:20]}>'


class Question(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, nullable=False)
    question_type = db.Column(db.Enum('choice', 'blank', 'proof', 'flow'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    # Relationship to options table
    options = db.relationship('Option', backref='question', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:20]}>'


class Discussion(db.Model):
    __tablename__ = 'discussions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score = db.Column(db.Integer, nullable=False)
    author = db.Column(db.String(255), nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())

    # 与回复的关系
    replies = db.relationship('Reply', backref='discussion', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Discussion {self.id}: {self.content[:20]}>'


class Reply(db.Model):
    __tablename__ = 'replies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    discussion_id = db.Column(db.Integer, db.ForeignKey('discussions.id', ondelete='CASCADE'), nullable=False)
    replier = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    reply_content = db.Column(db.Text, nullable=False)
    reply_time = db.Column(db.TIMESTAMP, server_default=db.func.now())

    def __repr__(self):
        return f'<Reply {self.id} to Discussion {self.discussion_id}: {self.reply_content[:20]}>'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)  # 教工号或学号
    phone_number = db.Column(db.String(15))
    role = db.Column(db.Enum('admin', 'teacher', 'student'), nullable=False)
    extra = db.Column(db.Text)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
