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

# ---------------------------------------------------------
# 1. 페이지 기본 설정 및 커스텀 CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="스마트 파동 매매 Pro Max [공격형 Alpha]",
    page_icon="🔥",
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
        padding: 15px 18px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .brief-title {
        font-size: 0.98rem;
        font-weight: 800;
        color: #D32F2F;
        margin-bottom: 8px;
        border-bottom: 1px solid #F0F2F5;
        padding-bottom: 6px;
    }
    .mindset-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
        border: 1px solid #BFDBFE;
        border-left: 6px solid #2563EB;
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }
    .scenario-box {
        background-color: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 12px 14px;
        height: 100%;
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
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.subheader("🔥 스마트 파동 매매 Pro Max (지표 컬러 · 차트/백테스팅 · 심리 안정 브리핑 통합판)")

# ---------------------------------------------------------
# 2. 포트폴리오 & 즐겨찾기 영구 저장 관리
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
                    if "items" not in data or not isinstance(data["items"], list) or not data["items"]:
                        data["items"] = default_data["items"]
                    if "trade_logs" not in data or not isinstance(data["trade_logs"], list):
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

if "account_data" not in st.session_state:
    st.session_state.account_data = load_saved_portfolio()

# ---------------------------------------------------------
# 3. 네이버 금융 시세 크롤링 & 종목명/호가 유틸리티
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_naver_stock_data(code, count=1500):
    clean_code = str(code).strip()
    if not clean_code:
        clean_code = "233740"
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={clean_code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if response.status_code != 200:
            return None, None
        root = ET.fromstring(response.text)
        item_list = root.findall(".//item")
        data = []
        for item in item_list:
            vals = item.get("data").split("|")
            if len(vals) >= 6:
                dt = datetime.strptime(vals[0], "%Y%m%d").strftime("%Y-%m-%d")
                data.append({
                    "Date": dt,
                    "Open": float(vals[1]),
                    "High": float(vals[2]),
                    "Low": float(vals[3]),
                    "Close": float(vals[4]),
                    "Volume": float(vals[5])
                })
        if not data:
            return None, None
        df = pd.DataFrame(data)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.drop_duplicates(subset=["Date"]).sort_values("Date", ascending=True)
        df.set_index("Date", inplace=True)
        return df, clean_code
    except Exception:
        return None, None

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_naver_stock_name(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        res.encoding = "euc-kr"
        match = re.search(r"<title>(.*?) : Npay 증권</title>", res.text)
        if not match:
            match = re.search(r"<title>(.*?) : 네이버", res.text)
        if match and match.group(1).strip():
            return match.group(1).strip()
    except Exception:
        pass
    return f"종목({code})"

name_to_code = {
    "코스피지수": "KOSPI", "코스닥지수": "KOSDAQ",
    "KODEX 코스닥150레버리지": "233740", "코스닥150레버리지": "233740",
    "KODEX 코스닥150선물인버스": "251340", "코스닥150선물인버스": "251340",
    "TIGER 미국나스닥100타겟데일리커버드콜": "486290",
    "KODEX 레버리지": "122630", "KODEX 200선물인버스2X": "252670",
    "곱버스": "252670", "KODEX 200": "069500",
    "삼성전자": "005930", "SK하이닉스": "000660"
}
code_to_name = {
    "KOSPI": "코스피지수", "KOSDAQ": "코스닥지수",
    "233740": "KODEX 코스닥150레버리지", "251340": "KODEX 코스닥150선물인버스",
    "486290": "TIGER 미국나스닥100타겟데일리커버드콜", "122630": "KODEX 레버리지",
    "252670": "KODEX 200선물인버스2X", "069500": "KODEX 200",
    "005930": "삼성전자", "000660": "SK하이닉스"
}

ETF_BRAND_PREFIXES = (
    "KODEX", "TIGER", "KBSTAR", "RISE", "ACE", "SOL",
    "HANARO", "KOSEF", "ARIRANG", "PLUS", "TIMEFOLIO", "WOORI", "파워", "마이티"
)
KNOWN_ETF_CODES = {"233740", "251340", "486290", "122630", "252670", "069500"}

def is_etf_security(code="", name=""):
    c_str = str(code).strip()
    n_str = str(name).strip().upper()
    if c_str in KNOWN_ETF_CODES:
        return True
    return any(n_str.startswith(prefix) or prefix in n_str for prefix in ETF_BRAND_PREFIXES)

def get_krx_tick_size(price, is_etf=False):
    p = float(price)
    if p <= 0:
        return 1
    if is_etf:
        return 1 if p < 2000 else 5
    if p < 2000:
        return 1
    elif p < 5000:
        return 5
    elif p < 20000:
        return 10
    elif p < 50000:
        return 50
    elif p < 200000:
        return 100
    elif p < 500000:
        return 500
    return 1000

def round_tick(val, is_etf=False):
    if val <= 0:
        return 0
    tick = get_krx_tick_size(val, is_etf=is_etf)
    return int(np.floor(val / float(tick) + 0.5) * tick)

def r10(val):
    if val <= 0:
        return 0
    if val < 2000:
        return int(round(val))
    return int(np.floor(val / 10.0 + 0.5) * 10)

def trunc_int(val):
    return int(np.trunc(val))

def calc_exact_s_target_price(active_high, active_low, s_target, is_etf=False):
    if active_high <= 0 or active_low <= 0:
        return 0
    raw_tp = active_high + (s_target * active_low) / 100.0
    if raw_tp <= 0:
        return 0
    cand = round_tick(raw_tp, is_etf=is_etf)
    tick = get_krx_tick_size(cand, is_etf=is_etf)
    mm_raw = (active_high / active_low - 1.0) * 100.0
    for _ in range(5):
        lm_raw = (cand / active_low - 1.0) * 100.0
        s_check = trunc_int(lm_raw - mm_raw)
        if s_check <= s_target:
            break
        cand = max(tick, cand - tick)
    return cand

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
if "current_target_query" not in st.session_state:
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
        extracted_code = re.search(r"\(([^)]+)\)$", quick_pick)
        st.session_state.current_target_query = extracted_code.group(1) if extracted_code else user_input
    else:
        st.session_state.current_target_query = user_input

stock_code, stock_name = resolve_code_and_name(st.session_state.current_target_query)
is_current_etf = is_etf_security(stock_code, stock_name)
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

# ---------------------------------------------------------
# 5. 웹 표 스타일러 (MM, PM, LM, S, RM 색상 복원 및 고도화)
# ---------------------------------------------------------
def style_table(df_target, df_full):
    cols_grad = ["MM", "PM", "LM", "RM", "S"]
    col_bounds = {}
    for c in cols_grad:
        if c in df_full.columns:
            vals = pd.to_numeric(df_full[c], errors="coerce")
            col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = ["text-align: center;"] * len(row)
        chg_str = str(row.get("등락률(C)", "0%")).strip()
        is_up = "+" in chg_str
        is_down = "-" in chg_str

        for idx, col_name in enumerate(row.index):
            val = row[col_name]
            base_style = "text-align: center;"

            if col_name in ["종가(B)", "등락률(C)"]:
                if is_up:
                    styles[idx] = f"{base_style} color: #D32F2F; font-weight: bold;"
                elif is_down:
                    styles[idx] = f"{base_style} color: #1976D2; font-weight: bold;"
                else:
                    styles[idx] = f"{base_style} color: #111111;"

            elif col_name == "거래량(F)":
                try:
                    curr_vol = float(val)
                    row_pos = row.name
                    prev_vol = float(df_full.loc[row_pos - 1, "거래량(F)"]) if (row_pos - 1) in df_full.index else curr_vol
                    vol_diff_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                    if vol_diff_ratio >= 0:
                        ratio = min(1.0, vol_diff_ratio / 1.0)
                        r = 255
                        g = int(240 - ratio * 180)
                        b = int(240 - ratio * 180)
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.3 else "#222222"}; font-weight: bold;'
                    else:
                        ratio = min(1.0, abs(vol_diff_ratio) / 0.5)
                        r = int(240 - ratio * 180)
                        g = int(240 - ratio * 180)
                        b = 255
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#0D47A1" if ratio > 0.3 else "#222222"}; font-weight: bold;'
                except Exception:
                    pass

            elif col_name == "S":
                try:
                    s_num = float(val)
                    if s_num > 0:
                        ratio = min(1.0, s_num / 50.0)
                        r = 255
                        g = int(230 - ratio * 150)
                        b = int(230 - ratio * 150)
                        styles[idx] = f"{base_style} background-color: rgb({r}, {g}, {b}); color: #B71C1C; font-weight: 900; border-radius: 4px;"
                    elif s_num < 0:
                        ratio = min(1.0, abs(s_num) / 60.0)
                        r = int(230 - ratio * 150)
                        g = int(230 - ratio * 150)
                        b = 255
                        styles[idx] = f"{base_style} background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: 900; border-radius: 4px;"
                    else:
                        styles[idx] = f"{base_style} background-color: #E0E0E0; color: #333333; font-weight: bold;"
                except Exception:
                    pass

            elif col_name in ["MM", "PM", "LM", "RM"]:
                try:
                    v = float(val)
                    vmin, vmax = col_bounds.get(col_name, (0, 1))
                    ratio = 0.0 if vmax == vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))

                    if col_name in ["PM", "RM"] and v < 0:
                        ratio_neg = min(1.0, abs(v) / 50.0)
                        r = int(240 - ratio_neg * 150)
                        g = int(240 - ratio_neg * 150)
                        b = 255
                        styles[idx] = f"{base_style} background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: bold;"
                    else:
                        r = 255
                        g = int(245 - ratio * 170)
                        b = int(245 - ratio * 170)
                        styles[idx] = f'{base_style} background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.5 else "#222222"}; font-weight: {"bold" if ratio > 0.4 else "normal"};'
                except Exception:
                    pass

            elif col_name == "매수신호":
                val_str = str(val)
                if "4차" in val_str:
                    styles[idx] = f"{base_style} background-color: #6A1B9A; color: #FFFFFF; font-weight: 900;"
                elif "3차" in val_str and "청산" not in val_str:
                    styles[idx] = f"{base_style} background-color: #C62828; color: #FFFFFF; font-weight: 900;"
                elif "2차" in val_str and "익절" not in val_str:
                    styles[idx] = f"{base_style} background-color: #E53935; color: #FFFFFF; font-weight: 900;"
                elif "1차 탐색" in val_str:
                    styles[idx] = f"{base_style} color: #757575; font-weight: bold;"
                elif "청산" in val_str:
                    styles[idx] = f"{base_style} background-color: #1A237E; color: #FFFFFF; font-weight: 900;"
                elif "집중익절" in val_str:
                    styles[idx] = f"{base_style} background-color: #1565C0; color: #FFFFFF; font-weight: 900;"
                elif "선제익절" in val_str:
                    styles[idx] = f"{base_style} background-color: #00897B; color: #FFFFFF; font-weight: 900;"
                elif val_str == "관망":
                    styles[idx] = f"{base_style} color: #2E7D32; font-weight: bold;"
        return styles

    format_dict = {
        "종가(B)": "{:,}",
        "거래량(F)": "{:,}",
        "거래비율(G)": "{:.2f}",
        "MA200": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) else "-",
        "부-반등(M)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-",
        "반등(N)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-",
        "상-추세(O)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-",
        "하-추세(Q)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-",
        "조정(R)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-",
        "부-조정(S)": lambda x: f"{int(round(float(x))):,}" if pd.notna(x) and str(x).strip() not in ["", "-"] else "-"
    }
    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format(format_dict, na_rep="-")

