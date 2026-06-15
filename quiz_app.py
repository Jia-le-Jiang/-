import streamlit as st
import pandas as pd
import os
import re
import sys


# ==================== 获取程序所在目录（支持打包后运行）====================
def get_base_dir():
    """获取程序所在目录（支持PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()

# ==================== 图片目录配置 ====================
IMAGE_DIR = os.path.join(BASE_DIR, "images")
EXCEL_PATH = os.path.join(BASE_DIR, "题库整理.xlsx")

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="海上风电安全知识竞赛",
    page_icon="🌊",
    layout="wide"
)


# ==================== 判断是否为图片 ====================
def is_image_file(filename):
    if not isinstance(filename, str):
        return False
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
    return any(filename.lower().endswith(ext) for ext in image_extensions)


def get_image_path(filename):
    return os.path.join(IMAGE_DIR, filename)


# ==================== 题型统一映射 ====================
def normalize_type(type_name):
    if pd.isna(type_name):
        return "未知"
    type_map = {
        "单选": "单选题",
        "单选择": "单选题",
        "判断": "判断题",
        "是非": "判断题",
        "判断题": "判断题",
        "多选": "多选题",
        "多选择": "多选题",
    }
    type_str = str(type_name).strip()
    return type_map.get(type_str, type_str)


# ==================== 加载题库 ====================
@st.cache_data
def load_questions():
    try:
        # 检查Excel文件是否存在
        if not os.path.exists(EXCEL_PATH):
            st.error(f"❌ 未找到题库文件！")
            st.info(f"请确保以下文件存在：{EXCEL_PATH}")
            return []

        df = pd.read_excel(EXCEL_PATH)

        questions = []
        skipped_count = 0

        for index, row in df.iterrows():
            question_id = row["题号"]
            if pd.isna(question_id):
                skipped_count += 1
                continue

            raw_type = str(row["题型"]).strip() if pd.notna(row["题型"]) else ""
            question_type = normalize_type(raw_type)

            question_text = row["题目"] if pd.notna(row["题目"]) else ""
            if not question_text:
                skipped_count += 1
                continue

            explain_raw = row["纠正/解析"] if pd.notna(row["纠正/解析"]) else "暂无解析"

            options = []
            option_letters = []
            answer_raw = str(row["答案"]).strip() if pd.notna(row["答案"]) else ""

            if question_type == "判断题":
                options = ["对", "错"]
                option_letters = ["A", "B"]
                if answer_raw == "对":
                    answer_letters = ["A"]
                    answer_display = "对"
                elif answer_raw == "错":
                    answer_letters = ["B"]
                    answer_display = "错"
                else:
                    answer_letters = [answer_raw] if answer_raw in ["A", "B"] else []
                    answer_display = answer_raw
            else:
                for opt in ["选项A", "选项B", "选项C", "选项D", "选项E", "选项F"]:
                    if opt in df.columns:
                        opt_val = row[opt]
                        if pd.notna(opt_val) and str(opt_val).strip():
                            opt_text = str(opt_val).strip()
                            if opt_text and opt_text != 'nan':
                                options.append(opt_text)
                                option_letters.append(opt[-1])

                if not options:
                    skipped_count += 1
                    continue

                answer_letters = []
                answer_display = answer_raw
                for ch in answer_raw.upper():
                    if ch in option_letters:
                        answer_letters.append(ch)

            questions.append({
                "id": question_id,
                "type": question_type,
                "question": question_text,
                "options": options,
                "option_letters": option_letters,
                "answer_letters": answer_letters,
                "answer_display": answer_display,
                "explain": str(explain_raw) if explain_raw != "暂无解析" else "暂无解析"
            })

        if questions:
            type_counts = {}
            for q in questions:
                t = q["type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            st.success(f"✅ 成功加载 {len(questions)} 道题目")
            st.write("📊 题型统计：", type_counts)

        return questions

    except Exception as e:
        st.error(f"❌ 加载题库失败：{e}")
        return []


# ==================== 初始化状态 ====================
def init_session():
    if "questions" not in st.session_state:
        all_questions = load_questions()
        if not all_questions:
            st.session_state.questions = []
            return

        st.session_state.all_questions = all_questions
        st.session_state.questions = all_questions.copy()
        st.session_state.total = len(st.session_state.questions)

        if st.session_state.total > 0:
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.session_state.quiz_completed = False
            st.session_state.wrong_questions = []
            st.session_state.answered_status = [False] * st.session_state.total
            st.session_state.question_results = [None] * st.session_state.total
            st.session_state.selected_answer = None
            st.session_state.show_result = False
            st.session_state.result_correct = False
            st.session_state.result_message = ""
            st.session_state.result_explain = ""

    if "filter_type" not in st.session_state and st.session_state.get("all_questions"):
        types = list(set([q["type"] for q in st.session_state.all_questions]))
        st.session_state.type_list = ["全部"] + sorted(types)
        st.session_state.filter_type = "全部"

    if "show_wrong_only" not in st.session_state:
        st.session_state.show_wrong_only = False

# ==================== 应用筛选 ====================
def apply_filter():
    if st.session_state.filter_type == "全部":
        st.session_state.questions = st.session_state.all_questions.copy()
    else:
        st.session_state.questions = [q for q in st.session_state.all_questions if
                                      q["type"] == st.session_state.filter_type]

    st.session_state.total = len(st.session_state.questions)
    if st.session_state.total > 0:
        st.session_state.quiz_order = list(range(st.session_state.total))
    st.session_state.current_index = 0
    st.session_state.score = 0
    st.session_state.answered = False
    st.session_state.quiz_completed = False
    st.session_state.wrong_questions = []
    st.session_state.answered_status = [False] * st.session_state.total
    st.session_state.question_results = [None] * st.session_state.total
    st.session_state.selected_answer = None
    st.session_state.show_result = False


# ==================== 获取当前题目 ====================
def get_current_question():
    if st.session_state.show_wrong_only:
        if st.session_state.wrong_questions and st.session_state.current_index < len(st.session_state.wrong_questions):
            return st.session_state.wrong_questions[st.session_state.current_index]
        return None
    else:
        if st.session_state.questions and st.session_state.current_index < st.session_state.total:
            idx = st.session_state.quiz_order[st.session_state.current_index]
            return st.session_state.questions[idx]
        return None


# ==================== 显示单选题（图片直接显示）====================
def display_single_choice(question, q_idx, disabled):
    options = question['options']
    option_letters = question['option_letters']
    option_dict = {letter: opt for letter, opt in zip(option_letters, options)}

    selected_letter = None

    # 每行显示2个选项
    num_options = len(options)
    cols_per_row = 2

    for row in range(0, num_options, cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            opt_idx = row + col_idx
            if opt_idx >= num_options:
                break
            letter = option_letters[opt_idx]
            opt_text = options[opt_idx]

            with cols[col_idx]:
                # 显示图片或文字
                if is_image_file(opt_text):
                    img_path = get_image_path(opt_text)
                    if os.path.exists(img_path):
                        st.image(img_path, caption=f"选项 {letter}", use_container_width=True)
                    else:
                        st.warning(f"图片不存在：{opt_text}")
                        st.write(f"{letter}. {opt_text}")
                else:
                    st.write(f"{letter}. {opt_text}")

                # 单选按钮
                radio_key = f"single_{q_idx}_{letter}"
                if st.radio(
                        "选择",
                        [letter],
                        key=radio_key,
                        label_visibility="collapsed",
                        disabled=disabled,
                        index=None
                ):
                    selected_letter = letter

    return selected_letter, option_dict


# ==================== 显示多选题（图片直接显示）====================
def display_multiple_choice(question, q_idx, disabled):
    options = question['options']
    option_letters = question['option_letters']
    option_dict = {letter: opt for letter, opt in zip(option_letters, options)}

    st.write("**请选择所有正确答案（可多选）：**")

    selected_letters = []
    num_options = len(options)
    cols_per_row = 2

    for row in range(0, num_options, cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            opt_idx = row + col_idx
            if opt_idx >= num_options:
                break
            letter = option_letters[opt_idx]
            opt_text = options[opt_idx]

            with cols[col_idx]:
                if is_image_file(opt_text):
                    img_path = get_image_path(opt_text)
                    if os.path.exists(img_path):
                        st.image(img_path, caption=f"选项 {letter}", use_container_width=True)
                    else:
                        st.warning(f"图片不存在：{opt_text}")
                        st.write(f"{letter}. {opt_text}")

                    if st.checkbox(f"选择选项 {letter}", key=f"multi_{q_idx}_{letter}", disabled=disabled, value=False):
                        selected_letters.append(letter)
                else:
                    if st.checkbox(f"{letter}. {opt_text}", key=f"multi_{q_idx}_{letter}", disabled=disabled,
                                   value=False):
                        selected_letters.append(letter)

    return sorted(selected_letters), option_dict


# ==================== 显示判断题 ====================
def display_judgment(question, q_idx, disabled):
    selected_display = st.radio(
        "请选择答案：",
        ["A. 对", "B. 错"],
        key=f"judge_{q_idx}",
        disabled=disabled,
        label_visibility="collapsed",
        index=None
    )

    selected_letter = None
    if selected_display:
        selected_letter = selected_display.split(".")[0]

    option_dict = {"A": "对", "B": "错"}
    return selected_letter, option_dict


# ==================== 显示结果 ====================
def show_result():
    if st.session_state.show_result:
        if st.session_state.result_correct:
            st.success(f"✅ {st.session_state.result_message}")
        else:
            st.error(f"❌ {st.session_state.result_message}")
        if st.session_state.result_explain and st.session_state.result_explain != "暂无解析":
            st.info(f"📖 解析：{st.session_state.result_explain}")


# ==================== 获取用户答案的文字显示 ====================
def get_answer_display(selected_letters, option_dict):
    if not selected_letters:
        return ""
    items = []
    for letter in selected_letters:
        if letter in option_dict:
            opt = option_dict[letter]
            if is_image_file(opt):
                items.append(f"{letter}.[图片]")
            else:
                items.append(f"{letter}.{opt}")
    return "、".join(items)


# ==================== 题目列表侧边栏 ====================
def show_question_list():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 题目列表")

    questions = st.session_state.questions
    total = st.session_state.total

    if total == 0:
        st.sidebar.info("暂无题目")
        return

    cols_per_row = 10

    for row in range(0, total, cols_per_row):
        cols = st.sidebar.columns(cols_per_row, gap="small")
        for col_idx in range(cols_per_row):
            q_idx = row + col_idx
            if q_idx >= total:
                break

            q = questions[q_idx]
            q_num = q['id']

            is_answered = st.session_state.answered_status[q_idx] if q_idx < len(
                st.session_state.answered_status) else False
            result = st.session_state.question_results[q_idx] if q_idx < len(
                st.session_state.question_results) else None
            is_current = (q_idx == st.session_state.current_index and not st.session_state.show_wrong_only)

            if is_current:
                label = f"**{q_num}**"
                button_type = "primary"
            elif is_answered:
                if result is True:
                    label = f"✓{q_num}"
                    button_type = "secondary"
                elif result is False:
                    label = f"✗{q_num}"
                    button_type = "secondary"
                else:
                    label = f"✓{q_num}"
                    button_type = "secondary"
            else:
                label = str(q_num)
                button_type = "secondary"

            if cols[col_idx].button(
                    label,
                    key=f"qlist_{q_idx}",
                    use_container_width=True,
                    type=button_type
            ):
                if not st.session_state.show_wrong_only:
                    st.session_state.current_index = q_idx
                    st.session_state.answered = False
                    st.session_state.selected_answer = None
                    st.session_state.show_result = False
                    st.rerun()


# ==================== 错题本页面 ====================
def show_wrong_book():
    st.header("📖 错题本")

    if not st.session_state.wrong_questions:
        st.info("🎉 太棒了！你还没有错题，继续保持！")
        if st.button("返回练习"):
            st.session_state.show_wrong_only = False
            st.rerun()
        return

    st.write(f"共 **{len(st.session_state.wrong_questions)}** 道错题")

    for i, wrong in enumerate(st.session_state.wrong_questions, 1):
        with st.expander(f"错题 {i}：{wrong['question'][:80]}..."):
            st.write(f"**题型：** {wrong['type']}")
            st.write(f"**你的答案：** {wrong['user_answer']}")
            st.write(f"**正确答案：** {wrong['correct_answer']}")
            st.write(f"**解析：** {wrong['explain']}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清空错题本"):
            st.session_state.wrong_questions = []
            st.rerun()
    with col2:
        if st.button("🔙 返回练习"):
            st.session_state.show_wrong_only = False
            st.rerun()


# ==================== 提交答案处理 ====================
def handle_submit(q, option_dict):
    # 获取用户答案
    if q['type'] == "多选题":
        user_letters = sorted(st.session_state.selected_answer) if st.session_state.selected_answer else []
    else:
        user_letters = [st.session_state.selected_answer] if st.session_state.selected_answer else []

    if not user_letters:
        st.warning("请先选择答案")
        return False

    # 获取正确答案
    correct_letters = q['answer_letters']

    # 获取显示文字
    user_display = get_answer_display(user_letters, option_dict)
    correct_display = get_answer_display(correct_letters, option_dict)

    # 判断对错
    is_correct = set(user_letters) == set(correct_letters)

    # 记录本题结果
    st.session_state.question_results[st.session_state.current_index] = is_correct

    if is_correct:
        st.session_state.score += 1
        st.session_state.result_correct = True
        st.session_state.result_message = "回答正确！"
    else:
        st.session_state.result_correct = False
        st.session_state.result_message = f"回答错误！正确答案是：{correct_display}"

        # 记录错题
        already_recorded = False
        for w in st.session_state.wrong_questions:
            if w.get('question') == q['question']:
                already_recorded = True
                break

        if not already_recorded:
            st.session_state.wrong_questions.append({
                "id": q['id'],
                "type": q['type'],
                "question": q['question'],
                "user_answer": user_display,
                "correct_answer": correct_display,
                "explain": q['explain']
            })

    st.session_state.result_explain = q['explain']
    st.session_state.show_result = True
    st.session_state.answered = True
    st.session_state.answered_status[st.session_state.current_index] = True

    return True


# ==================== 下一题处理 ====================
def handle_next():
    if st.session_state.current_index + 1 < st.session_state.total:
        st.session_state.current_index += 1
        st.session_state.answered = False
        st.session_state.selected_answer = None
        st.session_state.show_result = False
        st.rerun()
    else:
        st.session_state.quiz_completed = True
        st.rerun()


# ==================== 主界面 ====================
def main():
    init_session()

    if st.session_state.get("show_wrong_only", False):
        show_wrong_book()
        return

    st.title("🌊 海上风电安全知识竞赛")
    st.caption("每日一练，安全第一 | 支持单选、多选、判断")

    if not st.session_state.get("all_questions"):
        st.stop()

    # ==================== 侧边栏 ====================
    with st.sidebar:
        st.header("⚙️ 设置")

        if hasattr(st.session_state, 'type_list') and st.session_state.type_list:
            selected_type = st.selectbox(
                "按题型练习",
                st.session_state.type_list,
                index=st.session_state.type_list.index(st.session_state.filter_type),
                key="filter_select"
            )
            if selected_type != st.session_state.filter_type:
                st.session_state.filter_type = selected_type
                apply_filter()
                st.rerun()

        st.markdown("---")
        st.header("📊 统计")
        st.metric("当前题库总数", st.session_state.total)
        st.metric("已完成", sum(st.session_state.answered_status))
        st.metric("当前得分", f"{st.session_state.score} / {st.session_state.total}")

        wrong_count = len(st.session_state.wrong_questions)
        if wrong_count > 0:
            st.warning(f"📖 错题数：{wrong_count}")
            if st.button("📖 查看错题本", use_container_width=True):
                st.session_state.show_wrong_only = True
                st.rerun()
        else:
            st.success("错题数：0")

        show_question_list()

    # ==================== 答题完成 ====================
    if st.session_state.quiz_completed:
        st.success("🎉 恭喜你完成了所有题目！")

        if st.session_state.total > 0:
            score_percent = st.session_state.score / st.session_state.total * 100
            st.metric("最终得分", f"{st.session_state.score} / {st.session_state.total} ({score_percent:.1f}%)")
            st.progress(st.session_state.score / st.session_state.total)

        if st.session_state.wrong_questions:
            st.warning(f"📖 你有 {len(st.session_state.wrong_questions)} 道错题需要复习")
            if st.button("📖 查看错题本"):
                st.session_state.show_wrong_only = True
                st.rerun()
        else:
            st.balloons()
            st.success("完美！没有错题！")

        if st.button("🔄 重新练习"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        return

    # ==================== 答题主界面 ====================
    if st.session_state.total == 0:
        st.warning("当前筛选条件下没有题目，请切换题型")
        if st.button("显示全部题目"):
            st.session_state.filter_type = "全部"
            apply_filter()
            st.rerun()
        return

    q = get_current_question()
    if q is None:
        st.error("出错了，无法获取题目")
        return

    # 进度
    progress_value = st.session_state.current_index / st.session_state.total
    st.progress(progress_value)
    st.write(f"第 {st.session_state.current_index + 1} / {st.session_state.total} 题")
    st.caption(f"题型：{q['type']}")

    # 题目
    st.markdown(f"### {q['question']}")

    # 构建选项字典
    option_dict = {letter: opt for letter, opt in zip(q['option_letters'], q['options'])}

    # 根据题型显示选项（未答题时才显示选项）
    if not st.session_state.answered:
        if q['type'] == "单选题":
            selected = display_single_choice(q, st.session_state.current_index, False)
            if selected[0]:  # selected_letter
                st.session_state.selected_answer = selected[0]
        elif q['type'] == "多选题":
            selected = display_multiple_choice(q, st.session_state.current_index, False)
            st.session_state.selected_answer = selected[0]
        else:  # 判断题
            selected = display_judgment(q, st.session_state.current_index, False)
            if selected[0]:  # selected_letter
                st.session_state.selected_answer = selected[0]
    else:
        # 已答题时显示禁用的选项
        if q['type'] == "单选题":
            display_single_choice(q, st.session_state.current_index, True)
        elif q['type'] == "多选题":
            display_multiple_choice(q, st.session_state.current_index, True)
        else:
            display_judgment(q, st.session_state.current_index, True)

    # 显示结果
    show_result()

    # 提交按钮和下一题按钮
    col1, col2 = st.columns(2)

    with col1:
        if not st.session_state.answered:
            if st.button("✅ 提交答案", use_container_width=True):
                handle_submit(q, option_dict)
                st.rerun()
        else:
            st.button("✅ 已提交", disabled=True, use_container_width=True)

    with col2:
        if st.session_state.answered:
            if st.button("⏩ 下一题", use_container_width=True):
                handle_next()


if __name__ == "__main__":
    main()