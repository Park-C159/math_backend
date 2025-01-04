import base64
import json
import random
from datetime import datetime, timedelta

import os
from flask import Blueprint, jsonify, request, send_file, send_from_directory
from flask_socketio import emit
from sqlalchemy import and_
import pandas as pd
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import current_user
from werkzeug.utils import secure_filename

from datetime import datetime
import os
import base64
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF库用于处理PDF
from PIL import Image

from .config import Config
from .models import *
from .utils import generate_truth_table, convert_to_python_operators, generate_truth_table_for_equivalence, \
    convert_to_logic_symbols, save_questions, add_test, get_questions_data, create_response

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
    questions = Questions.query.filter(Questions.course_id == course_id).all()

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
        user_answer = UserAnswers.query.filter_by(user_id=user_id, question_id=question.id).first()

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


@main.route('/api/get_main_discussions', methods=['GET'])
def get_main_discussions():
    course_name = request.args.get('course_name')
    page = request.args.get('page', 1, type=int)  # 页码，默认1
    per_page = request.args.get('per_page', 5, type=int)  # 每页记录数，默认5
    search = request.args.get('search')
    time_filter = request.args.get('time_filter')  # 时间筛选
    author_filter = request.args.get('author_filter', type=str)
    user_id = request.args.get('user_id')

    if not course_name:
        return jsonify({'error': 'No course name provided'}), 400

    course = Course.query.filter_by(name=course_name).first()
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    query = Discussion.query.filter_by(course_id=course.id)

    if search:
        query = query.filter(Discussion.content.like(f'%{search}%'))

    if time_filter:
        now = datetime.utcnow()
        if time_filter == "last_week":
            start_time = now - timedelta(days=7)
            query = query.filter(Discussion.created_at >= start_time)
        elif time_filter == "last_month":
            start_time = now - timedelta(days=30)
            query = query.filter(Discussion.created_at >= start_time)

    if author_filter:
        if author_filter == 'created_by_me':
            query = query.filter(Discussion.author_id == user_id)
        elif author_filter == 'teacher_involved':
            query = query.filter(Discussion.teacher_involved == True)

    query = query.order_by(Discussion.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    discussions = pagination.items

    # 获取用户的点赞记录
    user_likes = User_Like_Comment.query.filter_by(user_id=user_id).all() if user_id else []
    liked_discussions = {like.comment_id for like in user_likes if like.dor == 'discussion'}

    discussions_data = []
    for discussion in discussions:
        replies_count = Reply.query.filter_by(parent_id=discussion.id).count()

        discussions_data.append({
            'id': discussion.id,
            'course_name': course.name,
            'author_name': discussion.author.username if discussion.author else None,
            'content': discussion.content,
            'like': discussion.like,
            'isLiked': discussion.id in liked_discussions,
            'created_at': discussion.created_at,
            'replies_count': replies_count
        })

    response_data = {
        'discussions': discussions_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }

    return jsonify(response_data), 200


@main.route('/api/get_detailed_discussions', methods=['GET'])
def get_detailed_discussions():
    discussion_id = request.args.get('discussion_id', type=int)
    user_id = request.args.get('user_id')

    if not discussion_id:
        return jsonify({'error': 'No discussion ID provided'}), 400

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return jsonify({'error': 'Discussion not found'}), 404

    # 获取用户的点赞记录
    user_likes = User_Like_Comment.query.filter_by(user_id=user_id).all() if user_id else []
    liked_discussions = {like.comment_id for like in user_likes if like.dor == 'discussion'}
    liked_replies = {like.comment_id for like in user_likes if like.dor == 'reply'}

    all_replies = Reply.query.filter_by(parent_id=discussion.id).order_by(
        Reply.reply_time.desc()).all()

    replies_data = []
    for reply in all_replies:
        # Fetch the target username based on the target_id
        target_name = None
        if reply.target_type == 'reply' and reply.target_id:
            target_reply = Reply.query.get(reply.target_id)
            if target_reply:
                target_replier = User.query.get(target_reply.replier_id)
                if target_replier:
                    target_name = target_replier.username

        replies_data.append({
            'id': reply.id,
            'replier_name': reply.replier.username if reply.replier else None,
            'reply_type': reply.target_type,
            'target_name': target_name,
            'reply_content': reply.reply_content,
            'reply_time': reply.reply_time,
            'like': reply.like,
            'isLiked': reply.id in liked_replies
        })

    response_data = {
        'discussion_id': discussion.id,
        'course_name': discussion.course.name if discussion.course else None,
        'author_name': discussion.author.username if discussion.author else None,
        'content': discussion.content,
        'like': discussion.like,
        'isLiked': discussion.id in liked_discussions,  # 是否已点赞
        'created_at': discussion.created_at,
        'replies': replies_data
    }

    return jsonify(response_data), 200


@main.route('/api/submit_discussion', methods=['POST'])
def submit_discussion():
    data = request.get_json()
    user_id = data.get('user_id')
    course_name = data.get('course_name')
    content = data.get('content')

    if not user_id or not course_name or not content:
        return jsonify({"message": "缺少必要的参数"}), 400

    # 首先查找用户并检查其角色
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "无效的用户"}), 404

    course = Course.query.filter_by(name=course_name).first()
    if not course:
        return jsonify({"message": "无效的课程"}), 404

    # 根据用户角色设置 teacher_involved
    teacher_involved = user.role == 'teacher'

    new_discussion = Discussion(
        author_id=user_id,
        course_id=course.id,
        content=content,
        teacher_involved=teacher_involved
    )

    try:
        db.session.add(new_discussion)
        db.session.commit()
        return jsonify({
            "message": "讨论创建成功",
            "discussion": new_discussion.as_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "创建讨论失败", "error": str(e)}), 500


