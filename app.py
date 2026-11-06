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
    page_title="매매 시스템 Pro Max",
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

st.subheader("📈 스마트 파동 매매 시스템 Pro Max (4대 지표·거래량 통합)")

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
# 3. 네이버 금융 시세 & 종목명 크롤링 (외부 API 불필요)
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
    """외부 API 없이 네이버 금융 웹페이지 타이틀에서 종목명 자동 추출"""
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

# 주요 종목 빠른 매핑 사전
name_to_code = {
    "코스피지수": "KOSPI",
    "코스닥지수": "KOSDAQ",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
    "KODEX 코스닥150선물인버스": "251340",
    "코스닥150선물인버스": "251340",
    "TIGER 미국나스닥100타겟데일리커버드콜": "486290",
    "KODEX 레버리지": "122630",
    "KODEX 200선물인버스2X": "252670",
    "곱버스": "252670",
    "KODEX 200": "069500",
    "TIGER 미국나스닥100": "133690",
    "TIGER 미국S&P500": "360750",
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "현대차": "005380",
    "기아": "000270",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "NAVER": "035420",
    "카카오": "035720",
    "알테오젠": "196170",
    "에코프로비엠": "247540",
    "에코프로": "086520",
    "HLB": "028300",
    "리가켐바이오": "141080",
    "피엔티": "137400"
}

code_to_name = {v: k for k, v in name_to_code.items()}
code_to_name["233740"] = "KODEX 코스닥150레버리지"
code_to_name["251340"] = "KODEX 코스닥150선물인버스"
code_to_name["252670"] = "KODEX 200선물인버스2X"
code_to_name["486290"] = "TIGER 미국나스닥100타겟데일리커버드콜"

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
            fetched_name = fetch_naver_stock_name(code)
            return code, fetched_name
    else:
        for k, v in name_to_code.items():
            if clean_str.lower() in k.lower():
                return v, code_to_name.get(v, k)
        return clean_str, clean_str

# ---------------------------------------------------------
# 4. 상단 종목 빠른 선택 및 즐겨찾기 자유 관리 바
# ---------------------------------------------------------
acc_favs = st.session_state.account_data.get("favorites", [])
if 'current_target_query' not in st.session_state:
    st.session_state.current_target_query = "233740"

with st.form(key="search_form"):
    col_in1, col_in2, col_in3, col_in4 = st.columns([1.6, 1.4, 0.9, 0.7])
    with col_in1:
        user_input = st.text_input(
            "🔍 직접 입력 (종목명 또는 6자리 코드)",
            value=st.session_state.current_target_query,
            placeholder="예: 233740, 삼성전자, 피엔티"
        ).strip()
    with col_in2:
        quick_pick = st.selectbox(
            "⭐ 내 즐겨찾기 종목 바로 선택",
            options=["직접 입력 사용"] + acc_favs,
            index=0
        )
    with col_in3:
        years_back = st.selectbox("📅 표시 기간", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
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

# 원클릭 별표(☆/★) 버튼 & 오른쪽 목록 관리창(⚙️)
fav_col1, fav_col2 = st.columns([1.3, 2.7])
with fav_col1:
    if current_fav_label in acc_favs:
        if st.button(f"★ 즐겨찾기 해제 [{stock_name}]", use_container_width=True):
            acc_favs.remove(current_fav_label)
            st.session_state.account_data["favorites"] = acc_favs
            save_current_portfolio(st.session_state.account_data)
            st.rerun()
    else:
        if st.button(f"☆ 현재 종목 즐겨찾기 추가 [{stock_name}]", use_container_width=True):
            acc_favs.append(current_fav_label)
            st.session_state.account_data["favorites"] = acc_favs
            save_current_portfolio(st.session_state.account_data)
            st.rerun()

with fav_col2:
    with st.expander("⚙️ 즐겨찾기 목록 직접 추가 / 순서·삭제 관리"):
        m_col1, m_col2 = st.columns([3, 1])
        with m_col1:
            new_fav_str = st.text_input(
                "새로 등록할 종목명 또는 6자리 코드 입력",
                placeholder="예: 005380, 현대차, 알테오젠",
                key="new_fav_input",
                label_visibility="collapsed"
            )
        with m_col2:
            if st.button("➕ 목록에 추가", use_container_width=True):
                if new_fav_str.strip():
                    f_code, f_name = resolve_code_and_name(new_fav_str.strip())
                    new_entry = f"{f_name} ({f_code})"
                    if new_entry not in acc_favs:
                        acc_favs.append(new_entry)
                        st.session_state.account_data["favorites"] = acc_favs
                        save_current_portfolio(st.session_state.account_data)
                        st.success(f"✅ '{new_entry}' 추가 완료!")
                        st.rerun()

        updated_favs = st.multiselect(
            "현재 등록된 즐겨찾기 (X를 눌러 삭제 후 아래 저장 클릭)",
            options=acc_favs,
            default=acc_favs
        )
        if updated_favs != acc_favs:
            if st.button("💾 변경된 즐겨찾기 목록 저장", use_container_width=True):
                st.session_state.account_data["favorites"] = updated_favs
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
# 5. 웹 표 스타일러 & 4대 지표(MM,PM,LM,S)+거래량(G) 결합 수식 엔진
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
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: #B71C1C; font-weight: 900; border-radius: 4px;'
                    elif s_num < 0:
                        ratio = min(1.0, abs(s_num) / 60.0)
                        r = int(230 - ratio * 150); g = int(230 - ratio * 150); b = 255
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: 900; border-radius: 4px;'
                    else:
                        styles[idx] = f'{base_style} background-color: #E0E0E0; color: #333333; font-weight: bold;'
                except Exception:
                    pass

            elif col_name in ['MM', 'PM', 'LM', 'RM']:
                try:
                    v = float(val)
                    vmin, vmax = col_bounds.get(col_name, (0, 1))
                    ratio = 0.0 if vmax == vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
                    
                    if col_name == 'PM' and v < 0:
                        ratio_neg = min(1.0, abs(v) / 50.0)
                        r = int(240 - ratio_neg * 150); g = int(240 - ratio_neg * 150); b = 255
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: bold;'
                    else:
                        r = 255; g = int(245 - ratio * 170); b = int(245 - ratio * 170)
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.5 else "#222222"}; font-weight: {"bold" if ratio > 0.4 else "normal"};'
                except Exception:
                    pass

            elif col_name == '매수신호':
                val_str = str(val)
                if '4차' in val_str or '강력' in val_str:
                    styles[idx] = f'{base_style} background-color: #7B1FA2; color: #FFFFFF; font-weight: 900;'
                elif '3차' in val_str or '2차' in val_str or '진입' in val_str:
                    styles[idx] = f'{base_style} background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '1차' in val_str or '신호' in val_str:
                    styles[idx] = f'{base_style} background-color: #FF8F00; color: #FFFFFF; font-weight: 900;'
                elif '전량청산' in val_str or '상투' in val_str:
                    styles[idx] = f'{base_style} background-color: #0D47A1; color: #FFFFFF; font-weight: 900;'
                elif '집중익절' in val_str or '매도' in val_str:
                    styles[idx] = f'{base_style} background-color: #1976D2; color: #FFFFFF; font-weight: 900;'
                elif '선제익절' in val_str:
                    styles[idx] = f'{base_style} background-color: #0288D1; color: #FFFFFF; font-weight: 800;'
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

