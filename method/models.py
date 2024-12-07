from . import db


class Course(db.Model):
    __tablename__ = 'course'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    teacher = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.Date, nullable=True)
    end_time = db.Column(db.Date, nullable=True)
    intro = db.Column(db.Text, nullable=True)
    period = db.Column(db.String(32), nullable=True)  # 添加计划学时字段
    credit = db.Column(db.Integer, nullable=True)  # 添加学分字段
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(),
                           onupdate=db.func.current_timestamp())
    cookies = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index('idx_name', 'name'),  # 创建索引
    )

    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'teacher': self.teacher,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'intro': self.intro,
            'period': self.period,  # 添加计划学时到字典
            'credit': self.credit,  # 添加学分到字典
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'cookies': self.cookies
        }

    def __repr__(self):
        return f'<Course {self.name}>'


class Exams(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=True)  # 外键约束
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    is_checked = db.Column(db.Boolean, default=False)  # 是否批改完成
    is_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())  # 发布时间

    # 定义与 `Course` 模型的关系
    course = db.relationship('Course', backref=db.backref('exams', lazy=True))
    # 添加级联删除
    questions = db.relationship('ExamsQuestion', backref='questions', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_exam_name', 'name'),  # 创建索引
    )

    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'course_id': self.course_id,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'is_checked': self.is_checked,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }

    def __repr__(self):
        return f'<Exam {self.name}>'


# 新QuestionOption
class QuestionOption(db.Model):
    __tablename__ = 'question_option'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 自增主键
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)  # 外键，关联 Question 表
    option_label = db.Column(db.String(1), nullable=False)  # 选项标识
    option_text = db.Column(db.Text, nullable=False)  # 选项内容

    def __repr__(self):
        return f'<QuestionOption {self.option_label}>'

    def as_dict(self):
        return {
            'id': self.id,
            'option_label': self.option_label,
            'option_text': self.option_text
        }


# 新QuestionFlow
class QuestionFlow(db.Model):
    __tablename__ = 'question_flow'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 自增主键
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)  # 外键，关联 Question 表
    step_label = db.Column(db.BigInteger, nullable=False)  # 步骤标识
    step_text = db.Column(db.Text, nullable=False)  # 步骤内容
    is_hidden = db.Column(db.Boolean, default=False)  # 是否隐藏步骤

    def __repr__(self):
        return f'<QuestionFlow Step {self.step_label}>'

    def as_dict(self):
        return {
            'id': self.id,
            'step_label': self.step_label,
            'step_text': self.step_text,
            'is_hidden': self.is_hidden
        }


# 新Question
class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.Enum('choice', 'blank', 'proof', 'flow', name='question_type'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=True)
    correct_answer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    # 关系
    options = db.relationship('QuestionOption', backref='question', lazy=True, cascade='all, delete-orphan')
    flows = db.relationship('QuestionFlow', backref='question', lazy=True, cascade='all, delete-orphan')
    # user_answers = db.relationship(
    #     'UserAnswer',
    #     primaryjoin="Question.id == UserAnswer.question_id",
    #     backref='related_question',
    #     cascade='all, delete-orphan',
    #     lazy=True,
    # )

    def as_dict(self, isCorrectAnswer=True):
        question_dict = {
            'id': self.id,
            'type': self.type,
            'question_text': self.question_text,
            'score': self.score,
            'created_at': self.created_at,
            'options': [option.as_dict() for option in self.options],
            'flows': [flow.as_dict() for flow in self.flows]
        }
        if isCorrectAnswer:
            question_dict['correct_answer'] = self.correct_answer
        return question_dict


# 考试与题目关系表（ExamsQuestion）
class ExamsQuestion(db.Model):
    __tablename__ = 'exams_question'
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), primary_key=True)

    # 使用字符串表示相关的类，避免循环依赖
    # exam = db.relationship('Exams', backref=db.backref('questions', lazy=True))
    question = db.relationship('Question', backref=db.backref('exams', lazy=True))


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)  # 教工号或学号
    phone_number = db.Column(db.String(15))
    gender = db.Column(db.Integer, nullable=False)
    role = db.Column(db.Enum('admin', 'teacher', 'student'), nullable=False)
    extra = db.Column(db.Text)

    user_info = db.relationship('CourseUser', backref=db.backref('user_info', lazy=True))


    def as_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'user_id': self.user_id,
            'phone_number': self.phone_number,
            'gender': self.gender,
            'role': self.role,
            'extra': self.extra
        }

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class UserAnswer(db.Model):
    __tablename__ = 'user_answer'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)
    user_answer = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, default=-1)
    is_correct = db.Column(db.Boolean, default=None)
    answered_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # 关系
    user = db.relationship('User', backref=db.backref('question_answers', cascade='all, delete-orphan'))
    question = db.relationship('Question', backref=db.backref('user_answer_relationship', cascade='all, delete-orphan'))

    def as_dict(self):
        return {
            'user_id': self.user_id,
            'question_id': self.question_id,
            'user_answer': self.user_answer,
            'score':self.score,
            'is_correct': self.is_correct,
            'answered_at': self.answered_at,
        }

    def __repr__(self):
        return (f"<UserAnswer(user_id={self.user_id}, "
                f"question_id={self.question_id}, is_correct={self.is_correct})>")


class CourseUser(db.Model):
    __tablename__ = 'course_user'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), primary_key=True)

    course_info = db.relationship('Course', backref=db.backref('course_info', lazy=True))



class CourseContent(db.Model):
    __tablename__ = 'course_content'

    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(255), nullable=False)
    chapter_title = db.Column(db.String(255), nullable=False)
    section_title = db.Column(db.String(255))
    planned_hours = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    video_link = db.Column(db.String(255))

    questions = db.relationship('CourseQuestion', backref=db.backref('questions', lazy=True))

    def __repr__(self):
        return f'<CourseContent {self.course_name}>'


class CourseQuestion(db.Model):
    __tablename__ = 'course_question'

    course_id = db.Column(db.Integer, db.ForeignKey('course_content.id', ondelete='CASCADE'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)

    question = db.relationship('Question', backref=db.backref('course', lazy=True))

    def __repr__(self):
        return f'<CourseQuestion {self.course_id}>'









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


class Questions(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, nullable=False)
    question_type = db.Column(db.Enum('choice', 'blank', 'proof', 'flow'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    # Relationship to options table
    options = db.relationship('Option', backref='question', cascade="all, delete-orphan")
    steps = db.relationship('Flows', backref='question', lazy='joined', cascade='all, delete-orphan')
    user_answers = db.relationship('UserAnswers', backref='question', lazy='joined', cascade='all, delete-orphan')

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


class UserAnswers(db.Model):
    __tablename__ = 'user_answers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 假设 users 表中的 id 是主键
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)  # 假设 questions 表中的 id 是主键
    user_answer = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=True)

    def __repr__(self):
        return f"<UserAnswer(id={self.id}, user_id={self.user_id}, question_id={self.question_id}, is_correct={self.is_correct})>"
