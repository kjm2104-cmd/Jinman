import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from io import BytesIO
from xml.etree import ElementTree as ET

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="간편 교대 매매 분석기 Pro",
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

st.subheader("📈  매매 시스템 ")

# 네이버 금융 일별 시세 크롤링 함수 (데이터 정제 & 중복 제거 보강)
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

# 종목별 외국인/기관 매매동향 크롤링 함수
@st.cache_data(ttl=300)
def get_investor_trend(code):
    clean_code = str(code).strip()
    if not clean_code or not clean_code.isdigit():
        return None
    url = f"https://finance.naver.com/item/frgn.naver?code={clean_code}"
    try:
        dfs = pd.read_html(url, encoding='euc-kr')
        for df in dfs:
            cols_str = str(df.columns)
            if '외국인' in cols_str and '기관' in cols_str:
                df_clean = df.dropna(how='all').copy()
                if len(df_clean) > 2:
                    if isinstance(df_clean.columns, pd.MultiIndex):
                        flat_cols = []
                        for c in df_clean.columns:
                            c_str = "_".join([str(sub) for sub in c if 'Unnamed' not in str(sub)]).strip('_')
                            flat_cols.append(c_str if c_str else 'col')
                        df_clean.columns = flat_cols

                    dt_col = [c for c in df_clean.columns if '날짜' in c or '일자' in c]
                    inst_col = [c for c in df_clean.columns if '기관' in c and '순매매' in c]
                    frgn_col = [c for c in df_clean.columns if '외국인' in c and '순매매' in c]

                    if dt_col and inst_col and frgn_col:
                        res_df = df_clean[[dt_col[0], inst_col[0], frgn_col[0]]].dropna().head(5).copy()
                        res_df.columns = ['일자', '기관순매수', '외국인순매수']
                        for col in ['기관순매수', '외국인순매수']:
                            res_df[col] = pd.to_numeric(
                                res_df[col].astype(str).str.replace(',', '').str.replace('+', ''), 
                                errors='coerce'
                            ).fillna(0).astype(int)
                        res_df['개인순매수'] = -(res_df['기관순매수'] + res_df['외국인순매수'])
                        return res_df[['일자', '개인순매수', '외국인순매수', '기관순매수']]
        return None
    except Exception:
        return None

# 종목별 최근 공시 목록 크롤링 함수
@st.cache_data(ttl=600)
def get_recent_disclosures(code):
    clean_code = str(code).strip()
    if not clean_code or not clean_code.isdigit():
        return None
    url = f"https://finance.naver.com/item/news_notice.naver?code={clean_code}"
    try:
        dfs = pd.read_html(url, encoding='euc-kr')
        for df in dfs:
            if '제목' in str(df.columns) or '뉴스제목' in str(df.columns):
                df_clean = df.dropna(how='all').copy()
                title_col = [c for c in df_clean.columns if '제목' in c]
                date_col = [c for c in df_clean.columns if '날짜' in c or '일자' in c]
                src_col = [c for c in df_clean.columns if '정보제공' in c or '출처' in c]

                if title_col and date_col:
                    cols_to_keep = [title_col[0], date_col[0]]
                    if src_col:
                        cols_to_keep.append(src_col[0])
                    res_df = df_clean[cols_to_keep].dropna().head(4).copy()
                    if src_col:
                        res_df.columns = ['공시/뉴스 제목', '일자', '제공처']
                    else:
                        res_df.columns = ['공시/뉴스 제목', '일자']
                    return res_df
        return None
    except Exception:
        return None

# 주요 종목 빠른 매핑 사전
name_to_code = {
    "코스피지수": "KOSPI",
    "코스닥지수": "KOSDAQ",
    "삼성전자": "005930",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
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
            placeholder="예: 삼성전자, 또는 233740"
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

# 표 스타일러 함수 (등락률 부호 직결 판별로 색상 꼬임 완벽 방지)
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

# 엑셀 원본(PPP 시트) 수식 계산 함수
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
        'state': "상승 파동 진행 중" if state == 'UP' else "하락 파동 진행 중"
    }
    return df_out, summary

# 코스피 및 코스닥 지수 데이터 실시간 조회
kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)

