import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime, timedelta
from io import BytesIO
from xml.etree import ElementTree as ET
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="매매 시스템 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 모바일 가독성 및 카드 스타일 최적화 CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.82rem; }
    
    div[data-testid="stDataFrame"] { width: 100%; }
    table, th, td { 
        font-size: 0.80rem !important; 
        padding: 2px 3px !important; 
        text-align: center !important; 
        line-height: 1.2 !important;
    }
    .brief-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 13px 15px;
        margin-bottom: 11px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .brief-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1565C0;
        margin-bottom: 8px;
        border-bottom: 1px solid #EEEEEE;
        padding-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 매매 시스템")

# 포트폴리오 & 계좌 정보 영구 저장 파일명
PORTFOLIO_FILE = "portfolio_data.json"

def load_saved_portfolio():
    default_data = {
        "user_principal": 30000000,
        "user_cash": 10000000,
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
                    return data
                elif isinstance(data, list):
                    default_data["items"] = data
                    return default_data
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

# 세션 초기화 시 영구 데이터 로드
if 'account_data' not in st.session_state:
    st.session_state.account_data = load_saved_portfolio()

# 네이버 금융 일별 시세 크롤링 함수
@st.cache_data(ttl=300)
def get_naver_stock_data(code, count=1500):
    clean_code = str(code).strip()
    if not clean_code:
        clean_code = "233740"
        
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={clean_code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
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

# 주요 종목 빠른 매핑 사전
name_to_code = {
    "코스피지수": "KOSPI",
    "코스닥지수": "KOSDAQ",
    "삼성전자": "005930",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
    "KODEX 코스닥150선물인버스": "251340",
    "코스닥150선물인버스": "251340",
    "KODEX 200": "069500",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "현대차": "005380",
    "피엔티": "137400"
}

code_to_name = {
    "KOSPI": "코스피지수",
    "KOSDAQ": "코스닥지수",
    "005930": "삼성전자",
    "233740": "KODEX 코스닥150레버리지",
    "251340": "KODEX 코스닥150선물인버스",
    "069500": "KODEX 200",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "137400": "피엔티"
}

def resolve_code_and_name(user_str):
    clean_str = str(user_str).strip()
    if not clean_str:
        return "233740", "KODEX 코스닥150레버리지"
    
    if clean_str in name_to_code:
        return name_to_code[clean_str], clean_str
    elif clean_str.isdigit():
        code = clean_str.zfill(6)
        name = code_to_name.get(code, f"종목({code})")
        return code, name
    else:
        for k, v in name_to_code.items():
            if clean_str.lower() in k.lower():
                return v, k
        return clean_str, clean_str

# 상단 메인 검색 Form
with st.form(key="search_form"):
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        user_input = st.text_input(
            "🔍 조회할 메인 종목 또는 종목코드 입력",
            value="233740",
            placeholder="예: 삼성전자, 233740"
        ).strip()
    with col_in2:
        years_back = st.selectbox("표시 기간 (엑셀 기본: 2년 고정)", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
    with col_in3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submit_search = st.form_submit_button("🔍 조회하기", use_container_width=True)

stock_code, stock_name = resolve_code_and_name(user_input)

def r10(val):
    return int(np.floor(val / 10.0 + 0.5) * 10)

def trunc_int(val):
    return int(np.trunc(val))

# 웹 표 스타일러 함수
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
                if '강력진입구간' in val_str:
                    styles[idx] = f'{base_style} background-color: #7B1FA2; color: #FFFFFF; font-weight: 900;'
                elif '진입구간' in val_str:
                    styles[idx] = f'{base_style} background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '신호' in val_str:
                    styles[idx] = f'{base_style} background-color: #FF8F00; color: #FFFFFF; font-weight: 900;'
                elif val_str == '매도 추천':
                    styles[idx] = f'{base_style} background-color: #1976D2; color: #FFFFFF; font-weight: 900;'
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

# 엑셀 원본 수식 계산 함수
def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    closes = pd.to_numeric(df['Close'], errors='coerce').ffill().values
    vols = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).values
    opens = pd.to_numeric(df['Open'], errors='coerce').ffill().values
    highs = pd.to_numeric(df['High'], errors='coerce').ffill().values
    lows = pd.to_numeric(df['Low'], errors='coerce').ffill().values
    dates = pd.to_datetime(df['Date']).values
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

        if s_val >= -15 and active_low > 0:
            sig = "매도 추천" if s_val >= 0 else "관망"
        else:
            if s_val <= -55:
                sig = "4차 강력진입구간"
            elif s_val <= -40:
                sig = "3차 진입구간"
            elif s_val <= -32:
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

# 원본 엑셀 PPP 시트 생성 함수
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
    fill_sig_blue = PatternFill(start_color="1976D2", end_color="1976D2", fill_type="solid")
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
        'A11': "일자", 'B11': "종가(B)", 'C11': "등락률(C)", 'D11': "매수신호",
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

        if "강력진입구간" in sig_val:
            c_d.fill = fill_sig_purple
            c_d.font = font_white_bold
        elif "진입구간" in sig_val:
            c_d.fill = fill_sig_red
            c_d.font = font_white_bold
        elif "신호" in sig_val:
            c_d.fill = fill_sig_orange
            c_d.font = font_white_bold
        elif sig_val == "매도 추천":
            c_d.fill = fill_sig_blue
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
        'A': 12, 'B': 10, 'C': 10, 'D': 16, 'E': 3, 'F': 14, 'G': 9,
        'H': 7, 'I': 7, 'J': 7, 'K': 8, 'L': 7,
        'M': 10, 'N': 10, 'O': 10, 'P': 3, 'Q': 10, 'R': 10, 'S': 10
    }
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width

    out = BytesIO()
    wb.save(out)
    return out.getvalue()

# 코스피 및 코스닥 지수 데이터 실시간 조회
kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)

