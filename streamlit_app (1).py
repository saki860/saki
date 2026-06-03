import streamlit as st
import json
import datetime
from typing import Dict, List, Tuple
import google.generativeai as genai

# ページ設定
st.set_page_config(
    page_title="学生相談支援システム",
    page_icon="💭",
    layout="centered"
)

# セッション状態の初期化
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'feedback_data' not in st.session_state:
    st.session_state.feedback_data = []
if 'current_risk_level' not in st.session_state:
    st.session_state.current_risk_level = 0
if 'api_key_set' not in st.session_state:
    st.session_state.api_key_set = False
if 'show_info' not in st.session_state:
    st.session_state.show_info = False
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'show_summary' not in st.session_state:
    st.session_state.show_summary = False
# ①モード切り替え用
if 'chat_mode' not in st.session_state:
    st.session_state.chat_mode = 'listening'  # 'listening' or 'solution'

# リスクレベル判定用キーワード辞書
RISK_KEYWORDS = {
    5: {
        'keywords': ['死にたい', '自殺', '消えたい', '生きる意味', '死のう',
                    '飛び降り', '首を', 'リストカット', '薬を大量に'],
        'weight': 10
    },
    4: {
        'keywords': ['誰も信じられない', '絶望', '助けて', '限界', '耐えられない',
                    '居場所がない', '孤独', '消えたい', '不登校', '行けない'],
        'weight': 7
    },
    3: {
        'keywords': ['辛い', 'しんどい', '苦しい', 'ストレス', '眠れない',
                    '食欲がない', '疲れた', '不安', '心配', 'プレッシャー'],
        'weight': 4
    },
    2: {
        'keywords': ['悩み', '困っている', 'どうしよう', '迷っている',
                    '友達', '勉強', '進路', '部活', '先生'],
        'weight': 2
    },
    1: {
        'keywords': ['相談', '聞いて', '話したい', 'アドバイス'],
        'weight': 1
    }
}

# ニーズ判定用キーワード
NEEDS_KEYWORDS = {
    'listening': ['聞いてほしい', '話を聞いて', '誰かに話したい', '吐き出したい',
                 'わかってほしい', '共感', '理解してほしい'],
    'solution': ['どうすれば', '解決', '方法', 'アドバイス', '改善',
                '対策', 'やり方', '教えて'],
    'thinking': ['どう思う', '考えたい', '一緒に', '選択', '決断',
                '進路', 'どちらが', '迷っている']
}


def analyze_risk_level(text: str) -> Tuple[int, List[str]]:
    """相談内容からリスクレベルを判定"""
    detected_keywords = []
    risk_scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    text_lower = text.lower()

    for level, data in RISK_KEYWORDS.items():
        for keyword in data['keywords']:
            if keyword in text_lower:
                risk_scores[level] += data['weight']
                detected_keywords.append(keyword)

    max_level = 1
    max_score = 0
    for level, score in risk_scores.items():
        if score > max_score:
            max_score = score
            max_level = level

    return max_level, detected_keywords


def analyze_needs(text: str) -> str:
    """相談者のニーズを分析"""
    text_lower = text.lower()
    needs_scores = {'listening': 0, 'solution': 0, 'thinking': 0}

    for need_type, keywords in NEEDS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                needs_scores[need_type] += 1

    if max(needs_scores.values()) == 0:
        return 'listening'

    return max(needs_scores, key=needs_scores.get)


