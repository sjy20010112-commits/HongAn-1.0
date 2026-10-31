import os
from flask import Flask, render_template, request, jsonify
import pandas as pd
from database import init_db
from model import predict, load_matches

app = Flask(__name__)

BASE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}足球比赛预测{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
               background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
               color: #fff; min-height: 100vh; }
        .container { max-width: 720px; margin: 0 auto; padding: 20px 16px 60px; }
        h1 { text-align: center; margin: 24px 0 8px; font-size: 26px; }
        .subtitle { text-align: center; color: #9fc5e8; margin-bottom: 28px; font-size: 14px; }
        nav { display: flex; justify-content: center; gap: 12px; margin-bottom: 24px; }
        nav a { color: #fff; text-decoration: none; padding: 8px 20px; border-radius: 20px;
                background: rgba(255,255,255,0.1); font-size: 14px; }
        nav a:hover { background: #4a90d9; }
        .card { background: rgba(255,255,255,0.08); border-radius: 14px; padding: 20px;
                margin-bottom: 16px; }
        select, button { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px;
                         border: 1px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.3);
                         color: #fff; font-size: 16px; }
        select option { color: #000; }
        button { background: #4a90d9; border: none; cursor: pointer; font-weight: bold; margin-top: 12px; }
        button:disabled { background: #666; }
        .prob-bar { display: flex; height: 34px; border-radius: 8px; overflow: hidden; margin: 14px 0; font-size: 13px; }
        .prob-bar div { display: flex; align-items: center; justify-content: center; font-weight: bold; }
        .bar-home { background: #2ecc71; }
        .bar-draw { background: #f1c40f; color: #333; }
        .bar-away { background: #e74c3c; }
        .big-num { font-size: 30px; font-weight: bold; color: #5dade2; }
        .value-tip { background: #fff3cd; color: #856404; padding: 10px; border-radius: 8px; margin-top: 12px; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 8px 4px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #9fc5e8; }
        .err { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚽ 足球比赛预测</h1>
        <p class="subtitle">基于泊松分布模型 · 五大联赛历史数据</p>
        <nav>
            <a href="{{ url_for('index') }}">预测</a>
            <a href="{{ url_for('stats') }}">数据统计</a>
        </nav>
        {% block content %}{% endblock %}
    </div>
</body>
</html>"""

INDEX_HTML = """{% extends 'base.html' %}
{% block content %}
<div class="card">
    <select id="home">
        <option value="">选择主队</option>
        {% for t in teams %}<option value="{{ t }}">{{ t }}</option>{% endfor %}
    </select>
    <select id="away">
        <option value="">选择客队</option>
        {% for t in teams %}<option value="{{ t }}">{{ t }}</option>{% endfor %}
    </select>
    <button id="btn" onclick="doPredict()">开始预测</button>
</div>
<div id="result"></div>
<script>
async function doPredict() {
    var h = document.getElementById('home').value;
    var a = document.getElementById('away').value;
    var box = document.getElementById('result');
    if (!h || !a) { box.innerHTML = '<div class="card err">请选择两支球队</div>'; return; }
    if (h === a) { box.innerHTML = '<div class="card err">主客队不能相同</div>'; return; }
    var btn = document.getElementById('btn');
    btn.disabled = true; btn.textContent = '预测中...';
    try {
        var resp = await fetch('/predict', {method:'POST',
            headers:{'Content-Type':'application/x-www-form-urlencoded'},
            body:'home=' + encodeURIComponent(h) + '&away=' + encodeURIComponent(a)});
        var d = await resp.json();
        if (d.error) { box.innerHTML = '<div class="card err">' + d.error + '</div>'; }
        else {
            var html = '<div class="card result-box">';
            html += '<h3>' + d.home + ' vs ' + d.away + '</h3>';
            html += '<p>预期进球: ' + d.exp_home_goals + ' : ' + d.exp_away_goals + '</p>';
            html += '<div class="prob-bar">';
            html += '<div class="bar-home" style="width:' + d.p_home + '%">' + d.p_home + '%</div>';
            html += '<div class="bar-draw" style="width:' + d.p_draw + '%">' + d.p_draw + '%</div>';
            html += '<div class="bar-away" style="width:' + d.p_away + '%">' + d.p_away + '%</div></div>';
            html += '<p>主胜 ' + d.p_home + '% · 平局 ' + d.p_draw + '% · 客胜 ' + d.p_away + '%</p>';
            html += '<p>大2.5球概率: <span class="big-num">' + d.p_over25 + '%</span></p>';
            if (d.value_bet) { html += '<div class="value-tip">💡 价值投注参考: ' + d.value_bet + '</div>'; }
            html += '</div>';
            box.innerHTML = html;
        }
    } catch(e) { box.innerHTML = '<div class="card err">请求失败: ' + e + '</div>'; }
    btn.disabled = false; btn.textContent = '开始预测';
}
</script>
{% endblock %}"""

STATS_HTML = """{% extends 'base.html' %}
{% block content %}
<div class="card">
    <h3 style="margin-bottom:12px">📊 数据总览</h3>
    <p>比赛总数: <span class="big-num">{{ total }}</span> 场</p>
    <p>时间范围: {{ date_range[0] }} ~ {{ date_range[1] }}</p>
    <p style="margin-top:10px">
    {% for league, n in by_league.items() %}
        <span style="display:inline-block;background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:12px;margin:4px">{{ league }}: {{ n }} 场</span>
    {% endfor %}
    </p>
</div>
<div class="card">
    <h3 style="margin-bottom:12px">🕐 最近20场比赛</h3>
    <table>
        <tr><th>日期</th><th>赛事</th><th>主队</th><th>比分</th><th>客队</th></tr>
        {% for m in recent %}
        <tr>
            <td>{{ m['match_date'] }}</td>
            <td>{{ m['league'] }}</td>
            <td>{{ m['home_team'] }}</td>
            <td>{{ m['home_goals'] }} : {{ m['away_goals'] }}</td>
            <td>{{ m['away_team'] }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}"""


def write_templates():
    """启动时自动生成模板文件（解决手机无法粘贴HTML的问题）"""
    os.makedirs('templates', exist_ok=True)
    files = {'base.html': BASE_HTML, 'index.html': INDEX_HTML, 'stats.html': STATS_HTML}
    for name, content in files.items():
        path = os.path.join('templates', name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def get_teams():
    df = load_matches()
    if df.empty:
        return []
    return sorted(set(df['home_team']) | set(df['away_team']))


@app.route('/')
def index():
    return render_template('index.html', teams=get_teams())


@app.route('/predict', methods=['POST'])
def do_predict():
    home = request.form.get('home')
    away = request.form.get('away')
    if not home or not away or home == away:
        return jsonify({'error': '请选择两支不同的球队'}), 400
    result = predict(home, away)
    if result is None:
        return jsonify({'error': '数据不足，无法预测'}), 400
    return jsonify(result)


@app.route('/stats')
def stats():
    conn = init_db()
    df = pd.read_sql("SELECT * FROM matches", conn)
    conn.close()
    total = len(df)
    by_league = df.groupby('league').size().to_dict() if total else {}
    date_range = (df['match_date'].min(), df['match_date'].max()) if total else ('-', '-')
    recent = []
    if total:
        recent = df.sort_values('match_date', ascending=False).head(20).to_dict('records')
    return render_template('stats.html', total=total, by_league=by_league,
                           date_range=date_range, recent=recent)


write_templates()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
