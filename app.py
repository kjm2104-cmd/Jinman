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
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; }
    table dataframe, th, td { font-size: 0.82rem !important; padding: 4px 5px !important; }
    .plan-box { background-color: #F8F9FA; border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 5px solid #1976D2; }
    .defense-box { background-color: #FFF8E1; border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 5px solid #FF8F00; }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 간편 교대 매매 시스템 (1안 정석 분할 방어형)")

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
            placeholder="예: 삼성전자, 피엔티 또는 233740"
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

def style_table(df_target, df_full):
    cols_grad = ['MM', 'PM', 'LM', 'RM', 'S']
    col_bounds = {}
    for c in cols_grad:
        if c in df_full.columns:
            vals = pd.to_numeric(df_full[c], errors='coerce')
            col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = [''] * len(row)
        curr_close = row.get('종가(B)', 0)
        prev_close = df_full.iloc[row.name - 1].get('종가(B)', 0) if row.name > 0 else None

        for idx, col_name in enumerate(row.index):
            val = row[col_name]
            if col_name in ['종가(B)', '등락률(C)'] and prev_close is not None:
                if curr_close > prev_close:
                    styles[idx] = 'color: #D32F2F; font-weight: bold;'
                elif curr_close < prev_close:
                    styles[idx] = 'color: #1976D2; font-weight: bold;'
                else:
                    styles[idx] = 'color: #111111;'
            
            elif col_name == '거래량(F)':
                try:
                    curr_vol = float(val)
                    prev_vol = float(df_full.iloc[row.name - 1]['거래량(F)']) if row.name > 0 else curr_vol
                    vol_diff_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                    
                    if vol_diff_ratio >= 0:
                        ratio = min(1.0, vol_diff_ratio / 1.0)
                        r = 255; g = int(240 - ratio * 180); b = int(240 - ratio * 180)
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.3 else "#222222"}; font-weight: bold; white-space: nowrap; text-align: right;'
                    else:
                        ratio = min(1.0, abs(vol_diff_ratio) / 0.5)
                        r = int(240 - ratio * 180); g = int(240 - ratio * 180); b = 255
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: {"#0D47A1" if ratio > 0.3 else "#222222"}; font-weight: bold; white-space: nowrap; text-align: right;'
                except Exception:
                    pass

            elif col_name == 'S':
                try:
                    s_num = float(val)
                    if s_num > 0:
                        ratio = min(1.0, s_num / 50.0)
                        r = 255; g = int(230 - ratio * 150); b = int(230 - ratio * 150)
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: #B71C1C; font-weight: 900; padding: 2px 6px; border-radius: 8px;'
                    elif s_num < 0:
                        ratio = min(1.0, abs(s_num) / 60.0)
                        r = int(230 - ratio * 150); g = int(230 - ratio * 150); b = 255
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: 900; padding: 2px 6px; border-radius: 8px;'
                    else:
                        styles[idx] = 'background-color: #E0E0E0; color: #333333; font-weight: bold;'
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
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: #0D47A1; font-weight: bold; padding: 2px 6px; border-radius: 6px;'
                    else:
                        r = 255; g = int(245 - ratio * 170); b = int(245 - ratio * 170)
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.5 else "#222222"}; font-weight: {"bold" if ratio > 0.4 else "normal"}; padding: 2px 6px; border-radius: 6px;'
                except Exception:
                    pass

            elif col_name == '매수신호':
                val_str = str(val)
                if '강력진입구간' in val_str:
                    styles[idx] = 'background-color: #7B1FA2; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif '진입구간' in val_str:
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif '신호' in val_str:
                    styles[idx] = 'background-color: #FF8F00; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif val_str == '매도 추천':
                    styles[idx] = 'background-color: #1976D2; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif val_str == '관망':
                    styles[idx] = 'color: #2E7D32; font-weight: bold; white-space: nowrap;'
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
        'C1': int(vols[-1]),
        'cur_chg': chg[-1] * 100,
        'MM': mm_list[-1],
        'PM': pm_list[-1],
        'LM': lm_list[-1],
        'S': s_list[-1],
        'RM': rm_list[-1],
        'current_signal': buy_signals[-1],
        'max_mn': next_high,
        'min_pq': next_low,
        'B7': peak if state == 'UP' else trough,
        'B8': r10(peak * (1.0 - 0.095)) if state == 'UP' else r10(trough * 1.095),
        'B9': r10(peak * (1.0 - 0.045)) if state == 'UP' else r10(trough * 1.045),
        'state': "상승추세" if state == 'UP' else "하락추세"
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
    with st.spinner(f"[{stock_name} ({stock_code})] 1안 정석 분할 방어형 플랜을 적용 중입니다..."):
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
        
        # 1안 기준 가격 단계 (기본 1~4차 및 재하락 2차 방어선 목표가)
        four_stages_info = [
            (-25, "1차 신호(5%)"), (-32, "2차 진입(10%)"), (-40, "3차 진입(25%)"), (-55, "4차 강력진입(30%)")
        ]
        
        target_prices_4step = []
        if max_mn_val > 0 and min_pq_val > 0:
            for s_tgt, name in four_stages_info:
                tp = r10(max_mn_val + (s_tgt * min_pq_val) / 100.0)
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
                <b>현재 3M — MM: <code>{s['MM']}</code> | PM: <code>{s['PM']}%</code> | LM: <code>{s['LM']}%</code> | S값: <code>{current_s_val}</code> ({s['state']})</b><br>
                기준 고점: {max_mn_val:,}원 / 기준 저점: {min_pq_val:,}원 | 기준가: {s['B7']:,}원 / 전환가: {s['B8']:,}원
            </p>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 8px 10px; border-radius: 6px; margin-top: 8px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if target_prices_4step:
            st.markdown(f"""
            <div style="background-color: #FFF3E0; border: 1px solid #FFB74D; padding: 10px; border-radius: 8px; margin-bottom: 12px; font-size: 0.85rem; color: #333; line-height: 1.4;">
                <b>🎯 [1안 기준 주요 진입 목표가]</b><br>
                {' | '.join(target_prices_4step)}
            </div>
            """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 3M 요약", f"S: {s['S']}", f"MM:{s['MM']} / PM:{s['PM']} / LM:{s['LM']}")
        c3.metric("코스피 지수", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 지수", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        tab1, tab2, tab3, tab4 = st.tabs(["🎯 1안 실전 가이드 & 계산기", "📊 매수·매도 표 (전체)", "💼 보유 포트폴리오", "💾 엑셀 다운로드"])

        with tab1:
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

        with tab2:
            st.caption("📈 엑셀 원본(PPP 시트)과 100% 일치하며 모든 변곡점 가격이 정수로 표시됩니다.")
            df_rev = df_display.iloc[::-1]
            st.dataframe(style_table(df_rev, df_full_result), use_container_width=True, height=520)

        with tab3:
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

        with tab4:
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