@main.route('/api/update_like', methods=['POST'])
def update_like():
    try:
        data = request.get_json()

        user_id = data.get('user_id')
        like_type = data.get('type')
        item_id = data.get('id')

        if not user_id or not like_type or not item_id:
            return jsonify({"error": "Missing required parameters"}), 400

        # 检查是否已经点过赞
        existing_like = User_Like_Comment.query.filter_by(
            user_id=user_id,
            dor=like_type,
            comment_id=item_id
        ).first()

        if existing_like:
            # 如果已经点过赞，则取消点赞
            if like_type == 'discussion':
                discussion = Discussion.query.get(item_id)
                if not discussion:
                    return jsonify({"error": "Discussion not found"}), 404

                discussion.like = max((discussion.like or 1) - 1, 0)

            elif like_type == 'reply':
                reply = Reply.query.get(item_id)
                if not reply:
                    return jsonify({"error": "Reply not found"}), 404

                reply.like = max((reply.like or 1) - 1, 0)

            db.session.delete(existing_like)
            db.session.commit()

            return jsonify({
                "message": "Like removed successfully",
                "like": discussion.like if like_type == 'discussion' else reply.like,
                "liked": False  # 返回未点赞状态
            })

        if like_type == 'discussion':
            discussion = Discussion.query.get(item_id)
            if not discussion:
                return jsonify({"error": "Discussion not found"}), 404

            # 增加点赞数
            discussion.like = (discussion.like or 0) + 1

            # 创建点赞记录
            new_like = User_Like_Comment(
                user_id=user_id,
                dor=like_type,
                comment_id=item_id
            )
            db.session.add(new_like)
            db.session.commit()

            return jsonify({
                "message": "Like added successfully",
                "like": discussion.like,
                "liked": True  # 返回已点赞状态
            })

        elif like_type == 'reply':
            reply = Reply.query.get(item_id)
            if not reply:
                return jsonify({"error": "Reply not found"}), 404

            # 增加点赞数
            reply.like = (reply.like or 0) + 1

            # 创建点赞记录
            new_like = User_Like_Comment(
                user_id=user_id,
                dor=like_type,
                comment_id=item_id
            )
            db.session.add(new_like)
            db.session.commit()

            return jsonify({
                "message": "Like added successfully",
                "like": reply.like,
                "liked": True  # 返回已点赞状态
            })

        else:
            return jsonify({"error": "Invalid like type"}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@main.route('/api/submit_reply', methods=['POST'])
def submit_reply():
    data = request.get_json()

    user_id = data.get('user_id')
    parent_id = data.get('parent_id')
    content = data.get('content')
    target_type = data.get('target_type')
    target_id = data.get('target_id')

    if not all([user_id, parent_id, content, target_type]):
        return jsonify({
            'message': '缺少必要参数',
            'success': False
        }), 400

    try:
        # 检查回复者的角色
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'message': '无效的用户',
                'success': False
            }), 404

        # 创建新的回复
        new_reply = Reply(
            parent_id=parent_id,
            replier_id=user_id,
            target_type=target_type,
            target_id=target_id,
            reply_content=content,
            like=0
        )

        db.session.add(new_reply)
        db.session.commit()

        # 检查是否需要更新 teacher_involved
        if user.role == 'teacher':
            # 获取父级讨论
            parent = Discussion.query.get(parent_id)
            if parent and not parent.teacher_involved:
                parent.teacher_involved = True
                db.session.commit()

        return jsonify({
            'message': '回复创建成功',
            'success': True,
            'reply': new_reply.as_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': '回复创建失败',
            'success': False,
            'error': str(e)
        }), 500


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


