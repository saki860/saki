
# streamlit_app.py
# 完全版（モード切替・要約・フィードバック・リスク判定・Gemini対応）

import streamlit as st
import datetime
import random
from typing import List, Dict, Tuple
import google.generativeai as genai

st.set_page_config(
    page_title="学生相談支援システム",
    page_icon="💭",
    layout="centered"
)

# -------------------------
# Session State
# -------------------------
defaults = {
    "chat_history": [],
    "feedback_data": [],
    "current_risk_level": 0,
    "show_summary": False,
    "summary": "",
    "show_info": False,
    "conversation_mode": "傾聴モード",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------
# Risk
# -------------------------
RISK_KEYWORDS = {
    5: ["死にたい", "自殺", "消えたい"],
    4: ["限界", "絶望", "助けて"],
    3: ["辛い", "しんどい", "不安", "眠れない"],
    2: ["悩み", "困っている", "迷っている"],
}

NEEDS = {
    "listening": ["聞いて", "話を聞いて", "わかってほしい"],
    "solution": ["解決", "方法", "アドバイス", "どうすれば"],
    "thinking": ["一緒に考えたい", "どう思う", "迷っている"]
}

def analyze_risk(text:str)->Tuple[int,list]:
    found=[]
    level=1
    for l, kws in RISK_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                found.append(kw)
                level=max(level,l)
    return level, found

def analyze_needs(text:str):
    scores={k:0 for k in NEEDS}
    for k, arr in NEEDS.items():
        for w in arr:
            if w in text:
                scores[k]+=1
    return max(scores,key=scores.get) if max(scores.values()) else "listening"

def response_style():
    return random.choice([
        "共感中心",
        "気持ちの整理",
        "深掘り質問",
        "視点の転換",
        "強みの発見"
    ])

def build_prompt(risk, needs, mode):
    base = """
あなたは学生向け相談パートナーです。
「私はAIです」という自己紹介は不要です。
自然で温かい会話をしてください。

禁止:
- 医療診断
- 危険行為の推奨
- 個人情報収集

応答は150〜300文字程度。
"""
    if mode == "傾聴モード":
        mode_text = """
気持ちの受容を最優先。
アドバイスは最小限。
"""
    else:
        mode_text = """
具体的な解決策を2〜3個提示。
選択肢形式で提案。
"""
    return f"""{base}

リスク:{risk}
ニーズ:{needs}
スタイル:{response_style()}

{mode_text}
"""

def gemini_response(message, history, api_key, risk, needs, mode):
    genai.configure(api_key=api_key)

    models=[
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash"
    ]

    hist="\n".join(
        [f"{m['role']}:{m['content']}" for m in history[-10:]]
    )

    prompt=f"""
{build_prompt(risk,needs,mode)}

会話履歴:
{hist}

相談者:
{message}
"""

    last_error=None

    for model_name in models:
        try:
            model=genai.GenerativeModel(model_name)
            res=model.generate_content(
                prompt,
                generation_config={
                    "temperature":0.9,
                    "top_p":0.95,
                    "max_output_tokens":600
                }
            )
            return res.text
        except Exception as e:
            last_error=e

    return f"応答生成エラー: {last_error}"

def make_summary(history, api_key):
    try:
        genai.configure(api_key=api_key)
        model=genai.GenerativeModel("gemini-2.5-flash")

        txt="\n".join(
            [f"{m['role']}:{m['content']}" for m in history]
        )

        prompt=f"""
以下の相談履歴を要約してください。

1. 相談テーマ
2. 気持ちの整理
3. 話し合った内容
4. 今後のヒント

{txt}
"""
        return model.generate_content(prompt).text
    except Exception as e:
        return str(e)

# -------------------------
# UI
# -------------------------
st.title("💭 学生相談支援システム")

with st.sidebar:
    st.header("⚙️ 対話設定")

    st.session_state.conversation_mode = st.radio(
        "応答モード",
        ["傾聴モード", "解決策提案モード"]
    )

    st.markdown("---")

    if st.button("会話をリセット"):
        st.session_state.chat_history=[]
        st.rerun()

api_key=st.text_input("Gemini API Key", type="password")

if not st.session_state.chat_history:
    st.info("👋 こんにちは。今日はどんなことについて話したいですか？")

col1,col2=st.columns(2)

with col1:
    if st.button("📝 会話まとめ", disabled=len(st.session_state.chat_history)<2):
        if api_key:
            st.session_state.summary=make_summary(
                st.session_state.chat_history,
                api_key
            )
            st.session_state.show_summary=True

with col2:
    if st.button("ℹ️ 情報"):
        st.session_state.show_info=not st.session_state.show_info

if st.session_state.show_info:
    st.warning("""
緊急時:
・学校カウンセラー
・保健室
・信頼できる大人
・よりそいホットライン
""")

if st.session_state.show_summary:
    st.markdown("## 会話のまとめ")
    st.write(st.session_state.summary)

for i,msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        if (
            msg["role"]=="assistant"
            and i==len(st.session_state.chat_history)-1
        ):
            score=st.slider(
                "この応答は役立ちましたか？",
                1,5,3,
                key=f"fb{i}"
            )
            if st.button("送信", key=f"send{i}"):
                st.session_state.feedback_data.append({
                    "score":score,
                    "time":datetime.datetime.now().isoformat()
                })
                st.success("ありがとうございます")

user_input=st.chat_input("相談内容を入力してください")

if user_input:
    if not api_key:
        st.error("Gemini API Keyを入力してください")
        st.stop()

    st.session_state.chat_history.append({
        "role":"user",
        "content":user_input
    })

    risk, words = analyze_risk(user_input)
    needs = analyze_needs(user_input)

    with st.spinner("考えています..."):
        answer = gemini_response(
            user_input,
            st.session_state.chat_history,
            api_key,
            risk,
            needs,
            st.session_state.conversation_mode
        )

    st.session_state.chat_history.append({
        "role":"assistant",
        "content":answer,
        "risk":risk,
        "needs":needs,
        "keywords":words
    })

    st.rerun()

st.markdown("---")
st.caption("学生向け相談支援システム")
