import streamlit as st
import json
import datetime
from typing import Dict, List, Tuple
import re

# ページ設定
st.set_page_config(
    page_title="学生相談支援システム",
    page_icon="💭",
    layout="wide"
)

# セッション状態の初期化
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'feedback_data' not in st.session_state:
    st.session_state.feedback_data = []
if 'current_risk_level' not in st.session_state:
    st.session_state.current_risk_level = 0

# リスクレベル判定用キーワード辞書
RISK_KEYWORDS = {
    5: {  # 最高リスク - 即座の専門家介入が必要
        'keywords': ['死にたい', '自殺', '消えたい', '生きる意味', '死のう', 
                    '飛び降り', '首を', 'リストカット', '薬を大量に'],
        'weight': 10
    },
    4: {  # 高リスク - 専門家への連携推奨
        'keywords': ['誰も信じられない', '絶望', '助けて', '限界', '耐えられない',
                    '居場所がない', '孤独', '消えたい', '不登校', '行けない'],
        'weight': 7
    },
    3: {  # 中リスク - AI対話継続・注意深い傾聴
        'keywords': ['辛い', 'しんどい', '苦しい', 'ストレス', '眠れない',
                    '食欲がない', '疲れた', '不安', '心配', 'プレッシャー'],
        'weight': 4
    },
    2: {  # 低リスク - AI対話継続
        'keywords': ['悩み', '困っている', 'どうしよう', '迷っている',
                    '友達', '勉強', '進路', '部活', '先生'],
        'weight': 2
    },
    1: {  # 最低リスク - 通常対話
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
    """
    相談内容からリスクレベルを判定
    
    Args:
        text: 相談テキスト
    
    Returns:
        リスクレベル(1-5)と検出されたキーワードのリスト
    """
    detected_keywords = []
    risk_scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    text_lower = text.lower()
    
    # 各リスクレベルのキーワードをチェック
    for level, data in RISK_KEYWORDS.items():
        for keyword in data['keywords']:
            if keyword in text_lower:
                risk_scores[level] += data['weight']
                detected_keywords.append(keyword)
    
    # 最も高いスコアのレベルを返す
    max_level = 1
    max_score = 0
    for level, score in risk_scores.items():
        if score > max_score:
            max_score = score
            max_level = level
    
    return max_level, detected_keywords


def analyze_needs(text: str) -> str:
    """
    相談者のニーズを分析
    
    Returns:
        'listening', 'solution', 'thinking' のいずれか
    """
    text_lower = text.lower()
    needs_scores = {'listening': 0, 'solution': 0, 'thinking': 0}
    
    for need_type, keywords in NEEDS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                needs_scores[need_type] += 1
    
    # 最もスコアの高いニーズを返す
    if max(needs_scores.values()) == 0:
        return 'listening'  # デフォルトは傾聴
    
    return max(needs_scores, key=needs_scores.get)


def generate_system_prompt(risk_level: int, needs_type: str) -> str:
    """
    リスクレベルとニーズに応じたシステムプロンプトを生成
    """
    base_guardrails = """
あなたは学生向けの相談支援AIアシスタントです。以下のガードレールを厳守してください:
- 医療的診断や治療の提供は行わない
- 違法行為や危険行為を推奨しない
- 個人情報の収集や保存を求めない
- 常に相談者の安全を最優先する
- 専門家ではないことを明示する
"""
    
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
- 「そうだったんですね」「大変でしたね」など、受容的な応答を心がけてください
""",
        'solution': """
【ニーズ: 解決策提示】
- 相談者は具体的な解決策やアドバイスを求めています
- 実践的で具体的な提案を行ってください
- ただし、押し付けにならないよう、複数の選択肢を提示してください
""",
        'thinking': """
【ニーズ: 共に考える】
- 相談者は一緒に考えてほしいと感じています
- 質問を通じて相談者自身の考えを引き出してください
- 意思決定のサポートをしつつ、最終判断は相談者に委ねてください
"""
    }
    
    prompt = base_guardrails + risk_prompts.get(risk_level, risk_prompts[1]) + needs_prompts.get(needs_type, needs_prompts['listening'])
    
    return prompt


def generate_ai_response(user_message: str, risk_level: int, needs_type: str, chat_history: List[Dict]) -> str:
    """
    AI応答を生成（実際の実装ではClaude APIやOpenAI APIを使用）
    ここではデモ用の応答生成
    """
    system_prompt = generate_system_prompt(risk_level, needs_type)
    
    # 実際の実装では、ここでClaude APIを呼び出す
    # 以下はデモ用の応答例
    
    if risk_level >= 4:
        response = f"""
{user_message}について、お話しいただきありがとうございます。
とても辛い状況なのですね。あなたの気持ちを受け止めます。

ただ、私はAIなので専門的なサポートには限界があります。
今のあなたには、人間の専門家によるサポートが必要だと感じます。

以下の相談先をぜひ検討してください:
- 学校のカウンセラー
- 保健室の先生
- 信頼できる先生や大人

{'緊急の場合は、24時間対応のいのちの電話(0120-783-556)もご利用いただけます。' if risk_level == 5 else ''}

一人で抱え込まないでください。あなたは一人じゃありません。
"""
    elif needs_type == 'listening':
        response = f"""
{user_message}について、お話しいただきありがとうございます。
{user_message[:20]}...という状況、とても大変ですね。

あなたの気持ち、よくわかります。そのような状況では、誰でも辛く感じると思います。
もう少し詳しく聞かせていただけますか?
"""
    elif needs_type == 'solution':
        response = f"""
{user_message}についてですね。いくつかの方法を一緒に考えてみましょう。

考えられるアプローチとして:
1. まず信頼できる人に相談してみる
2. 小さなステップから始めてみる
3. 自分のペースを大切にする

これらの中で、試してみたいと思うものはありますか?
"""
    else:  # thinking
        response = f"""
{user_message}について、一緒に考えていきましょう。

まず、あなた自身はどう感じていますか?
それぞれの選択肢について、あなたが大切にしたいことは何でしょうか?
"""
    
    return response


def save_feedback(message_id: int, rating: int, comment: str):
    """フィードバックを保存"""
    feedback = {
        'message_id': message_id,
        'rating': rating,
        'comment': comment,
        'timestamp': datetime.datetime.now().isoformat()
    }
    st.session_state.feedback_data.append(feedback)


# UI構築
st.title("💭 学生相談支援システム")
st.markdown("---")

# サイドバー
with st.sidebar:
    st.header("ℹ️ システム情報")
    
    st.info("""
    このシステムは、学生の皆さんが安心して相談できる場を提供します。
    
    **特徴:**
    - AIによる傾聴と支援
    - リスクレベル自動判定
    - あなたのニーズに合わせた応答
    - 必要に応じて専門家への連携
    """)
    
    if st.session_state.current_risk_level > 0:
        risk_color = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "🔴"}
        st.metric(
            "現在のリスクレベル", 
            f"{risk_color.get(st.session_state.current_risk_level, '🟢')} レベル{st.session_state.current_risk_level}"
        )
    
    st.markdown("---")
    st.warning("""
    **注意事項:**
    - このシステムは専門的な医療やカウンセリングの代替ではありません
    - 緊急時は必ず専門家にご相談ください
    - 相談内容は安全に管理されます
    """)
    
    if st.button("会話をリセット"):
        st.session_state.chat_history = []
        st.session_state.current_risk_level = 0
        st.rerun()

# メインエリア
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("相談窓口")
    
    # チャット履歴表示
    chat_container = st.container()
    with chat_container:
        for i, message in enumerate(st.session_state.chat_history):
            if message['role'] == 'user':
                with st.chat_message("user"):
                    st.write(message['content'])
            else:
                with st.chat_message("assistant"):
                    st.write(message['content'])
                    
                    # フィードバック機能
                    with st.expander("この応答は役に立ちましたか?"):
                        feedback_col1, feedback_col2 = st.columns([1, 3])
                        with feedback_col1:
                            rating = st.radio(
                                "評価", 
                                [1, 2, 3, 4, 5], 
                                key=f"rating_{i}",
                                horizontal=True,
                                label_visibility="collapsed"
                            )
                        with feedback_col2:
                            comment = st.text_input(
                                "コメント(任意)", 
                                key=f"comment_{i}",
                                label_visibility="collapsed",
                                placeholder="改善点などあればお聞かせください"
                            )
                        
                        if st.button("送信", key=f"submit_{i}"):
                            save_feedback(i, rating, comment)
                            st.success("フィードバックありがとうございます!")

# ユーザー入力
user_input = st.chat_input("相談内容を入力してください...")

if user_input:
    # ユーザーメッセージを追加
    st.session_state.chat_history.append({
        'role': 'user',
        'content': user_input,
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    # リスクレベル判定
    risk_level, detected_keywords = analyze_risk_level(user_input)
    st.session_state.current_risk_level = max(st.session_state.current_risk_level, risk_level)
    
    # ニーズ分析
    needs_type = analyze_needs(user_input)
    
    # AI応答生成
    ai_response = generate_ai_response(
        user_input, 
        risk_level, 
        needs_type,
        st.session_state.chat_history
    )
    
    # AI応答を追加
    st.session_state.chat_history.append({
        'role': 'assistant',
        'content': ai_response,
        'timestamp': datetime.datetime.now().isoformat(),
        'risk_level': risk_level,
        'needs_type': needs_type,
        'detected_keywords': detected_keywords
    })
    
    st.rerun()

with col2:
    st.subheader("📊 分析情報")
    
    if st.session_state.chat_history:
        last_message = st.session_state.chat_history[-1]
        
        if last_message['role'] == 'assistant':
            st.metric("リスクレベル", f"レベル {last_message.get('risk_level', 0)}")
            
            needs_labels = {
                'listening': '傾聴重視',
                'solution': '解決策提示',
                'thinking': '共に考える'
            }
            st.metric("検出ニーズ", needs_labels.get(last_message.get('needs_type', 'listening')))
            
            if last_message.get('detected_keywords'):
                st.write("**検出キーワード:**")
                for kw in last_message['detected_keywords'][:5]:
                    st.caption(f"- {kw}")

# 管理者向けデータ表示（開発用）
with st.expander("🔧 開発者向け情報"):
    st.json({
        'total_messages': len(st.session_state.chat_history),
        'feedback_count': len(st.session_state.feedback_data),
        'max_risk_level': st.session_state.current_risk_level
    })
    
    if st.button("履歴データをダウンロード"):
        data = {
            'chat_history': st.session_state.chat_history,
            'feedback_data': st.session_state.feedback_data
        }
        st.download_button(
            "JSONダウンロード",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"counseling_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )