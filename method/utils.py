import json
import sympy as sp
from itertools import product
import pandas as pd
import re
import requests
import statistics
import numpy as np
from scipy.stats import skew, kurtosis
from flask import jsonify

from method import db
from method.models import *


def generate_truth_table(expr_str):
    """
    该代码可以处理简单的逻辑表达式，如与（&）、或（|）、非（~）、蕴涵（>>）、等价（==）等运算。
    :param expr_str: 输入逻辑表达式字符串
    :return: 是否是重言式，真值表
    """
    # 解析输入的逻辑表达式
    expr = sp.sympify(expr_str)

    # 提取表达式中的所有符号
    symbols = sorted(expr.free_symbols, key=lambda x: x.name)

    # 构建所有符号的真值组合
    truth_values = []
    results = []
    for values in product([True, False], repeat=len(symbols)):
        # 将符号和对应的真值组合成字典
        assignment = dict(zip(symbols, values))
        # 计算表达式在当前真值组合下的结果
        result = expr.subs(assignment)
        truth_values.append(values)
        results.append(result)

    # 判断是否为重言式
    is_tautology = all(results)

    # 构建真值表 DataFrame
    df = pd.DataFrame(truth_values, columns=[str(s) for s in symbols])
    df['Result'] = results

    return is_tautology, df


def generate_truth_table_for_equivalence(expr_str1, expr_str2):
    # 解析输入的逻辑表达式
    expr1 = sp.sympify(expr_str1)
    expr2 = sp.sympify(expr_str2)

    # 提取两个表达式中的所有符号
    symbols = sorted(expr1.free_symbols.union(expr2.free_symbols), key=lambda x: x.name)

    # 构建所有符号的真值组合
    truth_values = []
    results_expr1 = []
    results_expr2 = []
    for values in product([True, False], repeat=len(symbols)):
        # 将符号和对应的真值组合成字典
        assignment = dict(zip(symbols, values))

        # 计算两个表达式在当前真值组合下的结果
        result1 = expr1.subs(assignment)
        result2 = expr2.subs(assignment)

        # 保存当前的真值组合和结果
        truth_values.append(values)
        results_expr1.append(result1)
        results_expr2.append(result2)

    # 判断两个表达式是否等值
    are_equivalent = all(res1 == res2 for res1, res2 in zip(results_expr1, results_expr2))

    # 构建真值表 DataFrame
    df = pd.DataFrame(truth_values, columns=[str(s) for s in symbols])
    df[expr_str1] = results_expr1
    df[expr_str2] = results_expr2

    return are_equivalent, df


def convert_to_python_operators(expr_str):
    # 创建一个替换映射
    replacements = {
        r'∨': '|',  # 或运算符
        r'∧': '&',  # 与运算符
        r'¬': '~',  # 非运算符
        r'→': '>>',  # 蕴涵运算符
        r'↔': '==',  # 等价运算符
    }

    # 逐一替换表达式中的符号
    for old, new in replacements.items():
        expr_str = re.sub(old, new, expr_str)

    return expr_str


def convert_to_logic_symbols(expr_str):
    # 创建一个反向替换映射
    reverse_replacements = {
        r'\|': '∨',  # 或运算符
        r'&': '∧',  # 与运算符
        r'~': '¬',  # 非运算符
        r'>>': '→',  # 蕴涵运算符
        r'==': '↔'  # 等价运算符
    }

    # 逐一将运算符替换回逻辑符号
    for old, new in reverse_replacements.items():
        expr_str = re.sub(old, new, expr_str)

    return expr_str


def save_questions(course_id, exercises):
    """
    根据题目类型，将题目和对应的选项或步骤分别保存到不同的表中。
    """
    try:
        for exercise in exercises:
            question_text = exercise.get('question_text')
            question_type = exercise.get('question_type')
            correct_answer = exercise.get('check')  # 获取check作为正确答案

            # 创建Question对象
            question = Questions(
                course_id=course_id,
                question_type=question_type,
                question_text=question_text,
                correct_answer=correct_answer if type(correct_answer) == str else ''
            )
            db.session.add(question)
            db.session.flush()  # 获取question_id

            # 根据题目类型处理不同的保存逻辑
            if question_type == 'choice':
                # 处理选择题的选项
                options = exercise.get('options', [])
                for opt in options:
                    option = Option(
                        question_id=question.id,
                        option_label=opt.get('option_label'),
                        option_text=opt.get('option_text')
                    )
                    db.session.add(option)

            elif question_type == 'flow':
                # 处理流程题的步骤
                steps = exercise.get('steps', [])
                for step in steps:
                    flow = Flows(
                        question_id=question.id,
                        step_label=str(step.get('step_label')),
                        step_text=step.get('step_text'),
                        is_hidden=step.get('is_hidden', False)
                    )
                    db.session.add(flow)

            # 其他题型（如'blank'和'proof'）不需要额外的选项或步骤表处理

        # 提交所有更改
        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()  # 回滚事务
        print(f"保存题目时出错: {e}")
        return False


def add_test(info):
    try:
        # 从 info 字典中提取值
        test_title = info.get('test_title')
        test_course = info.get('test_course')

        # 创建 CourseContent 实例
        new_course = CourseContent(
            course_name='考试',  # chapter_title
            chapter_title=test_course,  # chapter_title
            section_title=test_title,  # section_title
            planned_hours=0,  # 根据需要设置计划小时
            content='',  # 根据需要设置内容
            video_link=''  # 根据需要设置视频链接
        )

        # 添加到数据库会话并提交
        db.session.add(new_course)
        db.session.commit()

        print(f'新课程已添加: {new_course}')
        return new_course.id
    except Exception as e:
        db.session.rollback()  # 回滚会话以撤销更改
        print(f'插入失败: {e}')
        return False  # 插入失败


def user_answers_test():
    request = {

    }
    if request.method == "GET":
        user_id = request.args.get('user_id', type=int)
        exam_id = request.args.get('exam_id', type=int)
        course_id = request.args.get('course_id', type=int)

        exam = Exams.query.get(exam_id)
        if not exam:
            return None  # 如果找不到考试，返回 None

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


def get_questions_data(course_id=None):
    if course_id is None:
        return None

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

    return questions_data


def create_response(code, msg, data=None):
    """
    返回统一格式的 JSON 响应
    :param data: 响应的数据，可以是列表、字典或其他类型
    :param code: 状态码，默认为 200
    :param msg: 响应消息，默认为 "请求成功！"
    :return: Flask jsonify 对象，返回给前端
    """
    response = {
        'code': code,
        'data': data,
        'msg': msg
    }
    return jsonify(response)


def calculate_score_statistics(scores):
    """
    Calculate statistical metrics for a list of scores.

    Args:
        scores (list): List of numerical score values

    Returns:
        dict: Dictionary containing various statistical metrics
    """
    if not scores:
        return {
            "average_score": None,
            "median_score": None,
            "mode_score": None,
            "standard_deviation": None,
            "variance": None,
            "range": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "coefficient_of_variation": None,
            "skewness": None,
            "kurtosis": None
        }

    avg_score = statistics.mean(scores)
    median_score = statistics.median(scores)

    try:
        mode_score = statistics.mode(scores)
    except statistics.StatisticsError:
        mode_score = "无众数"

    stdev_score = statistics.stdev(scores) if len(scores) > 1 else 0
    variance_score = statistics.variance(scores) if len(scores) > 1 else 0
    range_score = max(scores) - min(scores) if scores else 0

    q1, q3 = np.percentile(scores, [25, 75])
    iqr_score = q3 - q1

    cv_score = (stdev_score / avg_score) * 100 if avg_score != 0 else 0
    skewness_score = skew(scores)
    kurtosis_score = kurtosis(scores)

    return {
        "average_score": avg_score,
        "median_score": median_score,
        "mode_score": mode_score,
        "standard_deviation": stdev_score,
        "variance": variance_score,
        "range": range_score,
        "q1": q1,
        "q3": q3,
        "iqr": iqr_score,
        "coefficient_of_variation": cv_score,
        "skewness": skewness_score,
        "kurtosis": kurtosis_score
    }


def calculate_question_statistics(question, user_answers):
    """
    Calculate statistics for a specific question based on user answers.

    Args:
        question: The question object
        user_answers: List of user answers for the question

    Returns:
        dict: Dictionary containing question statistics
    """
    if not user_answers:
        return None

    scores = [ua.score for ua in user_answers]
    stats = calculate_score_statistics(scores)

    return {
        "question_id": question.id,
        "question_text": question.question_text,
        **stats
    }


