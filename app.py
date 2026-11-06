import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os
import re
from datetime import datetime, timedelta
from io import BytesIO
from xml.etree import ElementTree as ET
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# ---------------------------------------------------------
# 1. 페이지 기본 설정 및 직관적 UI/UX를 위한 커스텀 CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="스마트 파동 매매 Pro Max v2",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2.5rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 800; }
    div[data-testid="stMetricLabel"] { font-size: 0.82rem; font-weight: 600; color: #555; }
    div[data-testid="stDataFrame"] { width: 100%; }
    table, th, td { 
        font-size: 0.80rem !important; 
        padding: 3px 4px !important; 
        text-align: center !important; 
        line-height: 1.25 !important;
    }
    .brief-card {
        background-color: #FFFFFF;
        border: 1px solid #E3E8EF;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .brief-title {
        font-size: 0.96rem;
        font-weight: 800;
        color: #1565C0;
        margin-bottom: 8px;
        border-bottom: 1px solid #F0F2F5;
        padding-bottom: 5px;
    }
    .gauge-container {
        width: 100%;
        background-color: #ECEFF1;
        border-radius: 8px;
        height: 22px;
        position: relative;
        overflow: hidden;
        margin: 8px 0;
    }
    .order-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.82rem;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 스마트 파동 매매 Pro Max (2차 진입 개시 & 안전강화형)")

# ---------------------------------------------------------
# 2. 포트폴리오 & 즐겨찾기 영구 저장 관리 (portfolio_data.json)
# ---------------------------------------------------------
PORTFOLIO_FILE = "portfolio_data.json"

def load_saved_portfolio():
    default_favorites = [
        "KODEX 코스닥150레버리지 (233740)",
        "KODEX 코스닥150선물인버스 (251340)",
        "TIGER 미국나스닥100타겟데일리커버드콜 (486290)",
        "KODEX 레버리지 (122630)",
        "KODEX 200선물인버스2X (252670)",
        "삼성전자 (005930)",
        "SK하이닉스 (000660)"
    ]
    default_data = {
        "user_principal": 30000000,
        "user_cash": 10000000,
        "favorites": default_favorites,
        "items": [
            {"id": 1, "input_val": "233740", "confirmed_code": "233740", "confirmed_name": "KODEX 코스닥150레버리지", "qty": 5717, "avg_price": 5330},
            {"id": 2, "input_val": "251340", "confirmed_code": "251340", "confirmed_name": "KODEX 코스닥150선물인버스", "qty": 0, "avg_price": 0}
        ],
        "trade_logs": []
    }
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "items" not in data or not data["items"]:
                        data["items"] = default_data["items"]
                    if "trade_logs" not in data:
                        data["trade_logs"] = []
                    if "user_principal" not in data:
                        data["user_principal"] = 30000000
                    if "user_cash" not in data:
                        data["user_cash"] = 10000000
                    if "favorites" not in data or not isinstance(data["favorites"], list):
                        data["favorites"] = default_favorites
                    return data
        except Exception:
            pass
    return default_data

def save_current_portfolio(data_to_save):
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

if 'account_data' not in st.session_state:
    st.session_state.account_data = load_saved_portfolio()

# ---------------------------------------------------------
# 3. 네이버 금융 시세 크롤링
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_naver_stock_data(code, count=1500):
    clean_code = str(code).strip()
    if not clean_code:
        clean_code = "233740"
        
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={clean_code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if response.status_code != 200:
            return None, None
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
            return None, None
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.drop_duplicates(subset=['Date']).sort_values('Date', ascending=True)
        df.set_index('Date', inplace=True)
        return df, clean_code
    except Exception:
        return None, None

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_naver_stock_name(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        res.encoding = 'euc-kr'
        match = re.search(r'<title>(.*?) : Npay 증권</title>', res.text)
        if not match:
            match = re.search(r'<title>(.*?) : 네이버', res.text)
        if match and match.group(1).strip():
            return match.group(1).strip()
    except Exception:
        pass
    return f"종목({code})"

name_to_code = {
    "코스피지수": "KOSPI", "코스닥지수": "KOSDAQ", "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740", "KODEX 코스닥150선물인버스": "251340", "코스닥150선물인버스": "251340",
    "TIGER 미국나스닥100타겟데일리커버드콜": "486290", "KODEX 레버리지": "122630", "KODEX 200선물인버스2X": "252670",
    "곱버스": "252670", "KODEX 200": "069500", "삼성전자": "005930", "SK하이닉스": "000660"
}
code_to_name = {v: k for k, v in name_to_code.items()}

def resolve_code_and_name(user_str):
    clean_str = str(user_str).strip()
    if not clean_str:
        return "233740", "KODEX 코스닥150레버리지"
    if clean_str in name_to_code:
        code = name_to_code[clean_str]
        return code, code_to_name.get(code, clean_str)
    elif clean_str.isdigit():
        code = clean_str.zfill(6)
        if code in code_to_name:
            return code, code_to_name[code]
        else:
            return code, fetch_naver_stock_name(code)
    else:
        for k, v in name_to_code.items():
            if clean_str.lower() in k.lower():
                return v, code_to_name.get(v, k)
        return clean_str, clean_str

# ---------------------------------------------------------
# 4. 상단 종목 검색 및 즐겨찾기
# ---------------------------------------------------------
acc_favs = st.session_state.account_data.get("favorites", [])
if 'current_target_query' not in st.session_state:
    st.session_state.current_target_query = "233740"

with st.form(key="search_form"):
    col_in1, col_in2, col_in3, col_in4 = st.columns([1.6, 1.4, 0.9, 0.7])
    with col_in1:
        user_input = st.text_input("🔍 종목 직접 입력", value=st.session_state.current_target_query, placeholder="예: 233740, 삼성전자").strip()
    with col_in2:
        quick_pick = st.selectbox("⭐ 즐겨찾기 선택", options=["직접 입력 사용"] + acc_favs, index=0)
    with col_in3:
        years_back = st.selectbox("📅 기간", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
    with col_in4:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submit_search = st.form_submit_button("🔍 조회", use_container_width=True)

if submit_search:
    if quick_pick != "직접 입력 사용":
        extracted_code = re.search(r'\(([^)]+)\)$', quick_pick)
        st.session_state.current_target_query = extracted_code.group(1) if extracted_code else user_input
    else:
        st.session_state.current_target_query = user_input

stock_code, stock_name = resolve_code_and_name(st.session_state.current_target_query)
current_fav_label = f"{stock_name} ({stock_code})"

fav_col1, fav_col2 = st.columns([1.3, 2.7])
with fav_col1:
    if current_fav_label in acc_favs:
        if st.button(f"★ 즐겨찾기 해제 [{stock_name}]", use_container_width=True):
            acc_favs.remove(current_fav_label)
            st.session_state.account_data["favorites"] = acc_favs
            save_current_portfolio(st.session_state.account_data)
            st.rerun()
    else:
        if st.button(f"☆ 즐겨찾기 추가 [{stock_name}]", use_container_width=True):
            acc_favs.append(current_fav_label)
            st.session_state.account_data["favorites"] = acc_favs
            save_current_portfolio(st.session_state.account_data)
            st.rerun()

with fav_col2:
    with st.expander("⚙️ 즐겨찾기 관리"):
        m_col1, m_col2 = st.columns([3, 1])
        with m_col1:
            new_fav_str = st.text_input("새 종목명/코드", placeholder="예: 005380, 현대차", key="new_fav_input", label_visibility="collapsed")
        with m_col2:
            if st.button("➕ 추가", use_container_width=True):
                if new_fav_str.strip():
                    f_code, f_name = resolve_code_and_name(new_fav_str.strip())
                    new_entry = f"{f_name} ({f_code})"
                    if new_entry not in acc_favs:
                        acc_favs.append(new_entry)
                        st.session_state.account_data["favorites"] = acc_favs
                        save_current_portfolio(st.session_state.account_data)
                        st.rerun()

def r10(val):
    if val <= 0:
        return 0
    if val < 2000:
        return int(round(val))
    return int(np.floor(val / 10.0 + 0.5) * 10)

def trunc_int(val):
    return int(np.trunc(val))

# ---------------------------------------------------------
# 5. 웹 표 스타일러
# ---------------------------------------------------------
def style_table(df_target, df_full):
    cols_grad = ['MM', 'PM', 'LM', 'RM', 'S']
    col_bounds = {}
    for c in cols_grad:
        if c in df_full.columns:
            vals = pd.to_numeric(df_full[c], errors='coerce')
            col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = ['text-align: center;'] * len(row)
        chg_str = str(row.get('등락률(C)', '0%')).strip()
        is_up = '+' in chg_str
        is_down = '-' in chg_str

        for idx, col_name in enumerate(row.index):
            val = row[col_name]
            base_style = 'text-align: center;'

            if col_name in ['종가(B)', '등락률(C)']:
                if is_up:
                    styles[idx] = f'{base_style} color: #D32F2F; font-weight: bold;'
                elif is_down:
                    styles[idx] = f'{base_style} color: #1976D2; font-weight: bold;'
                else:
                    styles[idx] = f'{base_style} color: #111111;'

            elif col_name == '거래량(F)':
                try:
                    curr_vol = float(val)
                    row_pos = row.name
                    prev_vol = float(df_full.loc[row_pos - 1, '거래량(F)']) if (row_pos - 1) in df_full.index else curr_vol
                    vol_diff_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                    if vol_diff_ratio >= 0:
                        ratio = min(1.0, vol_diff_ratio / 1.0)
                        r = 255; g = int(240 - ratio * 180); b = int(240 - ratio * 180)
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.3 else "#222222"}; font-weight: bold;'
                    else:
                        ratio = min(1.0, abs(vol_diff_ratio) / 0.5)
                        r = int(240 - ratio * 180); g = int(240 - ratio * 180); b = 255
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#0D47A1" if ratio > 0.3 else "#222222"}; font-weight: bold;'
                except Exception:
                    pass

            elif col_name == 'S':
                try:
                    s_num = float(val)
                    if s_num > 0:
                        ratio = min(1.0, s_num / 50.0)
                        r = 255; g = int(230 - ratio * 150); b = int(230 - ratio * 150)
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: #B71C1C; font-weight: 900;'
                    elif s_num < 0:
                        ratio = min(1.0, abs(s_num) / 60.0)
                        r = int(230 - ratio * 150); g = int(230 - ratio * 150); b = 255
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: 900;'
                    else:
                        styles[idx] = f'{base_style} background-color: #E0E0E0; color: #333333; font-weight: bold;'
                except Exception:
                    pass

            elif col_name == '매수신호':
                val_str = str(val)
                if '4차' in val_str:
                    styles[idx] = f'{base_style} background-color: #7B1FA2; color: #FFFFFF; font-weight: 900;'
                elif '3차' in val_str:
                    styles[idx] = f'{base_style} background-color: #C62828; color: #FFFFFF; font-weight: 900;'
                elif '2차' in val_str:
                    styles[idx] = f'{base_style} background-color: #E53935; color: #FFFFFF; font-weight: 900;'
                elif '1차' in val_str:
                    styles[idx] = f'{base_style} color: #757575; font-weight: bold;' # 1차는 관망/탐색
                elif '청산' in val_str:
                    styles[idx] = f'{base_style} background-color: #1A237E; color: #FFFFFF; font-weight: 900;'
                elif '집중익절' in val_str:
                    styles[idx] = f'{base_style} background-color: #1565C0; color: #FFFFFF; font-weight: 900;'
                elif '선제익절' in val_str:
                    styles[idx] = f'{base_style} background-color: #00897B; color: #FFFFFF; font-weight: 900;'
                elif val_str == '관망':
                    styles[idx] = f'{base_style} color: #2E7D32; font-weight: bold;'
        return styles

    format_dict = {
        '종가(B)': '{:,}',
        '거래량(F)': '{:,}',
        '거래비율(G)': '{:.2f}',
        '부-반등(M)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-",
        '반등(N)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-",
        '상-추세(O)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-",
        '하-추세(Q)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-",
        '조정(R)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-",
        '부-조정(S)': lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ['', '-'] else "-"
    }
    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format(format_dict, na_rep="-")

# ---------------------------------------------------------
# 6. 지표 계산 및 1차 관망 2차 5% 시작 알고리즘
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    closes = pd.to_numeric(df['Close'], errors='coerce').ffill().values
    vols = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).values
    opens = pd.to_numeric(df['Open'], errors='coerce').ffill().values
    n = len(closes)

    # 200일 이동평균선 산출 (Regime Filter)
    ma200 = pd.Series(closes).rolling(window=200, min_periods=1).mean().values

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / np.where(closes[:-1] == 0, 1, closes[:-1])) - 1.0

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    m_col, n_col, o_col, q_col, r_col, s_col = [None]*n, [None]*n, [None]*n, [None]*n, [None]*n, [None]*n
    buy_signals = []

    init_p = int(round(closes[0])) if n > 0 else 0
    state = 'UP'
    peak = init_p
    trough = init_p
    first_N = init_p
    first_R = init_p
    up_phase = 'N'
    down_phase = 'R'

    N8, O8, Q8, R8 = 0, init_p, 0, 0
    active_high = init_p
    active_low = 0
    pending_high = None
    pending_low = None

    for i in range(n):
        p = int(round(closes[i]))
        g_val = vol_ratio[i]
        is_bear_candle = closes[i] < opens[i]

        if pending_high is not None:
            active_high = pending_high
            pending_high = None
        if pending_low is not None:
            active_low = pending_low
            pending_low = None

        if active_high > 0 and active_low > 0:
            mm_raw = (active_high / active_low - 1.0) * 100.0
            pm_raw = (p / active_high - 1.0) * 100.0
            lm_raw = (p / active_low - 1.0) * 100.0
            mm = trunc_int(mm_raw)
            pm = trunc_int(pm_raw)
            lm = trunc_int(lm_raw)
            s_val = trunc_int(lm_raw - mm_raw)
        else:
            mm, pm, lm, s_val = 0, 0, 0, 0

        rm = trunc_int((p / active_high - 1.0) * 100.0) if active_high > 0 else 0
        prev_s = s_list[-1] if len(s_list) > 0 else s_val

        # =========================================================
        # 🏷️ [개편] 1차 관망, 2차 5% 진입 시작 + 매도 3단계
        # =========================================================
        if active_low > 0 and s_val >= 0:
            if s_val < prev_s or (is_bear_candle and g_val >= 1.5):
                sig = "3차 청산(상투)"
            elif is_bear_candle:
                sig = "3차 청산(음봉)"
            else:
                sig = "2차 집중익절"
        elif active_low > 0 and (s_val >= -5 or (mm > 0 and lm >= mm * 0.85)):
            sig = "1차 선제익절"
        elif s_val <= -55:
            sig = "4차 강력진입(35%)"
        elif s_val <= -40:
            sig = "3차 진입(20%)"
        elif s_val <= -32:
            sig = "2차 진입(5%)"  # 5%부터 첫 매수 개시
        elif s_val <= -25:
            sig = "1차 탐색(관망)" # 1차는 관망으로 넘김
        else:
            sig = "관망"

        mm_list.append(mm)
        pm_list.append(pm)
        lm_list.append(lm)
        s_list.append(s_val)
        rm_list.append(rm)
        buy_signals.append(sig)

        if i == 0:
            continue

        if state == 'UP':
            if p > peak:
                peak = p
                u_up_target = r10(first_N * 1.045)
                o_trigger = min(u_up_target, O8) if O8 > 0 else u_up_target
                if up_phase == 'O' or p >= o_trigger:
                    up_phase = 'O'
                    o_col[i] = p
                else:
                    n_col[i] = p
            else:
                down_turn_price = r10(peak * (1.0 - 0.095))
                first_step_down = r10(peak * (1.0 - 0.045))
                if p <= down_turn_price or (active_low == 0 and p <= first_step_down):
                    if up_phase == 'O':
                        O8 = peak
                    else:
                        N8 = peak
                    pending_high = peak
                    state = 'DOWN'
                    trough = p
                    first_R = p
                    u_dn_target = r10(first_R * (1.0 - 0.045))
                    q_trigger = max(u_dn_target, Q8) if Q8 > 0 else u_dn_target
                    if p <= q_trigger and active_low > 0:
                        down_phase = 'Q'
                        q_col[i] = p
                    else:
                        down_phase = 'R'
                        r_col[i] = p
                elif p <= first_step_down:
                    s_col[i] = p
        else:
            if p < trough:
                trough = p
                u_dn_target = r10(first_R * (1.0 - 0.045))
                q_trigger = max(u_dn_target, Q8) if Q8 > 0 else u_dn_target
                if down_phase == 'Q' or p <= q_trigger:
                    down_phase = 'Q'
                    q_col[i] = p
                else:
                    r_col[i] = p
            else:
                up_turn_price = r10(trough * 1.095)
                first_step_up = r10(trough * 1.045)
                if p >= up_turn_price:
                    if down_phase == 'Q':
                        Q8 = trough
                    else:
                        R8 = trough
                    pending_low = trough
                    state = 'UP'
                    peak = p
                    first_N = p
                    u_up_target = r10(first_N * 1.045)
                    o_trigger = min(u_up_target, O8) if O8 > 0 else u_up_target
                    if p >= o_trigger:
                        up_phase = 'O'
                        o_col[i] = p
                    else:
                        up_phase = 'N'
                        n_col[i] = p
                elif p >= first_step_up:
                    m_col[i] = p

    df_out = pd.DataFrame({
        '일자': pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d'),
        '종가(B)': closes.astype(int),
        '등락률(C)': [f"{x*100:+.2f}%" for x in chg],
        '매수신호': buy_signals,
        '거래량(F)': vols.astype(int),
        '거래비율(G)': vol_ratio,
        'MM': mm_list,
        'PM': pm_list,
        'LM': lm_list,
        'S': s_list,
        'RM': rm_list,
        '부-반등(M)': m_col,
        '반등(N)': n_col,
        '상-추세(O)': o_col,
        '하-추세(Q)': q_col,
        '조정(R)': r_col,
        '부-조정(S)': s_col,
        'MA200': ma200
    })

    next_high = pending_high if pending_high is not None else active_high
    next_low = pending_low if pending_low is not None else active_low

    summary = {
        'B1': int(closes[-1]),
        'Open': int(opens[-1]),
        'C1': int(vols[-1]),
        'cur_chg': chg[-1] * 100,
        'vol_ratio': vol_ratio[-1],
        'date': pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d').iloc[-1],
        'MM': mm_list[-1],
        'PM': pm_list[-1],
        'LM': lm_list[-1],
        'S': s_list[-1],
        'RM': rm_list[-1],
        'prev_s': s_list[-2] if len(s_list) >= 2 else s_list[-1],
        'current_signal': buy_signals[-1],
        'max_mn': next_high,
        'min_pq': next_low,
        'B7': peak if state == 'UP' else trough,
        'B8': r10(peak * (1.0 - 0.095)) if state == 'UP' else r10(trough * 1.095),
        'B9': r10(peak * (1.0 - 0.045)) if state == 'UP' else r10(trough * 1.045),
        'state': "상승추세" if state == 'UP' else "하락추세",
        'MA200': int(ma200[-1]),
        'is_below_ma200': closes[-1] < ma200[-1]
    }
    return df_out, summary

kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)
kospi_val = int(kospi_df['Close'].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df['Close'].iloc[-1] / kospi_df['Close'].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0
kosdaq_val = int(kosdaq_df['Close'].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df['Close'].iloc[-1] / kosdaq_df['Close'].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    with st.spinner(f"[{stock_name} ({stock_code})] 4대 지표 및 200일선 추세를 정밀 분석 중입니다..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=1500)

    if raw_df is not None and not raw_df.empty:
        df_full_result, s = calculate_indicator_sheet(raw_df)
        cutoff_date = (datetime.today() - timedelta(days=365 * years_back)).strftime('%Y-%m-%d')
        df_display = df_full_result[df_full_result['일자'] >= cutoff_date].copy()
        if df_display.empty:
            df_display = df_full_result.copy()

        current_s_val = s['S']
        cur_sig = s['current_signal']
        max_mn_val = s.get('max_mn', 0)
        min_pq_val = s.get('min_pq', 0)
        curr_p = s['B1']
        
        target_prices_dict = {}
        for s_tgt in [-25, -32, -40, -55]:
            tp = r10(max_mn_val + (s_tgt * min_pq_val) / 100.0) if (max_mn_val > 0 and min_pq_val > 0) else 0
            target_prices_dict[s_tgt] = tp

        my_port_item = None
        acc_principal = int(st.session_state.account_data.get("user_principal", 30000000))
        if 'items' in st.session_state.account_data:
            for itm in st.session_state.account_data['items']:
                if itm.get('confirmed_code') == stock_code and itm.get('qty', 0) > 0:
                    my_port_item = itm
                    break

        # ---------------------------------------------------------
        # 상단 실전 액션 배너 (200일선 국면 필터 결합)
        # ---------------------------------------------------------
        regime_msg = "📉 [200일선 하회 - 약세장] 비중 보수적 운용 & 현금 사수" if s['is_below_ma200'] else "📈 [200일선 상회 - 강세장] 정석 파동 매매 가동"
        
        if "청산" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 고점 꺾임·상투 출회! 잔여 물량 전량 청산"
            action_item = "💡 **[매도 수칙]**: S≥0 과열권에서 음봉 또는 대량 거래가 발생했습니다. **남은 물량을 전량 익절**하고 현금을 회수하세요."
            badge_color = "#1A237E"
        elif "집중익절" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 상승 파동 에너지 100% 충족 (S ≥ 0)"
            action_item = "💡 **[매도 수칙]**: S값이 0 이상 도달했습니다. **보유 물량의 40%를 집중 익절**하세요."
            badge_color = "#1565C0"
        elif "선제익절" in cur_sig:
            action_title = f"🟢 [{cur_sig}] ➔ 파동 에너지 85% 복원 (S ≥ -5)"
            action_item = "💡 **[매도 수칙]**: 반등이 일정 수준 진행되었습니다. 평단가 위라면 **보유량의 30%를 선제 매도**하여 현금을 확보하세요."
            badge_color = "#00897B"
        elif "4차" in cur_sig:
            action_title = f"🟣 [{cur_sig}] ➔ S≤-55 바닥권 도달!"
            action_item = "💡 **[매수 수칙]**: 4차 비중(35%)을 집행하고, **예비 현금 40%는 반드시 사수**하세요."
            badge_color = "#7B1FA2"
        elif "3차" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 본격 주력 매수 구간 (S ≤ -40)"
            action_item = "💡 **[매수 수칙]**: 지정가 이하에서 3차 비중(20%)을 분할 체결 대기하세요."
            badge_color = "#C62828"
        elif "2차" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 5% 첫 분할 매수 시작 (S ≤ -32)"
            action_item = "💡 **[매수 수칙]**: 1차 관망 후 첫 진입입니다. **정해진 5% 비중만 소액 진입**하세요."
            badge_color = "#E53935"
        elif "1차" in cur_sig:
            action_title = f"⚪ [{cur_sig}] ➔ 하락 초입 탐색 (매수 금지 / 관망)"
            action_item = "💡 **[규칙 적용]**: 1차 구간은 매수하지 않고 관망합니다. 2차(-32) 도달 시까지 현금을 100% 지키세요."
            badge_color = "#757575"
        else:
            action_title = "🟢 [관망 구간] ➔ 타점 대기 및 현금 사수"
            action_item = "💡 **[행동 수칙]**: 뇌동매매를 금지하고 다음 타점이 올 때까지 예수금을 안전하게 유지하세요."
            badge_color = "#2E7D32"

        gauge_pct = max(2, min(98, int(((current_s_val + 70) / 100.0) * 100)))
        tp1, tp2, tp3, tp4 = target_prices_dict.get(-25, 0), target_prices_dict.get(-32, 0), target_prices_dict.get(-40, 0), target_prices_dict.get(-55, 0)

        st.markdown(f"""
        <div style="background-color: #F8FAFC; border-left: 6px solid {badge_color}; padding: 15px 18px; border-radius: 10px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                <h3 style="margin: 0; color: {badge_color}; font-size: 1.15rem;">{action_title}</h3>
                <span style="font-size:0.83rem; color:#444; font-weight:700;">{regime_msg} | 200일선: {s['MA200']:,}원</span>
            </div>
            <p style="margin: 8px 0 6px 0; color: #222222; font-size: 0.92rem;">
                <b>4대 지표</b> — MM(진폭): <code>{s['MM']}%</code> | PM(낙폭): <code>{s['PM']}%</code> | LM(반등): <code>{s['LM']}%</code> | <b>S값: <code style="font-size:1.0rem; color:{badge_color};">{current_s_val}</code></b>
            </p>
            <div class="gauge-container" style="background: linear-gradient(90deg, #7B1FA2 0%, #D32F2F 30%, #FF8F00 45%, #4CAF50 65%, #00897B 80%, #1A237E 100%);">
                <div style="position:absolute; left:{gauge_pct}%; top:0; bottom:0; width:6px; background-color:#FFFFFF; border:2px solid #000; border-radius:3px;"></div>
            </div>
            <div style="font-size:0.86rem; color:#333; margin-top:6px;">
                🎯 <b>지정가 타점</b> — 
                <span class="order-badge" style="background:#EEEEEE; color:#616161;">1차(관망): {tp1:,}원</span>
                <span class="order-badge" style="background:#FFEBEE; color:#C62828;">2차(5% 시작): {tp2:,}원</span>
                <span class="order-badge" style="background:#FFCDD2; color:#B71C1C;">3차(20%): {tp3:,}원</span>
                <span class="order-badge" style="background:#F3E5F5; color:#6A1B9A;">4차(35%): {tp4:,}원</span>
            </div>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 9px 12px; border-radius: 6px; margin-top: 10px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{curr_p:,}원", f"{s['cur_chg']:+.2f}%")
        if my_port_item:
            my_avg = my_port_item['avg_price']
            my_ret = ((curr_p / my_avg) - 1.0) * 100 if my_avg > 0 else 0.0
            c2.metric("내 보유 평단 / 수익률", f"{my_avg:,}원 ({my_port_item['qty']:,}주)", f"{my_ret:+.2f}%")
        else:
            c2.metric("S값 / 거래비율(G)", f"S: {s['S']}", f"G: {s['vol_ratio']:.2f}배 (전일S: {s['prev_s']})")
        c3.metric("코스피 (KOSPI)", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 (KOSDAQ)", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        # ---------------------------------------------------------
        # 7. 메인 탭 구성
        # ---------------------------------------------------------
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 매수·매도 표", 
            "🎯 전략 주문표 (1차관망/2차5% & 트레일링)", 
            "💼 포트폴리오 & 체결 일지", 
            "📢 마감 브리핑"
        ])

        with tab1:
            st.caption("📈 1차 탐색(관망), 2차 5% 개시 룰이 적용된 파동 데이터 표입니다.")
            df_rev = df_display.iloc[::-1].copy()
            st.dataframe(style_table(df_rev, df_full_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("#### 🎯 [개편] 실전 매수 & 매도 주문 계산기")
            total_seed = st.number_input("💰 기준 투자 원금 (원)", min_value=1000000, value=acc_principal, step=1000000, format="%d")

            # 1. 매수 주문표
            st.markdown("##### 📥 1. 분할 매수 플랜 (1차 관망 ➔ 2차 5% 개시 / 기본 60% + 예비 40%)")
            base_plan = [
                {"단계": "⚪ 1차 신호", "조건": "S ≤ -25", "비중": "0% (관망)", "예산": "0원", "목표단가": f"{tp1:,}원", "수량": "0주", "가이드": "하락 초입 진입 금지, 방향성 관망"},
                {"단계": "🔴 2차 진입", "조건": "S ≤ -32 & PM ≤ -10%", "비중": "5%", "예산": f"{int(total_seed*0.05):,}원", "목표단가": f"{tp2:,}원", "수량": f"{int(total_seed*0.05//tp2 if tp2>0 else 0):,}주", "가이드": "첫 매수 5% 소액 탐색 시작"},
                {"단계": "🔴 3차 진입", "조건": "S ≤ -40 & PM ≤ -15%", "비중": "20%", "예산": f"{int(total_seed*0.20):,}원", "목표단가": f"{tp3:,}원", "수량": f"{int(total_seed*0.20//tp3 if tp3>0 else 0):,}주", "가이드": "낙폭 과대 주력 1차 확보"},
                {"단계": "🟣 4차 강력진입", "조건": "S ≤ -55 & (G≥1.3 or 양봉)", "비중": "35%", "예산": f"{int(total_seed*0.35):,}원", "목표단가": f"{tp4:,}원", "수량": f"{int(total_seed*0.35//tp4 if tp4>0 else 0):,}주", "가이드": "바닥 승부수 집행 (기본 60% 완결)"},
                {"단계": "🛡️ 예비 1차 방어", "조건": "재하락 S ≤ -40", "비중": "15%", "예산": f"{int(total_seed*0.15):,}원", "목표단가": f"{tp3:,}원", "수량": f"{int(total_seed*0.15//tp3 if tp3>0 else 0):,}주", "가이드": "반등 실패 추가 하락 시 1차 방어"},
                {"단계": "🚨 최후 2차 방어", "조건": "재하락 S ≤ -55", "비중": "25%", "예산": f"{int(total_seed*0.25):,}원", "목표단가": f"{tp4:,}원", "수량": f"{int(total_seed*0.25//tp4 if tp4>0 else 0):,}주", "가이드": "극단적 언더슈팅 최후 투입"}
            ]
            st.dataframe(pd.DataFrame(base_plan), use_container_width=True, hide_index=True)

            # 2. 매도 주문표
            st.markdown("---")
            st.markdown("##### 📤 2. 분할 익절 & 트레일링 스탑 매도 플랜")

            user_avg_p = my_port_item['avg_price'] if my_port_item else curr_p
            user_hold_qty = my_port_item['qty'] if my_port_item else int((total_seed * 0.6) // curr_p) if curr_p > 0 else 1000

            sell_p1 = r10(user_avg_p * 1.05)
            sell_p2 = r10(user_avg_p * 1.10)
            sell_cut = r10(user_avg_p * 0.85)

            qty_s1 = int(round(user_hold_qty * 0.30))
            qty_s2 = int(round((user_hold_qty - qty_s1) * 0.50))
            qty_s3 = max(0, user_hold_qty - qty_s1 - qty_s2)

            sell_plan = [
                {"익절 단계": "🟢 1차 선제익절", "트리거 조건": "S ≥ -5 (평단+5% 이상)", "목표단가": f"{sell_p1:,}원 이상", "수량": f"{qty_s1:,}주 (30%)", "의도": "안전마진 선제 확보 & 예비 현금 복원"},
                {"익절 단계": "🔵 2차 집중익절", "트리거 조건": "S ≥ 0 (평단+10% 이상)", "목표단가": f"{sell_p2:,}원 이상", "수량": f"{qty_s2:,}주 (40%)", "의도": "파동 목표치 도달 주력 수익 확정"},
                {"익절 단계": "🏁 3차 트레일링", "트리거 조건": "고점 대비 -3.5% 밀림 or 상투 음봉", "목표단가": "추세 이탈 시 시장가", "수량": f"{qty_s3:,}주 (전량)", "의도": "추세 끝까지 먹고 하락 전환 시 전량 청산"},
                {"익절 단계": "⏱️ 타임스탑 룰", "트리거 조건": "4차 진입 후 20일간 무반등 횡보", "목표단가": "20영업일 경과 시점", "수량": "보유량 30% 매도", "의도": "레버리지 음의 복리 침식 방지"},
                {"익절 단계": "⚠️ 비상 리스크컷", "트리거 조건": "예비 방어선 소진 후 평단 -15% 이탈", "목표단가": f"{sell_cut:,}원 이탈 시", "수량": "상황별 손절", "의도": "계좌 붕괴 방지 최후 브레이크"}
            ]
            st.dataframe(pd.DataFrame(sell_plan), use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("##### 💼 실전 계좌 잔고 & 3중 결합 스마트 리밸런싱")
            acc = st.session_state.account_data

            col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.2])
            with col_acc1:
                new_principal = st.number_input("💰 총 원금", min_value=0, value=int(acc.get("user_principal", 30000000)), step=1000000)
            with col_acc2:
                new_cash = st.number_input("💵 예수금(현금)", min_value=0, value=int(acc.get("user_cash", 10000000)), step=500000)
            with col_acc3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("💾 계좌 저장", use_container_width=True):
                    acc["user_principal"] = new_principal
                    acc["user_cash"] = new_cash
                    save_current_portfolio(acc)
                    st.success("✅ 저장 완료!")

            # 종목 리스트 & 실시간 계산
            total_invested_stocks, total_eval_stocks = 0, 0
            stock_eval_dict = {}
            for item in acc["items"]:
                live_df, _ = get_naver_stock_data(item["confirmed_code"], count=5)
                lp = int(live_df['Close'].iloc[-1]) if live_df is not None and not live_df.empty else item["avg_price"]
                eval_item = item["qty"] * lp
                stock_eval_dict[item["confirmed_code"]] = eval_item
                total_invested_stocks += item["qty"] * item["avg_price"]
                total_eval_stocks += eval_item

            lev_val = stock_eval_dict.get("233740", 0)
            inv_val = stock_eval_dict.get("251340", 0)
            actual_hedge_ratio = (inv_val / lev_val * 100) if lev_val > 0 else 0.0

            st.markdown("---")
            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("총 투자 원금", f"{new_principal:,}원")
            fc2.metric("주식 실시간 평가액", f"{total_eval_stocks:,}원")
            fc3.metric("예수금(현금)", f"{new_cash:,}원")
            total_acc = total_eval_stocks + new_cash
            diff_acc = total_acc - new_principal
            diff_pct = (diff_acc / new_principal * 100) if new_principal > 0 else 0
            fc4.metric("계좌 총자산", f"{total_acc:,}원", f"{diff_pct:+.2f}%")

            # 리밸런싱 진단
            st.markdown("---")
            st.markdown("##### ⚖️ [S값 + 롱-숏 헤지] 리밸런싱 카드")
            if lev_val > 0:
                if current_s_val >= 0:
                    reb_title = "🔵 [고점 과열] 인버스 50% 구축 & 레버리지 분할 익절 타이밍"
                    reb_color = "#1565C0"
                    reb_desc = f"S값이 <b>{current_s_val}</b>입니다. 인버스(251340)를 레버리지의 50%(약 {int(lev_val*0.5):,}원) 채워 하방을 방어하세요."
                elif current_s_val <= -40:
                    reb_title = "🔴 [바닥권] 인버스 전량 익절 & 레버리지 저점 매수 집중"
                    reb_color = "#D32F2F"
                    reb_desc = "인버스를 전량 익절(수익 확정)하고 레버리지 저점 매수에 집중하세요."
                else:
                    if actual_hedge_ratio > 65.0:
                        reb_title = "🟠 [헤지 과다] 인버스 비중 상한 초과 ➔ 초과분 익절"
                        reb_color = "#FF8F00"
                        reb_desc = f"인버스 비중({actual_hedge_ratio:.1f}%)이 65%를 넘었습니다. 초과분을 익절하세요."
                    elif actual_hedge_ratio < 35.0:
                        reb_title = "🟠 [헤지 부족] 인버스 방어력 약화 ➔ 50% 수준 보충 권장"
                        reb_color = "#FF8F00"
                        reb_desc = f"인버스 비중({actual_hedge_ratio:.1f}%)이 35%에 미달합니다."
                    else:
                        reb_title = "🟢 [정상 균형] 50% 롱-숏 헤지 안정 구간"
                        reb_color = "#2E7D32"
                        reb_desc = "포지션을 그대로 유지하세요."

                st.markdown(f"""
                <div class="brief-card" style="border-left: 6px solid {reb_color};">
                    <div class="brief-title" style="color: {reb_color};">{reb_title}</div>
                    <div style="font-size:0.88rem; color:#222;">
                        • <b>포지션</b>: 레버리지 {lev_val:,}원 | 인버스 {inv_val:,}원 (비율: <b>{actual_hedge_ratio:.1f}%</b>)<br>
                        • <b>지침</b>: {reb_desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 체결 일지 기록
            st.markdown("---")
            with st.expander("📝 [체결 일지 입력 & 잔고 자동 연동]", expanded=False):
                with st.form("trade_form_v2"):
                    tf1, tf2, tf3, tf4, tf5 = st.columns([1.1, 1.3, 1.0, 1.0, 1.0])
                    with tf1:
                        log_date = st.date_input("체결 일자", datetime.today()).strftime('%Y-%m-%d')
                    with tf2:
                        log_stock = st.text_input("종목코드", value=stock_code)
                    with tf3:
                        log_type = st.selectbox("구분", ["🔴 매수", "🔵 매도"])
                    with tf4:
                        log_price = st.number_input("체결 단가", min_value=1, value=int(curr_p), step=5)
                    with tf5:
                        log_qty = st.number_input("체결 수량", min_value=1, value=100, step=10)

                    auto_sync = st.checkbox("보유 종목 및 예수금에 즉시 반영", value=True)
                    submit_log = st.form_submit_button("➕ 기록 저장", use_container_width=True)
                    if submit_log:
                        trade_amt = int(log_price * log_qty)
                        acc["trade_logs"].append({
                            "일자": log_date, "종목": stock_name, "구분": log_type,
                            "체결단가": int(log_price), "체결수량": int(log_qty), "체결금액": trade_amt
                        })
                        if auto_sync:
                            target_itm = next((x for x in acc["items"] if x["confirmed_code"] == log_stock), None)
                            if "매수" in log_type:
                                if target_itm:
                                    old_q = int(target_itm["qty"])
                                    old_p = int(target_itm["avg_price"])
                                    new_tot_q = old_q + int(log_qty)
                                    target_itm["avg_price"] = int(round((old_q * old_p + trade_amt) / new_tot_q)) if new_tot_q > 0 else int(log_price)
                                    target_itm["qty"] = new_tot_q
                                acc["user_cash"] = max(0, int(new_cash) - trade_amt)
                            else:
                                if target_itm:
                                    target_itm["qty"] = max(0, int(target_itm["qty"]) - int(log_qty))
                                    if target_itm["qty"] == 0:
                                        target_itm["avg_price"] = 0
                                acc["user_cash"] = int(new_cash) + trade_amt
                        save_current_portfolio(acc)
                        st.success("✅ 저장 완료!")
                        st.rerun()

                if acc.get("trade_logs"):
                    df_logs = pd.DataFrame(acc["trade_logs"]).iloc[::-1]
                    st.dataframe(df_logs.style.format({"체결단가": "{:,}원", "체결수량": "{:,}주", "체결금액": "{:,}원"}), use_container_width=True, height=200)

        with tab4:
            st.markdown(f"#### 📢 [{s['date']}] {stock_name} 종합 마감 브리핑")
            st.info(f"오늘 종가: {s['B1']:,}원 ({s['cur_chg']:+.2f}%) | S값: {s['S']} | 200일선: {s['MA200']:,}원")