@main.route('/api/question', methods=['PUT', 'GET', 'DELETE', 'POST'])
def question():
    if request.method == 'GET':
        # 从请求参数中获取 course_id
        course_id = request.args.get('course_id')
        user_id = request.args.get('user_id')
        if not course_id:
            return create_response(400, "参数缺失")

        course = CourseContent.query.get(course_id)
        if not course:
            return create_response(300, "未查询到对应课程")

        if not user_id:
            questions = []
            for course_question in course.questions:
                questions.append(course_question.question.as_dict())

            return create_response(200, "请求成功", questions)
        else:
            questions = []

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
        question = Questions.query.get(question_id)
        if not question:
            return jsonify({'message': 'Question not found'}), 404

        db.session.delete(question)
        db.session.commit()
        return jsonify({'message': '题目删除成功'}), 200
    elif request.method == 'POST':
        data = request.get_json()
        course_id = data.get('course_id')
        questions = data.get('questions')
        if not course_id or not questions:
            return create_response(400, "参数缺失！")
        #
        # for question in questions:
        #     print(question)

        return create_response(200, "上传成功！")


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
    courses = Course.query.all()
    course_list = []
    for course in courses:
        course_list.append({
            "name": course.name,
            "id": course.id
        })
    return create_response(200, "ok", course_list)

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
    gender = data['gender']
    if gender == 'male':
        gender_label = 1
    else:
        gender_label = 0

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
        gender=gender_label,
        extra=''  # 扩展信息，若有
    )

    db.session.add(new_user)
    db.session.flush()

    # 默认分配第一节课程，后续需要完善逻辑
    new_course_user = CourseUser(
        course_id=1,
        user_id=new_user.id,
    )
    db.session.add(new_course_user)
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
        existing_answer = UserAnswers.query.filter_by(user_id=user_id, question_id=question_id).first()

        if existing_answer:
            # 更新已存在的记录
            existing_answer.user_answer = user_answer_text
            existing_answer.is_correct = is_correct
        else:
            # 创建新的答题记录
            new_answer = UserAnswers(
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
        questions = Questions.query.filter_by(course_id=course_id).options(
            joinedload(Questions.options),  # 加载题目选项（如果有）
            joinedload(Questions.steps),
            joinedload(Questions.user_answers)  # 加载题目的答题情况（需建立关系）
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
def allowed_file(filename, file_type=None):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    if file_type == 'image':
        return extension in Config.ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'pdf':
        return extension in Config.ALLOWED_PDF_EXTENSIONS
    return extension in (Config.ALLOWED_IMAGE_EXTENSIONS | Config.ALLOWED_PDF_EXTENSIONS)


def process_image(file, filename):
    """处理图片文件"""
    try:
        # 验证是否为有效图片
        img = Image.open(file)
        img.verify()

        # 重新打开文件（verify会关闭文件）
        file.seek(0)

        # 生成唯一文件名
        unique_filename = f"img_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        # 保存文件
        file.save(file_path)
        return True, file_path, "图片上传成功"
    except Exception as e:
        return False, None, f"图片处理失败: {str(e)}"


def process_pdf(file, filename):
    """处理PDF文件"""
    try:
        # 生成唯一文件名
        unique_filename = f"pdf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        print(unique_filename)
        file_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        print(file_path)

        # 保存PDF文件
        file.save(file_path)

        # 验证PDF文件
        pdf_document = fitz.open(file_path)

        # 获取PDF信息
        pdf_info = {
            'pages': len(pdf_document),
            'title': pdf_document.metadata.get('title', ''),
            'author': pdf_document.metadata.get('author', ''),
            'file_path': file_path
        }

        pdf_document.close()
        return True, pdf_info, "PDF上传成功"
    except Exception as e:
        # 如果处理失败，删除已上传的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        return False, None, f"PDF处理失败: {str(e)}"


@main.route('/api/upload', methods=['POST', 'GET', 'DELETE', 'PUT'])
def manage_files():
    if request.method == 'POST':
        if 'file' not in request.files:
            return create_response(400, 'No file part in the request')

        file = request.files['file']
        if file.filename == '':
            return create_response(400, 'No file selected')

        # 获取文件类型
        file_type = request.form.get('file_type', 'image')  # 从请求中获取文件类型
        filename = file.filename

        # 根据文件类型分别处理
        if file_type == 'pdf' and allowed_file(filename, 'pdf'):
            success, result, message = process_pdf(file, filename)
            if success:
                file_url = f"/uploads/{os.path.basename(result['file_path'])}"
                return create_response(200, message, file_url)
            return create_response(400, message)

        elif file_type == 'image' and allowed_file(filename, 'image'):
            success, result, message = process_image(file, filename)
            if success:
                file_url = f"/uploads/{os.path.basename(result)}"
                return create_response(200, message, file_url)
            return create_response(400, message)

        return create_response(400, '不支持的文件格式或文件类型不匹配')

    elif request.method == 'GET':
        try:
            files = os.listdir(Config.UPLOAD_FOLDER)
            file_list = []
            for file in files:
                file_type = 'image' if file.startswith('img_') else 'pdf' if file.startswith('pdf_') else 'unknown'
                if file_type != 'unknown':  # 只返回有效的文件
                    file_list.append({
                        "file_name": file,
                        "file_type": file_type,
                        "file_path": f"/uploads/{file}"
                    })
            return jsonify({'files': file_list}), 200
        except Exception as e:
            return create_response(500, f"获取文件列表失败: {str(e)}")

    elif request.method == 'DELETE':
        file_name = request.args.get('file_name')
        if not file_name:
            return create_response(400, "无效的文件名")

        try:
            file_path = os.path.join(Config.UPLOAD_FOLDER, secure_filename(file_name))
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
                return create_response(200, "文件已删除")
            return create_response(404, "文件不存在")
        except Exception as e:
            return create_response(500, f"删除文件失败: {str(e)}")

    elif request.method == 'PUT':
        try:
            data = request.json
            if not data:
                return create_response(400, "请求数据为空")

            file_name = data.get('file_name')
            file_data = data.get('file_data')
            file_type = data.get('file_type', 'image')

            if not file_name or not file_data:
                return create_response(400, "数据不完整")

            # 验证文件名
            file_name = secure_filename(file_name)
            if not allowed_file(file_name, file_type):
                return create_response(400, "不支持的文件格式")

            # 解码base64数据
            try:
                file_data = file_data.split(",")[1] if "," in file_data else file_data
                file_binary = base64.b64decode(file_data)
            except Exception:
                return create_response(400, "无效的文件数据格式")

            # 生成文件路径
            prefix = 'img_' if file_type == 'image' else 'pdf_'
            unique_filename = f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_name}"
            file_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(file_binary)

            return create_response(200, "文件保存成功", f"/uploads/{unique_filename}")
        except Exception as e:
            return create_response(500, f"保存文件失败: {str(e)}")

    return create_response(405, "不支持的请求方法")


@main.route('/api/uploads/<filename>', methods=['GET'])
def uploaded_file(filename):
    try:
        # 返回文件内容
        upload_folder = os.path.join(os.getcwd(), Config.UPLOAD_FOLDER)
        return send_from_directory(upload_folder, filename)
    except FileNotFoundError:
        # 如果文件不存在，返回 404
        return jsonify({'error': 'File not found'}), 404


@main.route('/api/get_user_answers', methods=['GET', 'PUT'])
def check_question():
    return jsonify({'questions': Questions.query.all()}), 200


@main.route('/api/exams', methods=['GET', 'POST', 'PUT', 'DELETE'])
def exams():
    if request.method == "GET":
        exam_id = request.args.get('exam_id')
        if not exam_id:
            return create_response(400, "缺少参数：exam_id", None)
        else:
            exam = Exams.query.get(exam_id)
            isCorrectAnswer = exam.is_checked
            if exam:
                questions = [exam_question.question for exam_question in exam.questions]
                return create_response(
                    200,
                    "请求成功",
                    [question.as_dict(isCorrectAnswer) for question in questions]
                )
            else:
                return create_response(404, "当前考试不存在！")
    elif request.method == "POST":
        exam = request.json.get('exam')
        questions = request.json.get('questions')

        is_exist_exam = Exams.query.filter_by(name=exam.get('name')).first()
        if is_exist_exam is not None:
            return create_response(300, "考试已经存在")

        # Assuming exam.get('start_time') returns the ISO 8601 formatted string
        start_time_str = exam.get('start_time')
        end_time_str = exam.get('end_time')

        # Convert to a datetime object
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=8)
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=8)

        exam_entry = Exams(
            name=exam.get('name'),
            course_id=exam.get('course_id'),
            start_time=start_time,
            end_time=end_time,
        )
        db.session.add(exam_entry)
        db.session.flush()

        exam_id = exam_entry.id

        for question in questions:
            question_text = question.get('question_text')
            question_type = question.get('question_type')
            correct_answer_temp = question.get('correct_answer')
            options = question.get('options', [])
            steps = question.get('steps', [])
            if question_type == 'proof' or question_type == 'flow':
                correct_answer = json.dumps(correct_answer_temp, ensure_ascii=False)
            else:
                correct_answer = correct_answer_temp
            score = question.get('score')
            question_entry = Question(
                question_text=question_text,
                correct_answer=correct_answer,
                type=question_type,
                score=score,
            )
            db.session.add(question_entry)
            db.session.flush()

            question_id = question_entry.id
            if question_type == 'choice':
                # 处理选择题的选项
                for opt in options:
                    option = QuestionOption(
                        question_id=question_id,
                        option_label=opt.get('option_label'),
                        option_text=opt.get('option_text')
                    )
                    db.session.add(option)

            elif question_type == 'flow':
                # 处理流程题的步骤
                for step in steps:
                    flow = QuestionFlow(
                        question_id=question_id,
                        step_label=str(step.get('step_label')),
                        step_text=step.get('step_text'),
                        is_hidden=step.get('is_hidden', False)
                    )
                    db.session.add(flow)

            exams_question_entry = ExamsQuestion(
                exam_id=exam_id,
                question_id=question_id,
            )
            db.session.add(exams_question_entry)

        db.session.commit()

        return create_response(200, "上传成功！", exam_id)
    elif request.method == "PUT":
        exam_id = request.json.get('exam_id')
        if not exam_id:
            return create_response(400, "请求参数缺失！")

        exam_entry = Exams.query.get(exam_id)
        exam_entry.is_checked = True
        db.session.commit()

        return create_response(200, "完成阅卷！")
    elif request.method == "DELETE":
        exam_id = request.args.get('exam_id')
        if not exam_id:
            return create_response(400, "请求参数缺失！")

        exam_entry = Exams.query.get(exam_id)
        db.session.delete(exam_entry)
        db.session.commit()

        return create_response(200, "删除成功！")


