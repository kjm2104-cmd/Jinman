import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="간편 교대 매매 분석기 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 모바일 가독성 및 태그(Badge) 스타일링 CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 간편 교대 매매 시스템 (구글 스프레드시트 실시간 연동)")

# 🔗 구글 스프레드시트 연동 함수 (시트에서 데이터를 불러오고 저장하는 역할)
@st.cache_resource
def get_gsheet_connection():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # Streamlit secrets에 저장된 서비스 계정 정보 연동
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            # 사용자가 제공한 구글 스프레드시트 URL
            sheet_url = "https://docs.google.com/spreadsheets/d/14_iZl-8eS3nV7PW2JB7LSODbAE_Llf_DX0Do6ogBxes/edit?gid=0#gid=0"
            sheet = client.open_by_url(sheet_url).sheet1
            return sheet
    except Exception as e:
        return None
    return None

# 네이버 금융 일별 시세 크롤링 함수
@st.cache_data(ttl=3600)
def get_naver_stock_data(code, count=1250):
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return None
        
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.text)
        item_list = root.findall('.//item')
        
        data = []
        for item in item_list:
            vals = item.get('data').split('|')
            if len(vals) >= 6:
                dt = datetime.strptime(vals[0], '%Y%m%d').strftime('%Y-%m-%d')
                data.append({
                    'Date': dt,
                    'Open': float(vals[1]),
                    'High': float(vals[2]),
                    'Low': float(vals[3]),
                    'Close': float(vals[4]),
                    'Volume': float(vals[5])
                })
        
        if not data:
            return None
            
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        return None

# 주요 종목 빠른 매핑 사전
name_to_code = {
    "삼성전자": "005930",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
    "KODEX 200": "069500",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "현대차": "005380"
}