# ---------------------------------------------------------
# 6. 지표 계산 및 공격형 Alpha 로직 (PM / RM 역할 분리 반영)
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    closes = pd.to_numeric(df["Close"], errors="coerce").ffill().values
    vols = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).values
    opens = pd.to_numeric(df["Open"], errors="coerce").ffill().values
    n = len(closes)

    ma200 = pd.Series(closes).rolling(window=200, min_periods=1).mean().values
    ma20 = pd.Series(closes).rolling(window=20, min_periods=1).mean().values
    ma60 = pd.Series(closes).rolling(window=60, min_periods=1).mean().values

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / np.where(closes[:-1] == 0, 1, closes[:-1])) - 1.0

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    m_col, n_col, o_col, q_col, r_col, s_col = [None] * n, [None] * n, [None] * n, [None] * n, [None] * n, [None] * n
    buy_signals = []

    init_p = int(round(closes[0])) if n > 0 else 0
    state = "UP"
    peak = init_p
    trough = init_p
    first_N = init_p
    first_R = init_p
    up_phase = "N"
    down_phase = "R"

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

        # RM 분리: 진행 중인 현재 상승 파동 고점(peak) 대비 실시간 낙폭(%) -> 트레일링 스탑 감시용
        ref_wave_high = max(peak, p) if state == "UP" else active_high
        rm = trunc_int((p / ref_wave_high - 1.0) * 100.0) if ref_wave_high > 0 else 0
        prev_s = s_list[-1] if len(s_list) > 0 else s_val

        # [공격형 Alpha] 1차 관망, 2차 5%, 3차 25%, 4차 40%
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
            if g_val >= 1.5:
                sig = "4차 승부수(손바뀜 40%+)"
            else:
                sig = "4차 강력진입(40%)"
        elif s_val <= -40:
            sig = "3차 주력진입(25%)"
        elif s_val <= -32:
            sig = "2차 진입(5%)"
        elif s_val <= -25:
            sig = "1차 탐색(관망)"
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

        if state == "UP":
            if p > peak:
                peak = p
                u_up_target = r10(first_N * 1.045)
                o_trigger = min(u_up_target, O8) if O8 > 0 else u_up_target
                if up_phase == "O" or p >= o_trigger:
                    up_phase = "O"
                    o_col[i] = p
                else:
                    n_col[i] = p
            else:
                down_turn_price = r10(peak * (1.0 - 0.095))
                first_step_down = r10(peak * (1.0 - 0.045))
                if p <= down_turn_price or (active_low == 0 and p <= first_step_down):
                    if up_phase == "O":
                        O8 = peak
                    else:
                        N8 = peak
                    pending_high = peak
                    state = "DOWN"
                    trough = p
                    first_R = p
                    u_dn_target = r10(first_R * (1.0 - 0.045))
                    q_trigger = max(u_dn_target, Q8) if Q8 > 0 else u_dn_target
                    if p <= q_trigger and active_low > 0:
                        down_phase = "Q"
                        q_col[i] = p
                    else:
                        down_phase = "R"
                        r_col[i] = p
                elif p <= first_step_down:
                    s_col[i] = p
        else:
            if p < trough:
                trough = p
                u_dn_target = r10(first_R * (1.0 - 0.045))
                q_trigger = max(u_dn_target, Q8) if Q8 > 0 else u_dn_target
                if down_phase == "Q" or p <= q_trigger:
                    down_phase = "Q"
                    q_col[i] = p
                else:
                    r_col[i] = p
            else:
                up_turn_price = r10(trough * 1.095)
                first_step_up = r10(trough * 1.045)
                if p >= up_turn_price:
                    if down_phase == "Q":
                        Q8 = trough
                    else:
                        R8 = trough
                    pending_low = trough
                    state = "UP"
                    peak = p
                    first_N = p
                    u_up_target = r10(first_N * 1.045)
                    o_trigger = min(u_up_target, O8) if O8 > 0 else u_up_target
                    if p >= o_trigger:
                        up_phase = "O"
                        o_col[i] = p
                    else:
                        up_phase = "N"
                        n_col[i] = p
                elif p >= first_step_up:
                    m_col[i] = p

    df_out = pd.DataFrame({
        "일자": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d"),
        "종가(B)": closes.astype(int),
        "등락률(C)": [f"{x * 100:+.2f}%" for x in chg],
        "매수신호": buy_signals,
        "거래량(F)": vols.astype(int),
        "거래비율(G)": vol_ratio,
        "MM": mm_list,
        "PM": pm_list,
        "LM": lm_list,
        "S": s_list,
        "RM": rm_list,
        "부-반등(M)": m_col,
        "반등(N)": n_col,
        "상-추세(O)": o_col,
        "하-추세(Q)": q_col,
        "조정(R)": r_col,
        "부-조정(S)": s_col,
        "MA200": np.round(ma200).astype(int)
    })

    next_high = pending_high if pending_high is not None else active_high
    next_low = pending_low if pending_low is not None else active_low

    summary = {
        "B1": int(closes[-1]),
        "Open": int(opens[-1]),
        "C1": int(vols[-1]),
        "cur_chg": chg[-1] * 100,
        "vol_ratio": vol_ratio[-1],
        "date": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d").iloc[-1],
        "MM": mm_list[-1],
        "PM": pm_list[-1],
        "LM": lm_list[-1],
        "S": s_list[-1],
        "RM": rm_list[-1],
        "prev_s": s_list[-2] if len(s_list) >= 2 else s_list[-1],
        "current_signal": buy_signals[-1],
        "max_mn": next_high,
        "min_pq": next_low,
        "cur_peak": peak,
        "cur_trough": trough,
        "state": "상승추세" if state == "UP" else "하락추세",
        "MA200": int(round(ma200[-1])),
        "MA20": int(round(ma20[-1])),
        "MA60": int(round(ma60[-1])),
        "is_below_ma200": closes[-1] < ma200[-1]
    }
    return df_out, summary

