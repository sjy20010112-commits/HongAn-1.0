from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
from database import init_db
from model import predict, estimate_strengths, load_matches

app = Flask(__name__)

def get_teams():
    df = load_matches()
    if df.empty:
        return []
    teams = sorted(set(df['home_team']) | set(df['away_team']))
    return teams

@app.route('/')
def index():
    teams = get_teams()
    return render_template('index.html', teams=teams)

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

    # 近期比赛列表
    recent = []
    if total:
        sub = df.sort_values('match_date', ascending=False).head(20)
        recent = sub.to_dict('records')

    return render_template('stats.html',
                           total=total,
                           by_league=by_league,
                           date_range=date_range,
                           recent=recent)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