@main.route('/api/exams_list', methods=['GET'])
def exams_list():
    if request.method == "GET":
        course_id = request.args.get('course_id', type=int)
        one_year_ago = datetime.now() - timedelta(days=365)

        exams_list = Exams.query.filter(
            and_(Exams.course_id == course_id,
                 Exams.created_at >= one_year_ago)
        ).all()

        return create_response(
            data=[exam.as_dict() for exam in exams_list],  # 数据
            code=200,  # 状态码
            msg="请求成功！"  # 消息
        )


@main.route("/api/questions", methods=['GET'])
def questions():
    if request.method == "GET":
        question_id = request.args.get('question_id', type=int)
        if question_id:
            questions = Question.query.filter(Question.id == question_id).all()
        else:
            questions = Question.query.all()
        return create_response(
            200,
            msg="请求成功",
            data=[question.as_dict() for question in questions]
        )


@main.route("/api/user_answers", methods=['GET', 'POST', 'PUT'])
def user_answers():
    if request.method == "GET":
        user_id = request.args.get('user_id', type=int)
        exam_id = request.args.get('exam_id', type=int)
        course_id = request.args.get("course_id", type=int)

        if not course_id:
            exam = Exams.query.get(exam_id)
        else:
            exam = CourseContent.query.get(course_id)

        # 查询与考试关联的所有题目及用户的答案
        questions_with_answers = []

        for exam_question in exam.questions:  # 获取与该考试相关的题目
            question = exam_question.question  # 获取题目
            # 查询该用户对该问题的答案
            user_answer = UserAnswer.query.filter_by(user_id=user_id, question_id=question.id).first()

            # 将用户答案添加到题目字典中
            question_dict = question.as_dict()  # 获取题目字典
            question_dict['user_answer'] = user_answer.as_dict() if user_answer else None
            questions_with_answers.append(question_dict)

            print(question_dict, questions_with_answers)

        return create_response(200, "请求成功", questions_with_answers)
    elif request.method == "POST":
        exam_id = request.json.get('exam_id')
        user_answers = request.json.get('user_answer')
        if not exam_id or user_answers is None:
            return create_response(400, "请求参数缺失！")

        exam = Exams.query.get(exam_id)
        for user_answer in user_answers:
            question = Question.query.get(user_answer['question_id'])

            # 获取问题的正确答案
            correct_answer = question.correct_answer
            user_answer_value = user_answer['user_answer']

            # 确保字符串的统一处理
            # 处理字符串引号问题（去掉多余的引号）
            def clean_string(s):
                if isinstance(s, str):
                    s = s.strip().replace('"', '').replace("\\", "'").replace(" ", "")  # 去掉引号和空格
                return s

            correct_answer = clean_string(correct_answer)
            user_answer_value = clean_string(user_answer_value)

            # 如果是 JSON 格式的字符串，进行解析
            try:
                correct_answer_json = json.loads(correct_answer) if isinstance(correct_answer,
                                                                               str) else correct_answer
                user_answer_json = json.loads(user_answer_value) if isinstance(user_answer_value,
                                                                               str) else user_answer_value
            except json.JSONDecodeError:
                correct_answer_json = correct_answer
                user_answer_json = user_answer_value

            score = 0
            # 处理不同类型的题目
            if question.type != 'proof':
                if correct_answer_json == user_answer_json:
                    is_correct = True
                    score = question.score
                elif correct_answer_json != user_answer_json:
                    is_correct = False
                else:
                    is_correct = None
            else:
                # proof 类型题目直接跳过或特殊处理
                is_correct = None

            # 检查是否已经存在答案记录
            existing_answer = UserAnswer.query.filter_by(user_id=user_answer['user_id'],
                                                         question_id=user_answer['question_id']).first()
            if existing_answer:
                return create_response(300, "不可重复提交")  # 如果存在记录，返回不可重复提交的提示

            user_answer_entry = UserAnswer(
                user_id=user_answer['user_id'],
                question_id=user_answer['question_id'],
                user_answer=user_answer_value,
                score=score,
                is_correct=is_correct,
            )
            db.session.add(user_answer_entry)

        db.session.commit()
        return create_response(200, "提交成功！")
    elif request.method == "PUT":
        exam_id = request.json.get('exam_id')
        user_answers = request.json.get('user_answers')
        user_id = request.json.get('user_id')

        if not exam_id or user_answers is None:
            return create_response(400, "请求参数缺失！")

        for user_answer in user_answers:
            user_answer_entry = UserAnswer.query.filter_by(user_id=user_id,
                                                           question_id=user_answer['question_id']).first()
            if user_answer_entry:
                user_answer_entry.score = user_answer['score']

            else:
                user_answer_entry_add = UserAnswer(
                    user_id=user_id,
                    question_id=user_answer['question_id'],
                    is_correct=False,  # 根据需求设置初始值
                    score=user_answer['score'],
                    user_answer=''  # 假设用户的答案字段
                )
                db.session.add(user_answer_entry_add)
            db.session.flush()
        db.session.commit()

        return create_response(200, "提交成功！")