kospi_val = int(kospi_df['Close'].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df['Close'].iloc[-1] / kospi_df['Close'].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0

kosdaq_val = int(kosdaq_df['Close'].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df['Close'].iloc[-1] / kosdaq_df['Close'].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    with st.spinner(f"[{stock_name} ({stock_code})] 수급 및 시장 분석을 포함한 마감 브리핑을 준비 중입니다..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=1500)
        investor_df = get_investor_trend(stock_code)
        disclosure_df = get_recent_disclosures(stock_code)

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

        # 상단 실전 액션 가이드 브리핑 (공통)
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
            "💼 보유 포트폴리오", 
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
        # TAB 2: 마감 브리핑 전용 탭 (4가지 종합 고도화 반영)
        # -----------------------------
        with tab2:
            st.markdown(f"#### 📢 [{s['date']}] {stock_name} 장 마감 종합 브리핑")

            # 1. 🌐 전체 시장 종합 프리핑
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

            # 2. 🕯️ [신규 1번] 당일 캔들 형태 & 꼬리 분석 (바닥 반등 시그널)
            o_p, h_p, l_p, c_p = s['Open'], s['High'], s['Low'], s['B1']
            body_size = abs(c_p - o_p)
            candle_range = max(1, h_p - l_p)
            lower_shadow = min(o_p, c_p) - l_p
            upper_shadow = h_p - max(o_p, c_p)

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

            # 3. 👥 오늘 투자자별 매매동향
            st.markdown("""
            <div class="brief-card">
                <div class="brief-title">3. 👥 투자자별 매매동향 (수급 흐름)</div>
            """, unsafe_allow_html=True)

            if investor_df is not None and not investor_df.empty:
                latest_inv = investor_df.iloc[0]
                p_val = latest_inv['개인순매수']
                f_val = latest_inv['외국인순매수']
                i_val = latest_inv['기관순매수']

                def fmt_inv(val):
                    c = '#D32F2F' if val > 0 else ('#1976D2' if val < 0 else '#555555')
                    arrow = '▲ 순매수' if val > 0 else ('▼ 순매도' if val < 0 else '- 보합')
                    return f"<span style='color:{c}; font-weight:bold;'>{val:+,}주 ({arrow})</span>"

                st.markdown(f"""
                <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                    <div style="flex:1; background-color:#F5F5F5; border-radius:6px; padding:8px; text-align:center;">
                        <span style="font-size:0.75rem; color:#666;">개인</span><br>
                        <span style="font-size:0.85rem;">{fmt_inv(p_val)}</span>
                    </div>
                    <div style="flex:1; background-color:#F5F5F5; border-radius:6px; padding:8px; text-align:center;">
                        <span style="font-size:0.75rem; color:#666;">외국인</span><br>
                        <span style="font-size:0.85rem;">{fmt_inv(f_val)}</span>
                    </div>
                    <div style="flex:1; background-color:#F5F5F5; border-radius:6px; padding:8px; text-align:center;">
                        <span style="font-size:0.75rem; color:#666;">기관</span><br>
                        <span style="font-size:0.85rem;">{fmt_inv(i_val)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                inv_display = investor_df.head(3).copy()
                st.dataframe(inv_display.style.format({
                    '개인순매수': '{:+,}',
                    '외국인순매수': '{:+,}',
                    '기관순매수': '{:+,}'
                }), use_container_width=True)
            else:
                st.markdown("""
                <div style="font-size:0.86rem; color:#555; line-height:1.5;">
                    • <b>수급 핵심 체크포인트</b>: 파동 저점 구간에서 <b>개인의 투매 물량을 외국인·기관이 양매수로 받아낼 때</b> 가장 신뢰도 높은 V자 바닥 반등이 형성됩니다.<br>
                    • <i>(장 마감 후 네이버 금융 거래소 확정 집계 데이터 연동 중)</i>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # 4. ⚡ 거래량 시그널 & 바닥 경보
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
                <div class="brief-title">4. ⚡ 거래량 시그널 & 바닥 경보</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>오늘 거래량</b>: {s['C1']:,}주 (전일 대비 <b>{vol_ratio_val:.2f}배</b>)<br>
                    • <b>진단 결과</b>: <span style="color:{vol_color}; font-weight:bold;">{vol_badge}</span><br>
                    • <b>해석</b>: {vol_desc}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 5. 🎯 다음 목표가까지 남은 거리 (D-Day 카운트다운)
            curr_p = s['B1']
            tp_3 = target_prices_dict.get(-40, 0)
            tp_4 = target_prices_dict.get(-55, 0)
            diff_3 = tp_3 - curr_p if tp_3 > 0 else 0
            diff_3_pct = (diff_3 / curr_p) * 100.0 if curr_p > 0 else 0.0
            diff_4 = tp_4 - curr_p if tp_4 > 0 else 0
            diff_4_pct = (diff_4 / curr_p) * 100.0 if curr_p > 0 else 0.0

            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">5. 🎯 다음 목표가까지 남은 거리 (D-Day 카운트다운)</div>
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

            # 6. 📉 [신규 3번] 최근 5영업일 핵심 지표(S값) 궤적 추적
            recent_5 = df_full_result.tail(5).copy()
            s_traj_html = " ➔ ".join([f"<b>{row['일자'][5:]}</b> (S: <code>{row['S']}</code>)" for _, row in recent_5.iterrows()])
            s_diff_5 = recent_5['S'].iloc[-1] - recent_5['S'].iloc[0]
            
            st.markdown(f"""
            <div class="brief-card">
                <div class="brief-title">6. 📉 최근 5영업일 핵심 지표(S값) 궤적 추적</div>
                <div style="font-size:0.88rem; color:#222; line-height:1.6;">
                    • <b>5일간 S값 추이</b>: {s_traj_html}<br>
                    • <b>추세 진단</b>: 최근 5일간 S값이 <b>{s_diff_5:+d} 포인트</b> 변동했습니다. 
                      {'하락 폭이 둔화되며 바닥 수렴 국면에 진입하고 있습니다.' if abs(s_diff_5) <= 5 else '지표의 변동성이 확대되고 있으므로 단계별 지정가만 체결 대기하세요.'}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 7. 🧮 [신규 2번] 내 계좌 실전 탈출 시뮬레이터 (방어선 추가 매수 시 평단가 변화)
            my_port_item = None
            if 'my_portfolio_items' in st.session_state:
                for itm in st.session_state.my_portfolio_items:
                    if itm.get('confirmed_code') == stock_code and itm.get('qty', 0) > 0:
                        my_port_item = itm
                        break

            if my_port_item:
                curr_my_qty = my_port_item['qty']
                curr_my_price = my_port_item['avg_price']
                curr_eval_pct = ((curr_p / curr_my_price) - 1.0) * 100 if curr_my_price > 0 else 0
                
                # 가상 3차 방어선(시드의 10% 가정, 300만원 분량 매수 시뮬레이션)
                add_budget_3 = 3000000
                add_qty_3 = int(add_budget_3 / tp_3) if tp_3 > 0 else 0
                sim_price_3 = int((curr_my_qty * curr_my_price + add_qty_3 * tp_3) / (curr_my_qty + add_qty_3)) if (curr_my_qty + add_qty_3) > 0 else curr_my_price
                price_drop_3 = curr_my_price - sim_price_3

                st.markdown(f"""
                <div class="brief-card" style="border-left: 5px solid #6A1B9A;">
                    <div class="brief-title" style="color: #6A1B9A;">7. 🧮 내 계좌 실전 탈출 시뮬레이터 (보유 포트폴리오 연동)</div>
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
                    <div class="brief-title">7. 🧮 내 계좌 실전 탈출 시뮬레이터</div>
                    <div style="font-size:0.86rem; color:#555;">
                        • <i>[💼 보유 포트폴리오] 탭에 <b>{stock_name}</b>의 수량과 평단가를 입력해 두시면, 방어선 추가 매수 시 내 평단가가 얼마나 낮아지는지 자동 시뮬레이션됩니다.</i>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 8. 📋 최근 주요 공시 & 시장 조치 알림
            st.markdown("""
            <div class="brief-card">
                <div class="brief-title">8. 📋 최근 주요 공시 & 시장 조치 알림</div>
            """, unsafe_allow_html=True)
            if disclosure_df is not None and not disclosure_df.empty:
                st.dataframe(disclosure_df, use_container_width=True)
            else:
                st.markdown(f"""
                <div style="font-size:0.86rem; color:#555; line-height:1.5;">
                    • 최근 7영업일 이내에 주가 급변동을 야기할 특이 공시(유상증자, CB발행, 괴리율 경고 등)는 등록되지 않았습니다.<br>
                    • <i>({stock_name} 전자공시 및 거래소 공시 실시간 모니터링 중)</i>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # 9. 🧭 [신규 4번] 내일 장 시작 전 3대 체크포인트 (내일 08:50 행동 요강)
            st.markdown(f"""
            <div class="brief-card" style="border-left: 5px solid #D32F2F; background-color: #FFF8E1;">
                <div class="brief-title" style="color: #D32F2F;">9. 🧭 내일 장 시작 전 3대 체크포인트 (내일 08:50 행동 요강)</div>
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
        # TAB 4: 보유 포트폴리오
        # -----------------------------
        with tab4:
            st.markdown("##### 💼 실전 보유 포트폴리오 다중 종목 성과 분석기")
            if 'my_portfolio_items' not in st.session_state:
                st.session_state.my_portfolio_items = [
                    {"id": 1, "input_val": "233740", "confirmed_code": "233740", "confirmed_name": "KODEX 코스닥150레버리지", "qty": 5717, "avg_price": 5330}
                ]
            if st.button("➕ 보유 종목 추가하기"):
                new_id = max([item["id"] for item in st.session_state.my_portfolio_items], default=0) + 1
                st.session_state.my_portfolio_items.append({"id": new_id, "input_val": "", "confirmed_code": "233740", "confirmed_name": "", "qty": 0, "avg_price": 0})
                st.rerun()

            total_invested_all = 0
            total_eval_all = 0
            items_to_delete = []

            for idx, item in enumerate(st.session_state.my_portfolio_items):
                cols = st.columns([1.6, 0.9, 0.9, 0.9, 1.1, 0.5])
                with cols[0]:
                    item["input_val"] = st.text_input(f"종목명/코드 {idx+1}", value=item["input_val"], key=f"mp_input_{item['id']}")
                with cols[1]:
                    st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
                    if st.button("🔍 조회", key=f"btn_search_{item['id']}"):
                        c, n = resolve_code_and_name(item["input_val"])
                        item["confirmed_code"] = c
                        item["confirmed_name"] = n
                        st.rerun()
                with cols[2]:
                    item["qty"] = st.number_input(f"수량 {idx+1}", min_value=0, value=item["qty"], key=f"mp_qty_{item['id']}")
                with cols[3]:
                    item["avg_price"] = st.number_input(f"평단가 {idx+1}", min_value=0, value=item["avg_price"], key=f"mp_price_{item['id']}")
                
                live_df, _ = get_naver_stock_data(item["confirmed_code"], count=5)
                live_curr_price = int(live_df['Close'].iloc[-1]) if live_df is not None and not live_df.empty else item["avg_price"]

                with cols[4]:
                    disp_name = item["confirmed_name"] if item["confirmed_name"] else "종목 미조회"
                    st.markdown(f"<div style='font-size: 0.75rem; color: #555;'><b>{disp_name}</b></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 1.0rem; font-weight: bold; color: #D32F2F;'>{live_curr_price:,}원</div>", unsafe_allow_html=True)
                with cols[5]:
                    st.markdown("<div style='margin-top: 22px;'></div>", unsafe_allow_html=True)
                    if st.button("❌", key=f"del_mp_{item['id']}"):
                        items_to_delete.append(item)

                total_invested_all += item["qty"] * item["avg_price"]
                total_eval_all += item["qty"] * live_curr_price

            if items_to_delete:
                for itm in items_to_delete:
                    st.session_state.my_portfolio_items.remove(itm)
                st.rerun()

            st.markdown("---")
            total_pl = total_eval_all - total_invested_all
            total_pl_rate = (total_eval_all / total_invested_all - 1.0) * 100 if total_invested_all > 0 else 0
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("전체 총 투자원금", f"{total_invested_all:,}원")
            fc2.metric("전체 총 평가금액", f"{total_eval_all:,}원", f"{total_pl_rate:+.2f}%")
            fc3.metric("전체 총 평가 손익", f"{total_pl:,}원")

        # -----------------------------
        # TAB 5: 엑셀 다운로드
        # -----------------------------
        with tab5:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_display.to_excel(writer, index=False, sheet_name="PPP")
            st.download_button(
                label="📥 매매전략 엑셀 다운로드",
                data=output.getvalue(),
                file_name=f"0.ETF_{stock_code}_{stock_name}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("입력하신 종목의 데이터를 찾을 수 없습니다. 올바른 종목명 또는 6자리 종목코드를 입력해 주세요.")