# 🔍 검색 Form
with st.form(key="search_form"):
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        user_input = st.text_input(
            "🔍 조회할 종목 또는 종목코드 입력",
            value="233740",
            placeholder="예: 삼성전자 또는 005930"
        ).strip()
    with col_in2:
        years_back = st.selectbox("조회 기간", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
    with col_in3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submit_search = st.form_submit_button("🔍 조회하기", use_container_width=True)

# 입력값 파싱
if user_input in name_to_code:
    stock_code = name_to_code[user_input]
    stock_name = user_input
elif user_input.isdigit():
    stock_code = user_input.zfill(6)
    stock_name = "삼성전자" if stock_code == "005930" else ("KODEX 코스닥150레버리지" if stock_code == "233740" else f"종목코드 {stock_code}")
else:
    found = False
    for k, v in name_to_code.items():
        if user_input in k:
            stock_code = v
            stock_name = k
            found = True
            break
    if not found:
        stock_code = "233740"
        stock_name = "KODEX 코스닥150레버리지"

def r10(val):
    return int(np.floor(val / 10.0 + 0.5) * 10)

def style_table(df_target, df_full):
    cols_grad = ['MM', 'PM', 'LM', 'RM']
    col_bounds = {}
    for c in cols_grad:
        if c in df_full.columns:
            vals = pd.to_numeric(df_full[c], errors='coerce')
            col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = [''] * len(row)
        curr_close = row.get('종가(B)', 0)
        prev_close = df_full.iloc[row_idx - 1].get('종가(B)', 0) if row_idx > 0 else None

        for idx, col_name in enumerate(row.index):
            val = row[col_name]
            if col_name in ['종가(B)', '등락률(C)'] and prev_close is not None:
                styles[idx] = 'color: #D32F2F; font-weight: bold;' if curr_close > prev_close else ('color: #1976D2; font-weight: bold;' if curr_close < prev_close else 'color: #111111;')
            elif col_name == 'S':
                try:
                    s_num = float(val)
                    styles[idx] = 'background-color: #FFCDD2; color: #B71C1C; font-weight: 900; padding: 2px 6px; border-radius: 12px; display: inline-block;' if s_num > 0 else ('background-color: #BBDEFB; color: #0D47A1; font-weight: 900; padding: 2px 6px; border-radius: 12px; display: inline-block;' if s_num < 0 else 'background-color: #E0E0E0; color: #333333; font-weight: bold;')
                except:
                    pass
            elif col_name == '매수신호(레버리지/인버스)':
                val_str = str(val)
                if '7차 최종' in val_str or '7차 풀베팅' in val_str or '5차 최종익절' in val_str: 
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '매수' in val_str: 
                    styles[idx] = 'background-color: #D32F2F; color: #FFFFFF; font-weight: bold;'
                elif '익절' in val_str: 
                    styles[idx] = 'background-color: #E3F2FD; color: #0D47A1; font-weight: bold;'
            elif col_name in cols_grad:
                try:
                    v = float(val)
                    vmin, vmax = col_bounds.get(col_name, (0, 1))
                    ratio = 0.0 if vmax == vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
                    r = int(255 - ratio * 35); g = int(240 - ratio * 160); b = int(240 - ratio * 160)
                    styles[idx] = f'background-color: #{r:02x}{g:02x}{b:02x}; color: {"#FFFFFF" if ratio > 0.5 else "#222222"}; font-weight: {"bold" if ratio > 0.4 else "normal"}; padding: 2px 6px; border-radius: 8px;'
                except:
                    pass
        return styles

    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format({'종가(B)': '{:,}', '중심선(D)': '{:,}', '거래량(E)': '{:,}', '거래비율(F)': '{:.2f}'}, na_rep="-")

def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    
    closes = pd.to_numeric(df['Close'], errors='coerce').ffill().values
    vols = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).values
    dates = pd.to_datetime(df['Date']).values
    n = len(closes)

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / np.where(closes[:-1] == 0, 1, closes[:-1])) - 1.0
    ema = np.zeros(n); ema[0] = closes[0]
    for i in range(1, n): ema[i] = round((ema[i - 1] * 6.0 + closes[i]) / 7.0)

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    buy_signals = []

    state = 'UP'
    peak = int(closes[0]) if n > 0 else 0
    trough = int(closes[0]) if n > 0 else 0
    first_M = int(closes[0]) if n > 0 else 0
    up_phase = 'M'; down_phase = 'Q'
    M8, N8, P8, Q8 = peak, peak, peak, peak

    for i in range(n):
        p = int(round(closes[i]))
        if state == 'UP':
            if p > peak:
                peak = p
                l5_target = r10(first_M * 1.045)
                n_trigger = min(l5_target, N8) if N8 > 0 else l5_target
                up_phase = 'N' if (up_phase == 'N' or p >= n_trigger) else 'M'
            elif p <= r10(peak * (1.0 - 0.095)):
                N8 = peak if up_phase == 'N' else N8
                M8 = peak if up_phase == 'M' else M8
                state = 'DOWN'; trough = p
        else:
            if p < trough: trough = p
            elif p >= r10(trough * 1.095):
                P8 = trough if down_phase == 'P' else P8
                Q8 = trough if down_phase == 'Q' else Q8
                state = 'UP'; peak = p; first_M = p

        max_mn = max(M8, N8); min_pq = min(P8, Q8)
        mm = int(round((max_mn / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        pm = int(round((p / max_mn - 1.0) * 100)) if max_mn > 0 else 0
        lm = int(round((p / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        s_val = lm - mm

        if s_val <= -45:
            sig = "🔥 7차 매수 (풀베팅 / 누적 100%)"
            invest_pct = "레버리지 100% (2,700만)"
            cash_pct = "현금 관리"
            invest_ratio = 1.0
        elif s_val <= -35:
            sig = "🚨 6차 매수 (누적 85%)"
            invest_pct = "레버리지 85%"
            cash_pct = "현금 관리"
            invest_ratio = 0.85
        elif s_val <= -25:
            sig = "⚠️ 5차 매수 (누적 65%)"
            invest_pct = "레버리지 65%"
            cash_pct = "현금 관리"
            invest_ratio = 0.65
        elif s_val <= -18:
            sig = "⚠️ 4차 매수 (누적 45%)"
            invest_pct = "레버리지 45%"
            cash_pct = "현금 관리"
            invest_ratio = 0.45
        elif s_val <= -12:
            sig = "🔍 3차 매수 (누적 30%)"
            invest_pct = "레버리지 30%"
            cash_pct = "현금 관리"
            invest_ratio = 0.30
        elif s_val <= -7:
            sig = "🔍 2차 매수 (누적 15%)"
            invest_pct = "레버리지 15%"
            cash_pct = "현금 관리"
            invest_ratio = 0.15
        elif s_val <= -3:
            sig = "🔍 1차 매수 (5%)"
            invest_pct = "레버리지 5%"
            cash_pct = "현금 관리"
            invest_ratio = 0.05
        elif s_val >= 0:
            sig = "🔥 5차 최종익절 (전량 현금화 완료)"
            invest_pct = "레버리지 0% (현금 100%)"
            cash_pct = "현금 100%"
            invest_ratio = 0.0
        elif s_val >= -5:
            sig = "✨ 4차 익절 (누적 80% 현금화)"
            invest_pct = "레버리지 20% 잔여"
            cash_pct = "현금 80%"
            invest_ratio = 0.20
        elif s_val >= -15:
            sig = "✨ 3차 익절 (누적 60% 현금화)"
            invest_pct = "레버리지 40% 잔여"
            cash_pct = "현금 60%"
            invest_ratio = 0.40
        elif s_val >= -25:
            sig = "✨ 2차 익절 (누적 40% 현금화)"
            invest_pct = "레버리지 60% 잔여"
            cash_pct = "현금 40%"
            invest_ratio = 0.60
        elif s_val >= -35:
            sig = "✨ 1차 익절 (누적 20% 현금화)"
            invest_pct = "레버리지 80% 잔여"
            cash_pct = "현금 20%"
            invest_ratio = 0.80
        else:
            sig = "중립 대기 구간"
            invest_pct = "기존 비중 유지"
            cash_pct = "현금 관리"
            invest_ratio = 0.50

        d_cur = pd.Timestamp(dates[i])
        w_slice = closes[:i+1][pd.to_datetime(dates[:i+1]) >= (d_cur - pd.DateOffset(years=1))]
        rm = int(round((w_slice.max() / w_slice.min() - 1.0) * 100)) if len(w_slice) > 0 and w_slice.min() > 0 else 0

        mm_list.append(mm); pm_list.append(pm); lm_list.append(lm)
        s_list.append(s_val); rm_list.append(rm); buy_signals.append(sig)

    df_out = pd.DataFrame({
        '일자': pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d'),
        '종가(B)': closes.astype(int),
        '등락률(C)': [f"{x*100:+.2f}%" for x in chg],
        '매수신호(레버리지/인버스)': buy_signals,
        '중심선(D)': ema.astype(int),
        '거래량(E)': vols.astype(int),
        '거래비율(F)': vol_ratio,
        'MM': mm_list, 'PM': pm_list, 'LM': lm_list, 'S': s_list, 'RM': rm_list,
        '부-반등(L)': ["" for _ in range(n)], '반등(M)': ["" for _ in range(n)],
        '상-추세(N)': ["" for _ in range(n)], '하-추세(P)': ["" for _ in range(n)],
        '조정(Q)': ["" for _ in range(n)], '부-조정(R)': ["" for _ in range(n)]
    })

    summary = {
        'B1': int(closes[-1]), 'C1': int(vols[-1]), 'cur_chg': chg[-1] * 100,
        'MM': mm_list[-1], 'PM': pm_list[-1], 'LM': lm_list[-1], 'S': s_list[-1],
        'current_signal': buy_signals[-1], 'invest_pct': invest_pct, 'cash_pct': cash_pct,
        'invest_ratio': invest_ratio,
        'state': "상승 파동 중" if state == 'UP' else "하락
