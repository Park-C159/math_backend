import json

import pymysql
import pandas as pd

from datetime import datetime, timedelta


def upload_mark():
    """ 连接 MySQL """
    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="123456",
        database="math",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
    print("✅ MySQL 连接成功！")
    return conn


def readExcel(filepath):
    """ 读取 Excel 并返回前两列数据 """
    try:
        df = pd.read_excel(filepath, sheet_name="单科试卷得分明细表", engine="openpyxl")
        print("✅ Excel 读取成功！")

        return df


    except Exception as e:
        print("❌ 读取 Excel 失败:", e)
        return None


# def insertUserToMySQL(conn, df):
#     """ 将数据批量插入 MySQL """
#     if df is None or df.empty:
#         print("❌ 数据为空，无法插入")
#         return
#
#     # 提取前两列数据，并去掉前两行（如果 Excel 表头有额外信息）
#     user_df = df.iloc[2:-1, :2]  # 跳过前两行和最后一行，获取前两列
#     user_df.columns = ["user_id", "username"]  # 重命名列
#     print(user_df.head())  # 预览数据
#
#     cursor = conn.cursor()
#
#     sql = """
#     INSERT INTO users (user_id, username, password, phone_number, role, gender, extra)
#     VALUES (%s, %s, %s, %s, %s, %s, %s)
#     """
#
#     # 生成假数据
#     fake_password = "password123"
#     fake_phone = "13800000000"
#     fake_role = "student"
#     fake_gender = None
#     fake_extra = ""
#
#     data = [
#         (row["user_id"], row["username"], fake_password, fake_phone, fake_role, fake_gender, fake_extra)
#         for _, row in user_df.iterrows()
#     ]
#
#     try:
#         cursor.executemany(sql, data)  # 批量插入
#         conn.commit()
#         print(f"✅ {cursor.rowcount} 条数据插入成功！")
#     except Exception as e:
#         conn.rollback()
#         print("❌ 插入数据失败:", e)
#
#     cursor.close()


def insertUserToMySQL(conn, df, question_ids):
    """ 将数据批量插入 MySQL，并在 user_answer 关联上 question_id """
    if df is None or df.empty:
        print("❌ 数据为空，无法插入")
        return

    # 提取前两列数据，并去掉前两行（如果 Excel 表头有额外信息）
    df_new = df.iloc[2:-1, :]  # 跳过前两行和最后一行，获取前两列
    df_new.rename(columns={df_new.columns[0]: 'user_id', df_new.columns[1]: 'username'}, inplace=True)

    from_width = 10
    to_width = min(df_new.shape[1], from_width + 2 * len(question_ids))

    print(df_new.head())

    cursor = conn.cursor()

    user_ids = []

    sql_user = """
    INSERT INTO users (user_id, username, password, phone_number, role, gender, extra)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    sql_user_answer = """
    INSERT INTO user_answer (user_id, question_id, user_answer, is_correct, score)
    VALUES (%s, %s, %s, %s, %s)
    """

    sql_course_user = """
    INSERT INTO course_user (course_id, user_id)
    VALUES (%s, %s)
    """

    # 生成假数据
    fake_password = "password123"
    fake_phone = "13800000000"
    fake_role = "student"
    fake_gender = None
    fake_extra = ""

    for _, u in df_new.iterrows():
        cursor.execute(sql_user,
                       (u["user_id"], u["username"], fake_password, fake_phone, fake_role, fake_gender, fake_extra))
        user_id = cursor.lastrowid  # 获取刚插入的题目 ID
        user_ids.append(user_id)

        cursor.execute(sql_course_user, (2, user_id))

        i = 0

        for answer_idx in range(from_width, to_width, 2):
            is_correct = True
            user_score = u[answer_idx]
            user_answer = u[answer_idx + 1]
            if pd.isna(user_answer):
                user_answer = ""

            if user_score == 0:
                is_correct = False
            cursor.execute(sql_user_answer, (user_id, question_ids[i], user_answer, is_correct, user_score))
            i += 1

    conn.commit()

    # user_data = [
    #     (row["user_id"], row["username"], fake_password, fake_phone, fake_role, fake_gender, fake_extra)
    #     for _, row in user_df.iterrows()
    # ]
    #
    # try:
    #     cursor.executemany(sql_user, user_data)  # 批量插入用户
    #     conn.commit()
    #     print(f"✅ {cursor.rowcount} 条用户数据插入成功！")
    #
    #     # 获取所有 user_id
    #     user_ids = [row["user_id"] for _, row in user_df.iterrows()]
    #
    #     # 插入 user_answer
    #     sql_user_answer = """
    #     INSERT INTO user_answer (user_id, question_id, user_answer, is_correct, score, answered_at)
    #     VALUES (%s, %s, %s, %s, %s, %s)
    #     """
    #     default_answer = "-"
    #     default_score = -1
    #     default_time = datetime.now()
    #
    #     user_answer_data = [
    #         (user_id, question_id, default_answer, None, default_score, default_time)
    #         for user_id in user_ids
    #         for question_id in question_ids
    #     ]
    #
    #     cursor.executemany(sql_user_answer, user_answer_data)
    #     conn.commit()
    #     print(f"✅ {len(user_answer_data)} 条用户答题记录插入成功！")
    #
    # except Exception as e:
    #     conn.rollback()
    #     print("❌ 插入数据失败:", e)

    cursor.close()