@main.route("/api/course_user_list", methods=['GET'])
def get_user_list():
    if request.method == "GET":
        course_id = request.args.get("course_id")

        if not course_id:
            return create_response(400, "缺少请求参数！")

        users = CourseUser.query.filter(CourseUser.course_id == course_id).all()

        data = [user.user_info.as_dict() for user in users]
        # for user in users:
        #     data.append(user.user_info.as_dict())

        return create_response(200, "请求成功！", data)


@main.route("/api/download_users_mark", methods=['GET'])
def download_user_marks():
    exam_id = request.args.get("exam_id")
    if not exam_id:
        return create_response(400, "缺少exam_id参数")

    # 获取考试信息
    exam = Exams.query.get(exam_id)
    if not exam:
        return create_response(404, "未找到该考试")

    # 按用户查询所有用户的答案
    user_scores_map = {}

    # 遍历该考试的所有题目
    for exam_question in exam.questions:
        question = exam_question.question

        # 获取该题目的所有用户作答记录
        user_answers = UserAnswer.query.filter_by(question_id=question.id).all()
        if not user_answers:
            continue  # 如果没有用户作答，可以跳过该题目

        # 遍历所有作答该题目的用户
        for user_answer in user_answers:
            user_id = user_answer.user.user_id
            user_name = user_answer.user.username
            question_text = user_answer.question.question_text
            user_score = user_answer.score

            # 如果该用户还没有记录，初始化一个
            if user_id not in user_scores_map:
                user_scores_map[user_id] = {
                    'user_id': user_id,
                    'user_name': user_name,
                    'question_score': [],
                    'total_score': 0,
                }

            # 添加该题目得分
            user_scores_map[user_id]['question_score'].append({
                'question_id': question.id,
                'question_text': question_text,
                'user_score': user_score
            })

            # 累加总分
            user_scores_map[user_id]['total_score'] += user_score

    # 将所有用户的成绩数据返回
    result = list(user_scores_map.values())

    return create_response(200, "ok", result)


