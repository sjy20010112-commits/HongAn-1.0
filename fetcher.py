import requests
import pandas as pd
from io import StringIO
from database import init_db

LEAGUES = {
    '英超': 'E0',
    '西甲': 'SP1',
    '德甲': 'D1',
    '意甲': 'I1',
    '法甲': 'F1',
}
SEASONS = ['2223', '2324', '2425', '2526']
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

def fetch_league(name, code, seasons=SEASONS):
    dfs = []
    for season in seasons:
        url = BASE_URL.format(season=season, code=code)
        try:
