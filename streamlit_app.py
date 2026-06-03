# streamlit_app.py
import streamlit as st
import datetime
import random
from typing import Dict, List, Tuple
import google.generativeai as genai

st.set_page_config(page_title="学生相談支援システム", page_icon="💭")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "conversation_mode" not in st.session_state:
    st.session_state.conversation_mode = "傾聴モード"

RISK_KEYWORDS = {
    5:["死にたい","自殺","消えたい"],
    4:["限界","助けて","絶望"],
    3:["辛い","しんどい","不安","眠れない"],
    2:["悩み","困っている","迷っている"],
}

def analyze_risk_level(text:str):
    level=1
    for k,v in RISK_KEYWORDS.items():
        if any(w in text for w in v):
            level=max(level,k)
    return level

def analyze_needs(text:str):
    if any(x in text for x in ["どうすれば","解決","方法","アドバイス"]):
        return "solution"
    return "listening"

def get_response_style():
    return random.choice([
        "共感を中心に応答する",
        "気持ちを要約する",
        "深掘り質問を行う",
        "新しい視点を提示する",
        "強みに注目する"
    ])

def generate_system_prompt(risk_level, needs_type, mode):
    mode_prompt = """
【傾聴モード】
共感を重視しアドバイスは最小限。
""" if mode=="傾聴モード" else """
【解決策提案モード】
具体的な選択肢を2〜3個提示。
"""
    return f"""
あなたは学生向け相談パートナーです。
危険行為を推奨しないこと。
自然で温かい会話を行うこと。

リスクレベル:{risk_level}
ニーズ:{needs_type}
応答スタイル:{get_response_style()}

{mode_prompt}
"""

def generate_response(msg, api_key, risk, needs, mode, history):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    hist = "\n".join(
        [f"{m['role']}:{m['content']}" for m in history[-10:]]
    )
    prompt = generate_system_prompt(risk, needs, mode) + f"""
履歴:
{hist}

相談:
{msg}
"""
    res = model.generate_content(
        prompt,
        generation_config={
            "temperature":0.9,
            "max_output_tokens":500
        }
    )
    return res.text

st.title("💭 学生相談支援システム")

with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state.conversation_mode = st.radio(
        "応答モード",
        ["傾聴モード","解決策提案モード"]
    )

api_key = st.text_input("Gemini API Key", type="password")

if not st.session_state.chat_history:
    st.info("👋 こんにちは。今日はどんなことについて話したいですか？")

for m in st.session_state.chat_history:
    with st.chat_message(m["role"]):
        st.write(m["content"])

user_input = st.chat_input("相談内容を入力してください")

if user_input and api_key:
    st.session_state.chat_history.append({
        "role":"user",
        "content":user_input,
        "timestamp":datetime.datetime.now().isoformat()
    })

    risk = analyze_risk_level(user_input)
    needs = analyze_needs(user_input)

    with st.spinner("考えています..."):
        reply = generate_response(
            user_input,
            api_key,
            risk,
            needs,
            st.session_state.conversation_mode,
            st.session_state.chat_history
        )

    st.session_state.chat_history.append({
        "role":"assistant",
        "content":reply,
        "timestamp":datetime.datetime.now().isoformat()
    })

    st.rerun()
