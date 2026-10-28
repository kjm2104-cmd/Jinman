import streamlit as st
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="모바일 분석기",
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

st.subheader("📈 모바일 분석기 (10분할 시소 교대매매)")

# KRX 종목 리스트 캐싱
@st.cache_data(ttl=86400)
def get_krx_list():
    try:
        krx = fdr.StockListing('KRX')
        if 'Code' in krx.columns and 'Name' in krx.columns:
            return krx[['Code', 'Name']]
        elif 'Symbol' in krx.columns and 'Name' in krx.columns:
            return krx.rename(columns={'Symbol': 'Code'})[['Code', 'Name']]
        return krx
    except Exception:
        fallback_data = {
            'Code': ['233740', '229200', '137400', '088800', '005930', '069500'],
            'Name': ['KODEX 코스닥150레버리지', 'KODEX 코스닥150선물인버스', '피엔티', '에이스테크', '삼성전자', 'KODEX 200']
        }
        return pd.DataFrame(fallback_data)

krx_df = get_krx_list()

# 상단 입력창 (기본값: KODEX 코스닥150레버리지 233740)
col_in1, col_in2 = st.columns([2, 1])
with col_in1:
    user_input = st.text_input(
        "🔍 종목코드(6자리) 또는 종목명 입력",
        value="233740",
        placeholder="예: 삼성전자 005930"
    ).strip()
