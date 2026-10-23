"""Safe, per-model diagnostics shared by the Streamlit entry points."""
import re


def error_status(error):
    """Prefer an HTTP status from the SDK; accept text-only legacy exceptions."""
    code = getattr(error, 'code', None)
    if isinstance(code, int) and 400 <= code <= 599:
        return str(code)
    text = str(error)
    match = re.search(r'\b([45]\d{2})\b', text)
    if match:
        return match.group(1)
    for marker, status in (
        ('RESOURCE_EXHAUSTED', '429'), ('quota', '429'),
        ('PERMISSION_DENIED', '403'), ('API_KEY_INVALID', '400'),
        ('NOT_FOUND', '404'), ('UNAVAILABLE', '503'),
    ):
        if marker.lower() in text.lower():
            return status
    return '不明'


def format_api_errors(errors):
    """Keep every attempt's status, never echo exception text or request data."""
    statuses = [(model, error_status(error)) for model, error in errors]
    codes = {code for _, code in statuses}
    guidance = []
    if codes & {'400', '401', '403'}:
        guidance.append('APIキー・権限・リクエスト設定を確認してください。')
    if '429' in codes:
        guidance.append('APIの利用上限に達したモデルがあります。Google AI Studioで割り当てと利用状況を確認してください。')
    if '404' in codes:
        guidance.append('利用できないモデルがあります。モデル名と、このプロジェクトでの利用可否を確認してください。')
    if codes & {'500', '502', '503', '504'}:
        guidance.append('API側の一時的な障害やタイムアウトの可能性があります。時間をおいて再試行してください。')
    if not guidance:
        guidance.append('API呼び出しに失敗しました。接続状況やAPIの設定を確認してください。')
    details = '\n'.join(f'- {model}: {status}' for model, status in statuses)
    return '応答を生成できませんでした。\n\n' + '\n'.join(guidance) + '\n\nモデル別エラー（HTTPステータス）:\n' + details
