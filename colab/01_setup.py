# ==========================================
# 1. ライブラリ導入とGoogle認証
# ==========================================
!pip install ortools gspread pandas --quiet

import gspread
import pandas as pd
from google.colab import auth
from google.auth import default
from ortools.linear_solver import pywraplp
import collections

# 認証処理
print("認証を開始します...")
auth.authenticate_user()
creds, _ = default()
gc = gspread.authorize(creds)

# ▼▼▼ スプレッドシートのURL ▼▼▼
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1NxNVevKlGBhTfUrVEhMcaUgy4WJWPBiObetuWYX_u70'
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

wb = gc.open_by_url(SPREADSHEET_URL)

print("✅ 準備完了。次のセルを実行してデータを読み込んでください。")
