import numpy as np
import pandas as pd
from scipy.optimize import minimize
from database import init_db

def load_matches(db_path='football.db'):
    conn = init_db(db_path)
    df = pd.read_sql("SELECT * FROM matches WHERE home_odds IS NOT NULL", conn)
    conn.close()
    return df

def team_stats(df):
    """计算每支球队的攻防强度"""
    teams = sorted(set(df['home_team']) | set(df['away_team']))
    attack = {t: 1.0 for t in teams}
    defense = {t: 1.0 for t in teams}
    return teams, attack, defense

def poisson_pmf(lam, k):
    return np.exp(-lam) * lam**k / np.math.factorial(k)

def match_probabilities(lh, la, max_goals=8):
    """用泊松分布计算胜平负概率"""
    ph = pd = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(lh, i) * poisson_pmf(la, j)
            if i > j:
                ph += p
            elif i == j:
                pd += p
    return ph, pd, 1 - ph - pd

def expected_goals(home, away, league_avg_h=1.5, league_avg_a=1.2,
                   attack=None, defense=None):
    """根据攻防强度估算主客队预期进球"""
    ah = attack[home] if attack else 1.0
    dh = defense[home] if defense else 1.0
    aa = attack[away] if attack else 1.0
    da = defense[away] if defense else 1.0
    lh = league_avg_h * ah * da
    la = league_avg_a * aa * dh
    return max(lh, 0.2), max(la, 0.2)

def estimate_strengths(df):
    """用近期进球估计每队攻防系数"""
    teams = sorted(set(df['home_team']) | set(df['away_team']))
    df = df.sort_values('match_date')
    recent = df.tail(500)  # 最近500场

    avg_home_goals = recent['home_goals'].mean() or 1.5
    avg_away_goals = recent['away_goals'].mean() or 1.2

    attack, defense = {}, {}
    for t in teams:
        home = recent[recent['home_team'] == t]
        away = recent[recent['away_team'] == t]
        scored = (home['home_goals'].sum() + away['away_goals'].sum())
        conceded = (home['away_goals'].sum() + away['home_goals'].sum())
        n = len(home) + len(away)
        if n == 0:
            attack[t] = defense[t] = 1.0
            continue
        attack[t] = (scored / n) / ((avg_home_goals + avg_away_goals) / 2)
        defense[t] = (conceded / n) / ((avg_home_goals + avg_away_goals) / 2)
        # 限制范围，避免极端值
        attack[t] = np.clip(attack[t], 0.3, 2.5)
        defense[t] = np.clip(defense[t], 0.3, 2.5)
    return teams, attack, defense, avg_home_goals, avg_away_goals

def odds_to_probs(h, d, a):
    """从赔率反推市场概率（去除抽水）"""
    ih, id_, ia = 1/h, 1/d, 1/a
    s = ih + id_ + ia
    return ih/s, id_/s, ia/s

def predict(home, away, db_path='football.db'):
    """核心预测函数：返回胜平负概率 + 大小球建议"""
    df = load_matches(db_path)
    if df.empty:
        return None

    teams, attack, defense, avg_h, avg_a = estimate_strengths(df)
    if home not in teams or away not in teams:
        return None

    lh, la = expected_goals(home, away, avg_h, avg_a, attack, defense)
    ph, pd_, pa = match_probabilities(lh, la)

    # 该队近期赔率均值，用于价值判断
    sub = df[(df['home_team'] == home) & (df['away_team'] == away)]
    if sub.empty:
        sub_h = df[df['home_team'] == home]['home_odds'].mean()
        sub_d = df[df['home_team'] == home]['draw_odds'].mean()
        sub_a = df[df['away_team'] == away]['away_odds'].mean()
    else:
        row = sub.iloc[-1]
        sub_h, sub_d, sub_a = row['home_odds'], row['draw_odds'], row['away_odds']

    value = None
    if sub_h and sub_d and sub_a:
        mh, md, ma = odds_to_probs(sub_h, sub_d, sub_a)
        edges = {'主胜': ph - mh, '平局': pd_ - md, '客胜': pa - ma}
        best = max(edges, key=edges.get)
        if edges[best] > 0.03:
            value = best

    total_xg = lh + la
    over25 = 0.0
    for i in range(9):
        for j in range(9):
            if i + j > 2.5:
                over25 += poisson_pmf(lh, i) * poisson_pmf(la, j)

    return {
        'home': home, 'away': away,
        'exp_home_goals': round(lh, 2),
        'exp_away_goals': round(la, 2),
        'p_home': round(ph*100, 1),
        'p_draw': round(pd_*100, 1),
        'p_away': round(pa*100, 1),
        'p_over25': round(over25*100, 1),
        'value_bet': value,
    }