def generate_system_prompt(risk_level: int, needs_type: str, chat_mode: str) -> str:
    """①リスクレベル・ニーズ・モードに応じたシステムプロンプトを生成"""

    # ③「私はAIです」を使わない自然なペルソナ設定
    base_guardrails = """
あなたは学生向けの相談支援員として会話してください。以下のガードレールを厳守してください:
- 自分を「AI」や「人工知能」と名乗ったり説明したりしない
- 医療的診断や治療の提供は行わない
- 違法行為や危険行為を推奨しない
- 個人情報の収集や保存を求めない
- 常に相談者の安全を最優先する
- 応答は簡潔で温かみのあるトーンで、200文字程度を目安にする
- ②応答のバリエーションを豊かにする:
  * 同じような言い回しや定型文を繰り返さない
  * 相談内容に合わせて言葉を変える（口語的、やわらかい表現、問いかけなど）
  * 「そうなんですね」「それは大変でしたね」などを毎回使わず、多様な受け答えをする
  * ときに短く簡潔に、ときに具体的に、応答の長さにも緩急をつける
"""

    # ①モードに応じた基本スタンス
    mode_prompts = {
        'listening': """
【モード: 傾聴モード】
今は「聞く」ことを最優先にしてください。
- アドバイスや解決策は基本的に控える
- 相談者の気持ちを受け止め、共感を示す
- 質問するときも、詰問にならないよう1つだけ、やさしく聞く
- 「頑張れ」などの励ましより、「そういう気持ちになるのは自然なことだよ」など、気持ちに寄り添う言葉を選ぶ
""",
        'solution': """
【モード: 解決策提案モード】
相談者が具体的に前進できるよう、実践的なサポートをしてください。
- 状況を整理しながら、具体的な選択肢や行動案を提示する
- 押しつけにならず「こういう方法もあるよ」という提案スタイルにする
- 複数の選択肢を示し、最終判断は相談者に委ねる
- 小さな一歩から始められる現実的なアドバイスを心がける
"""
    }

    risk_prompts = {
        5: """
【緊急対応モード】
相談者は深刻な危機状態にあります。以下を実施してください:
1. 相談者の気持ちを否定せず、傾聴する
2. 生きる価値があることを穏やかに伝える
3. 必ず専門家への相談を強く推奨する
4. 学校のカウンセラー、保健室、信頼できる大人への相談を促す
5. 必要に応じて、いのちの電話(0120-783-556)などの緊急連絡先を案内する
""",
        4: """
【高リスク対応モード】
相談者は高いストレス状態にあります:
1. 丁寧に傾聴し、相談者の気持ちを受け止める
2. 一人で抱え込まないよう促す
3. 学校のカウンセラーや保健室、信頼できる先生への相談を推奨する
4. 具体的なサポート先の情報を提供する
""",
        3: """
【注意深い対話モード】
相談者は中程度のストレスを抱えています:
1. 共感的に傾聴する
2. 相談者の状況を整理し、理解を示す
3. 必要に応じて、友人や先生への相談も選択肢として提示する
4. セルフケアの方法を提案する
""",
        2: """
【通常対話モード】
相談者の悩みに対して:
1. 親身に傾聴する
2. 相談者の気持ちを理解し、共感を示す
3. 建設的な視点を提供する
""",
        1: """
【軽度相談モード】
日常的な相談に対して:
1. フレンドリーに対話する
2. 相談者の話を丁寧に聞く
3. 適切なアドバイスを提供する
"""
    }

    needs_prompts = {
        'listening': """
【ニーズ: 傾聴重視】
- 相談者は話を聞いてもらいたいと感じています
- アドバイスは最小限にし、共感と理解を示すことに重点を置いてください
- 受容的な応答を心がけてください
""",
        'solution': """
【ニーズ: 解決策提示】
- 相談者は具体的な解決策やアドバイスを求めています
- 実践的で具体的な提案を行ってください
- 押し付けにならないよう、複数の選択肢を提示してください
""",
        'thinking': """
【ニーズ: 共に考える】
- 相談者は一緒に考えてほしいと感じています
- 質問を通じて相談者自身の考えを引き出してください
- 意思決定のサポートをしつつ、最終判断は相談者に委ねてください
"""
    }

    prompt = (
        base_guardrails
        + mode_prompts.get(chat_mode, mode_prompts['listening'])
        + risk_prompts.get(risk_level, risk_prompts[1])
        + needs_prompts.get(needs_type, needs_prompts['listening'])
    )

    return prompt


def generate_conversation_summary(chat_history: List[Dict], api_key: str) -> str:
    """会話全体のまとめを生成"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        conversation_text = ""
        for msg in chat_history:
            if msg['role'] == 'user':
                conversation_text += f"相談者: {msg['content']}\n"
            else:
                conversation_text += f"サポーター: {msg['content']}\n"

        summary_prompt = f"""
以下は学生相談システムでの会話履歴です。この会話を振り返り、以下の観点でまとめてください:

【会話履歴】
{conversation_text}

【まとめる内容】
1. 相談の主なテーマ（2-3行）
2. 相談者の気持ちや状況（2-3行）
3. 話し合った内容のポイント（3-5項目、箇条書き）
4. 今後に向けてのヒント（2-3行）

温かく、前向きなトーンでまとめてください。専門用語は避け、相談者が自分の状況を客観的に振り返れるようにしてください。
"""

        generation_config = {
            "temperature": 0.5,
            "max_output_tokens": 800,
        }

        response = model.generate_content(summary_prompt, generation_config=generation_config)
        return response.text

    except Exception as e:
        return f"まとめの生成中にエラーが発生しました: {str(e)[:150]}"


def generate_ai_response_gemini(
    user_message: str,
    risk_level: int,
    needs_type: str,
    chat_history: List[Dict],
    api_key: str,
    chat_mode: str
) -> str:
    """Gemini APIを使用してAI応答を生成"""
    try:
        genai.configure(api_key=api_key)

        models_to_try = [
            'gemini-2.5-flash-lite',
            'gemini-2.5-flash',
            'gemini-1.5-flash'
        ]

        # ①モードを渡してプロンプト生成
        system_prompt = generate_system_prompt(risk_level, needs_type, chat_mode)

        history_text = ""
        for msg in chat_history[-4:]:
            if msg['role'] == 'user':
                history_text += f"相談者: {msg['content']}\n"
            else:
                history_text += f"サポーター: {msg['content']}\n"

        # ②バリエーション向上のための追加指示
        variation_hint = """
※応答の多様性を意識してください:
- 前の応答と似た書き出しや言い回しを避ける
- 相談内容のキーワードを拾って、その人の言葉で返す
- ときには問いかけで返す、ときには短く受け止めるだけにするなど、緩急をつける
"""

        full_prompt = (
            system_prompt
            + variation_hint
            + f"\n\n【会話履歴】\n{history_text}\n\n"
            + f"【現在の相談】\n相談者: {user_message}\n\nサポーター:"
        )

        last_error = None
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)

                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]

                generation_config = {
                    "temperature": 0.85,   # ②バリエーション向上のため少し高め
                    "top_p": 0.92,
                    "max_output_tokens": 500,
                }

                response = model.generate_content(
                    full_prompt,
                    safety_settings=safety_settings,
                    generation_config=generation_config
                )
                return response.text
            except Exception as e:
                last_error = e
                continue

        error_msg = str(last_error)
        if "429" in error_msg or "quota" in error_msg.lower():
            return """
申し訳ございません。現在、APIの利用制限に達しています。

**解決方法:**
- 数分待ってから再度お試しください
- 1日の制限に達した場合は、翌日00:00（太平洋時間）にリセットされます

**今すぐ相談したい場合:**
- 学校のカウンセラー
- 保健室の先生
- いのちの電話: 0120-783-556（24時間対応）
"""
        else:
            return f"エラーが発生しました。しばらくしてから再度お試しください。\n\nエラー詳細: {error_msg[:150]}"

    except Exception as e:
        return f"予期しないエラーが発生しました: {str(e)[:150]}\n\nAPIキーが正しいか確認してください。"


# ============================================================
# UI構築
# ============================================================

st.title("💭 学生相談支援システム")

# APIキー入力エリア
if not st.session_state.api_key_set:
    st.info("🔑 Google Gemini APIキーを入力してください")

    st.success("""
    **2025年時点の無料枠情報:**
    - 使用モデル: Gemini 2.5 Flash / Flash-Lite
    - Flash-Lite: 1日1,000リクエストまで（高速）
    - Flash: 1日250リクエストまで（高品質）
    - クレジットカード不要
    """)

    api_key_input = st.text_input(
        "APIキー",
        type="password",
        help="APIキーはGoogle AI Studioで取得できます"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("APIキーを設定", type="primary", use_container_width=True):
            if api_key_input:
                st.session_state.api_key = api_key_input
                st.session_state.api_key_set = True
                st.rerun()
            else:
                st.error("APIキーを入力してください")

    with col2:
        st.link_button(
            "APIキーを取得",
            "https://aistudio.google.com/app/apikey",
            use_container_width=True
        )

    st.markdown("---")
    st.markdown("""
    ### 📱 このシステムについて

    学生の皆さんが安心して相談できる場を提供します。

    **特徴:**
    - ✅ 傾聴モード・解決策提案モードの切り替え
    - ✅ あなたのニーズに合わせた応答
    - ✅ 必要に応じて専門家への連携

    **注意事項:**
    - ⚠️ このシステムは専門的な医療やカウンセリングの代替ではありません
    - ⚠️ 緊急時は必ず専門家にご相談ください
    - 🔒 相談内容は安全に管理されます
    """)

else:
    # ============================================================
    # メインチャットエリア
    # ============================================================

    # トップバーメニュー
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown("### 💬 相談窓口")
    with col2:
        if st.button("📝 まとめ", use_container_width=True, disabled=len(st.session_state.chat_history) < 2):
            if len(st.session_state.chat_history) >= 2:
                with st.spinner("会話をまとめています..."):
                    st.session_state.summary = generate_conversation_summary(
                        st.session_state.chat_history,
                        st.session_state.api_key
                    )
                    st.session_state.show_summary = True
    with col3:
        if st.button("ℹ️ 情報", use_container_width=True):
            st.session_state.show_info = not st.session_state.show_info
    with col4:
        if st.button("🔄 リセット", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.current_risk_level = 0
            st.session_state.summary = None
            st.session_state.show_summary = False
            st.rerun()

    # ①モード切り替えUI
    st.markdown("---")
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        listening_selected = st.session_state.chat_mode == 'listening'
        if st.button(
            "🫂 傾聴モード" + (" ✅" if listening_selected else ""),
            use_container_width=True,
            type="primary" if listening_selected else "secondary"
        ):
            if st.session_state.chat_mode != 'listening':
                st.session_state.chat_mode = 'listening'
                st.rerun()
    with mode_col2:
        solution_selected = st.session_state.chat_mode == 'solution'
        if st.button(
            "💡 解決策提案モード" + (" ✅" if solution_selected else ""),
            use_container_width=True,
            type="primary" if solution_selected else "secondary"
        ):
            if st.session_state.chat_mode != 'solution':
                st.session_state.chat_mode = 'solution'
                st.rerun()

    # モード説明
    if st.session_state.chat_mode == 'listening':
        st.caption("🫂 **傾聴モード**: 気持ちに寄り添い、じっくり話を聞きます。アドバイスより共感を大切にします。")
    else:
        st.caption("💡 **解決策提案モード**: 具体的な行動や選択肢を一緒に考えます。前向きに進むためのヒントをお伝えします。")

    # 情報パネル（トグル表示）
    if st.session_state.show_info:
        with st.expander("📊 システム情報", expanded=True):
            if st.session_state.chat_history:
                last_message = st.session_state.chat_history[-1]
                if last_message['role'] == 'assistant':
                    needs_labels = {
                        'listening': '傾聴重視',
                        'solution': '解決策提示',
                        'thinking': '共に考える'
                    }
                    mode_labels = {
                        'listening': '傾聴モード',
                        'solution': '解決策提案モード'
                    }
                    st.info(f"**検出ニーズ:** {needs_labels.get(last_message.get('needs_type', 'listening'))}")
                    st.info(f"**現在のモード:** {mode_labels.get(st.session_state.chat_mode, '傾聴モード')}")

            st.warning("""
            **緊急時の連絡先:**
            - いのちの電話: 0120-783-556
            - 学校のカウンセラー
            - 保健室の先生
            """)

            if st.button("APIキーを変更"):
                st.session_state.api_key_set = False
                st.rerun()

    # まとめ表示パネル
    if st.session_state.show_summary and st.session_state.summary:
        with st.expander("📝 会話のまとめ", expanded=True):
            st.markdown(st.session_state.summary)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 閉じる", use_container_width=True):
                    st.session_state.show_summary = False
                    st.rerun()
            with col2:
                st.download_button(
                    "💾 保存",
                    data=st.session_state.summary,
                    file_name=f"counseling_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

    st.markdown("---")

    # チャット履歴表示
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            # ③「私はAIです」を使わない自己紹介
            st.info("👋 こんにちは。何でも話しかけてみてください。ゆっくり、あなたのペースで大丈夫です。")

        for i, message in enumerate(st.session_state.chat_history):
            if message['role'] == 'user':
                with st.chat_message("user", avatar="🙂"):
                    st.write(message['content'])
            else:
                with st.chat_message("assistant", avatar="💭"):
                    st.write(message['content'])

                    # フィードバック機能（最新のメッセージのみ）
                    if i == len(st.session_state.chat_history) - 1:
                        with st.expander("この応答は役に立ちましたか？"):
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                rating = st.select_slider(
                                    "評価",
                                    options=[1, 2, 3, 4, 5],
                                    value=3,
                                    key=f"rating_{i}"
                                )
                            with col2:
                                if st.button("👍 送信", key=f"submit_{i}", use_container_width=True):
                                    feedback = {
                                        'message_id': i,
                                        'rating': rating,
                                        'timestamp': datetime.datetime.now().isoformat()
                                    }
                                    st.session_state.feedback_data.append(feedback)
                                    st.success("ありがとうございます！")

    # ユーザー入力
    st.markdown("---")
    user_input = st.chat_input("相談内容を入力してください...")

    if user_input:
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.datetime.now().isoformat()
        })

        risk_level, detected_keywords = analyze_risk_level(user_input)
        st.session_state.current_risk_level = max(st.session_state.current_risk_level, risk_level)

        needs_type = analyze_needs(user_input)

        # ①現在のモードを渡してAI応答生成
        with st.spinner("考えています..."):
            ai_response = generate_ai_response_gemini(
                user_input,
                risk_level,
                needs_type,
                st.session_state.chat_history,
                st.session_state.api_key,
                st.session_state.chat_mode
            )

        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.datetime.now().isoformat(),
            'risk_level': risk_level,
            'needs_type': needs_type,
            'detected_keywords': detected_keywords
        })

        st.rerun()

# フッター
st.markdown("---")
st.caption("💡 このシステムは学生の相談支援を目的としています。緊急時は必ず専門家にご相談ください。")