# ---------------------------------------------------------
# 7. 공격형 Alpha 백테스팅 엔진 & SVG 네이티브 차트 렌더러 (외부 패키지 불필요)
# ---------------------------------------------------------
def run_alpha_backtest(df_period, initial_capital=30000000):
    if df_period.empty:
        return None

    dates = df_period["일자"].values
    closes = df_period["종가(B)"].values.astype(float)
    s_vals = df_period["S"].values.astype(float)
    signals = df_period["매수신호"].values

    cash = float(initial_capital)
    shares = 0
    avg_price = 0.0
    cycle_seed = float(initial_capital)

    bought_stages = set()
    sold_stages = set()
    peak_since_buy = 0.0
    days_since_stage4 = 0

    equity_curve = []
    bnh_shares = initial_capital / closes[0] if closes[0] > 0 else 0
    bnh_curve = []
    trades = []
    completed_cycles = []
    cycle_realized_pnl = 0.0

    stage_weights = {
        "S2": 0.05,
        "S3": 0.25,
        "S4": 0.40,
        "R1": 0.10,
        "R2": 0.20,
    }

    for i in range(len(df_period)):
        dt = dates[i]
        p = closes[i]
        sv = s_vals[i]
        sig = str(signals[i])

        if shares == 0:
            cycle_seed = cash
            bought_stages.clear()
            sold_stages.clear()
            peak_since_buy = 0.0
            days_since_stage4 = 0
            cycle_realized_pnl = 0.0
        else:
            peak_since_buy = max(peak_since_buy, p)
            if "S4" in bought_stages:
                days_since_stage4 += 1

        buy_triggers = []
        if sv <= -32 and "S2" not in bought_stages:
            buy_triggers.append(("S2", "2차 진입(5%)", stage_weights["S2"]))
        if sv <= -40 and "S3" not in bought_stages:
            buy_triggers.append(("S3", "3차 주력진입(25%)", stage_weights["S3"]))
        if sv <= -55 and "S4" not in bought_stages:
            buy_triggers.append(("S4", "4차 승부수(40%)", stage_weights["S4"]))
        elif "S4" in bought_stages and days_since_stage4 >= 5 and sv <= -45 and "R1" not in bought_stages:
            buy_triggers.append(("R1", "예비 1차 방어(10%)", stage_weights["R1"]))
        elif "R1" in bought_stages and days_since_stage4 >= 10 and sv <= -60 and "R2" not in bought_stages:
            buy_triggers.append(("R2", "최후 2차 방어(20%)", stage_weights["R2"]))

        for stg_code, stg_label, weight in buy_triggers:
            budget = min(cash, cycle_seed * weight)
            buy_qty = int(budget // p) if p > 0 else 0
            if buy_qty > 0:
                cost = buy_qty * p
                total_cost = shares * avg_price + cost
                shares += buy_qty
                avg_price = total_cost / shares
                cash -= cost
                bought_stages.add(stg_code)
                sold_stages.clear()
                peak_since_buy = max(peak_since_buy, p)
                trades.append({
                    "일자": dt,
                    "구분": f"🔴 매수 [{stg_label}]",
                    "단가": int(p),
                    "수량": buy_qty,
                    "금액": int(cost),
                    "S값": int(sv),
                    "보유수량": shares,
                    "평단가": int(round(avg_price)),
                    "실현손익": "-"
                })

        if shares > 0 and avg_price > 0:
            cur_ret = (p / avg_price - 1.0) * 100.0
            drawdown_from_peak = (p / peak_since_buy - 1.0) * 100.0 if peak_since_buy > 0 else 0.0

            if "R1" in bought_stages and cur_ret <= -15.0:
                sell_qty = shares
                proceeds = sell_qty * p
                pnl = (p - avg_price) * sell_qty
                cash += proceeds
                cycle_realized_pnl += pnl
                shares = 0
                trades.append({
                    "일자": dt, "구분": "⚠️ 비상 리스크컷(전량)", "단가": int(p), "수량": sell_qty,
                    "금액": int(proceeds), "S값": int(sv), "보유수량": 0, "평단가": int(round(avg_price)),
                    "실현손익": f"{int(pnl):+,}원 ({cur_ret:+.1f}%)"
                })
                completed_cycles.append(cycle_realized_pnl)
                avg_price = 0.0

            elif (("청산" in sig and cur_ret > 1.5) or ("TP2" in sold_stages and drawdown_from_peak <= -4.5)):
                sell_qty = shares
                proceeds = sell_qty * p
                pnl = (p - avg_price) * sell_qty
                cash += proceeds
                cycle_realized_pnl += pnl
                shares = 0
                reason = "🏁 3차 트레일링 청산" if "TP2" in sold_stages and drawdown_from_peak <= -4.5 else f"🔵 {sig}(전량)"
                trades.append({
                    "일자": dt, "구분": reason, "단가": int(p), "수량": sell_qty,
                    "금액": int(proceeds), "S값": int(sv), "보유수량": 0, "평단가": int(round(avg_price)),
                    "실현손익": f"{int(pnl):+,}원 ({cur_ret:+.1f}%)"
                })
                completed_cycles.append(cycle_realized_pnl)
                avg_price = 0.0

            elif sv >= 0 and cur_ret >= 4.0 and "TP2" not in sold_stages:
                sell_ratio = 0.4375 if "TP1" in sold_stages else 0.55
                sell_qty = max(1, int(round(shares * sell_ratio)))
                if sell_qty >= shares:
                    sell_qty = shares
                proceeds = sell_qty * p
                pnl = (p - avg_price) * sell_qty
                cash += proceeds
                cycle_realized_pnl += pnl
                shares -= sell_qty
                sold_stages.add("TP2")
                trades.append({
                    "일자": dt, "구분": "🔵 2차 집중익절(35%)", "단가": int(p), "수량": sell_qty,
                    "금액": int(proceeds), "S값": int(sv), "보유수량": shares, "평단가": int(round(avg_price)),
                    "실현손익": f"{int(pnl):+,}원 ({cur_ret:+.1f}%)"
                })
                if shares == 0:
                    completed_cycles.append(cycle_realized_pnl)
                    avg_price = 0.0

            elif sv >= -5 and cur_ret >= 2.0 and "TP1" not in sold_stages:
                sell_qty = max(1, int(round(shares * 0.20)))
                if sell_qty < shares:
                    proceeds = sell_qty * p
                    pnl = (p - avg_price) * sell_qty
                    cash += proceeds
                    cycle_realized_pnl += pnl
                    shares -= sell_qty
                    sold_stages.add("TP1")
                    trades.append({
                        "일자": dt, "구분": "🟢 1차 선제익절(20%)", "단가": int(p), "수량": sell_qty,
                        "금액": int(proceeds), "S값": int(sv), "보유수량": shares, "평단가": int(round(avg_price)),
                        "실현손익": f"{int(pnl):+,}원 ({cur_ret:+.1f}%)"
                    })

        total_eq = cash + shares * p
        equity_curve.append(total_eq)
        bnh_curve.append(bnh_shares * p)

    eq_arr = np.array(equity_curve)
    bnh_arr = np.array(bnh_curve)
    running_max = np.maximum.accumulate(eq_arr)
    dd_arr = (eq_arr / np.where(running_max == 0, 1, running_max) - 1.0) * 100.0
    mdd = float(np.min(dd_arr)) if len(dd_arr) > 0 else 0.0

    bnh_max = np.maximum.accumulate(bnh_arr)
    bnh_dd = (bnh_arr / np.where(bnh_max == 0, 1, bnh_max) - 1.0) * 100.0
    bnh_mdd = float(np.min(bnh_dd)) if len(bnh_dd) > 0 else 0.0

    final_eq = float(eq_arr[-1]) if len(eq_arr) > 0 else float(initial_capital)
    total_ret = (final_eq / initial_capital - 1.0) * 100.0
    bnh_ret = (float(bnh_arr[-1]) / initial_capital - 1.0) * 100.0 if len(bnh_arr) > 0 else 0.0

    win_cycles = sum(1 for x in completed_cycles if x > 0)
    win_rate = (win_cycles / len(completed_cycles) * 100.0) if completed_cycles else 0.0

    curve_df = pd.DataFrame({
        "일자": dates,
        "공격형 Alpha 전략 자산(만원)": np.round(eq_arr / 10000.0, 1),
        "단순 보유(B&H) 자산(만원)": np.round(bnh_arr / 10000.0, 1)
    })

    return {
        "final_equity": int(round(final_eq)),
        "total_return": total_ret,
        "bnh_return": bnh_ret,
        "alpha_excess": total_ret - bnh_ret,
        "mdd": mdd,
        "bnh_mdd": bnh_mdd,
        "total_cycles": len(completed_cycles),
        "win_rate": win_rate,
        "open_shares": shares,
        "open_avg_price": int(round(avg_price)),
        "open_cash": int(round(cash)),
        "trades_df": pd.DataFrame(trades),
        "curve_df": curve_df
    }

def render_svg_wave_chart(df_display, tp2, tp3, tp4, stock_name, stock_code):
    """
    외부 차트 패키지(matplotlib 등) 없이도 모든 환경에서 한글 깨짐 없이 작동하는
    고해상도 SVG 파동 & S값 오실레이터 벡터 차트를 생성합니다.
    """
    if df_display.empty:
        return ""

    closes = df_display["종가(B)"].values.astype(float)
    ma200 = df_display["MA200"].values.astype(float)
    s_vals = df_display["S"].values.astype(float)
    sigs = df_display["매수신호"].values
    dates = df_display["일자"].values
    n = len(closes)

    w, h1, h2 = 960, 260, 170
    pad_l, pad_r, pad_t, pad_b = 65, 95, 28, 26

    # Panel 1: Price + MA200 + Target Lines
    all_p = list(closes) + list(ma200)
    for tp in [tp2, tp3, tp4]:
        if tp > 0:
            all_p.append(float(tp))
    p_min = min(all_p) * 0.96
    p_max = max(all_p) * 1.04
    if p_max <= p_min:
        p_max = p_min + 1.0

    def x_coord(idx):
        if n <= 1:
            return pad_l
        return pad_l + (idx / float(n - 1)) * (w - pad_l - pad_r)

    def y_price(val):
        return pad_t + (1.0 - (val - p_min) / (p_max - p_min)) * (h1 - pad_t - pad_b)

    close_pts = " ".join(f"{x_coord(i):.1f},{y_price(closes[i]):.1f}" for i in range(n))
    ma_pts = " ".join(f"{x_coord(i):.1f},{y_price(ma200[i]):.1f}" for i in range(n))

    grid_lines_p1 = []
    for k in range(5):
        gv = p_min + (p_max - p_min) * (k / 4.0)
        gy = y_price(gv)
        grid_lines_p1.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" stroke="#E2E8F0" stroke-dasharray="3,3" stroke-width="1"/>'
            f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" text-anchor="end" font-size="10" fill="#64748B">{int(round(gv)):,}</text>'
        )

    tp_lines = []
    for label, tp_val, color in [
        ("2차(-32)", tp2, "#E53935"),
        ("3차(-40)", tp3, "#C62828"),
        ("4차(-55)", tp4, "#6A1B9A")
    ]:
        if tp_val > 0 and p_min <= tp_val <= p_max:
            ty = y_price(tp_val)
            tp_lines.append(
                f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{w - pad_r}" y2="{ty:.1f}" stroke="{color}" stroke-dasharray="4,4" stroke-width="1.2"/>'
                f'<text x="{w - pad_r + 4}" y="{ty + 4:.1f}" text-anchor="start" font-size="10" font-weight="bold" fill="{color}">{label} {tp_val:,}</text>'
            )

    markers = []
    step_filter = max(1, n // 120)
    for i in range(0, n, step_filter):
        sg = str(sigs[i])
        cx, cy = x_coord(i), y_price(closes[i])
        if ("2차 진입" in sg) or ("3차" in sg and "청산" not in sg) or ("4차" in sg):
            markers.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="#D32F2F" stroke="#FFFFFF" stroke-width="1"/>')
        elif ("익절" in sg) or ("청산" in sg):
            markers.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="#1565C0" stroke="#FFFFFF" stroke-width="1"/>')

    # Panel 2: S-Value Oscillator
    s_min = min(-65.0, float(np.min(s_vals)) - 5.0)
    s_max = max(25.0, float(np.max(s_vals)) + 5.0)

    def y_s(sv):
        return pad_t + (1.0 - (sv - s_min) / (s_max - s_min)) * (h2 - pad_t - pad_b)

    s_pts = " ".join(f"{x_coord(i):.1f},{y_s(s_vals[i]):.1f}" for i in range(n))

    s_ref_lines = []
    for s_label, sv_ref, s_col in [
        ("S=0 (2차익절)", 0, "#1565C0"),
        ("S=-5 (1차익절)", -5, "#00897B"),
        ("S=-32 (2차매수)", -32, "#E53935"),
        ("S=-40 (3차주력)", -40, "#C62828"),
        ("S=-55 (4차승부)", -55, "#6A1B9A")
    ]:
        if s_min <= sv_ref <= s_max:
            sy = y_s(sv_ref)
            s_ref_lines.append(
                f'<line x1="{pad_l}" y1="{sy:.1f}" x2="{w - pad_r}" y2="{sy:.1f}" stroke="{s_col}" stroke-dasharray="3,3" stroke-width="1"/>'
                f'<text x="{pad_l - 6}" y="{sy + 4:.1f}" text-anchor="end" font-size="10" font-weight="bold" fill="{s_col}">{sv_ref}</text>'
                f'<text x="{w - pad_r + 4}" y="{sy + 4:.1f}" text-anchor="start" font-size="9.5" fill="{s_col}">{s_label}</text>'
            )

    date_labels = []
    for k in range(5):
        idx = int(round((n - 1) * (k / 4.0)))
        dx = x_coord(idx)
        date_labels.append(
            f'<text x="{dx:.1f}" y="{h2 - 6}" text-anchor="middle" font-size="10" fill="#475569">{dates[idx]}</text>'
        )

    svg_html = f"""
    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:12px 14px; margin-bottom:14px;">
        <div style="font-size:0.92rem; font-weight:800; color:#1E293B; margin-bottom:6px;">
            📈 [{stock_name} ({stock_code})] 주가 파동 · 200일선 · 지정가 타점 및 S값 오실레이터
            <span style="font-size:0.78rem; font-weight:600; color:#64748B; margin-left:10px;">
                (● 빨간점: 2~4차 매수 시그널 / ● 파란점: 익절·청산 시그널 / 주황 점선: 200일선)
            </span>
        </div>
        <svg viewBox="0 0 {w} {h1}" style="width:100%; height:auto; display:block; border-bottom:1px solid #F1F5F9;">
            {''.join(grid_lines_p1)}
            {''.join(tp_lines)}
            <polyline fill="none" stroke="#F59E0B" stroke-width="1.6" stroke-dasharray="5,3" points="{ma_pts}"/>
            <polyline fill="none" stroke="#0F172A" stroke-width="1.8" points="{close_pts}"/>
            {''.join(markers)}
        </svg>
        <div style="font-size:0.84rem; font-weight:800; color:#334155; margin:8px 0 4px 0;">
            🧭 S값 파동 에너지 오실레이터 (현재 S값: {int(s_vals[-1])})
        </div>
        <svg viewBox="0 0 {w} {h2}" style="width:100%; height:auto; display:block;">
            {''.join(s_ref_lines)}
            <polyline fill="none" stroke="#334155" stroke-width="1.6" points="{s_pts}"/>
            {''.join(date_labels)}
        </svg>
    </div>
    """
    return svg_html

def compute_historical_rebound_stats(df_full, target_s, forward_days=30):
    closes = df_full["종가(B)"].values.astype(float)
    s_vals = df_full["S"].values.astype(float)
    n = len(closes)
    threshold = min(target_s, -25) if target_s <= -20 else -32

    max_gains = []
    pos_count = 0
    i = 10
    while i < n - 5:
        if s_vals[i] <= threshold and closes[i] > 0:
            end_idx = min(n, i + forward_days + 1)
            future_window = closes[i + 1:end_idx]
            if len(future_window) > 0:
                max_p = float(np.max(future_window))
                gain_pct = (max_p / closes[i] - 1.0) * 100.0
                max_gains.append(gain_pct)
                if gain_pct >= 3.0:
                    pos_count += 1
            i += 5
        else:
            i += 1

    if not max_gains:
        return {"threshold": int(threshold), "count": 0, "win_prob": 0.0, "avg_max_gain": 0.0, "median_gain": 0.0}

    return {
        "threshold": int(threshold),
        "count": len(max_gains),
        "win_prob": (pos_count / len(max_gains)) * 100.0,
        "avg_max_gain": float(np.mean(max_gains)),
        "median_gain": float(np.median(max_gains))
    }

# ---------------------------------------------------------
# 8. 시장 지수 및 메인 종목 데이터 로딩
# ---------------------------------------------------------
kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)
kospi_val = int(kospi_df["Close"].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df["Close"].iloc[-1] / kospi_df["Close"].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0
kosdaq_val = int(kosdaq_df["Close"].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df["Close"].iloc[-1] / kosdaq_df["Close"].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    with st.spinner(f"[{stock_name} ({stock_code})] 5대 지표 컬러, 백테스팅 및 심리 안정 브리핑 로딩 중..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=1500)

    if raw_df is not None and not raw_df.empty:
        df_full_result, s = calculate_indicator_sheet(raw_df)
        cutoff_date = (datetime.today() - timedelta(days=365 * years_back)).strftime("%Y-%m-%d")
        df_display = df_full_result[df_full_result["일자"] >= cutoff_date].copy()
        if df_display.empty:
            df_display = df_full_result.copy()

        current_s_val = s["S"]
        cur_sig = s["current_signal"]
        max_mn_val = s.get("max_mn", 0)
        min_pq_val = s.get("min_pq", 0)
        curr_p = s["B1"]

        target_prices_dict = {}
        for s_tgt in [-25, -32, -40, -55, -5, 0]:
            target_prices_dict[s_tgt] = calc_exact_s_target_price(
                max_mn_val, min_pq_val, s_tgt, is_etf=is_current_etf
            )

        my_port_item = None
        acc_principal = int(st.session_state.account_data.get("user_principal", 30000000))
        if "items" in st.session_state.account_data:
            for itm in st.session_state.account_data["items"]:
                if itm.get("confirmed_code") == stock_code and itm.get("qty", 0) > 0:
                    my_port_item = itm
                    break

        regime_msg = "📉 [200일선 아래 - 역배열] 바닥 반등 폭발 승부수 대기" if s["is_below_ma200"] else "📈 [200일선 위 - 정배열] 적극적 추세 추종 가동"

        if "청산" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 상투 징후 포착! 트레일링 전량 청산"
            action_item = "💡 **[공격형 매도]**: 과열권 음봉 또는 거래량 폭발 출회. **남아있는 물량을 시장가 전량 청산**하여 차익을 확정합니다."
            badge_color = "#1A237E"
        elif "집중익절" in cur_sig:
            action_title = f"🔵 [{cur_sig}] ➔ 파동 에너지 100% 충족 (S ≥ 0)"
            action_item = "💡 **[공격형 매도]**: +10% 이상 도달 시 **보유량의 35% 집중 익절**, 나머지 45%는 트레일링으로 끌고 갑니다."
            badge_color = "#1565C0"
        elif "선제익절" in cur_sig:
            action_title = f"🟢 [{cur_sig}] ➔ 파동 에너지 85% 복원 (S ≥ -5)"
            action_item = "💡 **[공격형 매도]**: 물량의 **20%만 가볍게 선제 익절**하여 예비 탄약을 채우고, 80%는 랠리에 남겨둡니다."
            badge_color = "#00897B"
        elif "4차" in cur_sig:
            action_title = f"🟣 [{cur_sig}] ➔ S≤-55 바닥권 최대 승부처!"
            action_item = "💡 **[공격형 매수]**: 4차 비중을 **40%로 공격적 확대 집행**하여 평단가를 최저 수준으로 급격히 끌어내립니다."
            badge_color = "#6A1B9A"
        elif "3차" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 본격 주력 매수 구간 (S ≤ -40)"
            action_item = "💡 **[공격형 매수]**: 지정가에서 **3차 비중(25%)을 전격 매수**합니다."
            badge_color = "#C62828"
        elif "2차" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 5% 첫 분할 매수 시작 (S ≤ -32)"
            action_item = "💡 **[공격형 매수]**: 1차 관망 후 첫 진입. **5% 비중으로 탐색 진입**합니다."
            badge_color = "#E53935"
        elif "1차" in cur_sig:
            action_title = f"⚪ [{cur_sig}] ➔ 하락 초입 탐색 (매수 금지 / 관망)"
            action_item = "💡 **[원칙 준수]**: 잔파동 1차 구간은 매수하지 않고 관망합니다. 2차(-32)까지 현금을 100% 보존하세요."
            badge_color = "#757575"
        else:
            action_title = "🟢 [관망 구간] ➔ 타점 대기 및 현금 사수"
            action_item = "💡 **[행동 수칙]**: 불필요한 매매를 일절 배제하고 다음 타점이나 청산 신호를 기다리세요."
            badge_color = "#2E7D32"

        gauge_pct = max(2, min(98, int(((current_s_val + 70) / 100.0) * 100)))
        tp1 = target_prices_dict.get(-25, 0)
        tp2 = target_prices_dict.get(-32, 0)
        tp3 = target_prices_dict.get(-40, 0)
        tp4 = target_prices_dict.get(-55, 0)

        st.markdown(f"""
        <div style="background-color: #F8FAFC; border-left: 6px solid {badge_color}; padding: 15px 18px; border-radius: 10px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                <h3 style="margin: 0; color: {badge_color}; font-size: 1.15rem;">{action_title}</h3>
                <span style="font-size:0.83rem; color:#444; font-weight:700;">{regime_msg} | 200일선: {s['MA200']:,}원</span>
            </div>
            <p style="margin: 8px 0 6px 0; color: #222222; font-size: 0.92rem;">
                <b>5대 핵심 지표</b> — MM(파동진폭): <code>{s['MM']}%</code> | PM(확정고점낙폭): <code>{s['PM']}%</code> | LM(저점반등): <code>{s['LM']}%</code> | RM(현파동고점낙폭): <code>{s['RM']}%</code> | <b>S값: <code style="font-size:1.0rem; color:{badge_color};">{current_s_val}</code></b>
            </p>
            <div class="gauge-container" style="background: linear-gradient(90deg, #6A1B9A 0%, #D32F2F 30%, #FF8F00 45%, #4CAF50 65%, #00897B 80%, #1A237E 100%);">
                <div style="position:absolute; left:{gauge_pct}%; top:0; bottom:0; width:6px; background-color:#FFFFFF; border:2px solid #000; border-radius:3px;"></div>
            </div>
            <div style="font-size:0.86rem; color:#333; margin-top:6px;">
                🎯 <b>정밀 호가 지정가 타점</b> —
                <span class="order-badge" style="background:#EEEEEE; color:#616161;">1차(관망): {tp1:,}원</span>
                <span class="order-badge" style="background:#FFEBEE; color:#C62828;">2차(5% 시작): {tp2:,}원</span>
                <span class="order-badge" style="background:#FFCDD2; color:#B71C1C;">3차(25% 주력): {tp3:,}원</span>
                <span class="order-badge" style="background:#F3E5F5; color:#4A148C;">4차(40% 승부수): {tp4:,}원</span>
            </div>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 9px 12px; border-radius: 6px; margin-top: 10px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{curr_p:,}원", f"{s['cur_chg']:+.2f}%")
        if my_port_item:
            my_avg = my_port_item["avg_price"]
            my_ret = ((curr_p / my_avg) - 1.0) * 100 if my_avg > 0 else 0.0
            c2.metric("내 보유 평단 / 수익률", f"{my_avg:,}원 ({my_port_item['qty']:,}주)", f"{my_ret:+.2f}%")
        else:
            c2.metric("S값 / 거래비율(G)", f"S: {s['S']}", f"G: {s['vol_ratio']:.2f}배 (전일S: {s['prev_s']})")
        c3.metric("코스피 (KOSPI)", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 (KOSDAQ)", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        # ---------------------------------------------------------
        # 9. 메인 5대 탭 구성
        # ---------------------------------------------------------
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 매수·매도 표",
            "🎯 공격형 Alpha 주문 계산기",
            "📈 파동 차트 & 백테스팅",
            "💼 포트폴리오 & 롱-숏 진단",
            "📢 마감 브리핑 & 마인드 컨트롤"
        ])

        # =========================================================
        # TAB 1: 매수·매도 표
        # =========================================================
        with tab1:
            st.caption("📈 MM(파동진폭), PM(직전확정고점 대비 낙폭), LM(저점반등), S(파동에너지), RM(현파동고점 대비 낙폭) 히트맵 색상이 적용된 표입니다.")
            df_rev = df_display.iloc[::-1].copy()
            st.dataframe(style_table(df_rev, df_full_result), use_container_width=True, height=520)

        # =========================================================
        # TAB 2: 공격형 Alpha 주문 계산기 (매도 수량 비중 20/35/45% 일치)
        # =========================================================
        with tab2:
            st.markdown("#### 🎯 [공격형 Alpha] 실전 매수 & 매도 주문 계산기")
            calc_col1, calc_col2 = st.columns([1.5, 2.5])
            with calc_col1:
                total_seed = st.number_input("💰 기준 투자 원금 (원)", min_value=1000000, value=acc_principal, step=1000000, format="%d")
            with calc_col2:
                tick_unit_now = get_krx_tick_size(curr_p, is_etf=is_current_etf)
                st.info(
                    f"**종목 구분**: {'국내 ETF' if is_current_etf else '개별 주권'} (현재 호가단위: **{tick_unit_now:,}원**) | "
                    f"기준 확정 고점: **{max_mn_val:,}원** / 기준 확정 저점: **{min_pq_val:,}원**"
                )

            st.markdown("##### 📥 1. 공격형 분할 매수 플랜 (기본 70% + 예비 30% 배정)")
            base_plan = [
                {"단계": "⚪ 1차 신호", "조건": "S ≤ -25", "비중": "0% (관망)", "예산": "0원", "목표단가": f"{tp1:,}원", "현재가대비": f"{((tp1 / curr_p - 1)*100):+.2f}%" if tp1 > 0 else "-", "수량": "0주", "가이드": "하락 초입 진입 금지, 파동 관망"},
                {"단계": "🔴 2차 진입", "조건": "S ≤ -32", "비중": "5%", "예산": f"{int(total_seed * 0.05):,}원", "목표단가": f"{tp2:,}원", "현재가대비": f"{((tp2 / curr_p - 1)*100):+.2f}%" if tp2 > 0 else "-", "수량": f"{int(total_seed * 0.05 // tp2 if tp2 > 0 else 0):,}주", "가이드": "5% 소액 첫 탐색 진입"},
                {"단계": "🔴 3차 진입", "조건": "S ≤ -40", "비중": "25%", "예산": f"{int(total_seed * 0.25):,}원", "목표단가": f"{tp3:,}원", "현재가대비": f"{((tp3 / curr_p - 1)*100):+.2f}%" if tp3 > 0 else "-", "수량": f"{int(total_seed * 0.25 // tp3 if tp3 > 0 else 0):,}주", "가이드": "주력 1차 확보 (누적 30% 구축)"},
                {"단계": "🟣 4차 승부수", "조건": "S ≤ -55", "비중": "40%", "예산": f"{int(total_seed * 0.40):,}원", "목표단가": f"{tp4:,}원", "현재가대비": f"{((tp4 / curr_p - 1)*100):+.2f}%" if tp4 > 0 else "-", "수량": f"{int(total_seed * 0.40 // tp4 if tp4 > 0 else 0):,}주", "가이드": "🔥 바닥 승부수 투하 (기본 70% 완결)"},
                {"단계": "🛡️ 예비 1차 방어", "조건": "재하락 S ≤ -45", "비중": "10%", "예산": f"{int(total_seed * 0.10):,}원", "목표단가": f"{tp3:,}원", "현재가대비": f"{((tp3 / curr_p - 1)*100):+.2f}%" if tp3 > 0 else "-", "수량": f"{int(total_seed * 0.10 // tp3 if tp3 > 0 else 0):,}주", "가이드": "반등 실패 추가 하락 시 1차 방어"},
                {"단계": "🚨 최후 2차 방어", "조건": "재하락 S ≤ -60", "비중": "20%", "예산": f"{int(total_seed * 0.20):,}원", "목표단가": f"{tp4:,}원", "현재가대비": f"{((tp4 / curr_p - 1)*100):+.2f}%" if tp4 > 0 else "-", "수량": f"{int(total_seed * 0.20 // tp4 if tp4 > 0 else 0):,}주", "가이드": "극단적 언더슈팅 최후 투입"}
            ]
            st.dataframe(pd.DataFrame(base_plan), use_container_width=True, hide_index=True)

            st.markdown("##### 📤 2. 공격형 분할 익절 & 트레일링 룸 확대 플랜 (20% · 35% · 45% 정밀 배분)")
            user_avg_p = my_port_item["avg_price"] if my_port_item else curr_p
            user_hold_qty = my_port_item["qty"] if my_port_item else (int((total_seed * 0.7) // curr_p) if curr_p > 0 else 1000)

            s_minus5_p = target_prices_dict.get(-5, 0)
            s_zero_p = target_prices_dict.get(0, 0)
            sell_p1 = max(round_tick(user_avg_p * 1.05, is_etf=is_current_etf), s_minus5_p)
            sell_p2 = max(round_tick(user_avg_p * 1.10, is_etf=is_current_etf), s_zero_p)
            trailing_stop_p = round_tick(max(curr_p, s["cur_peak"]) * (1.0 - 0.045), is_etf=is_current_etf)
            sell_cut = round_tick(user_avg_p * 0.85, is_etf=is_current_etf)

            qty_s1 = int(round(user_hold_qty * 0.20))
            qty_s2 = int(round(user_hold_qty * 0.35))
            qty_s3 = max(0, user_hold_qty - qty_s1 - qty_s2)

            sell_plan = [
                {"익절 단계": "🟢 1차 선제익절", "트리거 조건": "S ≥ -5 또는 평단+5% 이상", "권장 목표단가": f"{sell_p1:,}원 이상 (S=-5: {s_minus5_p:,}원)", "주문 수량": f"{qty_s1:,}주 (20%)", "전략 의도": "소량만 덜어 예비 현금 확보, 80%는 랠리에 남겨둠"},
                {"익절 단계": "🔵 2차 집중익절", "트리거 조건": "S ≥ 0 또는 평단+10% 이상", "권장 목표단가": f"{sell_p2:,}원 이상 (S=0: {s_zero_p:,}원)", "주문 수량": f"{qty_s2:,}주 (35%)", "전략 의도": "파동 목표치 도달 시 주력 수익 확정 (누적 55% 회수)"},
                {"익절 단계": "🏁 3차 트레일링 스탑", "트리거 조건": "고점 대비 -4.5% 밀림(RM≤-4) or 상투 음봉", "권장 목표단가": f"현 고점 대비 {trailing_stop_p:,}원 이탈 시", "주문 수량": f"{qty_s3:,}주 (잔여 45% 전량)", "전략 의도": "🔥 20~30% 이상 대세 상승 파동을 끝까지 쥐고 극대화"},
                {"익절 단계": "⏱️ 타임스탑 룰", "트리거 조건": "4차 진입 후 20영업일간 무반등 횡보", "권장 목표단가": "20영업일 경과 시점", "주문 수량": f"{int(round(user_hold_qty * 0.25)):,}주 (보유량 25%)", "전략 의도": "레버리지 ETF 음의 복리(변동성 끌림) 침식 방지"},
                {"익절 단계": "⚠️ 비상 리스크컷", "트리거 조건": "예비 방어선 소진 후 평단 -15% 이탈", "권장 목표단가": f"{sell_cut:,}원 이탈 시", "주문 수량": "비상 방어 손절", "전략 의도": "극단적 시스템 리스크 발생 시 계좌 생존 최후 브레이크"}
            ]
            st.dataframe(pd.DataFrame(sell_plan), use_container_width=True, hide_index=True)

        # =========================================================
        # TAB 3: 파동 차트 & 백테스팅 (외부 라이브러리 없이 100% 작동)
        # =========================================================
        with tab3:
            st.markdown(f"#### 📈 [{stock_name}] 파동 에너지 차트 & 공격형 Alpha 백테스팅 (최근 {years_back}년)")

            bt_result = run_alpha_backtest(df_display, initial_capital=acc_principal)
            if bt_result:
                bk1, bk2, bk3, bk4, bk5 = st.columns(5)
                bk1.metric(
                    "전략 누적 수익률",
                    f"{bt_result['total_return']:+.2f}%",
                    f"최종자산 {bt_result['final_equity']:,}원"
                )
                bk2.metric(
                    "단순보유(B&H) 대비 Alpha",
                    f"{bt_result['alpha_excess']:+.2f}%p",
                    f"단순보유 {bt_result['bnh_return']:+.2f}%"
                )
                bk3.metric(
                    "전략 최대낙폭 (MDD)",
                    f"{bt_result['mdd']:.2f}%",
                    f"단순보유 MDD {bt_result['bnh_mdd']:.2f}%"
                )
                bk4.metric(
                    "완결 매매 사이클 / 승률",
                    f"{bt_result['total_cycles']}회 / {bt_result['win_rate']:.1f}%",
                    "분할매수➔익절 완결 기준"
                )
                open_status_str = f"{bt_result['open_shares']:,}주 (평단 {bt_result['open_avg_price']:,}원)" if bt_result["open_shares"] > 0 else "100% 현금 관망 중"
                bk5.metric("시뮬레이션 현재 포지션", open_status_str, f"현금 {bt_result['open_cash']:,}원")

            # 브라우저 네이티브 SVG 벡터 차트 렌더링 (한글 폰트 깨짐 및 패키지 에러 원천 차단)
            svg_chart_html = render_svg_wave_chart(df_display, tp2, tp3, tp4, stock_name, stock_code)
            st.markdown(svg_chart_html, unsafe_allow_html=True)

            if bt_result:
                st.markdown("##### 💰 공격형 Alpha 전략 vs 단순 보유(Buy & Hold) 자산 증식 곡선 (단위: 만원)")
                chart_df = bt_result["curve_df"].set_index("일자")
                st.line_chart(chart_df, height=260)

                if not bt_result["trades_df"].empty:
                    with st.expander(f"📋 백테스팅 상세 매매 기록 보기 (총 {len(bt_result['trades_df'])}건)", expanded=False):
                        tdf = bt_result["trades_df"].iloc[::-1].copy()
                        st.dataframe(
                            tdf.style.format({"단가": "{:,}원", "수량": "{:,}주", "금액": "{:,}원", "보유수량": "{:,}주", "평단가": "{:,}원"}),
                            use_container_width=True,
                            hide_index=True
                        )

        # =========================================================
        # TAB 4: 포트폴리오 & 롱-숏 진단
        # =========================================================
        with tab4:
            st.markdown("##### 💼 실전 계좌 잔고 & 공격형 롱-숏 헤지 진단")
            acc = st.session_state.account_data

            col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.2])
            with col_acc1:
                new_principal = st.number_input("💰 총 원금", min_value=0, value=int(acc.get("user_principal", 30000000)), step=1000000)
            with col_acc2:
                new_cash = st.number_input("💵 예수금(현금)", min_value=0, value=int(acc.get("user_cash", 10000000)), step=500000)
            with col_acc3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("💾 계좌 원금/예수금 저장", use_container_width=True):
                    acc["user_principal"] = new_principal
                    acc["user_cash"] = new_cash
                    save_current_portfolio(acc)
                    st.success("✅ 계좌 정보가 저장되었습니다!")
                    st.rerun()

            total_invested_stocks, total_eval_stocks = 0, 0
            stock_eval_dict = {}
            holdings_rows = []
            for item in acc["items"]:
                c_code = str(item.get("confirmed_code", "")).strip()
                c_name = item.get("confirmed_name") or resolve_code_and_name(c_code)[1]
                qty_val = int(item.get("qty", 0))
                avg_val = int(item.get("avg_price", 0))
                live_df, _ = get_naver_stock_data(c_code, count=5)
                lp = int(live_df["Close"].iloc[-1]) if live_df is not None and not live_df.empty else avg_val
                invested_amt = qty_val * avg_val
                eval_item = qty_val * lp
                pnl_amt = eval_item - invested_amt
                pnl_pct = ((lp / avg_val) - 1.0) * 100.0 if avg_val > 0 and qty_val > 0 else 0.0

                stock_eval_dict[c_code] = eval_item
                total_invested_stocks += invested_amt
                total_eval_stocks += eval_item
                holdings_rows.append({
                    "종목코드": c_code,
                    "종목명": c_name,
                    "보유수량": qty_val,
                    "매수평단가": avg_val,
                    "현재가": lp,
                    "매입금액": invested_amt,
                    "평가금액": eval_item,
                    "평가손익": pnl_amt,
                    "수익률": f"{pnl_pct:+.2f}%"
                })

            lev_val = stock_eval_dict.get("233740", 0)
            inv_val = stock_eval_dict.get("251340", 0)
            actual_hedge_ratio = (inv_val / lev_val * 100.0) if lev_val > 0 else 0.0

            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("총 투자 원금", f"{new_principal:,}원")
            fc2.metric("주식 실시간 평가액", f"{total_eval_stocks:,}원", f"매입원금 대비 {total_eval_stocks - total_invested_stocks:+,}원")
            fc3.metric("예수금(현금)", f"{new_cash:,}원")
            total_acc = total_eval_stocks + new_cash
            diff_acc = total_acc - new_principal
            diff_pct = (diff_acc / new_principal * 100.0) if new_principal > 0 else 0.0
            fc4.metric("계좌 총자산", f"{total_acc:,}원", f"{diff_pct:+.2f}% ({diff_acc:+,}원)")

            if holdings_rows:
                st.markdown("##### 📋 보유 종목 실시간 현황판")
                df_hold = pd.DataFrame(holdings_rows)
                st.dataframe(
                    df_hold.style.format({
                        "보유수량": "{:,}주", "매수평단가": "{:,}원", "현재가": "{:,}원",
                        "매입금액": "{:,}원", "평가금액": "{:,}원", "평가손익": "{:+,}원"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            if stock_code == "233740":
                lev_s_val = current_s_val
            else:
                lev_raw_df, _ = get_naver_stock_data("233740", count=600)
                if lev_raw_df is not None and not lev_raw_df.empty:
                    _, lev_summary = calculate_indicator_sheet(lev_raw_df)
                    lev_s_val = lev_summary["S"]
                else:
                    lev_s_val = current_s_val

            st.markdown("##### ⚖️ [코스닥150 레버리지(233740) 고유 S값 기준] 롱-숏 리밸런싱 카드")
            if lev_val > 0:
                if lev_s_val >= 0:
                    reb_title = "🔵 [고점 과열] 인버스 50~60% 공격적 숏 구축 & 레버리지 분할 익절"
                    reb_color = "#1565C0"
                    reb_desc = f"레버리지(233740) S값이 <b>{lev_s_val}</b>입니다. 하락 전환에 대비해 인버스(251340)를 레버리지의 <b>50~60%(약 {int(lev_val * 0.55):,}원)</b> 수준으로 구축하세요."
                elif lev_s_val <= -40:
                    reb_title = "🔴 [바닥권] 인버스 전량 청산(수익 확정) ➔ 레버리지 3·4차 승부수 투입"
                    reb_color = "#D32F2F"
                    reb_desc = f"레버리지(233740) S값이 <b>{lev_s_val}</b> 바닥권입니다. 하락을 방어해 준 인버스를 현금화하여 레버리지 주력 승부수 자금으로 전환하세요."
                else:
                    if actual_hedge_ratio > 65.0:
                        reb_title = "🟠 [헤지 과다] 인버스 비중 상한 초과 ➔ 초과분 익절"
                        reb_color = "#FF8F00"
                        reb_desc = f"인버스 헤지 비율({actual_hedge_ratio:.1f}%)이 65%를 넘었습니다. 초과분을 익절해 현금으로 확보하세요."
                    elif actual_hedge_ratio < 35.0:
                        reb_title = "🟠 [헤지 부족] 인버스 방어력 약화 ➔ 보충 검토"
                        reb_color = "#FF8F00"
                        reb_desc = f"인버스 헤지 비율({actual_hedge_ratio:.1f}%)이 35%에 미달합니다. S값 반등 구간에서 분할 보충을 검토하세요."
                    else:
                        reb_title = "🟢 [정상 균형] 롱-숏 헤지 안정 구간"
                        reb_color = "#2E7D32"
                        reb_desc = f"레버리지(233740) S값 <b>{lev_s_val}</b> 기준 롱-숏 비율이 안정 범위(35~65%) 내에 있습니다."

                st.markdown(f"""
                <div class="brief-card" style="border-left: 6px solid {reb_color};">
                    <div class="brief-title" style="color: {reb_color};">{reb_title}</div>
                    <div style="font-size:0.88rem; color:#222;">
                        • <b>기준 지표</b>: KODEX 코스닥150레버리지(233740) S값 = <code>{lev_s_val}</code> (현재 조회 종목 S값과 무관하게 233740 기준으로 고정 진단)<br>
                        • <b>포지션 현황</b>: 레버리지 {lev_val:,}원 | 인버스 {inv_val:,}원 (현재 헤지 비율: <b>{actual_hedge_ratio:.1f}%</b>)<br>
                        • <b>대응 지침</b>: {reb_desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("현재 KODEX 코스닥150레버리지(233740) 보유 수량이 0주입니다. 보유 수량 입력 시 롱-숏 헤지 비율 진단이 자동 활성화됩니다.")

            col_edit1, col_edit2 = st.columns(2)
            with col_edit1:
                with st.expander("📝 [체결 일지 입력 & 잔고 자동 연동 (신규 종목 자동 추가)]", expanded=False):
                    with st.form("trade_form_alpha"):
                        tf1, tf2 = st.columns(2)
                        with tf1:
                            log_date = st.date_input("체결 일자", datetime.today()).strftime("%Y-%m-%d")
                            log_stock_input = st.text_input("종목코드 또는 종목명", value=stock_code)
                            log_type = st.selectbox("구분", ["🔴 매수", "🔵 매도"])
                        with tf2:
                            log_price = st.number_input("체결 단가 (원)", min_value=1, value=int(curr_p), step=5)
                            log_qty = st.number_input("체결 수량 (주)", min_value=1, value=100, step=10)
                            auto_sync = st.checkbox("보유 종목 및 예수금에 즉시 반영", value=True)

                        submit_log = st.form_submit_button("➕ 체결 기록 저장", use_container_width=True)
                        if submit_log:
                            resolved_code, resolved_name = resolve_code_and_name(log_stock_input)
                            trade_amt = int(log_price * log_qty)
                            acc["trade_logs"].append({
                                "일자": log_date,
                                "종목코드": resolved_code,
                                "종목": resolved_name,
                                "구분": log_type,
                                "체결단가": int(log_price),
                                "체결수량": int(log_qty),
                                "체결금액": trade_amt
                            })
                            if auto_sync:
                                target_itm = next((x for x in acc["items"] if x.get("confirmed_code") == resolved_code), None)
                                if "매수" in log_type:
                                    if target_itm:
                                        old_q = int(target_itm.get("qty", 0))
                                        old_p = int(target_itm.get("avg_price", 0))
                                        new_tot_q = old_q + int(log_qty)
                                        target_itm["avg_price"] = int(round((old_q * old_p + trade_amt) / new_tot_q)) if new_tot_q > 0 else int(log_price)
                                        target_itm["qty"] = new_tot_q
                                        target_itm["confirmed_name"] = resolved_name
                                    else:
                                        next_id = max([int(x.get("id", 0)) for x in acc["items"]] + [0]) + 1
                                        acc["items"].append({
                                            "id": next_id,
                                            "input_val": resolved_code,
                                            "confirmed_code": resolved_code,
                                            "confirmed_name": resolved_name,
                                            "qty": int(log_qty),
                                            "avg_price": int(log_price)
                                        })
                                    acc["user_cash"] = max(0, int(acc.get("user_cash", new_cash)) - trade_amt)
                                else:
                                    if target_itm:
                                        target_itm["qty"] = max(0, int(target_itm.get("qty", 0)) - int(log_qty))
                                        if target_itm["qty"] == 0:
                                            target_itm["avg_price"] = 0
                                    acc["user_cash"] = int(acc.get("user_cash", new_cash)) + trade_amt
                            save_current_portfolio(acc)
                            st.success(f"✅ [{resolved_name} ({resolved_code})] 체결 내역 및 잔고 반영 완료!")
                            st.rerun()

            with col_edit2:
                with st.expander("🛠️ [보유 종목 수동 수정/삭제 & 데이터 백업]", expanded=False):
                    with st.form("manual_item_form"):
                        mi1, mi2, mi3 = st.columns(3)
                        with mi1:
                            man_code_in = st.text_input("종목코드/명", value=stock_code)
                        with mi2:
                            default_q = my_port_item["qty"] if my_port_item else 0
                            man_qty_in = st.number_input("보유수량 (0입력시 초기화)", min_value=0, value=int(default_q), step=10)
                        with mi3:
                            default_avg = my_port_item["avg_price"] if my_port_item else int(curr_p)
                            man_avg_in = st.number_input("매수평단가 (원)", min_value=0, value=int(default_avg), step=5)

                        if st.form_submit_button("🔄 보유 종목 정보 업데이트", use_container_width=True):
                            m_code, m_name = resolve_code_and_name(man_code_in)
                            existing = next((x for x in acc["items"] if x.get("confirmed_code") == m_code), None)
                            if existing:
                                existing["qty"] = int(man_qty_in)
                                existing["avg_price"] = int(man_avg_in) if int(man_qty_in) > 0 else 0
                                existing["confirmed_name"] = m_name
                            else:
                                next_id = max([int(x.get("id", 0)) for x in acc["items"]] + [0]) + 1
                                acc["items"].append({
                                    "id": next_id, "input_val": m_code,
                                    "confirmed_code": m_code, "confirmed_name": m_name,
                                    "qty": int(man_qty_in), "avg_price": int(man_avg_in)
                                })
                            save_current_portfolio(acc)
                            st.success(f"✅ [{m_name}] 보유 정보가 업데이트되었습니다.")
                            st.rerun()

                    b_col1, b_col2 = st.columns(2)
                    with b_col1:
                        json_bytes = json.dumps(acc, ensure_ascii=False, indent=2).encode("utf-8")
                        st.download_button(
                            "📥 포트폴리오 JSON 백업 다운로드",
                            data=json_bytes,
                            file_name=f"portfolio_backup_{datetime.today().strftime('%Y%m%d')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    with b_col2:
                        if st.button("🗑️ 체결 일지 전체 초기화", use_container_width=True):
                            acc["trade_logs"] = []
                            save_current_portfolio(acc)
                            st.rerun()

            if acc.get("trade_logs"):
                st.markdown("##### 🧾 최근 체결 일지")
                df_logs = pd.DataFrame(acc["trade_logs"]).iloc[::-1]
                st.dataframe(
                    df_logs.style.format({"체결단가": "{:,}원", "체결수량": "{:,}주", "체결금액": "{:,}원"}),
                    use_container_width=True,
                    height=220,
                    hide_index=True
                )

        # =========================================================
        # TAB 5: 마감 브리핑 & 심리 안정 마인드 컨트롤
        # =========================================================
        with tab5:
            st.markdown(f"#### 📢 [{s['date']}] {stock_name} ({stock_code}) 정밀 마감 브리핑 & 마인드 컨트롤")

            ma200_gap = ((curr_p / s["MA200"]) - 1.0) * 100.0 if s["MA200"] > 0 else 0.0
            ma20_gap = ((curr_p / s["MA20"]) - 1.0) * 100.0 if s["MA20"] > 0 else 0.0
            s_diff = current_s_val - s["prev_s"]
            reb_stats = compute_historical_rebound_stats(df_full_result, current_s_val, forward_days=30)

            my_qty_now = my_port_item["qty"] if my_port_item else 0
            my_avg_now = my_port_item["avg_price"] if my_port_item else 0
            my_ret_now = ((curr_p / my_avg_now) - 1.0) * 100.0 if (my_qty_now > 0 and my_avg_now > 0) else 0.0

            if current_s_val <= -40:
                mind_title = "🧘 [심리 안정 처방 — 과매도 공포 구간] 지금 느끼는 불안감은 파동 바닥권의 가장 정확한 역발상 신호입니다"
                mind_body = (
                    f"현재 S값은 <b>{current_s_val}</b>로, 대중의 투매와 공포가 극에 달하는 깊은 조정 구간입니다. "
                    f"하락장에서는 '끝없이 추락할 것 같은 공포(손실 회피 편향)' 때문에 바닥에서 손절하고 싶은 충동이 들기 쉽습니다. "
                    f"하지만 공격형 Alpha 전략은 바로 이 구간을 위해 1차(-25)를 관망하고 현금을 아껴두었습니다.<br><br>"
                    f"📊 <b>데이터가 증명하는 객관적 사실</b>: 과거 [{stock_name}]에서 S값이 <b>{reb_stats['threshold']} 이하</b>로 내려갔던 "
                    f"총 <b>{reb_stats['count']}회</b>의 국면 중, 이후 30영업일 이내에 의미 있는 반등(+3% 이상)에 성공한 비율은 "
                    f"<b>{reb_stats['win_prob']:.1f}%</b>였으며, 평균 최대 반등폭은 <b>+{reb_stats['avg_max_gain']:.1f}%</b>(중앙값 +{reb_stats['median_gain']:.1f}%)에 달했습니다. "
                    f"감정을 내려놓고 정해진 지정가 분할 비중(3차 25%, 4차 40%)만 차분히 집행하세요."
                )
            elif current_s_val <= -25:
                mind_title = "🧘 [심리 안정 처방 — 조정 진행 구간] 조급한 물타기를 멈추고 가격이 내 타점으로 걸어오게 하세요"
                mind_body = (
                    f"현재 S값은 <b>{current_s_val}</b>로 조정이 진행 중입니다. 이 구간에서 가장 흔한 실수는 "
                    f"'조금만 내렸는데도 불안해서 섣불리 추격 매수하거나 예정보다 큰 비중을 한꺼번에 투입하는 것'입니다.<br><br>"
                    f"📊 <b>데이터가 증명하는 객관적 사실</b>: 과거 S값 <b>{reb_stats['threshold']} 이하</b> 진입 후 30영업일 내 평균 최대 반등폭은 "
                    f"<b>+{reb_stats['avg_max_gain']:.1f}%</b>(반등 성공률 <b>{reb_stats['win_prob']:.1f}%</b>)입니다. "
                    f"우리는 이미 2차(<b>{tp2:,}원</b>), 3차(<b>{tp3:,}원</b>), 4차(<b>{tp4:,}원</b>)라는 명확한 그물을 쳐 두었습니다. "
                    f"주가가 그물에 닿기 전까지는 현금이 곧 가장 강력한 무기입니다."
                )
            elif current_s_val >= 0:
                mind_title = "🧘 [심리 안정 처방 — 파동 목표 달성 구간] 환희와 욕심을 경계하고 수익을 내 계좌의 현금으로 확정할 때입니다"
                mind_body = (
                    f"현재 S값은 <b>{current_s_val}</b>로 파동 에너지가 100% 이상 채워진 과열·목표 달성권입니다. "
                    f"상승장에서는 '더 오를 텐데 팔면 아깝다(FOMO)'는 욕심이 수익 확정을 방해합니다.<br><br>"
                    f"💡 <b>마인드 컨트롤 핵심</b>: 2차 집중익절(35%)로 원금과 확정 수익을 금고에 넣어두어야, "
                    f"남은 45% 물량을 고점 대비 -4.5% 트레일링 스탑까지 흔들림 없이 끝까지 끌고 갈 수 있습니다. "
                    f"일부 익절은 상승을 포기하는 것이 아니라, 대세 상승을 끝까지 누리기 위한 '심리적 안전벨트'입니다."
                )
            else:
                mind_title = "🧘 [심리 안정 처방 — 중립/대기 구간] 아무것도 하지 않는 것도 고수의 핵심 매매 기술입니다"
                mind_body = (
                    f"현재 S값은 <b>{current_s_val}</b>(전일 대비 {s_diff:+d})로 매수 타점(S ≤ -32)과 익절 타점(S ≥ -5) 사이의 중립 지대입니다. "
                    f"장중 호가창을 계속 바라보면 불필요한 매매 충동(뇌동매매)이 생기기 쉽습니다.<br><br>"
                    f"💡 <b>마인드 컨트롤 핵심</b>: 프로 트레이더와 개인 투자자의 차이는 '자신의 타점이 아닐 때 매매를 참아내는 인내심'에서 갈립니다. "
                    f"오늘 장은 마감되었습니다. 예약 지정가 주문만 점검해 두고 편안한 저녁 시간을 보내세요."
                )

            st.markdown(f"""
            <div class="mindset-card">
                <div style="font-size:1.02rem; font-weight:800; color:#1E40AF; margin-bottom:8px;">{mind_title}</div>
                <div style="font-size:0.90rem; color:#1E293B; line-height:1.6;">{mind_body}</div>
            </div>
            """, unsafe_allow_html=True)

            b_left, b_right = st.columns(2)
            with b_left:
                st.markdown(f"""
                <div class="brief-card">
                    <div class="brief-title">📊 1. 금일 종가 & 파동 위치 정밀 진단</div>
                    <div style="font-size:0.88rem; color:#222; line-height:1.65;">
                        • <b>금일 종가 / 등락률</b>: <b>{curr_p:,}원</b> ({s['cur_chg']:+.2f}%) | 시가: {s['Open']:,}원<br>
                        • <b>거래량 / 거래비율(G)</b>: {s['C1']:,}주 (전일 대비 <b>{s['vol_ratio']:.2f}배</b>)<br>
                        • <b>파동 추세 / S값 변화</b>: <b>{s['state']}</b> | 전일 S(<code>{s['prev_s']}</code>) ➔ 금일 S(<code>{current_s_val}</code>, <b>{s_diff:+d}</b>)<br>
                        • <b>이동평균선 이격도</b>: 20일선({s['MA20']:,}원, <b>{ma20_gap:+.2f}%</b>) | 200일선({s['MA200']:,}원, <b>{ma200_gap:+.2f}%</b>)<br>
                        • <b>기준 파동 밴드</b>: 직전 확정고점 <b>{max_mn_val:,}원</b> (PM {s['PM']}%) ~ 확정저점 <b>{min_pq_val:,}원</b> (LM {s['LM']}%)<br>
                        • <b>내 보유 포지션 진단</b>: {f"{my_qty_now:,}주 보유 (평단 {my_avg_now:,}원 / 수익률 <b>{my_ret_now:+.2f}%</b>)" if my_qty_now > 0 else "현재 보유 물량 없음 (현금 대기 중)"}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with b_right:
                s_m5_price = target_prices_dict.get(-5, 0)
                s_0_price = target_prices_dict.get(0, 0)
                st.markdown(f"""
                <div class="brief-card">
                    <div class="brief-title" style="color:#1565C0;">🧭 2. 핵심 지지선(매수 타점) & 저항선(익절 타점) 매트릭스</div>
                    <div style="font-size:0.88rem; color:#222; line-height:1.65;">
                        • 🔵 <b>2차 집중익절 저항선 (S = 0)</b>: <b>{s_0_price:,}원</b> (현재가 대비 <b>{((s_0_price/curr_p - 1)*100):+.2f}%</b>)<br>
                        • 🟢 <b>1차 선제익절 저항선 (S = -5)</b>: <b>{s_m5_price:,}원</b> (현재가 대비 <b>{((s_m5_price/curr_p - 1)*100):+.2f}%</b>)<br>
                        • ⚪ <b>1차 탐색 지지선 (S = -25)</b>: <b>{tp1:,}원</b> (현재가 대비 <b>{((tp1/curr_p - 1)*100):+.2f}%</b> — 관망)<br>
                        • 🔴 <b>2차 진입 지지선 (S = -32)</b>: <b>{tp2:,}원</b> (현재가 대비 <b>{((tp2/curr_p - 1)*100):+.2f}%</b> — 5% 진입)<br>
                        • 🔴 <b>3차 주력 지지선 (S = -40)</b>: <b>{tp3:,}원</b> (현재가 대비 <b>{((tp3/curr_p - 1)*100):+.2f}%</b> — 25% 진입)<br>
                        • 🟣 <b>4차 승부수 지지선 (S = -55)</b>: <b>{tp4:,}원</b> (현재가 대비 <b>{((tp4/curr_p - 1)*100):+.2f}%</b> — 40% 투입)
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("##### 🗺️ 3. 내일 장 시나리오별 기계적 대응 프로토콜 (장중 감정 배제용 If-Then 가이드)")
            sc1, sc2, sc3 = st.columns(3)

            qty_2nd = int((acc_principal * 0.05) // tp2) if tp2 > 0 else 0
            qty_3rd = int((acc_principal * 0.25) // tp3) if tp3 > 0 else 0
            qty_4th = int((acc_principal * 0.40) // tp4) if tp4 > 0 else 0
            sell_1st_q = int(round(my_qty_now * 0.20)) if my_qty_now > 0 else 0
            sell_2nd_q = int(round(my_qty_now * 0.35)) if my_qty_now > 0 else 0

            with sc1:
                st.markdown(f"""
                <div class="scenario-box" style="border-top: 4px solid #D32F2F;">
                    <div style="font-weight:800; color:#D32F2F; margin-bottom:6px;">📈 시나리오 A: 내일 상승 / 반등 시</div>
                    <div style="font-size:0.85rem; color:#333; line-height:1.55;">
                        • <b>추격 매수 절대 금지</b>: 양봉에 따라붙지 않습니다.<br>
                        • <b>1차 익절 대기</b>: 주가가 <b>{s_m5_price:,}원(S=-5)</b> 이상 도달 시 보유 물량의 20%(<b>{sell_1st_q:,}주</b>) 지정가 매도.<br>
                        • <b>2차 익절 대기</b>: 주가가 <b>{s_0_price:,}원(S=0)</b> 돌파 시 35%(<b>{sell_2nd_q:,}주</b>) 추가 익절 후 잔여 물량 홀딩.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with sc2:
                st.markdown(f"""
                <div class="scenario-box" style="border-top: 4px solid #2E7D32;">
                    <div style="font-weight:800; color:#2E7D32; margin-bottom:6px;">⚖️ 시나리오 B: 내일 보합 / 횡보 시</div>
                    <div style="font-size:0.85rem; color:#333; line-height:1.55;">
                        • <b>기존 포지션 유지</b>: S값 변화가 크지 않은 잔파동 구간에서는 매매 버튼을 누르지 않습니다.<br>
                        • <b>시간을 내 편으로</b>: 지정가 알림만 설정해 두고 호가창 관찰 시간을 줄여 심리적 피로도를 낮춥니다.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with sc3:
                st.markdown(f"""
                <div class="scenario-box" style="border-top: 4px solid #1565C0;">
                    <div style="font-weight:800; color:#1565C0; margin-bottom:6px;">📉 시나리오 C: 내일 하락 / 조정 시</div>
                    <div style="font-size:0.85rem; color:#333; line-height:1.55;">
                        • <b>공포 투매 금지</b>: 하락은 손실이 아니라 '더 싸게 주식을 모으는 할인 구간'입니다.<br>
                        • <b>지정가 그물망 가동</b>:<br>
                        &nbsp;&nbsp;- 2차(S≤-32): <b>{tp2:,}원</b>에 <b>{qty_2nd:,}주</b>(5%)<br>
                        &nbsp;&nbsp;- 3차(S≤-40): <b>{tp3:,}원</b>에 <b>{qty_3rd:,}주</b>(25%)<br>
                        &nbsp;&nbsp;- 4차(S≤-55): <b>{tp4:,}원</b>에 <b>{qty_4th:,}주</b>(40%) 예약 주문.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
            with st.expander("📋 [메모장/카톡 보관용] 오늘의 마감 브리핑 & 내일 주문표 텍스트 복사하기", expanded=False):
                summary_text = (
                    f"[{s['date']} {stock_name}({stock_code}) 마감 브리핑]\n"
                    f"1. 현재가: {curr_p:,}원 ({s['cur_chg']:+.2f}%) | 거래비율(G): {s['vol_ratio']:.2f}배\n"
                    f"2. 파동지표: 추세={s['state']} | MM={s['MM']}% | PM={s['PM']}% | LM={s['LM']}% | RM={s['RM']}% | S값={current_s_val} (전일 {s['prev_s']})\n"
                    f"3. 현재신호: {cur_sig} (200일선: {s['MA200']:,}원, 이격 {ma200_gap:+.2f}%)\n"
                    f"4. 매수 지정가 타점: 1차(관망) {tp1:,}원 / 2차(5%) {tp2:,}원 / 3차(25%) {tp3:,}원 / 4차(40%) {tp4:,}원\n"
                    f"5. 익절 목표 타점: 1차(S=-5, 20%) {s_m5_price:,}원 / 2차(S=0, 35%) {s_0_price:,}원\n"
                    f"6. 과거 통계: S≤{reb_stats['threshold']} 진입 후 30영업일 내 반등 성공률 {reb_stats['win_prob']:.1f}% (평균 최대반등 +{reb_stats['avg_max_gain']:.1f}%)\n"
                    f"7. 오늘의 다짐: 예측하지 말고 파동 에너지(S값)와 정해진 비중 원칙만 기계적으로 집행한다."
                )
                st.code(summary_text, language="text")
    else:
        st.error("데이터를 불러올 수 없습니다. 종목코드 또는 네트워크 상태를 확인해 주세요.")