kospi_val = int(kospi_df['Close'].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df['Close'].iloc[-1] / kospi_df['Close'].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0

kosdaq_val = int(kosdaq_df['Close'].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df['Close'].iloc[-1] / kosdaq_df['Close'].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    with st.spinner(f"[{stock_name} ({stock_code})] 핵심 지표 및 종합 마감 브리핑을 준비 중입니다..."):
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
        
        four_stages_info = [
            (-25, "1차 신호(5%)"), (-32, "2차 진입(10%)"), (-40, "3차 진입(25%)"), (-55, "4차 강력진입(30%)")
        ]
        
        target_prices_dict = {}
        target_prices_4step = []
        if max_mn_val > 0 and min_pq_val > 0:
            for s_tgt, name in four_stages_info:
                tp = r10(max_mn_val + (s_tgt * min_pq_val) / 100.0)
                target_prices_dict[s_tgt] = tp
                target_prices_4step.append(f"<b>{name}</b>: <span style='color:#D32F2F;'>{tp:,}원</span> (S≤{s_tgt})")

        # 상단 실전 액션 가이드 브리핑
        if "강력진입구간" in cur_sig:
            action_title = f"🟣 [{cur_sig}] ➔ 4차 승부수 구간 도달!"
            action_desc = "S ≤ -55 1차 바닥권 도달! 4차 기본 비중(30%)을 집행합니다."
            action_item = "💡 **[1안 행동 수칙]**: 4차 비중(30%) 집행 완료 후, 남은 **예비 현금 30%는 반드시 계좌에 홀딩**하세요!"
            badge_color = "#7B1FA2"
        elif "진입구간" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 분할 매수 진행 구간!"
            action_desc = "하락이 진행되어 정해진 비중을 차분하게 모아가는 구간입니다."
            action_item = "💡 **[1안 행동 수칙]**: 단계별 목표가 이하에서만 정해진 비중(2차 10%, 3차 25%)만큼 매수 체결 대기"
            badge_color = "#D32F2F"
        elif "신호" in cur_sig:
            action_title = f"🟠 [{cur_sig}] ➔ 하락 초입 탐색 신호!"
            action_desc = "본격 진입 전 첫 신호 포착 구간입니다."
            action_item = "💡 **[1안 행동 수칙]**: 1차 탐색 소액(5%)만 체결하거나, 이미 물량이 있다면 추가 매수 없이 관망"
            badge_color = "#FF8F00"
        elif cur_sig == "매도 추천":
            action_title = f"🔵 [{cur_sig}] ➔ 지표 회복! 수익 실현 검토"
            action_desc = "S값이 안전지대로 회복되었습니다."
            action_item = "💡 **[1안 행동 수칙]**: 평단가 위 익절 타이밍 포착 시 미련 없이 현금화하여 다음 농사 탄약 확보"
            badge_color = "#1976D2"
        else:
            action_title = "🟢 [관망] ➔ 안전 구간"
            action_desc = "현금 비중을 유지하며 기회를 기다리는 안전 지대입니다."
            action_item = "💡 **[1안 행동 수칙]**: 불필요한 매수 금지! 다음 파동 신호가 올 때까지 예수금을 안전하게 지키세요."
            badge_color = "#2E7D32"

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 6px solid {badge_color}; padding: 14px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin: 0; color: {badge_color}; font-size: 1.1rem;">{action_title}</h3>
            <p style="margin: 6px 0 4px 0; color: #222222; font-size: 0.9rem;">
                <b>현재 핵심 지표 — MM: <code>{s['MM']}</code> | PM: <code>{s['PM']}%</code> | LM: <code>{s['LM']}%</code> | S값: <code>{current_s_val}</code> ({s['state']})</b>
            </p>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 8px 10px; border-radius: 6px; margin-top: 8px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 3M 요약", f"S: {s['S']}", f"MM:{s['MM']} / PM:{s['PM']} / LM:{s['LM']}")
        c3.metric("코스피 지수", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 지수", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        # 탭 5개 구성
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 매수·매도 표 (전체)", 
            "📢 마감 브리핑", 
            "🎯 1안 실전 가이드 & 계산기", 
            "💼 보유 포트폴리오 & 거래 일지", 
            "💾 엑셀 다운로드"
        ])

        # -----------------------------
        # TAB 1: 매수·매도 표 (전체)
        # -----------------------------
        with tab1:
            st.caption("📈 엑셀 원본(PPP 시트)과 100% 일치하며 여백 없이 칸에 딱 맞게 정렬된 밀착형 표입니다.")
            df_rev = df_display.iloc[::-1]

            col_configs = {
                "일자": st.column_config.TextColumn("일자", width=86),
                "종가(B)": st.column_config.TextColumn("종가", width=68),
                "등락률(C)": st.column_config.TextColumn("등락률", width=62),
                "매수신호": st.column_config.TextColumn("매수신호", width=105),
                "거래량(F)": st.column_config.TextColumn("거래량", width=98),
                "거래비율(G)": st.column_config.TextColumn("비율", width=55),
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
        # TAB 2: 마감 브리핑 전용 탭
        # -----------------------------
        with tab2:
            st.markdown(f"#### 📢 [{s['date']}] {stock_name} 장 마감 종합 브리핑")

            # 1. 전체 시장 종합 프리핑
            if kosdaq_chg <= -1.5:
                mkt_stage = "🚨 [지수 급락 / 공포 심리 고조]"
                mkt_color = "#D32F2F"
                mkt_eval = "외국인·기관의 현물 매도세가 집중되며 지수가 하방 지지선을 테스트하는 장세입니다. 레버리지 종목은 변동성이 2배로 확대되므로 신규 추격매수는 절대 금물이며 방어선 가격만 지켜봐야 합니다."
            elif kosdaq_chg < 0:
                mkt_stage = "📉 [지수 약세 조정 / 숨고르기]"
                mkt_color = "#1976D2"
                mkt_eval = "대형주 중심의 차익 매물 출회로 코스닥 시장 전반이 조정을 받았습니다. 투매성 패닉은 아니며 파동상 하방 지지력과 거래량 변화를 탐색하는 구간입니다."
            elif kosdaq_chg >= 1.5:
                mkt_stage = "🔥 [지수 급반등 / 위험선호 회복]"
                mkt_color = "#C2185B"
                mkt_eval = "쇼트커버링과 저가 매수세가 유입되며 지수가 강하게 튀어 오른 장세입니다. 기존 저점 매수 물량의 반등 폭을 점검하고 익절 목표가 도달 여부를 주시하세요."
            else:
                mkt_stage = "⚖️ [지수 보합권 / 눈치보기 횡보]"
                mkt_color = "#333333"
                mkt_eval = "뚜렷한 주도 수급 없이 지수가 제한된 밴드 내에서 등락을 거듭했습니다. 파동의 방향성이 확정되기 전까지는 관망을 유지하는 것이 유리합니다."

            st.markdown(f"""
            <div class="brief-card" style="border-left: 5px solid {mkt_color};">
                <div class="brief-title" style="color: {mkt_color};">1. 전체 시장 종합 프리핑 (정밀 분석)</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>지수 현황</b>: 코스피 <b>{kospi_val:,}p</b> ({kospi_chg:+.2f}%) | 코스닥 <b>{kosdaq_val:,}p</b> ({kosdaq_chg:+.2f}%)<br>
                    • <b>시장 국면 판정</b>: <span style="font-weight:bold; color:{mkt_color};">{mkt_stage}</span><br>
                    • <b>시장 상세 진단</b>: {mkt_eval}<br>
                    • <b>종목 상대 강도</b>: 오늘 {stock_name} 등락률({s['cur_chg']:+.2f}%)은 코스닥 지수({kosdaq_chg:+.2f}%) 대비 
                      {'상대적 강세' if s['cur_chg'] > kosdaq_chg else '지수 추종 약세'}를 기록했습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 2. 당일 캔들 형태 & 꼬리 분석
            o_p, h_p, l_p, c_p = s['Open'], s['High'], s['Low'], s['B1']
            body_size = abs(c_p - o_p)
            candle_range = max(1, h_p - l_p)
            lower_shadow = min(o_p, c_p) - l_p

            if lower_shadow / candle_range >= 0.45 and (lower_shadow >= body_size * 1.5):
                candle_type = "🔨 [아래꼬리 망치형 / 저가 매수세 유입]"
                candle_color = "#D32F2F"
                candle_desc = "장중 급락 투매를 저가에서 강하게 받아내며 아래꼬리를 길게 달았습니다. <b>단기 바닥 지지력이 확인되는 반등 긍정 시그널</b>입니다."
            elif c_p < o_p and (body_size / candle_range >= 0.65):
                candle_type = "📉 [장대음봉 / 매도세 우위]"
                candle_color = "#1976D2"
                candle_desc = "시가 이후 장 마감까지 매도세가 지속되었습니다. 아직 하방 압력이 남아있으므로 <b>익일 추가 방어선 도달 여부를 차분히 대기</b>해야 합니다."
            elif body_size / candle_range <= 0.2:
                candle_type = "⚖️ [도지(팽이형) / 매수·매도 팽팽한 균형]"
                candle_color = "#333333"
                candle_desc = "시가와 종가가 거의 일치하며 방향성 탐색 국면입니다. <b>하락세가 진정되며 숨고르기</b>에 들어간 형태입니다."
            elif c_p > o_p:
                candle_type = "📈 [양봉 반등 / 매수 우위]"
                candle_color = "#D32F2F"
                candle_desc = "시가 대비 종가를 끌어올리며 양봉으로 마감했습니다. <b>단기 기술적 반등 흐름이 유효</b>합니다."
            else:
                candle_type = "단기 조정 캔들"
                candle_color = "#555555"
                candle_desc = "통상적인 박스권 잔파동 내에서 등락을 보였습니다."

            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">2. 🕯️ 당일 캔들 형태 & 꼬리 분석</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>당일 시세</b>: 시가 {o_p:,}원 | 고가 {h_p:,}원 | 저가 {l_p:,}원 | <b>종가 {c_p:,}원</b><br>
                    • <b>캔들 판정</b>: <span style="font-weight:bold; color:{candle_color};">{candle_type}</span><br>
                    • <b>실전 해석</b>: {candle_desc}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 3. 거래량 시그널 & 바닥 경보
            vol_ratio_val = s['vol_ratio']
            if vol_ratio_val >= 1.5:
                vol_badge = "🚨 [공포 투매 / 대량 손바뀜 발생]"
                vol_color = "#D32F2F"
                vol_desc = "거래량이 전일 대비 1.5배 이상 폭증했습니다. 패닉 셀링과 저가 매수세의 격돌로 <b>진바닥 형성 가능성이 매우 높은 시그널</b>입니다."
            elif vol_ratio_val <= 0.7:
                vol_badge = "💤 [거래량 소강 / 바닥 다지기]"
                vol_color = "#1976D2"
                vol_desc = "매도세가 진정되며 거래량이 말라붙었습니다. 급격한 추가 폭락보다는 <b>지지선을 확인하며 횡보 바닥을 다지는 구간</b>입니다."
            else:
                vol_badge = "⚖️ [평균 수준 거래량 유지]"
                vol_color = "#333333"
                vol_desc = "전일과 유사한 수준의 거래량을 유지하며 기존 파동 흐름을 이어가고 있습니다."

            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">3. ⚡ 거래량 시그널 & 바닥 경보</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>오늘 거래량</b>: {s['C1']:,}주 (전일 대비 <b>{vol_ratio_val:.2f}배</b>)<br>
                    • <b>진단 결과</b>: <span style="color:{vol_color}; font-weight:bold;">{vol_badge}</span><br>
                    • <b>해석</b>: {vol_desc}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 4. 다음 목표가까지 남은 거리
            curr_p = s['B1']
            tp_3 = target_prices_dict.get(-40, 0)
            tp_4 = target_prices_dict.get(-55, 0)
            diff_3 = tp_3 - curr_p if tp_3 > 0 else 0
            diff_3_pct = (diff_3 / curr_p) * 100.0 if curr_p > 0 else 0.0
            diff_4 = tp_4 - curr_p if tp_4 > 0 else 0
            diff_4_pct = (diff_4 / curr_p) * 100.0 if curr_p > 0 else 0.0

            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">4. 🎯 다음 목표가까지 남은 거리 (D-Day 카운트다운)</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>다음 3차 진입가 ({tp_3:,}원 / 예비 10%)까지</b>: 
                      <span style="color:{'#D32F2F' if diff_3 < 0 else '#2E7D32'}; font-weight:bold;">
                        {diff_3:+d}원 ({diff_3_pct:+.2f}%)
                      </span> 남음 ➔ <i>{f'내일 {abs(diff_3_pct):.1f}% 추가 하락 시 1차 방어선 체결 시작' if diff_3 < 0 else '현재 3차 도달 구간 이하 위치'}</i><br>
                    • <b>최후 4차 진입가 ({tp_4:,}원 / 예비 20%)까지</b>: 
                      <span style="color:{'#D32F2F' if diff_4 < 0 else '#2E7D32'}; font-weight:bold;">
                        {diff_4:+d}원 ({diff_4_pct:+.2f}%)
                      </span> 남음 ➔ <i>{f'내일 {abs(diff_4_pct):.1f}% 추가 하락 시 최후 승부수 체결 시작' if diff_4 < 0 else '최후 바닥선 도달 상태'}</i>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 5. 최근 5영업일 핵심 지표 궤적 추적
            recent_5 = df_full_result.tail(5).copy()
            s_traj_html = " ➔ ".join([f"<b>{row['일자'][5:]}</b> (S: <code>{row['S']}</code>)" for _, row in recent_5.iterrows()])
            s_diff_5 = recent_5['S'].iloc[-1] - recent_5['S'].iloc[0]
            
            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">5. 📉 최근 5영업일 핵심 지표(S값) 궤적 추적</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>5일간 S값 추이</b>: {s_traj_html}<br>
                    • <b>추세 진단</b>: 최근 5일간 S값이 <b>{s_diff_5:+d} 포인트</b> 변동했습니다. 
                      {'하락 폭이 둔화되며 바닥 수렴 국면에 진입하고 있습니다.' if abs(s_diff_5) <= 5 else '지표의 변동성이 확대되고 있으므로 단계별 지정가만 체결 대기하세요.'}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 6. 내 계좌 실전 탈출 시뮬레이터
            my_port_item = None
            if 'items' in st.session_state.account_data:
                for itm in st.session_state.account_data['items']:
                    if itm.get('confirmed_code') == stock_code and itm.get('qty', 0) > 0:
                        my_port_item = itm
                        break

            if my_port_item:
                curr_my_qty = my_port_item['qty']
                curr_my_price = my_port_item['avg_price']
                curr_eval_pct = ((curr_p / curr_my_price) - 1.0) * 100 if curr_my_price > 0 else 0
                
                add_budget_3 = 3000000
                add_qty_3 = int(add_budget_3 / tp_3) if tp_3 > 0 else 0
                sim_price_3 = int((curr_my_qty * curr_my_price + add_qty_3 * tp_3) / (curr_my_qty + add_qty_3)) if (curr_my_qty + add_qty_3) > 0 else curr_my_price
                price_drop_3 = curr_my_price - sim_price_3

                st.markdown(f"""
                <div class="brief-card" style="border-left: 5px solid #6A1B9A;">
                    <div class="brief-title" style="color: #6A1B9A;">6. 🧮 내 계좌 실전 탈출 시뮬레이터 (보유 포트폴리오 연동)</div>
                    <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                        • <b>현재 내 포지션</b>: 보유 수량 <b>{curr_my_qty:,}주</b> | 평단가 <b>{curr_my_price:,}원</b> (현재 평가손익: <span style="color:{'#D32F2F' if curr_eval_pct > 0 else '#1976D2'}; font-weight:bold;">{curr_eval_pct:+.2f}%</span>)<br>
                        • <b>만약 내일 3차 방어선({tp_3:,}원, 10%) 추가 체결 시:</b><br>
                          ➔ 내 예상 평단가는 <span style="text-decoration:line-through; color:#777;">{curr_my_price:,}원</span> ➔ 
                          <span style="color:#D32F2F; font-size:1.0rem; font-weight:bold;">{sim_price_3:,}원</span>으로 <b>{price_drop_3:,}원 즉시 인하!</b><br>
                        • <b>실전 코멘트</b>: 방어선 집행 시 평단가가 대폭 낮아져 기술적 반등 시 원금 회복 및 익절 탈출이 훨씬 수월해집니다.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="brief-card">
                    <div class="brief-title">6. 🧮 내 계좌 실전 탈출 시뮬레이터</div>
                    <div style="font-size:0.86rem; color:#555;">
                        • <i>[💼 보유 포트폴리오] 탭에 <b>{stock_name}</b>의 수량과 평단가를 입력해 두시면, 방어선 추가 매수 시 내 평단가가 얼마나 낮아지는지 자동 시뮬레이션됩니다.</i>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 7. 신형 네이버 증권 링크
            st.markdown(f"""
            <div class="brief-card" style="border-left: 5px solid #00897B;">
                <div class="brief-title" style="color: #00897B;">7. 🔗 {stock_name} 상세 정보 원클릭 바로가기</div>
                <div style="font-size:0.86rem; color:#444; margin-bottom: 8px;">
                    네이버페이 증권 공식 화면으로 즉시 연결되어 최신 공시, 뉴스 및 투자자별 매매동향을 정확히 확인할 수 있습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_link1, col_link2 = st.columns(2)
            with col_link1:
                st.link_button(
                    f"📋 {stock_name} 공시·뉴스 보러가기", 
                    f"https://stock.naver.com/domestic/stock/{stock_code}/news",
                    use_container_width=True
                )
            with col_link2:
                st.link_button(
                    f"👥 {stock_name} 매매동향(수급) 보러가기", 
                    f"https://stock.naver.com/domestic/stock/{stock_code}/trend",
                    use_container_width=True
                )

            # 8. 내일 장 시작 전 3대 체크포인트
            st.markdown(f"""
            <div class="brief-card" style="border-left: 5px solid #D32F2F; background-color: #FFF8E1; margin-top: 12px;">
                <div class="brief-title" style="color: #D32F2F;">8. 🧭 내일 장 시작 전 3대 체크포인트 (내일 08:50 행동 요강)</div>
                <div style="font-size:0.88rem; color:#111; line-height:1.7;">
                    <b>1️⃣ 지정가 예약 주문 세팅:</b><br>
                    • 3차 목표가: <span style="color:#D32F2F; font-weight:bold;">{tp_3:,}원 이하</span>에만 1차 방어선(10%) 예약 매수 걸기<br>
                    <b>2️⃣ 개장 시가 갭(Gap) 체크:</b><br>
                    • 시초가가 갭하락으로 출발해도 장 시작 10분간은 시장가 추격 매수를 일절 금지하고 호가 안정 확인<br>
                    <b>3️⃣ 절대 현금 사수 원칙:</b><br>
                    • 주가가 {tp_3:,}원 위에서 잔파동을 보일 때는 <b>예비 현금 30%를 계좌에 100% 사수하며 관망(홀딩) 유지!</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # -----------------------------
        # TAB 3: 1안 실전 가이드 & 계산기
        # -----------------------------
        with tab3:
            st.markdown("##### 🎯 [1안. 정석 분할 방어형: 기본 70% + 예비 방어 30% 플랜]")
            total_seed = st.number_input("💰 총 투자 예정 금액 (원)", min_value=100000, max_value=10000000000, value=30000000, step=1000000, format="%d")

            st.markdown("###### 🔹 1단계: 기본 4단계 분할 매수 (총 70% 집행)")
            base_plan = [
                {"단계": "🟠 1차 신호", "조건": "S ≤ -25", "비중": 0.05, "가이드": "하락 초입 ➔ 소액(5%) 탐색 진입"},
                {"단계": "🔴 2차 진입구간", "조건": "S ≤ -32", "비중": 0.10, "가이드": "하락 진행 ➔ 2차 비중(10%) 체결"},
                {"단계": "🔴 3차 진입구간", "조건": "S ≤ -40", "비중": 0.25, "가이드": "하락 심화 ➔ 3차 비중(25%) 확대"},
                {"단계": "🟣 4차 강력진입구간", "조건": "S ≤ -55", "비중": 0.30, "가이드": "🚨 **[1차 바닥]** 4차 승부수(30%) 집행 완료"}
            ]
            
            calc_base = []
            for row in base_plan:
                amt = int(total_seed * row["비중"])
                calc_base.append({
                    "매수 구분": row["단계"],
                    "S값 조건": row["조건"],
                    "투입 비중": f"{int(row['비중']*100)}%",
                    "배정 금액": f"{amt:,}원",
                    "실전 행동 가이드": row["가이드"]
                })
            st.dataframe(pd.DataFrame(calc_base), use_container_width=True)

            st.markdown("---")
            st.markdown("###### 🛡️ 2단계: 매도 없이 재하락 시 [예비 현금 30%] 방어선 집행")
            defense_plan = [
                {"구분": "🛡️ 2차 방어선", "조건": "재하락 S ≤ -40", "비중": 0.10, "가이드": "4차 진입 후 익절 없이 다시 밀릴 때 ➔ 예비 현금 10% 1차 방어 투입"},
                {"구분": "🚨 최후 방어선", "조건": "재하락 S ≤ -55 (전저점 이탈)", "비중": 0.20, "가이드": "극단적 언더슈팅 시 ➔ 남은 예비 현금 20% 전액 투입하여 평단가 최저 하강"}
            ]
            
            calc_def = []
            for row in defense_plan:
                amt = int(total_seed * row["비중"])
                calc_def.append({
                    "방어선 구분": row["구분"],
                    "발동 조건": row["조건"],
                    "투입 비중": f"{int(row['비중']*100)}%",
                    "배정 금액": f"{amt:,}원",
                    "실전 행동 가이드": row["가이드"]
                })
            st.dataframe(pd.DataFrame(calc_def), use_container_width=True)

        # -----------------------------
        # TAB 4: 보유 포트폴리오 & 3중 결합 스마트 리밸런싱
        # -----------------------------
        with tab4:
            st.markdown("##### 💼 실전 계좌 잔고 & 3중 결합 스마트 리밸런싱")
            st.caption("내 투자 원금, 예수금, 종목 수량 및 평단가를 자유롭게 입력·수정하고 아래 [💾 전체 계좌 데이터 영구 저장] 버튼을 누르면 새로고침(F5)을 해도 100% 안전하게 유지됩니다.")

            acc = st.session_state.account_data

            # 1. 초기 원금 & 예수금 설정
            col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.5])
            with col_acc1:
                new_principal = st.number_input(
                    "💰 내 총 투자 원금 (원)",
                    min_value=0,
                    value=int(acc.get("user_principal", 30000000)),
                    step=1000000,
                    format="%d",
                    key="input_user_principal"
                )
            with col_acc2:
                new_cash = st.number_input(
                    "💵 현재 계좌 예수금(현금) (원)",
                    min_value=0,
                    value=int(acc.get("user_cash", 10000000)),
                    step=500000,
                    format="%d",
                    key="input_user_cash"
                )
            with col_acc3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("💾 전체 계좌 데이터 영구 저장", use_container_width=True):
                    acc["user_principal"] = new_principal
                    acc["user_cash"] = new_cash
                    if save_current_portfolio(acc):
                        st.success("✅ 원금, 예수금, 종목 정보가 안전하게 영구 저장되었습니다!")
                    else:
                        st.error("저장 중 오류가 발생했습니다.")

            st.markdown("---")
            # 2. 보유 종목 리스트 테이블
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown("###### 📊 현재 보유 종목 현황")
            with col_h2:
                if st.button("➕ 보유 종목 추가하기", use_container_width=True):
                    new_id = max([item["id"] for item in acc["items"]], default=0) + 1
                    acc["items"].append({
                        "id": new_id, "input_val": "", "confirmed_code": "233740", "confirmed_name": "", "qty": 0, "avg_price": 0
                    })
                    save_current_portfolio(acc)
                    st.rerun()

            total_invested_stocks = 0
            total_eval_stocks = 0
            items_to_delete = []
            stock_eval_dict = {}

            for idx, item in enumerate(acc["items"]):
                cols = st.columns([1.6, 0.9, 0.9, 0.9, 1.1, 0.5])
                with cols[0]:
                    item["input_val"] = st.text_input(f"종목명/코드 {idx+1}", value=item["input_val"], key=f"mp_input_{item['id']}")
                with cols[1]:
                    st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
                    if st.button("🔍 조회", key=f"btn_search_{item['id']}"):
                        c, n = resolve_code_and_name(item["input_val"])
                        item["confirmed_code"] = c
                        item["confirmed_name"] = n
                        save_current_portfolio(acc)
                        st.rerun()
                with cols[2]:
                    item["qty"] = st.number_input(f"수량 {idx+1}", min_value=0, value=item["qty"], key=f"mp_qty_{item['id']}")
                with cols[3]:
                    item["avg_price"] = st.number_input(f"평단가 {idx+1}", min_value=0, value=item["avg_price"], key=f"mp_price_{item['id']}")
                
                live_df, _ = get_naver_stock_data(item["confirmed_code"], count=5)
                live_curr_price = int(live_df['Close'].iloc[-1]) if live_df is not None and not live_df.empty else item["avg_price"]

                eval_item = item["qty"] * live_curr_price
                invest_item = item["qty"] * item["avg_price"]
                stock_eval_dict[item["confirmed_code"]] = eval_item

                with cols[4]:
                    disp_name = item["confirmed_name"] if item["confirmed_name"] else "종목 미조회"
                    st.markdown(f"<div style='font-size: 0.75rem; color: #555;'><b>{disp_name}</b></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 1.0rem; font-weight: bold; color: #D32F2F;'>{live_curr_price:,}원</div>", unsafe_allow_html=True)
                with cols[5]:
                    st.markdown("<div style='margin-top: 22px;'></div>", unsafe_allow_html=True)
                    if st.button("❌", key=f"del_mp_{item['id']}"):
                        items_to_delete.append(item)

                total_invested_stocks += invest_item
                total_eval_stocks += eval_item

            if items_to_delete:
                for itm in items_to_delete:
                    acc["items"].remove(itm)
                save_current_portfolio(acc)
                st.rerun()

            st.markdown("---")
            # 3. 실시간 계좌 대시보드
            curr_cash = new_cash
            principal = new_principal

            total_account_assets = total_eval_stocks + curr_cash
            net_profit_total = total_account_assets - principal
            net_profit_rate = (net_profit_total / principal * 100) if principal > 0 else 0.0

            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("내 총 투자 원금", f"{principal:,}원")
            fc2.metric("보유 주식 실시간 평가액", f"{total_eval_stocks:,}원", f"{((total_eval_stocks/total_invested_stocks - 1.0)*100 if total_invested_stocks>0 else 0):+.2f}% (평가손익)")
            fc3.metric("실시간 계좌 예수금(현금)", f"{curr_cash:,}원", f"비중 {(curr_cash/total_account_assets*100 if total_account_assets>0 else 0):.1f}%")
            fc4.metric("계좌 총자산 (주식+현금)", f"{total_account_assets:,}원", f"{net_profit_rate:+.2f}% ({net_profit_total:+,}원)")

            # ------------------------------------------------------------------
            # ⚖️ [고도화] S값 트리거 + 50% 롱-숏 밴드 룰 + 반기 점검 통합 대시보드
            # ------------------------------------------------------------------
            st.markdown("---")
            st.markdown("##### ⚖️ [S값 시그널 + 50% 롱-숏 헤지 밴드 룰] 통합 리밸런싱 진단기")
            
            lev_val = stock_eval_dict.get("233740", 0)
            inv_val = stock_eval_dict.get("251340", 0)
            target_inv_hedge = lev_val * 0.50
            hedge_diff = inv_val - target_inv_hedge
            actual_hedge_ratio = (inv_val / lev_val * 100) if lev_val > 0 else 0.0

            # 반기(6월 말, 12월 말) 점검 D-Day 계산
            today_dt = datetime.today()
            this_year = today_dt.year
            d_june = datetime(this_year, 6, 30)
            d_dec = datetime(this_year, 12, 31)
            
            if today_dt <= d_june:
                next_check_dt = d_june
                next_check_name = "전반기(6월 말)"
            else:
                next_check_dt = d_dec
                next_check_name = "후반기(12월 말)"
            d_day = (next_check_dt - today_dt).days

            if lev_val > 0:
                # 1단계: S값 시그널 기반 교대 판정
                if current_s_val >= 0:
                    reb_title = "🔵 [S값 고점 회복] 인버스 50% 진입 & 레버리지 분할 익절 타이밍 (S ≥ 0)"
                    reb_color = "#1976D2"
                    reb_guidance = f"현재 메인 종목의 S값이 <b>{current_s_val}</b>로 회복되었습니다. 레버리지 평가액의 50% 수준인 <b>약 {int(target_inv_hedge):,}원</b>으로 선물인버스(251340)를 진입하여 하락장 방어 태세를 갖추세요."
                elif current_s_val <= -40:
                    reb_title = "🔴 [S값 바닥권 도달] 인버스 전량 익절 & 레버리지 3~4차 집중 전환 (S ≤ -40)"
                    reb_color = "#D32F2F"
                    reb_guidance = f"현재 메인 종목이 3~4차 바닥권(S값: <b>{current_s_val}</b>)에 진입했습니다. 하락을 방어해 준 <b>인버스를 전량 매도(수익 확정)</b>하고, 그 자금으로 레버리지 추가 매수에 집중하세요."
                else:
                    # 2단계: 밴드 룰 판정 (목표 50% 기준 ±15%p 이탈 여부: 35% ~ 65%)
                    if actual_hedge_ratio > 65.0:
                        reb_title = "🟠 [밴드 상방 이탈] 인버스 비중 과다 ➔ 초과분 부분 익절 권장"
                        reb_color = "#FF8F00"
                        reb_guidance = f"인버스 비중(<b>{actual_hedge_ratio:.1f}%</b>)이 허용 상한(65%)을 초과했습니다. 초과된 <b>약 {int(hedge_diff):,}원</b> 상당의 인버스를 부분 익절하여 현금을 확보하세요."
                    elif actual_hedge_ratio < 35.0:
                        reb_title = "🟠 [밴드 하방 이탈] 인버스 방어력 약화 ➔ 50% 수준 보충 권장"
                        reb_color = "#FF8F00"
                        reb_guidance = f"인버스 비중(<b>{actual_hedge_ratio:.1f}%</b>)이 허용 하한(35%)에 미달합니다. 안정적 방어를 위해 인버스를 <b>약 {int(abs(hedge_diff)):,}원</b> 보충하는 것을 권장합니다."
                    else:
                        reb_title = "🟢 [정상 균형] 50% 롱-숏 헤지 밴드 범위 안착"
                        reb_color = "#2E7D32"
                        reb_guidance = f"인버스 헤지 비율(<b>{actual_hedge_ratio:.1f}%</b>)이 50% 목표 범위(35%~65%) 내에 완벽하게 안착해 있습니다. 포지션을 그대로 유지하세요."

                st.markdown(f"""
                <div class="brief-card" style="border-left: 6px solid {reb_color}; background-color: #FAFAFA;">
                    <div class="brief-title" style="color: {reb_color}; font-size: 0.98rem;">{reb_title}</div>
                    <div style="font-size: 0.88rem; color: #222; line-height: 1.6;">
                        • <b>포트폴리오 헤지 현황</b>: 레버리지 <b>{lev_val:,}원</b> | 인버스 <b>{inv_val:,}원</b> (헤지 비율: <b>{actual_hedge_ratio:.1f}%</b> / 권장: 50.0%)<br>
                        • <b>실시간 행동 지침</b>: {reb_guidance}<br>
                        • <b>📅 차기 정기 점검일</b>: <b>{next_check_name}</b>까지 <b>D-{d_day}일</b> 남음 (파동 신호 없을 시 최종 잔액 균형 점검)
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("💡 보유 종목 현황에 [KODEX 코스닥150레버리지(233740)]를 등록하시면 실시간 S값 & 50% 롱-숏 헤지 진단 카드가 즉시 활성화됩니다.")

            # 4. 체결 일지 기록 (단독 기록형)
            st.markdown("---")
            with st.expander("📝 [매수·매도 체결 기록 일지 입력]", expanded=False):
                with st.form("simple_trade_log_form"):
                    tf1, tf2, tf3, tf4, tf5 = st.columns([1.2, 1.2, 1.0, 1.0, 1.0])
                    with tf1:
                        log_date = st.date_input("체결 일자", datetime.today()).strftime('%Y-%m-%d')
                    with tf2:
                        log_stock = st.text_input("종목명/코드", value="233740")
                    with tf3:
                        log_type = st.selectbox("구분", ["🔴 매수", "🔵 매도"])
                    with tf4:
                        log_price = st.number_input("체결 단가(원)", min_value=1, value=5000, step=10)
                    with tf5:
                        log_qty = st.number_input("체결 수량(주)", min_value=1, value=100, step=10)

                    submit_log = st.form_submit_button("➕ 체결 기록 추가하기", use_container_width=True)
                    if submit_log:
                        _, resolved_name = resolve_code_and_name(log_stock)
                        acc["trade_logs"].append({
                            "일자": log_date,
                            "종목": resolved_name,
                            "구분": log_type,
                            "체결단가": log_price,
                            "체결수량": log_qty,
                            "체결금액": log_price * log_qty
                        })
                        save_current_portfolio(acc)
                        st.success(f"✅ [{log_type}] {resolved_name} {log_qty:,}주 기록 추가 완료!")
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
                        height=200
                    )
                    if st.button("🗑️ 체결 기록 전체 비우기"):
                        acc["trade_logs"] = []
                        save_current_portfolio(acc)
                        st.rerun()

        # -----------------------------
        # TAB 5: 엑셀 다운로드 (정렬 일치 & 지표 컬러 완벽 동기화)
        # -----------------------------
        with tab5:
            st.markdown("##### 💾 원본 통합 엑셀 다운로드 (`PPP` 시트)")
            st.caption("화면의 매수·매도 표와 동일한 최신순 정렬로 저장되며, MM, PM, LM, S, RM 및 매수신호 색상이 100% 동일하게 적용됩니다.")
            
            excel_bytes = generate_original_style_excel(stock_name, stock_code, s, df_display, df_full_result, reverse_order=True)
            st.download_button(
                label=f"📥 [{stock_name}] 원본 양식 컬러 엑셀 다운로드 (화면 표와 100% 일치)",
                data=excel_bytes,
                file_name=f"0.ETF_{stock_code}_{stock_name}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.error("입력하신 종목의 데이터를 찾을 수 없습니다. 올바른 종목명 또는 6자리 종목코드를 입력해 주세요.")
