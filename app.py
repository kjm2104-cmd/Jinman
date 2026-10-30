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

# 모바일 가독성 및 표 칸 넓이 최적화 CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; }
    table dataframe, th, td { font-size: 0.82rem !important; padding: 4px 5px !important; }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 간편 교대 매매 시스템 (엑셀 원본 수식 100% 동기화)")

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
    """엑셀 ROUND(값, -1)과 동일하게 10원 단위 반올림"""
    return int(np.floor(val / 10.0 + 0.5) * 10)

def trunc_int(val):
    """엑셀 INT / TRUNC(소수점 버림) 처리"""
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

    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format({
        '종가(B)': '{:,}', '거래량(F)': '{:,}', '거래비율(G)': '{:.2f}'
    }, na_rep="-")

# 🔥 엑셀 파일(0.ETF_233740KODEX 코스닥150 레버리지.xlsx)의 PPP 시트 수식 완벽 구현
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
    first_N = init_p   # 반등 첫 가격
    first_R = init_p   # 조정 첫 가격
    up_phase = 'N'     # 'N'(반등) 또는 'O'(상-추세)
    down_phase = 'R'   # 'R'(조정) 또는 'Q'(하-추세)

    # 엑셀 7~8행 파동 기록 레지스터
    N8, O8, Q8, R8 = 0, init_p, 0, 0
    # 직전 완료된 고점과 저점 (1영업일 뒤 MM/PM/LM/S에 반영되는 엑셀 규칙 적용)
    active_high = init_p
    active_low = 0
    pending_high = None
    pending_low = None

    for i in range(n):
        p = int(round(closes[i]))

        # 전일(i-1)에 확정된 파동 전환이 있다면 오늘(i)부터 MM, PM, LM, S 기준값에 반영 (엑셀 1일 이연 규칙)
        if pending_high is not None:
            active_high = pending_high
            pending_high = None
        if pending_low is not None:
            active_low = pending_low
            pending_low = None

        # 당일 MM, PM, LM, S 계산 (엑셀 TRUNC/INT 방식 동기화)
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

        # RM 계산 (최근 완료 고점/저점 흐름 대비)
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

        # 당일 종가(p)에 따른 파동 추적 및 변곡점 기록 (다음 날 아침부터 MM/PM/LM에 반영됨)
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
                # 고점 대비 하락 전환 체크 (첫 파동은 -4.5% 조정 진입, 이후 -9.5% 전환가 적용)
                down_turn_price = r10(peak * (1.0 - 0.095))
                first_step_down = r10(peak * (1.0 - 0.045))
                if p <= down_turn_price or (active_low == 0 and p <= first_step_down):
                    # 상승 파동 마감 -> 내일부터 새로운 고점(peak)이 active_high로 적용됨
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
        else:  # state == 'DOWN'
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
                # 저점 대비 +9.5% 반등 전환가 도달 여부 확인
                up_turn_price = r10(trough * 1.095)
                first_step_up = r10(trough * 1.045)
                if p >= up_turn_price:
                    # 하락 파동 마감 -> 내일부터 새로운 저점(trough)이 active_low로 적용됨
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

    # 다음 영업일 목표가 계산을 위한 최신 기준 고점/저점 반영
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
    with st.spinner(f"[{stock_name} ({stock_code})] 엑셀 원본 수식으로 파동을 계산 중입니다..."):
        # 파동 뿌리가 흔들리지 않도록 충분한 과거 데이터를 불러온 뒤 고정 시작점 유지
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
            (-25, "1차 신호"), (-32, "2차 진입구간"), (-40, "3차 진입구간"), (-55, "4차 강력진입구간")
        ]
        
        target_prices_4step = []
        if max_mn_val > 0 and min_pq_val > 0:
            for s_tgt, name in four_stages_info:
                tp = r10(max_mn_val + (s_tgt * min_pq_val) / 100.0)
                target_prices_4step.append(f"<b>{name}</b>: <span style='color:#D32F2F;'>{tp:,}원 이하</span> (S≤{s_tgt})")

        if "강력진입구간" in cur_sig:
            action_title = f"🟣 [{cur_sig}] ➔ 최후 승부수 구간 도달!"
            action_desc = "S ≤ -55 최하단 바닥에 도달했습니다. 모든 화력을 집중할 때입니다."
            action_item = "🚨 **[오늘의 Action Item]**: 4차 강력진입구간 비중(40%) 전액 집행 및 지정가 매수 세팅"
            badge_color = "#7B1FA2"
        elif "진입구간" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 분할 매수 진행 구간!"
            action_desc = "하락이 깊어져 점진적으로 비중을 담아가는 구간입니다."
            action_item = "📌 **[오늘의 Action Item]**: 해당 단계별 목표가 이하로 내려올 때 분할 매수 비중 체결 대기"
            badge_color = "#D32F2F"
        elif "신호" in cur_sig:
            action_title = f"🟠 [{cur_sig}] ➔ 하락 초입 탐색 신호!"
            action_desc = "본격적인 진입 전, 첫 번째 신호가 포착되었습니다."
            action_item = "👀 **[오늘의 Action Item]**: 무리한 매수 자제, 1차 탐색 소액(10%)만 열어두고 관망 강화"
            badge_color = "#FF8F00"
        elif cur_sig == "매도 추천":
            action_title = f"🔵 [{cur_sig}] ➔ 지표 회복! 수익 실현 검토"
            action_desc = "S값이 안전지대로 회복되었습니다."
            action_item = "💰 **[오늘의 Action Item]**: 평단가 위 익절 타이밍 포착 시 미련 없이 현금화 및 수확"
            badge_color = "#1976D2"
        else:
            action_title = "🟢 [관망] ➔ 안전 구간"
            action_desc = "현금 100%를 유지하며 기회를 기다립니다."
            action_item = "🛡️ **[오늘의 Action Item]**: 현금 100% 사수! 지수가 흔들려도 차분하게 기회를 기다리세요."
            badge_color = "#2E7D32"

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 6px solid {badge_color}; padding: 14px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin: 0; color: {badge_color}; font-size: 1.1rem;">{action_title}</h3>
            <p style="margin: 6px 0 4px 0; color: #222222; font-size: 0.9rem;">
                <b>현재 3M — MM: <code>{s['MM']}</code> | PM: <code>{s['PM']}%</code> | LM: <code>{s['LM']}%</code> | S값: <code>{current_s_val}</code> ({s['state']})</b><br>
                기준 고점: {max_mn_val:,}원 / 기준 저점: {min_pq_val:,}원 | 기준가(B7): {s['B7']:,}원 / 전환가(B8): {s['B8']:,}원 / 1차가격(B9): {s['B9']:,}원
            </p>
            <div style="background-color: #FFFFFF; border: 1px dashed {badge_color}; padding: 8px 10px; border-radius: 6px; margin-top: 8px; font-size: 0.88rem; color: #111;">
                {action_item}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if target_prices_4step:
            st.markdown(f"""
            <div style="background-color: #FFF3E0; border: 1px solid #FFB74D; padding: 10px; border-radius: 8px; margin-bottom: 12px; font-size: 0.85rem; color: #333; line-height: 1.4;">
                <b>🎯 [4단계 지정가 세팅 가이드] 다음 영업일 주요 도달 목표가</b><br>
                {' | '.join(target_prices_4step)}
            </div>
            """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 3M 요약", f"S: {s['S']}", f"MM:{s['MM']} / PM:{s['PM']} / LM:{s['LM']}")
        c3.metric("코스피 지수", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥 지수", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 표 (전체)", "🎯 4단계 가이드 & 자동금액", "💼 보유 포트폴리오", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 엑셀 원본(PPP 시트)의 1일 이연 규칙과 INT 버림 수식이 그대로 적용되어 과거 일자의 값이 절대 바뀌지 않습니다.")
            df_rev = df_display.iloc[::-1]
            st.dataframe(style_table(df_rev, df_full_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 🎯 [4단계 핵심 매수 가이드 & 자동금액 계산기]")
            total_seed = st.number_input("💰 총 투자 예정 금액 (원)", min_value=100000, max_value=10000000000, value=30000000, step=1000000, format="%d")

            four_step_rows = [
                {"단계": "🟠 1차 신호", "조건": "S ≤ -25", "비중": 0.10, "가이드": "하락 초입 ➔ 신호 감지 (관망 또는 소액 탐색)"},
                {"단계": "🔴 2차 진입구간", "조건": "S ≤ -32", "비중": 0.20, "가이드": "하락 진행 ➔ 2차 진입 시작"},
                {"단계": "🔴 3차 진입구간", "조건": "S ≤ -40", "비중": 0.30, "가이드": "하락 심화 ➔ 3차 비중 확대"},
                {"단계": "🟣 4차 강력진입구간", "조건": "S ≤ -55", "비중": 0.40, "가이드": "🚨 **[최후 승부수]** 바닥 올인 강력진입"},
            ]

            calc_data = []
            for row in four_step_rows:
                amt = int(total_seed * row["비중"])
                calc_data.append({
                    "매수 단계": row["단계"],
                    "S값 조건": row["조건"],
                    "투입 비중": f"{int(row['비중']*100)}%",
                    "자동 계산 투입금액": f"{amt:,}원",
                    "행동 가이드": row["가이드"]
                })

            st.dataframe(pd.DataFrame(calc_data), use_container_width=True)

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