def insertExamToMySQL(conn, exam_name):
    """ 将考试数据插入 MySQL """
    if exam_name is None or exam_name == "":
        print("❌ 数据为空，无法插入")

        return None

    cursor = conn.cursor()

    sql = """
    INSERT INTO exams (name, course_id, start_time, end_time, is_checked, is_submitted)
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    # 生成假数据
    fake_course_id = 2
    fake_start_time = datetime(2024, 10, 15, 9, 0, 0)  # 假设的开始时间
    fake_end_time = fake_start_time + timedelta(hours=2)  # 2 小时后结束
    fake_is_checked = 0
    fake_is_submitted = 0

    data = (exam_name, fake_course_id, fake_start_time, fake_end_time, fake_is_checked, fake_is_submitted)

    try:
        # cursor.executemany(sql, data)  # 批量插入
        cursor.execute(sql,
                       (exam_name, fake_course_id, fake_start_time, fake_end_time, fake_is_checked, fake_is_submitted))
        conn.commit()
        exam_id = cursor.lastrowid  # 获取插入的 exam_id
        print(f"✅ 考试 '{exam_name}' 插入成功，exam_id: {exam_id}")
        return exam_id
    except Exception as e:
        conn.rollback()
        print("❌ 插入考试数据失败:", e)

    cursor.close()


def insertQuestionToMySQL(conn, exam_id, questions=None):
    """ 插入题目，并建立 exam-question 关联 """

    if exam_id is None:
        print("❌ exam_id 无效，无法插入题目")
        return

    cursor = conn.cursor()

    # 如果没有传入 questions，则使用默认题目
    if questions is None:
        questions = [
            {
                "type": "choice",
                "question_text": "已知向量 $\\boldsymbol{\\vec{a}}, \\boldsymbol{\\vec{b}}$ 满足 $|\\bm{a}| = 5$, $|\\bm{b}| = 12$, $|\\bm{a} + \\bm{b}| = 13$，则 "
                                 "$|\\bm{a} - \\bm{b}|$ = __________。",
                "score": 3,
                "correct_answer": "C",
                "options": [
                    {"option": "A", "value": "5"},
                    {"option": "B", "value": "12"},
                    {"option": "C", "value": "13"},
                    {"option": "D", "value": "17"}
                ]
            },
            {
                "type": "choice",
                "question_text": "假设向量 a, b 不共线，若 λa + μb = 0，则 ____。",
                "score": 3,
                "correct_answer": "C",
                "options": [
                    {"option": "A", "value": "$\\lambda + \\mu = 1$"},
                    {"option": "B", "value": "$\\lambda + \\mu = 0$"},
                    {"option": "C", "value": "$\\lambda = \\mu = 0$"},
                    {"option": "D", "value": "$\\lambda = 0$ 或 $\\mu = 0$"}
                ]
            }
        ]

    question_ids = []  # 记录插入的问题 ID

    for q in questions:
        # 插入题目
        sql_question = "INSERT INTO question (type, question_text, score, correct_answer) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql_question, (q["type"], q["question_text"], q["score"], q["correct_answer"]))
        question_id = cursor.lastrowid  # 获取刚插入的题目 ID
        question_ids.append(question_id)

        # 插入选项
        if "options" in q and q["options"]:
            sql_option = "INSERT INTO question_option (question_id, option_label, option_text) VALUES (%s, %s, %s)"
            option_data = [(question_id, opt['option'], opt['value']) for opt in q["options"]]
            cursor.executemany(sql_option, option_data)



    # 关联 exams_question 表
    sql_exam_question = "INSERT INTO exams_question (exam_id, question_id) VALUES (%s, %s)"
    exam_question_data = [(exam_id, q_id) for q_id in question_ids]
    cursor.executemany(sql_exam_question, exam_question_data)

    conn.commit()
    print(f"✅ {len(questions)} 道题目及其选项插入成功！")

    cursor.close()
    return question_ids


if __name__ == '__main__':
    conn = upload_mark()  # 连接 MySQL
    filepath = "static/单科试卷得分明细表(2023期中).xlsx"  # Excel 文件路径
    df = readExcel(filepath)  # 读取 Excel 数据
    exam_id = insertExamToMySQL(conn, "2023年期中考试")

    question_path = "static/2023期中.json"

    with open(question_path, "r", encoding="utf-8") as f:
        questions = json.load(f)


    question_ids = insertQuestionToMySQL(conn, exam_id, questions)
    insertUserToMySQL(conn, df, question_ids)  # 插入 MySQL

    conn.close()  # 关闭 MySQL 连接
    print("🔌 MySQL 连接已关闭！")