@main.route("/api/users", methods=['GET', 'DELETE', 'PUT'])
def users():
    if request.method == "GET":
        user_id = request.args.get("user_id")
        if user_id:
            return create_response(300, "功能尚未完善")
        data = []

        user_entries = User.query.all()
        for user_entry in user_entries:
            user = user_entry.as_dict()
            course_users = user_entry.user_info

            course_infos = []
            for course_user in course_users:
                course_info = course_user.course_info
                course_infos.append({
                    "course_id": course_info.id,
                    "course_name": course_info.name,
                })
            user['course_infos'] = course_infos
            data.append(user)

        return create_response(200, "获取所用用户", data)
    elif request.method == "DELETE":
        id = request.args.get("user_id")
        if not id:
            return create_response(400, "缺少参数user_id")

        course_users = CourseUser.query.filter(CourseUser.user_id == id).all()
        if course_users is not None:
            for course_user in course_users:
                db.session.delete(course_user)
            db.session.flush()

        discussion_entries = Discussion.query.filter(Discussion.author_id == id).all()
        if discussion_entries is not None:
            for discussion_entry in discussion_entries:
                db.session.delete(discussion_entry)
            db.session.flush()

        user_entry = User.query.get(id)
        if not user_entry:
            return create_response(300, "所删除的用户不存在")

        try:
            db.session.delete(user_entry)
            db.session.commit()
            return create_response(200, "删除成功！")
        except Exception as e:
            db.session.rollback()
            print(f"删除失败的原因: {str(e)}")  # 打印异常信息
            return create_response(400, "删除失败，请联系管理员")
    elif request.method == "PUT":
        data = request.get_json()  # 获取请求体中的数据

        user = User.query.get(data['id'])
        if not user:
            return create_response(404, "用户未找到")

        # 更新用户基本信息
        user.username = data['username']
        user.user_id = data['user_id']
        user.role = data['role']
        user.phone_number = data['phone_number']

        # 更新课程信息（假设你用 course_user 表来管理用户和课程的关系）
        course_infos = data['course_infos']
        # 清空之前的课程信息
        CourseUser.query.filter(CourseUser.user_id == user.id).delete()

        # 添加新的课程信息
        for course_info in course_infos:
            course_user = CourseUser(user_id=user.id, course_id=course_info['course_id'])
            db.session.add(course_user)

        try:
            db.session.commit()
            return create_response(200, "更新成功")
        except Exception as e:
            db.session.rollback()
            return create_response(400, f"更新失败: {str(e)}")


