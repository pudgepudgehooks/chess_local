"""English/Simplified Chinese messages shared by the app and board component."""
import re
import streamlit as st

ZH = {
    'Chess Mistake Trainer': '国际象棋错题训练',
    'Chess Trainer · Private Beta': '国际象棋训练 · 内测版',
    'Generate puzzles': '生成练习题',
    'Your Chess.com username': '你的 Chess.com 用户名',
    'Stockfish executable path': 'Stockfish 可执行文件路径',
    'Game source': '棋谱来源', 'Chess.com month': 'Chess.com 月度棋谱', 'Upload PGN': '上传 PGN',
    'PGN file': 'PGN 棋谱文件', 'Year': '年份', 'Month': '月份',
    'Analysis depth': '分析深度', 'Minimum loss (centipawns)': '最低失分（厘兵）',
    '100 centipawns = one pawn. Beta: up to five games per request, six requests per day.': '100 厘兵等于一个兵的价值。内测版每次最多分析 5 局，每天最多提交 6 次。',
    '100 centipawns = one pawn. Analyzing all alternatives can take several minutes per game.': '100 厘兵等于一个兵的价值。分析所有候选着法可能需要每局数分钟。',
    'Analyzing games…': '正在分析棋谱……',
    'Enter your username to select your moves.': '请输入你的用户名，以筛选你走过的着法。',
    'Choose a PGN file first.': '请先选择 PGN 文件。',
    'Beta uploads are limited to 1 MB.': '内测版上传文件不能超过 1 MB。',
    'Analysis queued (or already analyzed). You can leave and return later.': '分析已加入队列（或已分析过）。你可以稍后回来查看。',
    'Analyzed {games} games. Added {added} puzzles.': '已分析 {games} 局，新增 {added} 道练习题。',
    'Generation failed. Please try again later.': '生成失败，请稍后重试。',
    'Generation failed: {error}': '生成失败：{error}',
    'Only show puzzles due for review': '只显示到期复习的题目',
    'Puzzle owner': '棋谱用户名', 'All players': '所有用户名',
    'No puzzles are due. Generate puzzles or turn off the due-only filter.': '目前没有到期的题目。请生成练习题，或关闭到期筛选。',
    'Puzzle {index} of {total} · {side} to move': '第 {index} / {total} 题 · {side}先行',
    'White': '白方', 'Black': '黑方',
    'Imported sample: player ownership and game source are unknown. Regenerate games for verified personal puzzles.': '导入的示例题：用户名及棋谱来源未知。请重新分析自己的棋谱，生成个人练习题。',
    '{username} vs {opponent} · {date} · move {number}': '{username} 对 {opponent} · {date} · 第 {number} 回合',
    'Drag a piece to make your move. You can also click a piece and its destination.': '拖动棋子走棋，也可以依次点击棋子和目标格。',
    'Your move (SAN or UCI, e.g. Nf3, e2e4, or e7e8q)': '你的着法（SAN 或 UCI，例如 Nf3、e2e4 或 e7e8q）',
    'Check move': '检查着法',
    'Enter a legal move. Include the promotion piece when promoting.': '请输入合法着法。兵升变时请指定升变棋子。',
    'Correct! Review saved. Choose Next puzzle when ready.': '回答正确！复习记录已保存。准备好后点击“下一题”。',
    'That move loses more than the accepted alternatives. Try again.': '这步棋比可接受的候选着法失分更多，请再试一次。',
    'Could not save your review. Please try again.': '无法保存复习记录，请重试。',
    'Could not save review: {error}': '无法保存复习记录：{error}',
    'Hint': '提示', 'Look at the {piece} on {square}.': '请留意 {square} 格的{piece}。',
    'Reveal solution and original mistake': '查看答案与原来的错误着法',
    'Your game move: **{move}**': '你在实战中的着法：**{move}**',
    'Engine continuation: ': '引擎推荐续着：',
    'Your evaluation: {before} → {after}.': '你的局面评估：{before} → {after}。',
    'Evaluation lost: {loss} pawns': '评估下降：{loss} 个兵的价值',
    'Open original game': '打开原始对局',
    'Saved attempts: {attempts} · Correct: {correct}': '已记录尝试：{attempts} 次 · 正确：{correct} 次',
    'Next puzzle': '下一题', 'unavailable': '暂无数据', 'mate {mate}': '将杀 {mate}',
    '{cp} pawns': '{cp} 个兵的价值',
    'missed_mate': '错过强制将杀', 'allowed_mate': '允许对手强制将杀', 'evaluation_drop': '局面评估下降',
    'Missed mate': '错过强制将杀', 'Allowed mate': '允许对手强制将杀', 'Evaluation drop': '局面评估下降',
    'Analysis status is temporarily unavailable.': '暂时无法获取分析进度。',
    '{state} · {count} games analyzed': '{state} · 已分析 {count} 局',
    'Queued': '排队中', 'Running': '分析中', 'Done': '已完成', 'Failed': '失败',
    'Waiting for analysis': '等待分析', 'Analyzing games': '正在分析棋谱',
    'Added {count} puzzles. Refresh your library to review them.': '新增 {count} 道练习题。请刷新题库开始复习。',
    'Analysis failed or reached its time limit. Please try fewer games. Contact the beta owner if it repeats.': '分析失败或超时。请减少棋谱数量后重试。如反复出现，请联系内测管理员。',
    'Refresh puzzle library': '刷新题库',
    'Your puzzle library is temporarily unavailable.': '暂时无法加载你的题库。',
    'Cannot load puzzle library: {error}': '无法加载题库：{error}',
    'The private beta is not configured yet. Please contact the beta owner.': '内测版尚未配置完成，请联系管理员。',
    'Sign in with your invited Google account to generate and review your own chess puzzles.': '请使用受邀的 Google 账号登录，生成并复习你的个人练习题。',
    'Sign in with Google': '使用 Google 登录', 'Sign out': '退出登录',
    'Private beta · {email}': '内测版 · {email}',
    'The beta service is temporarily unavailable. Please contact the beta owner.': '内测服务暂时不可用，请联系管理员。',
    'Sign in with a verified, invited account.': '请使用已验证邮箱的受邀账号登录。',
    'Your sign-in expired. Sign out and sign in again.': '登录已过期，请退出后重新登录。',
    'This account is not on the private beta invitation list.': '该账号不在内测邀请名单中。',
    'Set STOCKFISH_PATH or enter the Stockfish executable path.': '请设置 STOCKFISH_PATH 或输入 Stockfish 可执行文件路径。',
    'Enter a username and valid month.': '请输入用户名和有效月份。',
    'Enter a valid player username (letters, numbers, underscores or hyphens).': '请输入有效用户名（字母、数字、下划线或连字符）。',
    'Analysis settings exceed beta limits.': '分析设置超出了内测版限制。',
    'No games found in this import.': '未在导入内容中找到对局。',
    'Import at most five games per request.': '每次最多导入 5 局棋谱。',
    'Every imported game must include your specified username.': '每局导入的棋谱都必须包含你指定的用户名。',
    'Only valid standard chess games are supported.': '仅支持有效的标准国际象棋对局。',
    'Beta games are limited to 400 half-moves.': '内测版每局最多支持 400 个半回合。',
    'You already have an analysis queued or running.': '你已有一个分析任务在排队或运行中。',
    'Beta limit: six analysis requests per day.': '内测版每天最多提交 6 次分析请求。',
    'The beta analysis queue is full. Please try again later.': '内测分析队列已满，请稍后重试。',
    'Puzzle not found in your library.': '你的题库中没有找到这道题。',
    'Archive response does not contain a games list.': '棋谱服务的响应中没有对局列表。',
    'Enter the username whose mistakes you want to study.': '请输入你想复习其错误着法的用户名。',
    'Engine did not evaluate the played move.': '引擎未能评估实战着法。',
    'Invalid PGN: {error}': '无效的 PGN：{error}',
    'pawn': '兵', 'knight': '马', 'bishop': '象', 'rook': '车', 'queen': '后', 'king': '王',
    'Chess puzzle board': '国际象棋练习棋盘', 'empty': '空格',
    'Drag a piece, or select its square and destination.': '拖动棋子，或依次点击起点格和目标格。',
    'Move submitted. See the result below the board.': '着法已提交，请查看棋盘下方的结果。',
    'Illegal move. Try another destination.': '不合法的着法，请选择其他目标格。',
    'Promote to:': '升变为：', 'Queen': '后', 'Rook': '车', 'Bishop': '象', 'Knight': '马',
    'Cancel': '取消', 'Choose your promotion piece.': '请选择升变棋子。',
}


