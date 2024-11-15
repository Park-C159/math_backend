import json
import sympy as sp
from itertools import product
import pandas as pd
import re

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


# # 测试示例
# expr_str1 = "p | q"
# expr_str2 = "~(~p & ~q)"
#
# # 生成真值表并判断等值性
# is_equivalent, truth_table = generate_truth_table_for_equivalence(expr_str1, expr_str2)
#
# print(f"表达式 '{expr_str1}' 和 '{expr_str2}' 是否等值: {is_equivalent}")
# print(truth_table)

# 测试示例
# expr_str1 = "p | ~p"  # 重言式
# expr_str2 = "p & q"  # 非重言式
#
# # 生成真值表并判断是否为重言式
# is_tautology1, truth_table1 = generate_truth_table(expr_str1)
# is_tautology2, truth_table2 = generate_truth_table(expr_str2)
#
# print(f"表达式: {expr_str1} 是重言式: {is_tautology1}")
# print(truth_table1)
# print("\n")
# print(f"表达式: {expr_str2} 是重言式: {is_tautology2}")
# print(truth_table2)


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
            print(exercise)
            question_text = exercise.get('question_text')
            question_type = exercise.get('question_type')
            correct_answer = exercise.get('check')  # 获取check作为正确答案

            # 创建Question对象
            question = Question(
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


def get_questions_data(course_id=None):
    if course_id is None:
        return None

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