category_list = (10, 11, 13, 16, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32)


@main.route("/api/knowledge_graph", methods=['GET', 'POST'])
def knowledge_graph():
    if request.method == "GET":
        nodes_data = {}
        nodes_map = {}
        # 生成窗口函数 ROW_NUMBER() 和 PARTITION BY category，ORDER BY value DESC
        ranked_nodes = (
            db.session.query(
                Node.id,
                Node.name,
                Node.value,
                Node.category,
                db.func.row_number().over(partition_by=Node.category, order_by=Node.value.desc()).label('rn')
            )
            .subquery()
        )

        # 现在查询前 5 名节点
        nodes = db.session.query(ranked_nodes.c.id, ranked_nodes.c.name, ranked_nodes.c.value, ranked_nodes.c.category) \
            .filter(ranked_nodes.c.rn <= 8) \
            .all()

        node_sum = 0

        for row in nodes:
            node_sum += row[2]

        # 打印每一行（可选调试输出）
        for row in nodes:
            if row[3] == 1:
                continue

            if row[2] > 100:
                value = int(row[2] / node_sum * 100)
                if value < 10:
                    value = 10
            else:
                value = row[2]
            # nodes_data.append({
            #     "id": row[0],
            #     "name": row[1],
            #     "value": value,
            #     "symbolSize": value,
            #     "category": row[3],
            # })
            if row[3] in category_list:
                break
            nodes_map[row[0]] = {
                "id": row[0],
                "name": row[1],
                "value": value,
                "symbolSize": value,
                "category": row[3],
            }

        categories = Category.query.all()
        categories_data = []
        for category in categories:
            if category.id in category_list:
                break
            categories_data.append({
                "id": category.id,
                "name": category.name,
            })

        links = Link.query.all()
        links_data = []

        for link in links:
            if link.source in nodes_map and link.target in nodes_map:
                links_data.append({
                    "id": link.id,
                    "name": link.name,
                    "source": link.source,
                    "target": link.target,
                })
                nodes_data[link.source] = nodes_map[link.source]
                nodes_data[link.target] = nodes_map[link.target]
        nodes_data = list(nodes_data.values())
        random.shuffle(nodes_data)

        graph = {
            "nodes": nodes_data,
            "categories": categories_data,
            "links": links_data,
        }
        return create_response(200, "ok", graph)