@st.cache_data(ttl=300, show_spinner=False)
def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    closes = pd.to_numeric(df['Close'], errors='coerce').ffill().values
    vols = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).values
    opens = pd.to_numeric(df['Open'], errors='coerce').ffill().values
    highs = pd.to_numeric(df['High'], errors='coerce').ffill().values
    lows = pd.to_numeric(df['Low'], errors='coerce').ffill().values
    n = len(closes)

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
        # 🌟 4대 지표(MM, PM, LM, S) + 거래량(G) 통합 매수·매도 판정 엔진
        # =========================================================
        if active_low > 0 and s_val >= 0:
            # 1) 과열권(S>=0, LM>=MM) 도달 시: 모멘텀 꺾임 또는 대량거래 음봉(상투) 체크
            if s_val < prev_s or (is_bear_candle and g_val >= 1.5):
                sig = "3차 전량청산(꺾임/상투)"
            elif is_bear_candle:
                sig = "3차 전량청산(음봉꺾임)"
            else:
                sig = "2차 집중익절(S≥0)"
        elif active_low > 0 and (s_val >= -5 or (mm > 0 and lm >= mm * 0.85)):
            # 2) 상승 에너지 85% 이상 회복 시 선제 분할 익절
            sig = "1차 선제익절(LM근접)"
        elif s_val <= -55:
            # 3) 4차 바닥 승부수 + 거래량 시그널(G>=1.5 투매손바뀜 or G<=0.7 바닥다지기) 결합
            if g_val >= 1.5:
                sig = "4차 강력진입(투매폭발)"
            elif g_val <= 0.7:
                sig = "4차 강력진입(바닥다지기)"
            else:
                sig = "4차 강력진입구간"
        elif s_val <= -40:
            # 4) 3차 집중 진입 + PM(고점 대비 낙폭 -15% 이하) 결합 확인
            if pm <= -15:
                sig = "3차 집중진입(낙폭확인)"
            else:
                sig = "3차 진입구간"
        elif s_val <= -32:
            if pm <= -10:
                sig = "2차 진입(할인확인)"
            else:
                sig = "2차 진입구간"
        elif s_val <= -25:
            sig = "1차 신호"
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
        '부-조정(S)': s_col
    })

    next_high = pending_high if pending_high is not None else active_high
    next_low = pending_low if pending_low is not None else active_low

    summary = {
        'B1': int(closes[-1]),
        'Open': int(opens[-1]),
        'High': int(highs[-1]),
        'Low': int(lows[-1]),
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
        'state': "상승추세" if state == 'UP' else "하락추세"
    }
    return df_out, summary

def rgb_to_hex(r, g, b):
    return f"{max(0, min(255, int(r))):02X}{max(0, min(255, int(g))):02X}{max(0, min(255, int(b))):02X}"

# 캐싱 적용으로 불필요한 엑셀 재생성 렉 완벽 방지
@st.cache_data(ttl=300, show_spinner=False)
def generate_original_style_excel(stock_name, stock_code, s, df_display, df_full_result, reverse_order=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PPP"

    font_bold = Font(name="맑은 고딕", size=10, bold=True)
    font_normal = Font(name="맑은 고딕", size=9)
    font_title = Font(name="맑은 고딕", size=11, bold=True)
    font_red_bold = Font(name="맑은 고딕", size=9, color="B71C1C", bold=True)
    font_blue_bold = Font(name="맑은 고딕", size=9, color="0D47A1", bold=True)
    font_white_bold = Font(name="맑은 고딕", size=9, color="FFFFFF", bold=True)
    
    fill_header = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    fill_blue_head = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    fill_sig_purple = PatternFill(start_color="7B1FA2", end_color="7B1FA2", fill_type="solid")
    fill_sig_red = PatternFill(start_color="D32F2F", end_color="D32F2F", fill_type="solid")
    fill_sig_orange = PatternFill(start_color="FF8F00", end_color="FF8F00", fill_type="solid")
    fill_sig_navy = PatternFill(start_color="0D47A1", end_color="0D47A1", fill_type="solid")
    fill_sig_blue = PatternFill(start_color="1976D2", end_color="1976D2", fill_type="solid")
    fill_sig_sky = PatternFill(start_color="0288D1", end_color="0288D1", fill_type="solid")
    fill_sig_green = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    col_bounds = {}
    for c in ['MM', 'PM', 'LM', 'RM', 'S']:
        vals = pd.to_numeric(df_full_result[c], errors='coerce')
        col_bounds[c] = (vals.min(), vals.max())

    ws['A2'] = "기간설정"
    ws['B2'] = "▼ 재무제표 ▼"
    ws['A3'] = "최신순 정렬" if reverse_order else "과거순 정렬"
    ws['B5'] = stock_name
    ws['C5'] = stock_code
    ws['B5'].font = font_title
    ws['C5'].font = font_bold

    ws['M2'] = "상승율"
    ws['Q2'] = "하락율"
    ws['M3'] = "하추대비"
    ws['S3'] = "상추대비"
    ws['M4'] = "조정대비"
    ws['S4'] = "반등대비"
    ws['O5'] = "U-point"
    ws['O5'].font = font_bold

    ws['A6'] = "일자"
    ws['A7'] = "기준가"
    ws['B7'] = s.get('B7', 0)
    ws['A8'] = "전환가"
    ws['B8'] = s.get('B8', 0)
    ws['A9'] = "1차가격"
    ws['B9'] = s.get('B9', 0)

    for cell_id in ['A7', 'A8', 'A9']:
        ws[cell_id].font = font_bold
        ws[cell_id].fill = fill_header
        ws[cell_id].alignment = align_center
    for cell_id in ['B7', 'B8', 'B9']:
        ws[cell_id].font = font_bold
        ws[cell_id].number_format = '#,##0'
        ws[cell_id].alignment = align_right

    headers_wave = {
        'M6': '부-반등', 'N6': '반등', 'O6': '상-추세',
        'Q6': '하-추세', 'R6': '조정', 'S6': '부-조정'
    }
    for pos, text in headers_wave.items():
        ws[pos] = text
        ws[pos].font = font_bold
        ws[pos].alignment = align_center
        ws[pos].fill = fill_yellow

    ws['N8'] = s.get('max_mn', 0)
    ws['O8'] = s.get('max_mn', 0)
    ws['Q8'] = s.get('min_pq', 0)
    ws['R8'] = s.get('min_pq', 0)
    for pos in ['N8', 'O8', 'Q8', 'R8']:
        ws[pos].font = font_bold
        ws[pos].number_format = '#,##0'
        ws[pos].alignment = align_right

    ws['F7'] = "현재 3M"
    ws['F7'].font = font_bold
    ws['F8'] = "현재가격"
    ws['G8'] = s.get('state', '')
    ws['H8'] = "MM"
    ws['I8'] = "PM"
    ws['J8'] = "LM"
    ws['K8'] = "S"
    ws['L8'] = "RM"

    ws['F9'] = s.get('B1', 0)
    ws['F9'].font = font_title
    ws['F9'].number_format = '#,##0'
    ws['H9'] = s.get('MM', 0)
    ws['I9'] = s.get('PM', 0)
    ws['J9'] = s.get('LM', 0)
    ws['K9'] = s.get('S', 0)
    ws['L9'] = s.get('RM', 0)

    for c in ['F8', 'G8', 'H8', 'I8', 'J8', 'K8', 'L8']:
        ws[c].font = font_bold
        ws[c].fill = fill_blue_head
        ws[c].alignment = align_center
    for c in ['H9', 'I9', 'J9', 'K9', 'L9']:
        ws[c].font = font_bold
        ws[c].alignment = align_center

    headers_11 = {
        'A11': "일자", 'B11': "종가(B)", 'C11': "등락률(C)", 'D11': "매수·매도신호",
        'F11': "거래량(F)", 'G11': "거래비율(G)",
        'H11': "MM", 'I11': "PM", 'J11': "LM", 'K11': "S", 'L11': "RM",
        'M11': "부-반등(M)", 'N11': "반등(N)", 'O11': "상-추세(O)",
        'Q11': "하-추세(Q)", 'R11': "조정(R)", 'S11': "부-조정(S)"
    }
    for pos, h_title in headers_11.items():
        ws[pos] = h_title
        ws[pos].font = font_bold
        ws[pos].alignment = align_center
        ws[pos].fill = fill_header
        ws[pos].border = thin_border

    df_to_export = df_display.iloc[::-1].copy() if reverse_order else df_display.copy()

    row_idx = 12
    for _, r in df_to_export.iterrows():
        c_a = ws.cell(row=row_idx, column=1, value=r['일자'])
        c_a.alignment = align_center
        c_a.font = font_normal
        c_a.border = thin_border

        chg_str = str(r['등락률(C)']).strip()
        is_up = '+' in chg_str
        is_down = '-' in chg_str

        c_b = ws.cell(row=row_idx, column=2, value=int(r['종가(B)']))
        c_b.number_format = '#,##0'
        c_b.alignment = align_right
        c_b.font = font_red_bold if is_up else (font_blue_bold if is_down else font_normal)
        c_b.border = thin_border

        try:
            chg_val = float(chg_str.replace('%', '').replace('+', '')) / 100.0
            c_c = ws.cell(row=row_idx, column=3, value=chg_val)
            c_c.number_format = '+0.00%;-0.00%;0.00%'
        except Exception:
            c_c = ws.cell(row=row_idx, column=3, value=chg_str)
        c_c.alignment = align_right
        c_c.font = font_red_bold if is_up else (font_blue_bold if is_down else font_normal)
        c_c.border = thin_border

        sig_val = str(r['매수신호']).strip()
        c_d = ws.cell(row=row_idx, column=4, value=sig_val)
        c_d.alignment = align_center
        c_d.border = thin_border

        if "4차" in sig_val or "강력" in sig_val:
            c_d.fill = fill_sig_purple
            c_d.font = font_white_bold
        elif "3차" in sig_val or "2차" in sig_val or "진입" in sig_val:
            c_d.fill = fill_sig_red
            c_d.font = font_white_bold
        elif "1차" in sig_val or "신호" in sig_val:
            c_d.fill = fill_sig_orange
            c_d.font = font_white_bold
        elif "전량청산" in sig_val:
            c_d.fill = fill_sig_navy
            c_d.font = font_white_bold
        elif "집중익절" in sig_val or "매도" in sig_val:
            c_d.fill = fill_sig_blue
            c_d.font = font_white_bold
        elif "선제익절" in sig_val:
            c_d.fill = fill_sig_sky
            c_d.font = font_white_bold
        elif sig_val == "관망":
            c_d.fill = fill_sig_green
            c_d.font = Font(name="맑은 고딕", size=9, color="2E7D32", bold=True)
        else:
            c_d.font = font_normal

        c_f = ws.cell(row=row_idx, column=6, value=int(r['거래량(F)']))
        c_f.number_format = '#,##0'
        c_f.alignment = align_right
        c_f.font = font_normal
        c_f.border = thin_border

        vol_ratio = float(r['거래비율(G)'])
        c_g = ws.cell(row=row_idx, column=7, value=vol_ratio)
        c_g.number_format = '0.00'
        c_g.alignment = align_right
        c_g.font = font_normal
        c_g.border = thin_border

        if vol_ratio >= 1.0:
            ratio_v = min(1.0, (vol_ratio - 1.0) / 1.0)
            red_hex = rgb_to_hex(255, 240 - ratio_v * 180, 240 - ratio_v * 180)
            c_f.fill = PatternFill(start_color=red_hex, end_color=red_hex, fill_type="solid")
            c_g.fill = PatternFill(start_color=red_hex, end_color=red_hex, fill_type="solid")
            if ratio_v > 0.3:
                c_f.font = font_red_bold
                c_g.font = font_red_bold
        else:
            ratio_v = min(1.0, abs(vol_ratio - 1.0) / 0.5)
            blue_hex = rgb_to_hex(240 - ratio_v * 180, 240 - ratio_v * 180, 255)
            c_f.fill = PatternFill(start_color=blue_hex, end_color=blue_hex, fill_type="solid")
            c_g.fill = PatternFill(start_color=blue_hex, end_color=blue_hex, fill_type="solid")
            if ratio_v > 0.3:
                c_f.font = font_blue_bold
                c_g.font = font_blue_bold

        for col_i, col_name in enumerate(['MM', 'PM', 'LM', 'S', 'RM'], start=8):
            val_num = float(r[col_name])
            cell_obj = ws.cell(row=row_idx, column=col_i, value=int(val_num))
            cell_obj.alignment = align_center
            cell_obj.border = thin_border

            if col_name == 'S':
                if val_num > 0:
                    ratio_s = min(1.0, val_num / 50.0)
                    s_hex = rgb_to_hex(255, 230 - ratio_s * 150, 230 - ratio_s * 150)
                    cell_obj.fill = PatternFill(start_color=s_hex, end_color=s_hex, fill_type="solid")
                    cell_obj.font = font_red_bold
                elif val_num < 0:
                    ratio_s = min(1.0, abs(val_num) / 60.0)
                    s_hex = rgb_to_hex(230 - ratio_s * 150, 230 - ratio_s * 150, 255)
                    cell_obj.fill = PatternFill(start_color=s_hex, end_color=s_hex, fill_type="solid")
                    cell_obj.font = font_blue_bold
                else:
                    cell_obj.fill = fill_header
                    cell_obj.font = font_bold
            else:
                vmin, vmax = col_bounds.get(col_name, (0, 1))
                ratio_m = 0.0 if vmax == vmin else max(0.0, min(1.0, (val_num - vmin) / (vmax - vmin)))
                
                if col_name == 'PM' and val_num < 0:
                    ratio_neg = min(1.0, abs(val_num) / 50.0)
                    pm_hex = rgb_to_hex(240 - ratio_neg * 150, 240 - ratio_neg * 150, 255)
                    cell_obj.fill = PatternFill(start_color=pm_hex, end_color=pm_hex, fill_type="solid")
                    cell_obj.font = font_blue_bold
                else:
                    m_hex = rgb_to_hex(255, 245 - ratio_m * 170, 245 - ratio_m * 170)
                    cell_obj.fill = PatternFill(start_color=m_hex, end_color=m_hex, fill_type="solid")
                    cell_obj.font = font_red_bold if ratio_m > 0.4 else font_normal

        for col_i, col_name in enumerate(['부-반등(M)', '반등(N)', '상-추세(O)'], start=13):
            val = r.get(col_name)
            cell_obj = ws.cell(row=row_idx, column=col_i)
            cell_obj.border = thin_border
            if pd.notna(val) and str(val).strip() not in ['', '-']:
                cell_obj.value = int(round(float(val)))
                cell_obj.number_format = '#,##0'
                cell_obj.alignment = align_right
                cell_obj.font = font_bold
                cell_obj.fill = fill_yellow

        for col_i, col_name in enumerate(['하-추세(Q)', '조정(R)', '부-조정(S)'], start=17):
            val = r.get(col_name)
            cell_obj = ws.cell(row=row_idx, column=col_i)
            cell_obj.border = thin_border
            if pd.notna(val) and str(val).strip() not in ['', '-']:
                cell_obj.value = int(round(float(val)))
                cell_obj.number_format = '#,##0'
                cell_obj.alignment = align_right
                cell_obj.font = font_bold
                cell_obj.fill = fill_yellow

        row_idx += 1

    widths = {
        'A': 12, 'B': 10, 'C': 10, 'D': 20, 'E': 3, 'F': 14, 'G': 9,
        'H': 7, 'I': 7, 'J': 7, 'K': 8, 'L': 7,
        'M': 10, 'N': 10, 'O': 10, 'P': 3, 'Q': 10, 'R': 10, 'S': 10
    }
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width

    out = BytesIO()
    wb.save(out)
    return out.getvalue()

# ---------------------------------------------------------
# 6. 메인 데이터 로드 및 4대 지표·거래량 융합 브리핑 헤더
# ---------------------------------------------------------
kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)

