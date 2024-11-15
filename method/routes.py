import json
from datetime import datetime

import os
from flask import Blueprint, jsonify, request, send_file, send_from_directory
from sqlalchemy import and_
import pandas as pd
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from .config import Config
from .models import *
from .utils import generate_truth_table, convert_to_python_operators, generate_truth_table_for_equivalence, \
    convert_to_logic_symbols, save_questions, add_test, get_questions_data

# 定义一个名为 main 的蓝图
main = Blueprint('main', __name__)


@main.route('/')
def index():
    return "Hello from the Modular Flask App!"


@main.route('/about')
def about():
    return "This is the About page."


@main.route('/api/course', methods=['GET', 'DELETE'])
def get_courses():
    if request.method == 'GET':
        # 获取查询参数中的 course_name
        course_name = request.args.get('courseName')

        # 如果传递了 course_name，则根据 course_name 进行筛选
        if course_name:
            courses = CourseContent.query.filter(CourseContent.course_name.like(f"%{course_name}%")).all()
        else:
            # 如果没有传递 course_name，则查询所有记录
            return jsonify({'error': 'No course name provided'}), 400

        # 构建树状结构
        tree = []

        # 创建一个辅助字典用于存储章节及其子章节的引用
        chapter_dict = {}

        for course in courses:
            # 检查章节是否已存在
            if course.chapter_title not in chapter_dict:
                # 如果章节不存在，创建并添加到 tree 和 chapter_dict
                chapter_node = {
                    'id': course.id,
                    'label': course.chapter_title,
                    'time': course.planned_hours,
                    'children': []
                }
                chapter_dict[course.chapter_title] = chapter_node
                tree.append(chapter_node)

            # 如果有子章节，则将其加入章节的 children 列表中
            if course.section_title:
                section_node = {
                    'label': course.section_title,
                    'id': course.id,
                    'time': course.planned_hours,
                    'children': []
                }
                chapter_dict[course.chapter_title]['children'].append(section_node)

                # 添加子章节内容（叶子节点）
                # content_node = {
                #     'label': course.content
                # }
                # section_node['children'].append(content_node)

        return jsonify(tree)

    elif request.method == 'DELETE':
        # 获取请求参数中的 course_id
        course_id = request.args.get('course_id')

        if not course_id:
            # 如果没有提供 course_id，返回错误信息
            return jsonify({'error': 'course_id is required'}), 400

        # 查找对应的课程记录
        course = CourseContent.query.get(course_id)

        if not course:
            # 如果找不到课程记录，返回错误信息
            return jsonify({'error': 'Course not found'}), 404

        try:
            # 删除课程记录
            db.session.delete(course)
            db.session.commit()
            return jsonify({'message': f'Course with ID {course_id} deleted successfully.'}), 200
        except Exception as e:
            # 如果删除过程中出现错误，返回错误信息
            return jsonify({'error': str(e)}), 500


@main.route('/api/course_content', methods=['GET'])
def get_course_contents():
    # 从请求参数中获取课程名称和课程ID
    course_name = request.args.get('course_name')
    course_id = request.args.get('course_id')

    if not course_name:
        return jsonify({'error': 'No course name provided'}), 400

    # 使用 SQLAlchemy 的 and_ 来组合多个查询条件
    courses = CourseContent.query.filter(
        and_(CourseContent.course_name == course_name, CourseContent.id == course_id)).all()

    if not courses:
        return jsonify({'error': 'No course content found'}), 404

    # 将课程内容转换为 JSON 格式
    courses_data = []
    for course in courses:
        course_dict = {
            'id': course.id,
            'course_name': course.course_name,
            'chapter_title': course.chapter_title,
            'section_title': course.section_title,
            'planned_hours': course.planned_hours,
            'content': course.content,
            'video_link': course.video_link
        }
        courses_data.append(course_dict)

    # 返回课程内容的 JSON 数据
    return jsonify(courses_data), 200