def calculate_exam_statistics(exam_id):
    """
    Calculate comprehensive statistics for an exam, including per-question stats
    and overall performance metrics.

    Args:
        exam_id: ID of the exam

    Returns:
        dict: Dictionary containing user scores, question statistics, and total statistics
    """
    from .models import Exams, UserAnswer, User

    # Get exam information
    exam = Exams.query.get(exam_id)
    if not exam:
        return None

    user_scores_map = {}
    question_stats_map = {}

    for exam_question in exam.questions:
        question = exam_question.question
        user_answers = UserAnswer.query.filter_by(question_id=question.id).all()

        if not user_answers:
            continue

        # Calculate question statistics
        question_stats = calculate_question_statistics(question, user_answers)
        if question_stats:
            question_stats_map[question.id] = question_stats

        # Calculate per-user scores
        for user_answer in user_answers:
            user_id = user_answer.user.user_id
            user_name = user_answer.user.username
            user_score = user_answer.score
            user_answer_value = user_answer.user_answer

            if user_id not in user_scores_map:
                user_scores_map[user_id] = {
                    'user_id': user_id,
                    'user_name': user_name,
                    'question_score': [],
                    'total_score': 0,
                }

            user_scores_map[user_id]['question_score'].append({
                'question_id': question.id,
                'question_text': question.question_text,
                'user_score': user_score,
                'user_answer_value': user_answer_value,
                'question_type': question.type,
            })

            user_scores_map[user_id]['total_score'] += user_score

    # Calculate total score statistics
    total_scores = [user["total_score"] for user in user_scores_map.values()]
    total_stats = calculate_score_statistics(total_scores)

    # Rename keys to be more specific
    total_stats_renamed = {}
    for key, value in total_stats.items():
        new_key = key.replace("score", "total_score") if "score" in key else f"{key}_total_score"
        total_stats_renamed[new_key] = value

    return {
        "user_scores": list(user_scores_map.values()),
        "question_statistics": list(question_stats_map.values()),
        "total_statistics": total_stats_renamed
    }


def get_class_statistics(exam_id):
    """
    Get statistics for a class based on an exam.
    Returns basic statistics that can be used in reports or analysis.

    Args:
        exam_id: ID of the exam

    Returns:
        dict: Dictionary containing class statistics
    """
    try:
        from .models import Exams, UserAnswer, User

        # Get exam information
        exam = Exams.query.get(exam_id)
        if not exam:
            return {}

        # Get all users who took the exam
        user_scores = {}

        for exam_question in exam.questions:
            question = exam_question.question

            # Get user answers for this question
            user_answers = UserAnswer.query.filter_by(question_id=question.id).all()

            for user_answer in user_answers:
                user_id = user_answer.user_id

                if user_id not in user_scores:
                    user_scores[user_id] = 0

                user_scores[user_id] += user_answer.score if user_answer.score is not None else 0

        # Calculate statistics from user scores
        if not user_scores:
            return {}

        scores = list(user_scores.values())

        # Sort scores to determine ranks
        sorted_scores = sorted(scores, reverse=True)

        # Create a mapping of user_id to their rank
        user_ranks = {}
        for user_id, score in user_scores.items():
            rank = sorted_scores.index(score) + 1  # Add 1 because ranks start at 1
            user_ranks[user_id] = rank

        stats = calculate_score_statistics(scores)

        return {
            "average_score": stats["average_score"],
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "median_score": stats["median_score"],
            "standard_deviation": stats["standard_deviation"],
            "user_ranks": user_ranks,
            "total_students": len(scores)
        }
    except Exception as e:
        print(f"Error in get_class_statistics: {str(e)}")
        return {}


def call_ai_api(prompt):
    url = "http://llms-se.baidu-int.com:8200/chat/completions"
    headers = {
        "Authorization": f"Bearer sk---jingyasen---lnYU+fwaaHuhoeZUvnlzHA==",
        "Content-Type": "application/json"
    }
    messages = [
        {"role": "system", "content": "你是一个成绩分析助手。"},
        {"role": "user", "content": prompt}
    ]
    payload = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 10000
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            return "No valid response received."
    else:
        return f"Error: {response.status_code}, {response.text}"