kospi_val = int(kospi_df['Close'].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df['Close'].iloc[-1] / kospi_df['Close'].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0

kosdaq_val = int(kosdaq_df['Close'].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df['Close'].iloc[-1] / kosdaq_df['Close'].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    with st.spinner(f"[{stock_name} ({stock_code})] 4대 파동 지표 및 거래량 결합 타점을 분석 중입니다..."):
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
        
        four_stages_info = [
            (-25, "1차 신호(5%)", 0.05),
            (-32, "2차 진입(10%)", 0.10),
            (-40, "3차 진입(25%)", 0.25),
            (-55, "4차 강력진입(30%)", 0.30)
        ]
        
        target_prices_dict = {}
        for s_tgt, name, w_ratio in four_stages_info:
            if max_mn_val > 0 and min_pq_val > 0:
                tp = r10(max_mn_val + (s_tgt * min_pq_val) / 100.0)
            else:
                tp = 0
            target_prices_dict[s_tgt] = tp

        # 보유 포트폴리오에서 현재 조회 중인 종목 찾기
        my_port_item = None
        acc_principal = int(st.session_state.account_data.get("user_principal", 30000000))
        if 'items' in st.session_state.account_data:
            for itm in st.session_state.account_data['items']:
                if itm.get('confirmed_code') == stock_code and itm.get('qty', 0) > 0:
                    my_port_item = itm
                    break

        # 상단 실전 액션 가이드 배너 (4대 지표 + 거래량 결합 판정)
        if "전량청산" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 고점 모멘텀 소멸·상투 포착! 잔여 물량 전량 청산"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: S≥0(LM≥MM) 과열권에서 S값이 꺾이거나 대량거래 음봉(G≥1.5)이 출회했습니다. **남은 물량을 100% 현금화**하고 인버스 헤지를 점검하세요."
            badge_color = "#0D47A1"
        elif "집중익절" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 상승 목표 에너지(LM≥MM) 100% 도달! 집중 익절 구간"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: S값이 0 이상으로 직전 파동 진폭(MM)을 모두 채웠습니다. **보유 물량의 40%를 집중 익절**하고 꺾임 신호를 주시하세요."
            badge_color = "#1976D2"
        elif "선제익절" in cur_sig:
            action_title = f"🌐 [{cur_sig}] ➔ 상승 에너지 85% 복원! 1차 안전마진 확보 구간"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: LM이 MM의 85% 이상 올라왔습니다. 평단가 위라면 **보유 물량의 30%를 선제 분할 익절**하여 현금 안전마진을 확보하세요."
            badge_color = "#0288D1"
        elif "4차" in cur_sig:
            action_title = f"🟣 [{cur_sig}] ➔ 1차 진바닥 & 거래량 시그널 포착!"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: S ≤ -55 바닥권입니다. 투매 손바뀜(G≥1.5) 또는 매도 고갈(G≤0.7)과 함께 **4차 승부수(30%)를 집행**하고 예비 현금 30%는 홀딩하세요!"
            badge_color = "#7B1FA2"
        elif "3차" in cur_sig or "2차" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 실질 낙폭(PM) 할인 확인 & 분할 매수 구간!"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: 고점 대비 낙폭(PM) 할인이 진행 중입니다. 추격 매수 없이 **단계별 지정가 이하에서만 정해진 비중(2차 10%, 3차 25%)**을 모아가세요."
            badge_color = "#D32F2F"
        elif "1차" in cur_sig:
            action_title = f"🟠 [{cur_sig}] ➔ 하락 초입 정찰병 진입 신호!"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: 1차 탐색 비중(5%)만 소액 체결하거나, 이미 보유 물량이 있다면 2·3차(PM≤-15%) 할인 구간까지 대기하세요."
            badge_color = "#FF8F00"
        else:
            action_title = "🟢 [관망 구간] ➔ 매수·매도 대기 및 현금 사수"
            action_item = "💡 **[4대 지표 & 거래량 수칙]**: 어중간한 위치에서의 매매를 멈추고, 1~4차 지정가 매수 타점이나 선제 익절(LM≥MM×85%) 신호가 올 때까지 대기하세요."
            badge_color = "#2E7D32"

        gauge_pct = max(2, min(98, int(((current_s_val + 70) / 100.0) * 100)))
        tp1, tp2, tp3, tp4 = target_prices_dict.get(-25, 0), target_prices_dict.get(-32, 0), target_prices_dict.get(-40, 0), target_prices_dict.get(-55, 0)

        st.markdown(f"""
        <div style="background-color: #F8FAFC; border-left: 6px solid {badge_color}; padding: 15px 18px; border-radius: 10px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                <h3 style="margin: 0; color: {badge_color}; font-size: 1.15rem;">{action_title}</h3>
                <span style="font-size:0.85rem; color:#555; font-weight:600;">기준일: {s['date']} | 거래비율(G): <b>{s['vol_ratio']:.2f}배</b> | 추세: <b>{s['state']}</b></span>
            </div>
            <p style="margin: 8px 0 6px 0; color: #222222; font-size: 0.92rem;">
                <b>4대 파동 지표 현황</b> — MM(진폭): <code>{s['MM']}%</code> | PM(고점낙폭): <code>{s['PM']}%</code> | LM(저점반등): <code>{s['LM']}%</code> | <b>현재 S값: <code style="font-size:1.0rem; color:{badge_color};">{current_s_val}</code></b> (전일 S: {s['prev_s']})
            </p>
            <div style="font-size:0.78rem; color:#666; display:flex; justify-content:space-between; margin-top:6px;">
                <span>🟣 4차 바닥(-55)</span><span>🔴 3차(-40, PM≤-15%)</span><span>🟠 1·2차(-25)</span><span>🟢 관망</span><span>🔵 익절·청산권(S≥-5~0)</span>
            </div>
            <div class="gauge-container" style="background: linear-gradient(90deg, #7B1FA2 0%, #D32F2F 30%, #FF8F00 45%, #4CAF50 65%, #1976D2 100%);">
                <div style="position:absolute; left:{gauge_pct}%; top:0; bottom:0; width:6px; background-color:#FFFFFF; border:2px solid #000; border-radius:3px;" title="현재 S값 위치"></div>
            </div>
            <div style="font-size:0.86rem; color:#333; margin-top:6px;">
                🎯 <b>단계별 지정가 매수 타점</b> — 
                <span class="order-badge" style="background:#FFF3E0; color:#E65100;">1차(5%): {tp1:,}원</span>
                <span class="order-badge" style="background:#FFEBEE; color:#C62828;">2차(10%): {tp2:,}원</span>
                <span class="order-badge" style="background:#FFCDD2; color:#B71C1C;">3차(25%): {tp3:,}원</span>
                <span class="order-badge" style="background:#F3E5F5; color:#6A1B9A;">4차(30%): {tp4:,}원</span>
            </div>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 9px 12px; border-radius: 6px; margin-top: 10px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 상단 4대 요약 메트릭 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{curr_p:,}원", f"{s['cur_chg']:+.2f}%")
        if my_port_item:
            my_avg = my_port_item['avg_price']
            my_ret = ((curr_p / my_avg) - 1.0) * 100 if my_avg > 0 else 0.0
            c2.metric("내 보유 평단가 / 수익률", f"{my_avg:,}원 ({my_port_item['qty']:,}주)", f"{my_ret:+.2f}%")
        else:
            c2.metric("S값 / 파동 고저점", f"S: {s['S']} (G:{s['vol_ratio']:.2f}배)", f"고점:{max_mn_val:,} / 저점:{min_pq_val:,}")
        c3.metric("코스피 (KOSPI)", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 (KOSDAQ)", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        # ---------------------------------------------------------
        # 7. 메인 5개 탭 구성
        # ---------------------------------------------------------
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 매수·매도 표 & 차트", 
            "📢 마감 브리핑 & 탈출 시뮬레이터", 
            "🎯 매수 & 매도 자동 주문표", 
            "💼 포트폴리오 & 자동 일지", 
            "💾 엑셀 다운로드 & 백업"
        ])

        # -----------------------------
        # TAB 1: 매수·매도 표 (전체) + 직관적 차트
        # -----------------------------
        with tab1:
            with st.expander("📈 [직관적 차트 보기] 최근 1년 주가 흐름 및 S값 바닥·고점 타점 추이", expanded=False):
                chart_df = df_full_result.tail(250).copy()
                chart_df['일자'] = pd.to_datetime(chart_df['일자'])
                chart_df.set_index('일자', inplace=True)
                
                ch_col1, ch_col2 = st.columns(2)
                with ch_col1:
                    st.caption(f"🔹 {stock_name} 최근 1년 종가 흐름")
                    st.line_chart(chart_df[['종가(B)']], height=220)
                with ch_col2:
                    st.caption("🔹 최근 1년 S값 추이 (-25 이하 분할매수권 / -5~0 이상 분할익절·청산권)")
                    st.line_chart(chart_df[['S']], height=220)

            f_col1, f_col2 = st.columns([2.5, 1.5])
            with f_col1:
                st.caption("📈 4대 지표(MM, PM, LM, S)와 거래비율(G)이 통합 반영된 실시간 파동 테이블입니다.")
            with f_col2:
                sig_filter = st.selectbox(
                    "🔍 표 신호 필터링",
                    ["전체 일자 보기", "매수 진입 신호만 모아보기 (1~4차)", "익절·청산 신호만 모아보기"],
                    label_visibility="collapsed"
                )

            df_rev = df_display.iloc[::-1].copy()
            if "매수 진입" in sig_filter:
                df_rev = df_rev[df_rev['매수신호'].str.contains("신호|진입")].copy()
            elif "익절·청산" in sig_filter:
                df_rev = df_rev[df_rev['매수신호'].str.contains("익절|청산|매도")].copy()

            col_configs = {
                "일자": st.column_config.TextColumn("일자", width=86),
                "종가(B)": st.column_config.TextColumn("종가", width=68),
                "등락률(C)": st.column_config.TextColumn("등락률", width=62),
                "매수신호": st.column_config.TextColumn("매수·매도신호", width=135),
                "거래량(F)": st.column_config.TextColumn("거래량", width=98),
                "거래비율(G)": st.column_config.TextColumn("비율(G)", width=55),
                "MM": st.column_config.TextColumn("MM", width=46),
                "PM": st.column_config.TextColumn("PM", width=46),
                "LM": st.column_config.TextColumn("LM", width=46),
                "S": st.column_config.TextColumn("S", width=48),
                "RM": st.column_config.TextColumn("RM", width=46),
                "부-반등(M)": st.column_config.TextColumn("부반등", width=68),
                "반등(N)": st.column_config.TextColumn("반등", width=68),
                "상-추세(O)": st.column_config.TextColumn("상추세", width=68),
                "하-추세(Q)": st.column_config.TextColumn("하추세", width=68),
                "조정(R)": st.column_config.TextColumn("조정", width=68),
                "부-조정(S)": st.column_config.TextColumn("부조정", width=68),
            }

            st.dataframe(
                style_table(df_rev, df_full_result),
                use_container_width=False,
                height=520,
                column_config=col_configs
            )

        # -----------------------------
        # TAB 2: 마감 브리핑 & 내 계좌 연동 시뮬레이터
        # -----------------------------
        with tab2:
            st.markdown(f"#### 📢 [{s['date']}] {stock_name} 장 마감 종합 브리핑")

            if kosdaq_chg <= -1.5:
                mkt_stage = "🚨 [지수 급락 / 공포 심리 고조]"
                mkt_color = "#D32F2F"
                mkt_eval = "외국인·기관의 매도세가 집중되며 지수가 하방 지지선을 테스트하는 장세입니다. 추격매수는 금물이며 PM 낙폭과 3·4차 지정가 방어선 가격만 지켜봐야 합니다."
            elif kosdaq_chg < 0:
                mkt_stage = "📉 [지수 약세 조정 / 숨고르기]"
                mkt_color = "#1976D2"
                mkt_eval = "차익 매물 출회로 시장이 조정을 받았습니다. 투매성 패닉은 아니며 파동상 하방 지지력과 거래량(G) 변화를 탐색하는 구간입니다."
            elif kosdaq_chg >= 1.5:
                mkt_stage = "🔥 [지수 급반등 / 매수세 유입]"
                mkt_color = "#C2185B"
                mkt_eval = "쇼트커버링과 저가 매수세가 유입되며 강하게 반등한 장세입니다. LM 반등 에너지가 MM에 근접하는지 확인하며 분할 익절 타점을 주시하세요."
            else:
                mkt_stage = "⚖️ [지수 보합권 / 방향성 탐색]"
                mkt_color = "#333333"
                mkt_eval = "뚜렷한 수급 주체 없이 지수가 제한된 박스권에서 등락했습니다. 파동의 방향성이 확정되기 전까지는 관망이 유리합니다."

            st.markdown(f"""
            <div class="brief-card" style="border-left: 5px solid {mkt_color};">
                <div class="brief-title" style="color: {mkt_color};">1. 전체 시장 종합 브리핑</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>지수 현황</b>: 코스피 <b>{kospi_val:,}p</b> ({kospi_chg:+.2f}%) | 코스닥 <b>{kosdaq_val:,}p</b> ({kosdaq_chg:+.2f}%)<br>
                    • <b>시장 국면 판정</b>: <span style="font-weight:bold; color:{mkt_color};">{mkt_stage}</span><br>
                    • <b>시장 상세 진단</b>: {mkt_eval}
                </div>
            </div>
            """, unsafe_allow_html=True)

            b_col1, b_col2 = st.columns(2)
            with b_col1:
                o_p, h_p, l_p, c_p = s['Open'], s['High'], s['Low'], s['B1']
                body_size = abs(c_p - o_p)
                candle_range = max(1, h_p - l_p)
                lower_shadow = min(o_p, c_p) - l_p

                if lower_shadow / candle_range >= 0.45 and (lower_shadow >= body_size * 1.5):
                    candle_type = "🔨 [아래꼬리 망치형 / 저가 매수 유입]"
                    candle_color = "#D32F2F"
                    candle_desc = "장중 급락을 저가에서 강하게 받아내며 아래꼬리를 길게 달았습니다. <b>단기 바닥 지지력이 확인되는 긍정 시그널</b>입니다."
                elif c_p < o_p and (body_size / candle_range >= 0.65):
                    candle_type = "📉 [장대음봉 / 매도세 우위]"
                    candle_color = "#1976D2"
                    candle_desc = "장 마감까지 매도 압력이 이어졌습니다. 고점권(S≥0)이라면 즉시 청산하고, 하락권이라면 <b>다음 방어선까지 차분히 대기</b>해야 합니다."
                elif body_size / candle_range <= 0.2:
                    candle_type = "⚖️ [도지(팽이형) / 팽팽한 균형]"
                    candle_color = "#333333"
                    candle_desc = "시가와 종가가 거의 일치하며 <b>추세가 진정되고 숨고르기</b>에 들어간 형태입니다."
                elif c_p > o_p:
                    candle_type = "📈 [양봉 반등 / 매수 우위]"
                    candle_color = "#D32F2F"
                    candle_desc = "시가 대비 종가를 끌어올리며 양봉 마감했습니다. <b>단기 기술적 반등 및 LM 회복 흐름이 유효</b>합니다."
                else:
                    candle_type = "단기 조정 캔들"
                    candle_color = "#555555"
                    candle_desc = "통상적인 박스권 잔파동 내에서 등락을 보였습니다."

                st.markdown(f"""
                <div class="brief-card">
                    <div class="brief-title">2. 🕯️ 당일 캔들 & 꼬리 분석</div>
                    <div style="font-size:0.87rem; color:#222; line-height:1.6;">
                        • <b>시세</b>: 시 {o_p:,} / 고 {h_p:,} / 저 {l_p:,} / <b>종 {c_p:,}원</b><br>
                        • <b>판정</b>: <span style="font-weight:bold; color:{candle_color};">{candle_type}</span><br>
                        • <b>해석</b>: {candle_desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with b_col2:
                vol_ratio_val = s['vol_ratio']
                if vol_ratio_val >= 1.5:
                    vol_badge = "🚨 [대량 거래 폭발 (G≥1.5) / 주요 변곡점]"
                    vol_color = "#D32F2F"
                    vol_desc = "거래량이 전일 대비 1.5배 이상 급증했습니다. <b>바닥권(S≤-40)이면 투매 손바뀜 진바닥</b>, <b>고점권(S≥0)이면 상투(전량청산)</b> 신호입니다."
                elif vol_ratio_val <= 0.7:
                    vol_badge = "💤 [거래량 소강 (G≤0.7) / 매도세 진정]"
                    vol_color = "#1976D2"
                    vol_desc = "거래량이 전일 대비 70% 이하로 말라붙었습니다. 하락 압력이 둔화되며 <b>지지선을 다지는 바닥 확인 구간</b>입니다."
                else:
                    vol_badge = "⚖️ [평균 수준 거래량 유지]"
                    vol_color = "#333333"
                    vol_desc = "전일과 유사한 거래량을 유지하며 기존 파동 흐름을 이어가고 있습니다."

                st.markdown(f"""
                <div class="brief-card">
                    <div class="brief-title">3. ⚡ 거래량 비율(G) 시그널 판독</div>
                    <div style="font-size:0.87rem; color:#222; line-height:1.6;">
                        • <b>거래량</b>: {s['C1']:,}주 (전일 대비 <b>{vol_ratio_val:.2f}배</b>)<br>
                        • <b>판정</b>: <span style="color:{vol_color}; font-weight:bold;">{vol_badge}</span><br>
                        • <b>해석</b>: {vol_desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            diff_3 = tp3 - curr_p if tp3 > 0 else 0
            diff_3_pct = (diff_3 / curr_p) * 100.0 if curr_p > 0 else 0.0
            diff_4 = tp4 - curr_p if tp4 > 0 else 0
            diff_4_pct = (diff_4 / curr_p) * 100.0 if curr_p > 0 else 0.0

            recent_5 = df_full_result.tail(5).copy()
            s_traj_html = " ➔ ".join([f"<b>{row['일자'][5:]}</b> (S:<code>{row['S']}</code>/G:<code>{row['거래비율(G)']:.1f}</code>)" for _, row in recent_5.iterrows()])

            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">4. 🎯 주요 방어선까지 남은 거리 & 최근 5일 S·거래비율(G) 궤적</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>3차 진입가 ({tp3:,}원)까지</b>: <span style="color:{'#D32F2F' if diff_3 < 0 else '#2E7D32'}; font-weight:bold;">{diff_3:+d}원 ({diff_3_pct:+.2f}%)</span> | 
                      <b>4차 강력진입가 ({tp4:,}원)까지</b>: <span style="color:{'#D32F2F' if diff_4 < 0 else '#2E7D32'}; font-weight:bold;">{diff_4:+d}원 ({diff_4_pct:+.2f}%)</span><br>
                    • <b>최근 5일 S값 & 거래비율 변화</b>: {s_traj_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if my_port_item:
                curr_my_qty = my_port_item['qty']
                curr_my_price = my_port_item['avg_price']
                curr_eval_pct = ((curr_p / curr_my_price) - 1.0) * 100 if curr_my_price > 0 else 0
                
                budget_10pct = int(acc_principal * 0.10)
                budget_25pct = int(acc_principal * 0.25)
                
                add_qty_10 = int(budget_10pct / tp3) if tp3 > 0 else 0
                sim_price_10 = int((curr_my_qty * curr_my_price + add_qty_10 * tp3) / (curr_my_qty + add_qty_10)) if (curr_my_qty + add_qty_10) > 0 else curr_my_price
                
                add_qty_25 = int(budget_25pct / tp3) if tp3 > 0 else 0
                sim_price_25 = int((curr_my_qty * curr_my_price + add_qty_25 * tp3) / (curr_my_qty + add_qty_25)) if (curr_my_qty + add_qty_25) > 0 else curr_my_price

                st.markdown(f"""
                <div class="brief-card" style="border-left: 5px solid #6A1B9A; background-color:#FDFBFF;">
                    <div class="brief-title" style="color: #6A1B9A;">5. 🧮 내 계좌 연동 평단가 인하(탈출) 시뮬레이터 (내 원금 {acc_principal:,}원 기준)</div>
                    <div style="font-size:0.88rem; color:#222; line-height:1.65;">
                        • <b>현재 내 보유 포지션</b>: <b>{curr_my_qty:,}주</b> | 현재 평단가 <b>{curr_my_price:,}원</b> (현재 수익률: <span style="color:{'#D32F2F' if curr_eval_pct > 0 else '#1976D2'}; font-weight:bold;">{curr_eval_pct:+.2f}%</span> / 본전 탈출까지 <b>{curr_my_price - curr_p:+,}원</b> 필요)<br>
                        • <b>시나리오 A [예비 방어 10% ({budget_10pct:,}원 / {add_qty_10:,}주) @ {tp3:,}원 체결 시]</b>:<br>
                          ➔ 평단가가 <b>{curr_my_price:,}원 ➔ <span style="color:#D32F2F; font-size:0.98rem;">{sim_price_10:,}원</span></b>으로 <b>{curr_my_price - sim_price_10:,}원 즉시 인하!</b><br>
                        • <b>시나리오 B [3차 기본 비중 25% ({budget_25pct:,}원 / {add_qty_25:,}주) @ {tp3:,}원 체결 시]</b>:<br>
                          ➔ 평단가가 <b>{curr_my_price:,}원 ➔ <span style="color:#6A1B9A; font-size:0.98rem;">{sim_price_25:,}원</span></b>으로 <b>{curr_my_price - sim_price_25:,}원 대폭 인하!</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info(f"💡 [💼 포트폴리오 & 자동 일지] 탭에 **{stock_name}** 보유 수량과 평단가를 등록해 두시면, 내 원금 기준 정확한 물타기 평단가 인하 시뮬레이션이 자동 계산됩니다.")

            col_link1, col_link2 = st.columns(2)
            with col_link1:
                st.link_button(f"📋 {stock_name} 실시간 공시·뉴스 (네이버 증권)", f"https://stock.naver.com/domestic/stock/{stock_code}/news", use_container_width=True)
            with col_link2:
                st.link_button(f"👥 {stock_name} 기관·외국인 수급 동향", f"https://stock.naver.com/domestic/stock/{stock_code}/trend", use_container_width=True)

        # -----------------------------
        # TAB 3: 4대 지표 + 거래량 결합 매수 & 매도 자동 주문표
        # -----------------------------
        with tab3:
            st.markdown("##### 🎯 [4대 지표 + 거래량 결합] 매수 & 매도 자동 주문 계산기")
            st.caption("내 총 투자 원금과 보유 평단가를 바탕으로 **단계별 매수 주문 수량**과 **분할 익절·청산 매도 주문 수량**을 자동 산출합니다.")
            
            total_seed = st.number_input(
                "💰 기준 투자 원금 설정 (원) — 기본값은 내 포트폴리오 원금과 연동됩니다.",
                min_value=100000, max_value=10000000000, value=acc_principal, step=1000000, format="%d"
            )

            # 1. 매수 주문표
            st.markdown("###### 📥 1단계: 4대 지표(S·PM) + 거래량(G) 결합 분할 매수 주문표 (기본 70% + 예비 30%)")
            base_plan = [
                {"단계": "🟠 1차 신호", "지표·거래량 조건": "S ≤ -25", "비중": 0.05, "목표가": tp1, "가이드": "하락 초입 정찰병 진입 (5%)"},
                {"단계": "🔴 2차 진입", "지표·거래량 조건": "S ≤ -32 & PM ≤ -10%", "비중": 0.10, "목표가": tp2, "가이드": "고점 대비 10% 이상 할인 확인 후 진입 (10%)"},
                {"단계": "🔴 3차 집중진입", "지표·거래량 조건": "S ≤ -40 & PM ≤ -15%", "비중": 0.25, "목표가": tp3, "가이드": "실질 낙폭 확인 후 주력 물량 확보 (25%)"},
                {"단계": "🟣 4차 강력진입", "지표·거래량 조건": "S ≤ -55 & (G≥1.5 투매 or G≤0.7 진정)", "비중": 0.30, "목표가": tp4, "가이드": "🚨 거래량 변곡 확인 후 1차 바닥 승부수 (30%)"},
                {"단계": "🛡️ 예비 1차 방어", "지표·거래량 조건": "재하락 S ≤ -40 (반등 실패 시)", "비중": 0.10, "목표가": tp3, "가이드": "4차 진입 후 익절 없이 다시 밀릴 때 10% 투입"},
                {"단계": "🚨 최후 2차 방어", "지표·거래량 조건": "재하락 S ≤ -55 (전저점 언더슈팅)", "비중": 0.20, "목표가": tp4, "가이드": "극단적 패닉셀 시 마지막 20% 투입"}
            ]
            
            calc_base = []
            for row in base_plan:
                amt = int(total_seed * row["비중"])
                t_price = row["목표가"]
                order_qty = int(amt // t_price) if t_price > 0 else 0
                reach_status = "✅ 도달 완료 (체결권)" if (curr_p <= t_price and t_price > 0) else f"대기 ({t_price - curr_p:+,}원)"
                calc_base.append({
                    "매수 단계": row["단계"],
                    "발동 지표 & 거래량 조건": row["지표·거래량 조건"],
                    "투입 비중": f"{int(row['비중']*100)}%",
                    "배정 예산": f"{amt:,}원",
                    "지정가 목표가": f"{t_price:,}원",
                    "예약 주문 수량": f"{order_qty:,}주",
                    "현재가 상태": reach_status,
                    "실전 행동 가이드": row["가이드"]
                })
            st.dataframe(pd.DataFrame(calc_base), use_container_width=True, hide_index=True)

            # 2. 매도(익절/청산) 주문표
            st.markdown("---")
            st.markdown("###### 📤 2단계: 4대 지표(LM·MM·S) + 거래량(G) 결합 분할 익절 & 청산 주문표")

            user_avg_p = my_port_item['avg_price'] if my_port_item else curr_p
            user_hold_qty = my_port_item['qty'] if my_port_item else int((total_seed * 0.7) // curr_p) if curr_p > 0 else 1000

            # 파동 에너지 기반 목표가 및 평단가 대비 목표가 계산
            wave_tp_85 = r10(min_pq_val * (1.0 + (s['MM'] * 0.85) / 100.0)) if (min_pq_val > 0 and s['MM'] > 0) else r10(user_avg_p * 1.05)
            wave_tp_100 = max_mn_val if max_mn_val > 0 else r10(user_avg_p * 1.10)

            sell_p1 = max(r10(user_avg_p * 1.05), wave_tp_85)
            sell_p2 = max(r10(user_avg_p * 1.10), wave_tp_100)
            sell_cut = r10(user_avg_p * 0.85)

            qty_step1 = int(round(user_hold_qty * 0.30))
            qty_step2 = int(round((user_hold_qty - qty_step1) * 0.50))
            qty_step3 = max(0, user_hold_qty - qty_step1 - qty_step2)

            sell_plan = [
                {
                    "매도 단계": "🌐 1차 선제익절 (30%)",
                    "4대 지표 & 거래량 트리거": "S ≥ -5 또는 LM ≥ (MM×85%) 도달",
                    "권장 목표단가": f"{sell_p1:,}원 (평단+5% 이상)",
                    "매도 주문 수량": f"{qty_step1:,}주 (보유량의 30%)",
                    "실전 전략 의도": "파동 에너지 85% 회복 시 원금 안전마진 선제 확보"
                },
                {
                    "매도 단계": "🔵 2차 집중익절 (40%)",
                    "4대 지표 & 거래량 트리거": "S ≥ 0 돌파 (LM ≥ MM 에너지 100% 충족)",
                    "권장 목표단가": f"{sell_p2:,}원 (전고점/평단+10%)",
                    "매도 주문 수량": f"{qty_step2:,}주 (보유량의 약 35~40%)",
                    "실전 전략 의도": "수학적 파동 상단 도달 시 주력 수익 확정 및 인버스 헤지 준비"
                },
                {
                    "매도 단계": "🏁 3차 전량청산 (잔여 100%)",
                    "4대 지표 & 거래량 트리거": "S ≥ 0 구간에서 S값 하락꺾임 or G ≥ 1.5 대량거래 음봉",
                    "권장 목표단가": "당일 종가 / 시장가 즉시",
                    "매도 주문 수량": f"{qty_step3:,}주 (남은 잔여수량 전량)",
                    "실전 전략 의도": "상투(Buying Climax) 및 모멘텀 종료 시 미련 없이 전량 현금화"
                },
                {
                    "매도 단계": "⚠️ 비상 리스크 컷",
                    "4대 지표 & 거래량 트리거": "최후 방어선 투입 후 평단 대비 -15% 이탈 & G ≥ 1.5 투매",
                    "권장 목표단가": f"{sell_cut:,}원 이탈 시",
                    "매도 주문 수량": "비중 축소 / 리스크 컷",
                    "실전 전략 의도": "레버리지 장기 물림 방지 및 계좌 생존권 보호"
                }
            ]
            st.dataframe(pd.DataFrame(sell_plan), use_container_width=True, hide_index=True)

        # -----------------------------
        # TAB 4: 보유 포트폴리오 & 체결 일지 자동 연동
        # -----------------------------
        with tab4:
            st.markdown("##### 💼 실전 계좌 잔고 & 3중 결합 스마트 리밸런싱")
            acc = st.session_state.account_data

            col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.2])
            with col_acc1:
                new_principal = st.number_input(
                    "💰 내 총 투자 원금 (원)",
                    min_value=0,
                    value=int(acc.get("user_principal", 30000000)),
                    step=1000000,
                    format="%d"
                )
            with col_acc2:
                new_cash = st.number_input(
                    "💵 현재 계좌 예수금(현금) (원)",
                    min_value=0,
                    value=int(acc.get("user_cash", 10000000)),
                    step=500000,
                    format="%d"
                )
            with col_acc3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("💾 계좌 및 보유종목 전체 저장", use_container_width=True):
                    acc["user_principal"] = new_principal
                    acc["user_cash"] = new_cash
                    if save_current_portfolio(acc):
                        st.success("✅ 원금, 예수금, 종목 수량/평단가가 영구 저장되었습니다!")

            st.markdown("---")
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown("###### 📊 현재 보유 종목 현황 (수량·평단가 수정 후 상단 저장 버튼 클릭)")
            with col_h2:
                if st.button("➕ 보유 종목 추가", use_container_width=True):
                    new_id = max([item["id"] for item in acc["items"]], default=0) + 1
                    acc["items"].append({
                        "id": new_id, "input_val": "", "confirmed_code": "233740", "confirmed_name": "종목 미지정", "qty": 0, "avg_price": 0
                    })
                    save_current_portfolio(acc)
                    st.rerun()

            total_invested_stocks = 0
            total_eval_stocks = 0
            items_to_delete = []
            stock_eval_dict = {}

            for idx, item in enumerate(acc["items"]):
                cols = st.columns([1.5, 0.7, 0.9, 0.9, 1.4, 0.4])
                with cols[0]:
                    item["input_val"] = st.text_input(f"종목명/코드 #{idx+1}", value=item["input_val"], key=f"mp_input_{item['id']}")
                with cols[1]:
                    st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
                    if st.button("🔍 적용", key=f"btn_search_{item['id']}", use_container_width=True):
                        c, n = resolve_code_and_name(item["input_val"])
                        item["confirmed_code"] = c
                        item["confirmed_name"] = n
                        save_current_portfolio(acc)
                        st.rerun()
                with cols[2]:
                    item["qty"] = st.number_input(f"보유 수량(주) #{idx+1}", min_value=0, value=int(item["qty"]), step=10, key=f"mp_qty_{item['id']}")
                with cols[3]:
                    item["avg_price"] = st.number_input(f"매수 평단가(원) #{idx+1}", min_value=0, value=int(item["avg_price"]), step=10, key=f"mp_price_{item['id']}")
                
                live_df, _ = get_naver_stock_data(item["confirmed_code"], count=5)
                live_curr_price = int(live_df['Close'].iloc[-1]) if live_df is not None and not live_df.empty else item["avg_price"]

                eval_item = item["qty"] * live_curr_price
                invest_item = item["qty"] * item["avg_price"]
                item_profit = eval_item - invest_item
                item_rate = ((live_curr_price / item["avg_price"]) - 1.0) * 100 if item["avg_price"] > 0 else 0.0

                c_code = item["confirmed_code"]
                stock_eval_dict[c_code] = stock_eval_dict.get(c_code, 0) + eval_item

                with cols[4]:
                    disp_name = item["confirmed_name"] if item["confirmed_name"] else "종목 미조회"
                    p_color = "#D32F2F" if item_profit > 0 else ("#1976D2" if item_profit < 0 else "#333333")
                    st.markdown(f"<div style='font-size: 0.78rem; color: #333;'><b>{disp_name}</b> (현재가 {live_curr_price:,}원)</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 0.90rem; font-weight: 800; color: {p_color};'>평가: {eval_item:,}원 ({item_rate:+.2f}% / {item_profit:+,}원)</div>", unsafe_allow_html=True)
                with cols[5]:
                    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_mp_{item['id']}"):
                        items_to_delete.append(item)

                total_invested_stocks += invest_item
                total_eval_stocks += eval_item

            if items_to_delete:
                for itm in items_to_delete:
                    acc["items"].remove(itm)
                save_current_portfolio(acc)
                st.rerun()

            st.markdown("---")
            curr_cash = new_cash
            principal = new_principal

            total_account_assets = total_eval_stocks + curr_cash
            net_profit_total = total_account_assets - principal
            net_profit_rate = (net_profit_total / principal * 100) if principal > 0 else 0.0
            stock_profit_total = total_eval_stocks - total_invested_stocks
            stock_profit_rate = ((total_eval_stocks / total_invested_stocks - 1.0) * 100) if total_invested_stocks > 0 else 0.0

            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("내 총 투자 원금", f"{principal:,}원")
            fc2.metric("보유 주식 실시간 평가액", f"{total_eval_stocks:,}원", f"{stock_profit_rate:+.2f}% ({stock_profit_total:+,}원)")
            fc3.metric("실시간 계좌 예수금(현금)", f"{curr_cash:,}원", f"현금 비중 {(curr_cash/total_account_assets*100 if total_account_assets>0 else 0):.1f}%")
            fc4.metric("계좌 총자산 (주식+현금)", f"{total_account_assets:,}원", f"원금대비 {net_profit_rate:+.2f}% ({net_profit_total:+,}원)")

            st.markdown("---")
            st.markdown("##### ⚖️ [S값 시그널 + 50% 롱-숏 헤지 밴드] 통합 리밸런싱 진단기")
            
            lev_val = stock_eval_dict.get("233740", 0)
            inv_val = stock_eval_dict.get("251340", 0)
            target_inv_hedge = lev_val * 0.50
            hedge_diff = inv_val - target_inv_hedge
            actual_hedge_ratio = (inv_val / lev_val * 100) if lev_val > 0 else 0.0

            today_dt = datetime.today()
            this_year = today_dt.year
            d_june = datetime(this_year, 6, 30)
            d_dec = datetime(this_year, 12, 31)
            
            if today_dt <= d_june:
                next_check_dt = d_june
                next_check_name = "전반기(6월 말)"
            elif today_dt <= d_dec:
                next_check_dt = d_dec
                next_check_name = "후반기(12월 말)"
            else:
                next_check_dt = datetime(this_year + 1, 6, 30)
                next_check_name = "내년 전반기(6월 말)"
            d_day = max(0, (next_check_dt - today_dt).days)

            if lev_val > 0:
                if current_s_val >= 0:
                    reb_title = "🔵 [S값 고점 회복] 인버스 50% 헤지 구축 & 레버리지 분할 익절 타이밍 (S ≥ 0)"
                    reb_color = "#1976D2"
                    reb_guidance = f"현재 S값이 <b>{current_s_val}</b>로 회복되었습니다. 레버리지 평가액의 50% 수준인 <b>약 {int(target_inv_hedge):,}원</b>으로 선물인버스(251340)를 진입하여 하락장 방어벽을 구축하세요."
                elif current_s_val <= -40:
                    reb_title = "🔴 [S값 바닥권 도달] 인버스 전량 수익 실현 & 레버리지 3~4차 집중 전환 (S ≤ -40)"
                    reb_color = "#D32F2F"
                    reb_guidance = f"현재 3~4차 바닥권(S값: <b>{current_s_val}</b>)에 진입했습니다. 하락을 방어해 준 <b>인버스를 전량 익절 매도</b>하고, 확보된 현금으로 레버리지 저점 매수에 집중하세요."
                else:
                    if actual_hedge_ratio > 65.0:
                        reb_title = "🟠 [밴드 상방 이탈] 인버스 비중 과다 ➔ 초과분 부분 익절 권장"
                        reb_color = "#FF8F00"
                        reb_guidance = f"인버스 비중(<b>{actual_hedge_ratio:.1f}%</b>)이 상한선(65%)을 넘었습니다. 초과분 <b>약 {int(hedge_diff):,}원</b> 상당의 인버스를 익절해 예수금을 늘리세요."
                    elif actual_hedge_ratio < 35.0:
                        reb_title = "🟠 [밴드 하방 이탈] 인버스 방어력 부족 ➔ 50% 수준 보충 권장"
                        reb_color = "#FF8F00"
                        reb_guidance = f"인버스 비중(<b>{actual_hedge_ratio:.1f}%</b>)이 하한선(35%)에 미달합니다. 안정적 헤지를 위해 인버스를 <b>약 {int(abs(hedge_diff)):,}원</b> 보충하거나 S값 시그널을 대기하세요."
                    else:
                        reb_title = "🟢 [정상 균형] 50% 롱-숏 헤지 밴드 범위 안착"
                        reb_color = "#2E7D32"
                        reb_guidance = f"인버스 헤지 비율(<b>{actual_hedge_ratio:.1f}%</b>)이 목표 밴드(35%~65%) 내에 안정적으로 유지되고 있습니다."

                st.markdown(f"""
                <div class="brief-card" style="border-left: 6px solid {reb_color}; background-color: #FAFAFA;">
                    <div class="brief-title" style="color: {reb_color}; font-size: 0.98rem;">{reb_title}</div>
                    <div style="font-size: 0.88rem; color: #222; line-height: 1.6;">
                        • <b>헤지 현황</b>: 레버리지 <b>{lev_val:,}원</b> | 인버스 <b>{inv_val:,}원</b> (현재 헤지 비율: <b>{actual_hedge_ratio:.1f}%</b> / 목표: 50.0%)<br>
                        • <b>행동 지침</b>: {reb_guidance}<br>
                        • <b>📅 정기 리밸런싱 점검</b>: <b>{next_check_name}</b>까지 <b>D-{d_day}일</b> 남음
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("💡 보유 종목에 [KODEX 코스닥150레버리지(233740)] 수량이 입력되면 50% 롱-숏 헤지 진단기가 즉시 작동합니다.")

            st.markdown("---")
            with st.expander("📝 [매수·매도 체결 일지 기록 & 잔고 자동 반영]", expanded=True):
                with st.form("smart_trade_log_form"):
                    tf1, tf2, tf3, tf4, tf5 = st.columns([1.1, 1.3, 1.0, 1.0, 1.0])
                    with tf1:
                        log_date = st.date_input("체결 일자", datetime.today()).strftime('%Y-%m-%d')
                    with tf2:
                        log_stock = st.text_input("종목명/코드", value=stock_code)
                    with tf3:
                        log_type = st.selectbox("매매 구분", ["🔴 매수", "🔵 매도"])
                    with tf4:
                        log_price = st.number_input("체결 단가(원)", min_value=1, value=int(curr_p), step=5)
                    with tf5:
                        log_qty = st.number_input("체결 수량(주)", min_value=1, value=100, step=10)

                    auto_sync = st.checkbox("✅ 이 체결 내역을 위 [보유 종목 수량·평단가] 및 [예수금]에 즉시 자동 반영하기", value=True)
                    submit_log = st.form_submit_button("➕ 체결 기록 저장 및 잔고 자동 업데이트", use_container_width=True)
                    
                    if submit_log:
                        code_res, name_res = resolve_code_and_name(log_stock)
                        trade_amt = int(log_price * log_qty)
                        
                        acc["trade_logs"].append({
                            "일자": log_date,
                            "종목코드": code_res,
                            "종목": name_res,
                            "구분": log_type,
                            "체결단가": int(log_price),
                            "체결수량": int(log_qty),
                            "체결금액": trade_amt
                        })

                        if auto_sync:
                            acc["user_principal"] = new_principal
                            target_itm = next((x for x in acc["items"] if x["confirmed_code"] == code_res), None)
                            if "매수" in log_type:
                                if target_itm:
                                    old_q = int(target_itm["qty"])
                                    old_p = int(target_itm["avg_price"])
                                    new_tot_q = old_q + int(log_qty)
                                    target_itm["avg_price"] = int(round((old_q * old_p + trade_amt) / new_tot_q)) if new_tot_q > 0 else int(log_price)
                                    target_itm["qty"] = new_tot_q
                                else:
                                    new_id = max([item["id"] for item in acc["items"]], default=0) + 1
                                    acc["items"].append({
                                        "id": new_id, "input_val": code_res, "confirmed_code": code_res,
                                        "confirmed_name": name_res, "qty": int(log_qty), "avg_price": int(log_price)
                                    })
                                acc["user_cash"] = max(0, int(new_cash) - trade_amt)
                            else:
                                if target_itm:
                                    target_itm["qty"] = max(0, int(target_itm["qty"]) - int(log_qty))
                                    if target_itm["qty"] == 0:
                                        target_itm["avg_price"] = 0
                                acc["user_cash"] = int(new_cash) + trade_amt

                        save_current_portfolio(acc)
                        st.success(f"✅ [{log_type}] {name_res} {log_qty:,}주 기록 및 계좌 잔고 자동 반영 완료!")
                        st.rerun()

                if acc.get("trade_logs"):
                    df_logs = pd.DataFrame(acc["trade_logs"]).iloc[::-1]
                    st.dataframe(
                        df_logs.style.format({
                            "체결단가": "{:,}원",
                            "체결수량": "{:,}주",
                            "체결금액": "{:,}원"
                        }),
                        use_container_width=True,
                        height=220
                    )
                    if st.button("🗑️ 체결 일지 기록 전체 초기화"):
                        acc["trade_logs"] = []
                        save_current_portfolio(acc)
                        st.rerun()

        # -----------------------------
        # TAB 5: 엑셀 다운로드 & 계좌 데이터 백업/복원
        # -----------------------------
        with tab5:
            st.markdown("##### 💾 원본 통합 엑셀 다운로드 (`PPP` 시트)")
            st.caption("화면의 매수·매도 표와 동일한 최신순 정렬로 저장되며, MM, PM, LM, S, RM 및 세분화된 매수·매도 신호 색상이 100% 동일하게 적용됩니다.")
            
            excel_bytes = generate_original_style_excel(stock_name, stock_code, s, df_display, df_full_result, reverse_order=True)
            st.download_button(
                label=f"📥 [{stock_name}] 원본 양식 컬러 엑셀 다운로드 (.xlsx)",
                data=excel_bytes,
                file_name=f"0.ETF_{stock_code}_{stock_name}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### 🔄 내 포트폴리오 & 즐겨찾기 백업 / 복원 (모바일·PC 연동용)")
            st.caption("스마트폰이나 다른 PC에서 접속할 때, 내 계좌 설정·즐겨찾기·체결 일지를 파일 하나로 간편하게 내려받고 복원할 수 있습니다.")
            
            bk_col1, bk_col2 = st.columns(2)
            with bk_col1:
                json_str = json.dumps(st.session_state.account_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📤 내 계좌·즐겨찾기 통합 백업 내려받기 (.json)",
                    data=json_str.encode('utf-8'),
                    file_name=f"portfolio_backup_{datetime.today().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            with bk_col2:
                uploaded_file = st.file_uploader("📥 백업된 JSON 파일 불러오기 (즉시 복원)", type=["json"], label_visibility="collapsed")
                if uploaded_file is not None:
                    try:
                        restored_data = json.load(uploaded_file)
                        if isinstance(restored_data, dict) and "items" in restored_data:
                            st.session_state.account_data = restored_data
                            save_current_portfolio(restored_data)
                            st.success("✅ 계좌 및 즐겨찾기 복원이 완료되었습니다! 페이지를 새로고침합니다.")
                            st.rerun()
                    except Exception:
                        st.error("올바른 백업 JSON 파일이 아닙니다.")
    else:
        st.error("입력하신 종목의 데이터를 찾을 수 없습니다. 올바른 종목명 또는 6자리 종목코드를 입력해 주세요.")