with col_in2:
    years_back = st.selectbox("조회 기간", options=[2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")

stock_code = user_input
stock_name = user_input

if not krx_df.empty:
    krx_df['Code'] = krx_df['Code'].astype(str).str.zfill(6)
    
    if user_input.isdigit() and len(user_input) <= 6:
        target_code = user_input.zfill(6)
        match = krx_df[krx_df['Code'] == target_code]
        if not match.empty:
            stock_code = target_code
            stock_name = match['Name'].iloc[0]
    else:
        match = krx_df[krx_df['Name'].str.contains(user_input, na=False)]
        if not match.empty:
            stock_code = match['Code'].iloc[0]
            stock_name = match['Name'].iloc[0]

def r10(val):
    return int(np.floor(val / 10.0 + 0.5) * 10)

def style_table(df_target, df_full):
    cols_grad = ['MM', 'PM', 'LM', 'RM']
    col_bounds = {}
    for c in cols_grad:
        vals = pd.to_numeric(df_full[c], errors='coerce')
        col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = [''] * len(row)
        
        curr_close = row['종가(B)']
        prev_close = None
        if row_idx > 0:
            prev_close = df_full.iloc[row_idx - 1]['종가(B)']

        for idx, col_name in enumerate(row.index):
            val = row[col_name]
            
            # ① 종가(B) 및 등락률(C): 전일 대비 상승 붉은색, 하락 파란색, 보합 검은색
            if col_name in ['종가(B)', '등락률(C)']:
                if prev_close is not None:
                    if curr_close > prev_close:
                        styles[idx] = 'color: #D32F2F; font-weight: bold;'
                    elif curr_close < prev_close:
                        styles[idx] = 'color: #1976D2; font-weight: bold;'
                    else:
                        styles[idx] = 'color: #111111; font-weight: normal;'
                else:
                    styles[idx] = 'color: #111111;'

            # ② S값 태그 스타일 적용
            elif col_name == 'S':
                try:
                    s_num = float(val)
                    if s_num > 0:
                        styles[idx] = 'background-color: #FFCDD2; color: #B71C1C; font-weight: 900; padding: 2px 6px; border-radius: 12px; display: inline-block;'
                    elif s_num < 0:
                        styles[idx] = 'background-color: #BBDEFB; color: #0D47A1; font-weight: 900; padding: 2px 6px; border-radius: 12px; display: inline-block;'
                    else:
                        styles[idx] = 'background-color: #E0E0E0; color: #333333; font-weight: bold; padding: 2px 6px; border-radius: 12px;'
                except:
                    pass

            # ③ 10분할 매수 신호 열 강조
            elif col_name == '매수신호(레버리지)':
                if '10차' in str(val):
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '8차' in str(val) or '9차' in str(val):
                    styles[idx] = 'background-color: #D32F2F; color: #FFFFFF; font-weight: bold;'
                elif '6차' in str(val) or '7차' in str(val):
                    styles[idx] = 'background-color: #FFCDD2; color: #B71C1C; font-weight: bold;'
                elif '4차' in str(val) or '5차' in str(val):
                    styles[idx] = 'background-color: #FFE0B2; color: #E65100; font-weight: bold;'
                elif '1차' in str(val) or '2차' in str(val) or '3차' in str(val):
                    styles[idx] = 'background-color: #FFF9C4; color: #F57F17; font-weight: bold;'
                elif '스위칭' in str(val):
                    styles[idx] = 'background-color: #E3F2FD; color: #0D47A1; font-weight: bold;'

            # ④ MM, PM, LM, RM 열: 알약 태그형 그라데이션
            elif col_name in cols_grad:
                try:
                    v = float(val)
                    vmin, vmax = col_bounds.get(col_name, (0, 1))
                    ratio = 0.0 if vmax == vmin else (v - vmin) / (vmax - vmin)
                    ratio = max(0.0, min(1.0, float(ratio)))
                    
                    r = int(255 - ratio * (255 - 220))
                    g = int(240 - ratio * (240 - 80))
                    b = int(240 - ratio * (240 - 80))
                    txt_color = '#FFFFFF' if ratio > 0.5 else '#222222'
                    fw = 'bold' if ratio > 0.4 else 'normal'
                    styles[idx] = f'background-color: #{r:02x}{g:02x}{b:02x}; color: {txt_color}; font-weight: {fw}; padding: 2px 6px; border-radius: 8px;'
                except:
                    pass
        return styles

    return (
        df_target.style
        .apply(lambda row: color_styler(row.name, row), axis=1)
        .format({
            '종가(B)': '{:,}',
            '중심선(D)': '{:,}',
            '거래량(E)': '{:,}',
            '거래비율(F)': '{:.2f}'
        })
    )

def calculate_ultima_sheet(df_raw):
    df = df_raw.copy().reset_index(drop=True)
    closes = df['Close'].astype(float).values
    vols = df['Volume'].astype(float).values
    dates = pd.to_datetime(df['Date']).values
    n = len(closes)

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / closes[:-1]) - 1.0

    ema = np.zeros(n)
    ema[0] = closes[0]
    for i in range(1, n):
        ema[i] = round((ema[i - 1] * 6.0 + closes[i]) / 7.0)

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    l_col, m_col, n_col, p_col, q_col, r_col = [None]*n, [None]*n, [None]*n, [None]*n, [None]*n, [None]*n
    buy_signals = []

    state = 'UP'
    peak = int(closes[0])
    trough = int(closes[0])
    first_M = int(closes[0])
    first_Q = int(closes[0])
    up_phase = 'M'
    down_phase = 'Q'

    M8 = int(closes[0])
    N8 = int(closes[0])
    P8 = int(closes[0])
    Q8 = int(closes[0])

    L9, M9, N9, P9, Q9, R9 = 0, 0, 0, 0, 0, 0

    for i in range(n):
        p = int(round(closes[i]))

        if state == 'UP':
            if p > peak:
                peak = p
                l5_target = r10(first_M * 1.045)
                n_trigger = min(l5_target, N8) if N8 > 0 else l5_target
                if up_phase == 'N' or p >= n_trigger:
                    up_phase = 'N'
                    n_col[i] = p
                    N9 = p
                else:
                    m_col[i] = p
                    M9 = p
            elif p == peak and i > 0:
                if up_phase == 'N':
                    n_col[i] = '-'
                else:
                    m_col[i] = '-'
            else:
                down_turn_price = r10(peak * (1.0 - 0.095))
                if p <= down_turn_price:
                    if up_phase == 'N':
                        N8 = peak
                    else:
                        M8 = peak
                    state = 'DOWN'
                    trough = p
                    first_Q = p
                    r5_target = r10(first_Q * (1.0 - 0.045))
                    p_trigger = max(r5_target, P8) if P8 > 0 else r5_target
                    if p <= p_trigger:
                        down_phase = 'P'
                        p_col[i] = p
                        P9 = p; Q9 = 0; R9 = 0
                    else:
                        down_phase = 'Q'
                        q_col[i] = p
                        Q9 = p; P9 = 0; R9 = 0
                elif p <= r10(peak * 0.955):
                    r_col[i] = p
                    R9 = p
        else:
            if p < trough:
                trough = p
                r5_target = r10(first_Q * (1.0 - 0.045))
                p_trigger = max(r5_target, P8) if P8 > 0 else r5_target
                if down_phase == 'P' or p <= p_trigger:
                    down_phase = 'P'
                    p_col[i] = p
                    P9 = p
                else:
                    q_col[i] = p
                    Q9 = p
            elif p == trough and i > 0:
                if down_phase == 'P':
                    p_col[i] = '-'
                else:
                    q_col[i] = '-'
            else:
                up_turn_price = r10(trough * 1.095)
                if p >= up_turn_price:
                    if down_phase == 'P':
                        P8 = trough
                    else:
                        Q8 = trough
                    state = 'UP'
                    peak = p
                    first_M = p
                    l5_target = r10(first_M * 1.045)
                    n_trigger = min(l5_target, N8) if N8 > 0 else l5_target
                    if p >= n_trigger:
                        up_phase = 'N'
                        n_col[i] = p
                        N9 = p; M9 = 0; L9 = 0
                    else:
                        up_phase = 'M'
                        m_col[i] = p
                        M9 = p; N9 = 0; L9 = 0
                elif p >= r10(trough * 1.045):
                    l_col[i] = p
                    L9 = p

        max_mn = max(M8, N8)
        min_pq = min(P8, Q8)
        mm = int(round((max_mn / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        pm = int(round((p / max_mn - 1.0) * 100)) if max_mn > 0 else 0
        lm = int(round((p / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        s_val = lm - mm

        # S값 기준 10분할 매수 및 인버스 스위칭 자동 판정 로직
        if s_val <= -50:
            sig = "🔥 10차 풀베팅 (바닥)"
            invest_pct = "100% (3,000만)"
            cash_pct = "0% (0원)"
        elif s_val <= -45:
            sig = "🔥 9차 매수"
            invest_pct = "90% (2,700만)"
            cash_pct = "10% (300만)"
        elif s_val <= -40:
            sig = "🚨 8차 매수"
            invest_pct = "80% (2,400만)"
            cash_pct = "20% (600만)"
        elif s_val <= -35:
            sig = "🚨 7차 매수"
            invest_pct = "70% (2,100만)"
            cash_pct = "30% (900만)"
        elif s_val <= -30:
            sig = "⚠️ 6차 매수"
            invest_pct = "60% (1,800만)"
            cash_pct = "40% (1,200만)"
        elif s_val <= -25:
            sig = "⚠️ 5차 매수"
            invest_pct = "50% (1,500만)"
            cash_pct = "50% (1,500만)"
        elif s_val <= -20:
            sig = "⚠️ 4차 매수"
            invest_pct = "40% (1,200만)"
            cash_pct = "60% (1,800만)"
        elif s_val <= -15:
            sig = "🔍 3차 매수"
            invest_pct = "30% (900만)"
            cash_pct = "70% (2,100만)"
        elif s_val <= -10:
            sig = "🔍 2차 매수"
            invest_pct = "20% (600만)"
            cash_pct = "80% (2,400만)"
        elif s_val <= -5:
            sig = "🔍 1차 입질"
            invest_pct = "10% (300만)"
            cash_pct = "90% (2,700만)"
        elif s_val >= 20:
            sig = "🔄 인버스 스위칭"
            invest_pct = "인버스 100%"
            cash_pct = "현금 0%"
        else:
            sig = "대기 및 관망"
            invest_pct = "현금 보유"
            cash_pct = "현금 보유"

        d_cur = pd.Timestamp(dates[i])
        d_start = d_cur - pd.DateOffset(years=1)
        w_slice = closes[:i+1][pd.to_datetime(dates[:i+1]) >= d_start]
        rm = int(round((w_slice.max() / w_slice.min() - 1.0) * 100)) if len(w_slice) > 0 and w_slice.min() > 0 else 0

        mm_list.append(mm); pm_list.append(pm); lm_list.append(lm)
        s_list.append(s_val); rm_list.append(rm); buy_signals.append(sig)

    def fmt_pos(col_data):
        res = []
        for v in col_data:
            if v is None:
                res.append("")
            elif isinstance(v, (int, np.integer)):
                res.append(f"{v:,}")
            else:
                res.append(str(v))
        return res

    df_out = pd.DataFrame({
        '일자': pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d'),
        '종가(B)': closes.astype(int),
        '등락률(C)': [f"{x*100:+.2f}%" for x in chg],
        '매수신호(레버리지)': buy_signals,
        '중심선(D)': ema.astype(int),
        '거래량(E)': vols.astype(int),
        '거래비율(F)': vol_ratio,
        'MM': mm_list,
        'PM': pm_list,
        'LM': lm_list,
        'S': s_list,
        'RM': rm_list,
        '부-반등(L)': fmt_pos(l_col),
        '반등(M)': fmt_pos(m_col),
        '상-추세(N)': fmt_pos(n_col),
        '하-추세(P)': fmt_pos(p_col),
        '조정(Q)': fmt_pos(q_col),
        '부-조정(R)': fmt_pos(r_col)
    })

    B1 = int(closes[-1])
    C1 = int(vols[-1])
    B7 = int(peak)
    C7 = int(trough)
    B8 = r10(B7 * (1.0 - 0.095))
    C8 = r10(C7 * 1.095)
    B9 = r10(B7 * 0.955)
    C9 = r10(C7 * 1.045)

    L5 = r10(first_M * 1.045)
    R5 = r10(first_Q * (1.0 - 0.045))
    F3 = N8 if N8 < L5 else None
    F4 = P8 if P8 > R5 else None
    M5 = F3
    Q5 = F4

    up_u_target = min(L5, M5) if M5 is not None else L5
    down_u_target = max(Q5, R5) if Q5 is not None else R5
    E1 = (up_u_target / B1 - 1.0) * 100 if B1 > 0 else 0
    E2 = (down_u_target / B1 - 1.0) * 100 if B1 > 0 else 0

    summary = {
        'B1': B1, 'C1': C1, 'cur_chg': chg[-1] * 100,
        'B7': B7, 'C7': C7, 'B8': B8, 'C8': C8, 'B9': B9, 'C9': C9,
        'L5': L5, 'M5': M5, 'Q5': Q5, 'R5': R5,
        'up_u_target': up_u_target, 'down_u_target': down_u_target,
        'E1': E1, 'E2': E2,
        'M8': M8, 'N8': N8, 'P8': P8, 'Q8': Q8,
        'L9': L9, 'M9': M9, 'N9': N9, 'P9': P9, 'Q9': Q9, 'R9': R9,
        'MM': mm_list[-1], 'PM': pm_list[-1], 'LM': lm_list[-1],
        'S': s_list[-1], 'RM': rm_list[-1],
        'current_signal': buy_signals[-1],
        'invest_pct': invest_pct,
        'cash_pct': cash_pct,
        'state': "상승 파동 중" if state == 'UP' else "하락 파동 중"
    }
    return df_out, summary

# 데이터 로드 처리
if stock_code:
    start_dt = (datetime.today() - timedelta(days=365 * years_back)).strftime('%Y-%m-%d')
    with st.spinner(f"[{stock_name} ({stock_code})] 실시간 데이터를 불러오는 중입니다..."):
        raw_df = fdr.DataReader(stock_code, start_dt)
        if raw_df is not None:
            raw_df = raw_df.reset_index()
            if 'Date' not in raw_df.columns:
                raw_df.rename(columns={raw_df.columns[0]: 'Date'}, inplace=True)
            if 'Close' not in raw_df.columns and '종가' in raw_df.columns:
                raw_df.rename(columns={'종가': 'Close', '거래량': 'Volume'}, inplace=True)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_ultima_sheet(raw_df)

        st.markdown(f"#### 📌 {stock_name} (`{stock_code}`) — 현재 상태: **{s['state']}** | 현재 매수신호: **{s['current_signal']}**")

        # 핵심 가격 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}% (거래량 {s['C1']:,})")
        c2.metric("3M & S값", f"MM:{s['MM']} / PM:{s['PM']} / LM:{s['LM']}", f"S: {s['S']} | 신호: {s['current_signal']}")
        c3.metric("레버리지 투입 비중", s['invest_pct'], "시드 3,000만 원 기준")
        c4.metric("확보된 현금 (예수금)", s['cash_pct'], "안전 자산 / 대기 자금")

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 일별 수식표 (전체)",
            "🎯 추세 전환일만 보기",
            "📋 상단 요약표 (1~9행 원본)",
            "💾 엑셀 다운로드"
        ])

        with tab1:
            st.caption("📈 S값 기준 [1차 입질 ~ 10차 풀베팅] 및 [인버스 스위칭] 신호가 표에 자동 반영됩니다.")
            df_rev = df_result.iloc[::-1]
            styled_all = style_table(df_rev, df_result)
            st.dataframe(styled_all, use_container_width=True, height=520)

        with tab2:
            pos_cols = ['부-반등(L)', '반등(M)', '상-추세(N)', '하-추세(P)', '조정(Q)', '부-조정(R)']
            mask = (df_result[pos_cols] != "").any(axis=1)
            st.caption("변곡점 가격이 기록된 날만 모아봅니다.")
            df_filtered = df_result[mask].iloc[::-1]
            styled_filtered = style_table(df_filtered, df_result)
            st.dataframe(styled_filtered, use_container_width=True, height=520)

        with tab3:
            st.markdown("##### 🔹 기준가 · 전환가 · 1차가격 · U-Point (엑셀 A1:R9 영역)")
            def fmt_pct(num, den):
                if not num or not den or num < 0.1 or den < 0.1:
                    return "-"
                return f"{(num / den - 1.0) * 100:+.1f}%"

            u_table = pd.DataFrame({
                '구분': ['현재가 대비(1행)', '하추/상추 대비(3행)', '조정/반등 대비(4행)', 'U-Point 목표(5행)', '직전파동(8행)', '현재파동(9행)'],
                '부-반등(L)': [fmt_pct(s['B1'], s['L9']), '-', '-', f"{s['L5']:,}", '-', f"{s['L9']:,}" if s['L9'] else '-'],
                '반등(M)': [fmt_pct(s['B1'], s['M9']), fmt_pct(s['M9'], s['P8']), fmt_pct(s['M9'], s['Q8']), f"{s['M5']:,}" if s['M5'] else '-', f"{s['M8']:,}", f"{s['M9']:,}" if s['M9'] else '-'],
                '상-추세(N)': [fmt_pct(s['B1'], s['N9']), fmt_pct(s['N9'], s['P8']), fmt_pct(s['N9'], s['Q8']), f"목표대비 {s['E1']:+.1f}%", f"{s['N8']:,}", f"{s['N9']:,}" if s['N9'] else '-'],
                '하-추세(P)': [fmt_pct(s['B1'], s['P9']), fmt_pct(s['P9'], s['N8']), fmt_pct(s['P9'], s['M8']), f"목표대비 {s['E2']:+.1f}%", f"{s['P8']:,}", f"{s['P9']:,}" if s['P9'] else '-'],
                '조정(Q)': [fmt_pct(s['B1'], s['Q9']), fmt_pct(s['Q9'], s['N8']), fmt_pct(s['Q9'], s['M8']), f"{s['Q5']:,}" if s['Q5'] else '-', f"{s['Q8']:,}", f"{s['Q9']:,}" if s['Q9'] else '-'],
                '부-조정(R)': [fmt_pct(s['B1'], s['R9']), '-', '-', f"{s['R5']:,}", '-', f"{s['R9']:,}" if s['R9'] else '-']
            })
            st.table(u_table)

        with tab4:
            output = BytesIO()
            sheet_title = f"{stock_name}_{stock_code}"[:31]
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False, sheet_name=sheet_title)
                ws = writer.sheets[sheet_title]
                max_row = len(df_result) + 1
                for col_name in ['MM', 'PM', 'LM', 'RM']:
                    col_idx = df_result.columns.get_loc(col_name) + 1
                    col_letter = get_column_letter(col_idx)
                    cell_range = f"{col_letter}2:{col_letter}{max_row}"
                    rule = ColorScaleRule(
                        start_type='min', start_color='FFF5F5',
                        mid_type='percentile', mid_value=50, mid_color='FFCDD2',
                        end_type='max', end_color='D32F2F'
                    )
                    ws.conditional_formatting.add(cell_range, rule)

            st.download_button(
                label=f"📥 {stock_name}({stock_code}) 10분할 매수신호 엑셀 다운로드",
                data=output.getvalue(),
                file_name=f"모바일분석기_{stock_name}_{stock_code}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("종목 데이터를 찾을 수 없습니다. 6자리 종목코드나 정확한 종목명을 입력해 주세요.")