@main.route("/api/save_messages", methods=['PUT'])
def save_messages():
    if request.method == "PUT":
        data = request.get_json()
        session_id = data.get('session_id')
        user_id = data.get('user_id')
        messages = data.get('messages', [])

        if not session_id or not messages:
            return create_response(400, "没有session_id或消息为空")

        # 保存到数据库 (假设有数据库模型 Message 和 Session)
        try:
            # 查询是否已经存在 session_id
            session = Session.query.filter_by(session_id=session_id).first()

            if not session:
                # 如果会话不存在，创建新会话并保存
                session = Session(session_id=session_id, user_id=user_id)
                db.session.add(session)  # 添加会话
                db.session.commit()  # 提交会话数据以便为后续消息使用

            # 保存每条消息
            for msg in messages:
                new_message = Message(
                    session_id=session_id,
                    user_id=user_id,
                    message=msg['content'],
                    message_type=msg['type']
                )
                db.session.add(new_message)

            db.session.commit()  # 提交所有消息
            return create_response(200, "消息保存成功")
        except Exception as e:
            db.session.rollback()
            # 可以打印异常到日志以便调试
            print(f"数据库异常: {str(e)}")
            return create_response(500, "数据库异常")


@main.route('/api/tags', methods=['GET'])
def get_tags():
    """获取所有话题标签列表"""
    topics = Topic.query.all()
    tags = [{'id': topic.id, 'name': topic.tag} for topic in topics]
    return jsonify(tags)


@main.route('/api/topics/<int:topic_id>', methods=['GET'])
def get_topic_content(topic_id):
    """获取指定话题的详细内容"""
    topic = Topic.query.get(topic_id)

    if not topic:
        return jsonify({"error": f"Topic ID {topic_id} not found"}), 404

    # 获取该话题的所有评论
    comments = TopicComment.query.filter_by(topic_id=topic_id).all()

    # 格式化评论数据
    formatted_comments = []
    for comment in comments:
        formatted_comments.append({
            'id': comment.id,
            'user': comment.user,
            'content': comment.content,
            'time': comment.created_at.strftime('%Y-%m-%d %H:%M')
        })

    # 构造返回的数据
    tag_content = {
        'description': topic.content if topic.content else '',
        'pdfUrl': topic.pdf_url if topic.pdf_url else '',
        'comments': formatted_comments
    }

    # 返回数据的外层结构
    tag_contents = {
        topic.id: tag_content
    }

    return jsonify(tag_contents)


@main.route("/api/save_messages", methods=['PUT'])
def save_messages():
    if request.method == "PUT":
        data = request.get_json()
        session_id = data.get('session_id')
        user_id = data.get('user_id')
        messages = data.get('messages', [])

        if not session_id or not messages:
            return create_response(400, "没有session_id或消息为空")

        # 保存到数据库 (假设有数据库模型 Message 和 Session)
        try:
            # 查询是否已经存在 session_id
            session = Session.query.filter_by(session_id=session_id).first()

            if not session:
                # 如果会话不存在，创建新会话并保存
                session = Session(session_id=session_id, user_id=user_id)
                db.session.add(session)  # 添加会话
                db.session.commit()  # 提交会话数据以便为后续消息使用

            # 保存每条消息
            for msg in messages:
                new_message = Message(
                    session_id=session_id,
                    user_id=user_id,
                    message=msg['content'],
                    message_type=msg['type']
                )
                db.session.add(new_message)

            db.session.commit()  # 提交所有消息
            return create_response(200, "消息保存成功")
        except Exception as e:
            db.session.rollback()
            # 可以打印异常到日志以便调试
            print(f"数据库异常: {str(e)}")
            return create_response(500, "数据库异常")