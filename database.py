import sqlite3

def init_db(db_path='football.db'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT,
        season TEXT,
        match_date TEXT,
        home_team TEXT,
        away_team TEXT,
        home_goals INTEGER,
        away_goals INTEGER,
        home_odds REAL,
        draw_odds REAL,
        away_odds REAL,
        UNIQUE(league, match_date, home_team, away_team)
    )''')
    conn.commit()
    return conn
