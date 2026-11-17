"""English/Simplified Chinese messages shared by the app and board component."""
import re
import streamlit as st

ZH = {
    'Saved game month': '已保存棋谱的月份',
    'All months': '所有月份',
    'Unknown date': '日期未知',
    'Filter by the month the game was played. Your saved puzzles and progress are kept.': '按对局发生的月份筛选，已保存的题目和复习进度会保留。',
    'Checking move…': '正在检查着法……',
    'The answer is incorrect, please try again': '答案不正确，请再试一次。',
    'Correct! Watch the continuation.': '回答正确！请观看后续着法演示。',
    'Click Next Puzzle to proceed.': '点击下一题以继续。',
    'Replay solution': '重新播放',
    'Step {step}/{total}: {move}': '第 {step}/{total} 步：{move}',
    'Correct! No continuation is available for this position.': '回答正确！此局面暂无可用的后续着法。',
    'Game {game}/{games} · Your moves analyzed: {done}/{total} · {percent}%': '第 {game}/{games} 局 · 已分析你的着法：{done}/{total} · {percent}%',
    'Analysis complete · 100%': '分析完成 · 100%',
    'Queued · Waiting for the engine': '排队中 · 等待引擎分析',
    'Analysis stopped before completion': '分析未完成，已停止',
    'Preparing analysis…': '正在准备分析……',
    'Saving puzzles…': '正在保存练习题……',
    'Sign in with the username and password assigned by your group owner.': '请使用群组管理员分配的用户名和密码登录。',
    'Need an account or forgot your password? Contact your group owner.': '需要账号或忘记密码？请联系群组管理员。',
    'Signed in as {username}': '当前账号：{username}',
    'Sign in or create an invited account to keep your puzzles and progress private.': '登录或使用邀请码注册，让你的题库和复习记录保持私密。',
    'Account': '账号', 'Sign in': '登录', 'Create account': '注册账号', 'Reset password': '重设密码',
    'Username': '用户名', 'Password': '密码', 'New password': '新密码', 'Confirm password': '确认密码',
    'Invitation code': '邀请码', 'Recovery code': '恢复码',
    'Passwords must contain 12–128 characters. Usernames are case-insensitive.': '密码长度须为 12–128 个字符。用户名不区分大小写。',
    'Passwords do not match.': '两次输入的密码不一致。',
    'Your account credentials were saved. You can now sign in.': '账号凭据已保存，现在可以登录。',
    'Save this recovery code privately. It is your only way to reset a forgotten password without the group owner.': '请妥善保存此恢复码。忘记密码时，你需要用它重设密码，否则只能联系群组管理员。',
    'I saved my recovery code': '我已保存恢复码',
    'Account service is temporarily unavailable. Please try again later.': '账号服务暂时不可用，请稍后重试。',
    'Your session expired. Please sign in again.': '登录会话已过期，请重新登录。',
    'Signed in for up to 12 hours. A full page refresh requires signing in again.': '登录最长有效 12 小时。完全刷新页面后需要重新登录。',
    'Use 3–32 letters, numbers, underscores or hyphens for your username.': '用户名须为 3–32 个字母、数字、下划线或连字符。',
    'Use a password with 12–128 characters.': '请使用长度为 12–128 个字符的密码。',
    'Invalid or already used invitation code.': '邀请码无效或已被使用。',
    'This private group has reached its account limit.': '本群组的账号数量已达上限。',
    'That username is already taken.': '该用户名已被使用。',
    'Invalid username or password.': '用户名或密码错误。',
    'Invalid username or recovery code.': '用户名或恢复码错误。',
    'Too many attempts. Please try again later.': '尝试次数过多，请稍后重试。',
    'Lichess month': 'Lichess 月度棋谱', 'Your Lichess username': '你的 Lichess 用户名',
    'Player username in PGN': 'PGN 棋谱中的用户名', 'Maximum games to import': '最多导入局数',
    'Lichess imports completed standard games from the selected UTC month, newest first.': 'Lichess 按 UTC 月份导入已结束的标准对局，最新对局优先。',
    'Choose a valid Lichess month (2013 or later) and 1–100 games.': '请选择有效的 Lichess 月份（2013 年起），并导入 1–100 局。',
    'Lichess is rate limiting requests. Wait at least one minute before retrying.': 'Lichess 请求频率受限，请至少等待一分钟后再试。',
    'Lichess username not found.': '未找到此 Lichess 用户名。',
    'Lichess download exceeded 1 MB. Request fewer games.': 'Lichess 下载超过 1 MB，请减少导入局数。',
    'Platform: {platform}': '平台：{platform}',
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
    'Drag a piece to make your move.': '拖动棋子走棋。',
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
    'Update puzzle library': '更新题库',
    'Cycle complete! Take a rest or practice your mistakes again.': '本轮练习已完成！休息一下，或再练习一轮错题。',
    'Take a rest': '休息一下',
    'Start over with shuffled puzzles': '打乱顺序重新练习',
    'Enjoy your break. Your progress is saved. Start over whenever you are ready.': '好好休息！你的进度已保存，准备好后可重新开始。',
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