def language():
    return st.session_state.get('ui_language', st.query_params.get('lang', 'en'))


def tr(message, _language=None, **values):
    english = {'missed_mate': 'Missed mate', 'allowed_mate': 'Allowed mate', 'evaluation_drop': 'Evaluation drop'}
    text = ZH.get(message, message) if (_language or language()) == 'zh' else english.get(message, message)
    return text.format(**values) if values else text


def error_text(error):
    text = str(error)
    if text.startswith('Invalid PGN: '):
        return tr('Invalid PGN: {error}', error=text[len('Invalid PGN: '):])
    return tr(text)


def job_message(message):
    match = re.fullmatch(r'Added (\d+) puzzles\. Refresh your library to review them\.', message)
    return tr('Added {count} puzzles. Refresh your library to review them.', count=match[1]) if match else tr(message)


def language_selector():
    if 'ui_language' not in st.session_state:
        requested = st.query_params.get('lang', 'en')
        st.session_state.ui_language = requested if requested in ('en', 'zh') else 'en'
    def remember():
        st.query_params['lang'] = st.session_state.ui_language
    st.sidebar.selectbox('Language / 语言', ['en', 'zh'],
                         format_func=lambda value: 'English' if value == 'en' else '简体中文',
                         key='ui_language', on_change=remember)