@main.route('/api/download_book', methods=['GET'])
def download_pdf():
    book_name = request.args.get('book_name')

    try:
        # 假设文件路径在服务器上
        file_path = f'../books/{book_name}.pdf'
        return send_file(file_path, as_attachment=True, mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/get_video', methods=['GET'])
def get_video():
    video_name = request.args.get('video_name')
    if not video_name:
        return jsonify({'error': 'No video name provided'}), 400

    video_path = f'../videos/{video_name}.mp4'  # 构建视频路径
    try:
        print(video_path)
        return send_file(video_path, as_attachment=False, mimetype='video/mp4')
    except FileNotFoundError:
        return jsonify({'error': 'Video not found'}), 404


@main.route('/api/get_questions', methods=['GET'])
def get_questions():
    course_id = request.args.get('course_id')
    user_id = request.args.get("user_id")
    if not course_id or not user_id:
        return jsonify({'error': 'No section id provided'}), 400

    # 查询对应小节的所有题目
    questions = Question.query.filter(Question.course_id == course_id).all()

    questions_data = []
    for question in questions:
        question_info = {
            'id': question.id,
            'course_id': question.course_id,
            'question_type': question.question_type,
            'question_text': question.question_text,
            'correct_answer': question.correct_answer,
            'created_at': question.created_at
        }
        # 查询用户的答题情况
        user_answer = UserAnswer.query.filter_by(user_id=user_id, question_id=question.id).first()

        # 如果用户有答题记录，加入答题情况和对错标记
        if user_answer:
            question_info['user_answer'] = user_answer.user_answer
            question_info['is_correct'] = bool(user_answer.is_correct)  # 将 1 或 0 转为 True 或 False
            question_info['answered'] = True
        else:
            question_info['user_answer'] = None
            question_info['is_correct'] = None
            question_info['answered'] = False  # 标记用户未答题

        # 如果是选择题，查询对应的选项
        if question.question_type == 'choice':
            options = Option.query.filter(Option.question_id == question.id).all()
            option_data = [{
                'option_id': option.id,
                'option_label': option.option_label,
                'option_text': option.option_text
            } for option in options]

            # 将选项数据添加到题目信息中
            question_info['options'] = option_data

        # 如果是流程题，查询对应的选项
        if question.question_type == 'flow':
            steps = Flows.query.filter(Flows.question_id == question.id).all()
            steps_data = [{
                'step_id': step.id,
                'step_label': step.step_label,
                'step_text': step.step_text,
                'is_hidden': step.is_hidden,
            } for step in steps]

            # 将选项数据添加到题目信息中
            question_info['steps'] = steps_data

        # 将题目添加到 questions_data 列表中
        questions_data.append(question_info)

    return jsonify(questions_data), 200


@main.route('/api/get_discussions', methods=['GET'])
def get_discussions():
    course_name = request.args.get('course_name')
    page = request.args.get('page', 1, type=int)  # 获取页码参数，默认值为1
    per_page = request.args.get('per_page', 5, type=int)  # 每页返回的记录数，默认值为5

    # 验证是否传递了课程名参数
    if not course_name:
        return jsonify({'error': 'No course name provided'}), 400

    # 获取 discussions 表中属于特定课程的所有讨论，并进行分页
    pagination = Discussion.query.filter_by(course_name=course_name).paginate(page=page, per_page=per_page,
                                                                              error_out=False)
    discussions = pagination.items  # 当前页的讨论列表

    discussions_data = []

    for discussion in discussions:
        # 获取该讨论的第一条回复
        first_reply = Reply.query.filter(Reply.discussion_id == discussion.id).order_by(Reply.reply_time.asc()).first()

        # 构建返回数据
        discussion_dict = {
            'id': discussion.id,
            'course_name': discussion.course_name,
            'author': discussion.author,
            'content': discussion.content,
            'score': discussion.score,
            'created_at': discussion.created_at,
            'first_reply': {
                'replier': first_reply.replier if first_reply else None,
                'reply_content': first_reply.reply_content if first_reply else None,
                'reply_time': first_reply.reply_time if first_reply else None,
                'score': first_reply.score if first_reply else None
            }
        }

        discussions_data.append(discussion_dict)

    # 构建分页信息
    response_data = {
        'discussions': discussions_data,
        'total': pagination.total,  # 总记录数
        'pages': pagination.pages,  # 总页数
        'current_page': pagination.page  # 当前页码
    }

    return jsonify(response_data), 200


@main.route('/api/is_tautology', methods=['GET'])
def is_truth():
    expr_str = request.args.get('expr1')
    if not expr_str:
        return jsonify({'error': 'No expression provided'}), 400

    expr_str = convert_to_python_operators(expr_str)

    try:
        is_tautology, truth_table = generate_truth_table(expr_str)
        import sympy as sp

        # 将所有np.bool_转换为原生bool类型
        truth_table = truth_table.map(lambda x: bool(x) if x in [sp.true, sp.false] else x)
        # 对表头进行逻辑符号转换
        converted_columns = [convert_to_logic_symbols(col) for col in truth_table.columns.tolist()]

        # 构造带表头的二维列表
        truth_table_list = [converted_columns] + truth_table.values.tolist()

        # 返回结果
        return jsonify({
            'expression': expr_str,
            'is_tautology': is_tautology,
            'truth_table': truth_table_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/is_equivalent', methods=['GET'])
def is_equivalent():
    expr_str1 = request.args.get('expr1')
    expr_str2 = request.args.get('expr2')
    if not expr_str1 or not expr_str2:
        return jsonify({'error': 'No expression provided'}), 400

    expr_str1 = convert_to_python_operators(expr_str1)
    expr_str2 = convert_to_python_operators(expr_str2)

    are_equivalent, truth_table = generate_truth_table_for_equivalence(expr_str1, expr_str2)
    import sympy as sp

    # 将所有np.bool_转换为原生bool类型
    truth_table = truth_table.map(lambda x: bool(x) if x in [sp.true, sp.false] else x)
    # 对表头进行逻辑符号转换
    converted_columns = [convert_to_logic_symbols(col) for col in truth_table.columns.tolist()]

    # 构造带表头的二维列表
    truth_table_list = [converted_columns] + truth_table.values.tolist()

    return jsonify({
        'expression1': expr_str1,
        'expression2': expr_str2,
        'is_equivalent': bool(are_equivalent),  # 转换为 0 或 1
        'truth_table': truth_table_list
    })


@main.route('/api/question', methods=['PUT', 'GET', 'DELETE'])
def question():
    if request.method == 'GET':
        # 从请求参数中获取 course_id
        course_id = request.args.get('course_id')

        questions_data = get_questions_data(course_id)

        return jsonify(questions_data), 200
    elif request.method == 'PUT':
        data = request.get_json()

        course_id = data.get('course_id')
        format_data = data.get('format_data')
        test_info = data.get('test_info')

        if not course_id or not format_data:
            return jsonify({'message': 'No course id provided'}), 400

        format_data_json = json.loads(format_data)
        if course_id == "0":
            test_info_json = json.loads(test_info)
            course_id = add_test(test_info_json)
            # if add_res:
            #     return jsonify({'message': "添加试卷成功"}), 200
            # else:
            #     return jsonify({'message': "添加试卷失败！"}), 200
            # print(test_info_json.get('test_title'))

        save_result = save_questions(course_id, format_data_json)

        if save_result:
            return jsonify({'message': '题目保存成功'}), 200
        else:
            return jsonify({'message': '题目保存失败'}), 500
    elif request.method == 'DELETE':
        # 获取 question_id 参数
        question_id = request.args.get('question_id')
        if not question_id:
            return jsonify({'message': 'No question id provided'}), 400

        # 查找并删除题目
        question = Question.query.get(question_id)
        if not question:
            return jsonify({'message': 'Question not found'}), 404

        db.session.delete(question)
        db.session.commit()
        return jsonify({'message': '题目删除成功'}), 200


@main.route('/api/content', methods=['POST'])
def content():
    data = request.json.get('params')
    course_name = data.get('course_name')
    chapter_title = data.get('chapter_title')
    section_title = data.get('section_title')
    is_section = data.get('is_section')
    content = data.get('content')

    # 查询是否已有此课程内容
    course_content = CourseContent.query.filter_by(
        course_name=course_name,
        chapter_title=chapter_title,
        section_title=section_title
    ).first()
    if course_content:
        # 如果存在，更新内容
        course_content.is_section = is_section
        course_content.section_title = section_title
        course_content.content = content
        db.session.commit()
        return jsonify({'message': 'Content updated successfully', 'status': 'updated'})
    else:
        # 如果不存在，插入新的记录
        new_content = CourseContent(
            course_name=course_name,
            chapter_title=chapter_title,
            section_title=section_title,
            planned_hours=0,  # 设置默认值，可以根据需要修改
            content=content,  # 设置默认值，可以根据需要修改
            video_link="",  # 设置默认值，可以根据需要修改
        )
        db.session.add(new_content)
        db.session.commit()
        return jsonify({'message': 'Content added successfully', 'status': 'added'})


@main.route('/api/get_course_name', methods=['GET'])
def get_course_name():
    # 查询所有 ID 大于 0 的课程名称
    courses = CourseContent.query.with_entities(CourseContent.course_name).filter(
        CourseContent.course_name != '考试').distinct().all()
    # 将结果转换为列表格式
    course_names = [course.course_name for course in courses]
    return jsonify(course_names)


@main.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or 'uname' not in data or 'upwd' not in data:
        return jsonify({'code': 400, 'msg': '请求数据不完整！'}), 200

    uname = data['uname']
    upwd = data['upwd']

    # 查询用户
    user = User.query.filter_by(username=uname).first()  # 假设 username 是账号字段

    if user is None:
        return jsonify({'code': 300, 'msg': '用户不存在！'}), 200

    # 验证密码
    if user.password != upwd:  # 假设 password 是密码字段
        return jsonify({'code': 300, 'msg': '密码错误！'}), 200

    # 登录成功，返回用户信息
    user_info = {
        'id': user.id,
        'username': user.username,
        'user_id': user.user_id,  # 教工号或学号
        'phone_number': user.phone_number,
        'role': user.role,
        'extra': user.extra,
    }

    return jsonify({'code': 200, 'msg': '登录成功！', 'data': [user_info]}), 200


@main.route('/api/regist', methods=['POST'])
def regist():
    data = request.get_json()

    if not data or 'uname' not in data or 'upwd' not in data or 'uid' not in data or 'uphone' not in data:
        return jsonify({'code': 400, 'msg': '请求数据不完整！'}), 200

    uname = data['uname']
    upwd = data['upwd']
    uid = data['uid']
    uphone = data['uphone']

    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=uname).first()
    if existing_user:
        return jsonify({'code': 300, 'msg': '用户名已存在！'}), 200

    # 创建新用户
    new_user = User(
        username=uname,
        password=upwd,  # 使用哈希加密存储密码
        user_id=uid,
        phone_number=uphone,
        role='student',  # 默认角色
        extra=''  # 扩展信息，若有
    )

    # 添加用户到数据库
    db.session.add(new_user)
    try:
        db.session.commit()
        return jsonify({'code': 200, 'msg': '注册成功！'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '注册失败，请重试！', 'error': str(e)}), 500


@main.route('/api/course_management', methods=['GET', 'DELETE', 'PUT'])
def course_manager():
    if request.method == 'GET':
        course_name = request.args.get('name')

        if course_name:
            # 获取指定名称的课程
            course = Course.query.filter_by(name=course_name).first()
            if course:
                return jsonify(course.as_dict()), 200
            return jsonify({'message': 'Course not found.'}), 404
        else:
            # 获取所有课程
            courses = Course.query.all()
            return jsonify([course.as_dict() for course in courses]), 200

    elif request.method == 'DELETE':
        course_id = request.args.get('id')
        if course_id:
            course = Course.query.get(course_id)
            if course:
                db.session.delete(course)
                db.session.commit()
                return jsonify({'message': 'Course deleted successfully.'}), 200
            return jsonify({'message': 'Course not found.'}), 404
        return jsonify({'message': 'Course ID is required.'}), 400

    elif request.method == 'PUT':

        data = request.json

        if not data:
            return jsonify({'message': 'Request body is required.'}), 400

        # 转换日期格式

        start_time_str = data.get('start_time')

        end_time_str = data.get('end_time')

        try:

            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')

            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')

        except ValueError as e:

            return jsonify({'message': f'Invalid date format: {str(e)}'}), 400

        # 创建新的课程对象

        new_course = Course(

            name=data.get('name'),

            teacher=data.get('teacher'),

            start_time=start_time,

            end_time=end_time,

            intro=data.get('intro')

        )

        # 添加到数据库

        db.session.add(new_course)

        db.session.commit()

        # 返回新课程的详细信息

        return jsonify(new_course.as_dict()), 201

    return jsonify({'message': 'Method not allowed.'}), 405


@main.route('/api/answered_questions', methods=['PUT'])
def answered_questions():
    data = request.get_json()
    if not data or 'user_answer' not in data:
        return jsonify({'error': 'No answer data provided'}), 400

    # 解析并加载 user_answer 数据
    user_answers = json.loads(data['user_answer'])

    # 遍历每个答题项并存储到数据库
    for answer in user_answers:
        user_id = answer.get('user_id')
        question_id = answer.get('question_id')
        user_answer_text = json.dumps(answer.get('user_answer'))
        is_correct = answer.get('is_correct')

        # 检查 question_id 是否为空
        if question_id is None:
            print(f"Error: question_id is None for user_id {user_id}. Skipping this entry.")
            continue  # 跳过无效的记录

        # 检查该用户是否已经答过该题目
        existing_answer = UserAnswer.query.filter_by(user_id=user_id, question_id=question_id).first()

        if existing_answer:
            # 更新已存在的记录
            existing_answer.user_answer = user_answer_text
            existing_answer.is_correct = is_correct
        else:
            # 创建新的答题记录
            new_answer = UserAnswer(
                user_id=user_id,
                question_id=question_id,
                user_answer=user_answer_text,
                is_correct=is_correct,
                answered_at=db.func.current_timestamp()
            )
            db.session.add(new_answer)

    # 提交所有更改到数据库
    db.session.commit()
    return jsonify({'message': 'Answers recorded successfully'}), 200


@main.route('/api/get_course_answers', methods=['GET'])
def get_course_answers():
    # 获取请求中的参数
    course_id = request.args.get('course_id', type=int)
    if not course_id:
        return jsonify({'error': 'course_id is required'}), 400

    try:
        # 查询所有该课程的题目及其答题情况
        questions = Question.query.filter_by(course_id=course_id).options(
            joinedload(Question.options),  # 加载题目选项（如果有）
            joinedload(Question.steps),
            joinedload(Question.user_answers)  # 加载题目的答题情况（需建立关系）
        ).all()
        # 构造返回数据
        course_answers = []
        for question in questions:
            question_info = {
                'question_id': question.id,
                'question_type': question.question_type,
                'question_text': question.question_text,
                'correct_answer': question.correct_answer,
                'options': [
                    {
                        'option_id': option.id,
                        'option_label': option.option_label,
                        'option_text': option.option_text,
                    }
                    for option in question.options
                ],
                'answers': [
                    {
                        'user_id': answer.user_id,
                        'user_answer': answer.user_answer,
                        'is_correct': answer.is_correct,
                        'answered_at': answer.answered_at
                    }
                    for answer in question.user_answers
                ]
            }
            course_answers.append(question_info)

        return jsonify(course_answers), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 检查文件是否是允许的类型
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@main.route('/api/upload', methods=['POST', 'GET', 'DELETE'])
def manage_files():
    if request.method == 'POST':
        # 处理文件上传
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if file and allowed_file(file.filename):
            # 确保文件名安全
            filename = secure_filename(file.filename)

            # 添加时间戳生成唯一文件名
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"

            # 保存文件
            file_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
            file.save(file_path)

            return jsonify({'message': 'File uploaded successfully', 'file_path': file_path}), 200
        else:
            return jsonify({'error': 'File type not allowed'}), 400

    elif request.method == 'GET':
        # 获取文件列表
        files = os.listdir(Config.UPLOAD_FOLDER)
        file_urls = [
            {
                "file_name": file,
                "file_path": f"http://localhost:5000/uploads/{file}"
            }
            for file in files
        ]
        return jsonify({'files': file_urls}), 200

    elif request.method == 'DELETE':
        # 删除指定文件
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'File name is required'}), 400

        file_path = file_name
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'message': f'File {file_name} deleted successfully.'}), 200
        else:
            return jsonify({'error': 'File not found'}), 404


@main.route('/api/uploads/<filename>', methods=['GET'])
def uploaded_file(filename):
    try:
        # 返回文件内容
        upload_folder = os.path.join(os.getcwd(), Config.UPLOAD_FOLDER)
        print(upload_folder)
        return send_from_directory(upload_folder, filename)
    except FileNotFoundError:
        # 如果文件不存在，返回 404
        return jsonify({'error': 'File not found'}), 404


@main.route('/api/get_user_answers', methods=['GET', 'PUT'])
def check_question():

    return jsonify({'questions': Question.query.all()}), 200
