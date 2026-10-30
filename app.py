import streamlit as st
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from io import BytesIO

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="울티마(U-Point) 자동 분석기",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 모바일 가독성을 높이는 CSS 스타일
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; }
    table dataframe, th, td { font-size: 0.82rem !important; padding: 4px 5px !important; }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 울티마(U-Point) 모바일 자동 계산기")

# KRX 종목 리스트 캐싱 (종목명/코드 자동 검색용)
@st.cache_data(ttl=86400)
def get_krx_Waitlist():
    try:
        krx = fdr.StockListing('KRX')[['Code', 'Name']]
        return krx
    except Exception:
        return pd.DataFrame(columns=['Code', 'Name'])

krx_df = get_krx_Waitlist()

# 상단 입력창 (종목코드 또는 종목명 입력)
col_in1, col_in2 = st.columns([2, 1])
with col_in1:
    user_input = st.text_input(
        "🔍 종목코드(6자리) 또는 종목명 입력",
        value="137400",
        placeholder="예: 137400, 피엔티, 에이스테크, 005930"
    ).strip()
with col_in2:
    years_back = st.selectbox("조회 기간", options=[3, 4, 5], index=0, format_func=lambda x: f"최근 {x}년")

# 입력값을 종목코드와 종목명으로 변환
stock_code = user_input
stock_name = user_input
if not krx_df.empty:
    if user_input.isdigit() and len(user_input) == 6:
        match = krx_df[krx_df['Code'] == user_input]
        if not match.empty:
            stock_name = match['Name'].iloc[0]
    else:
        match = krx_df[krx_df['Name'] == user_input]
        if not match.empty:
            stock_code = match['Code'].iloc[0]
            stock_name = match['Name'].iloc[0]

def r10(val):
    """엑셀 ROUND(값, -1)과 동일하게 원단위(10원 단위) 반올림"""
    return int(np.floor(val / 10.0 + 0.5) * 10)

def calculate_ultima_sheet(df_raw):
    """과거 값 고정 및 순차적 파동 누적 계산 로직 (엑셀 원본 정석 구현)"""
    df = df_raw.copy().reset_index(drop=True)
    closes = df['Close'].astype(float).values
    vols = df['Volume'].astype(float).values
    dates = pd.to_datetime(df['Date']).values
    n = len(closes)

    # 1. C열(등락률), D열(중심선: α=1/7 지수이동평균), F열(거래비율)
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

    state = 'UP'
    peak = int(closes[0])
    trough = int(closes[0])
    first_M = int(closes[0])
    first_Q = int(closes[0])
    up_phase = 'M'    # 'M'(반등) 또는 'N'(상-추세)
    down_phase = 'Q'  # 'Q'(조정) 또는 'P'(하-추세)

    M8 = int(closes[0])
    N8 = int(closes[0])
    P8 = int(closes[0])
    Q8 = int(closes[0])

    # 순차적 누적 시뮬레이션 (과거 데이터의 계산값이 나중에 변하지 않도록 일자별 상태를 누적 유지)
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
                else:
                    m_col[i] = p
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
                    else:
                        down_phase = 'Q'
                        q_col[i] = p
                elif p <= r10(peak * 0.955):
                    r_col[i] = p
        else:  # state == 'DOWN'
            if p < trough:
                trough = p
                r5_target = r10(first_Q * (1.0 - 0.045))
                p_trigger = max(r5_target, P8) if P8 > 0 else r5_target
                if down_phase == 'P' or p <= p_trigger:
                    down_phase = 'P'
                    p_col[i] = p
                else:
                    q_col[i] = p
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
                    else:
                        up_phase = 'M'
                        m_col[i] = p
                elif p >= r10(trough * 1.045):
                    l_col[i] = p

        # G(MM), H(PM), I(LM), J(S), K(RM) 계산
        max_mn = max(M8, N8)
        min_pq = min(P8, Q8)
        mm = int(round((max_mn / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        pm = int(round((p / max_mn - 1.0) * 100)) if max_mn > 0 else 0
        lm = int(round((p / min_pq - 1.0) * 100)) if min_pq > 0 else 0
        s_val = lm - mm

        # 최근 1년(달력 기준 1년) 최고/최저 대비 RM 계산
        d_cur = pd.Timestamp(dates[i])
        d_start = d_cur - pd.DateOffset(years=1)
        w_slice = closes[:i+1][pd.to_datetime(dates[:i+1]) >= d_start]
        rm = int(round((w_slice.max() / w_slice.min() - 1.0) * 100)) if len(w_slice) > 0 and w_slice.min() > 0 else 0

        mm_list.append(mm); pm_list.append(pm); lm_list.append(lm)
        s_list.append(s_val); rm_list.append(rm)

    df_out = pd.DataFrame({
        '일자': pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d'),
        '종가(B)': closes.astype(int),
        '등락률(C)': [f"{x*100:.2f}%" for x in chg],
        '중심선(D)': ema.astype(int),
        '거래량(E)': vols.astype(int),
        '거래비율(F)': vol_ratio,
        'MM': mm_list,
        'PM': pm_list,
        'LM': lm_list,
        'S': s_list,
        'RM': rm_list,
        '부-반등(L)': l_col,
        '반등(M)': m_col,
        '상-추세(N)': n_col,
        '하-추세(P)': p_col,
        '조정(Q)': q_col,
        '부-조정(R)': r_col
    })

    # 상단 요약표 수식 결과 계산
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
        'MM': mm_list[-1], 'PM': pm_list[-1], 'LM': lm_list[-1],
        'S': s_list[-1], 'RM': rm_list[-1],
        'state': "상승 파동 중" if state == 'UP' else "하락 파동 중"
    }
    return df_out, summary

# 데이터 호출 및 화면 표시
if stock_code:
    start_dt = (datetime.today() - timedelta(days=365 * years_back)).strftime('%Y-%m-%d')
    with st.spinner(f"[{stock_name} ({stock_code})] 데이터를 불러와 수식을 계산 중입니다..."):
        raw_df = fdr.DataReader(stock_code, start_dt)

    if raw_df is not None and not raw_df.empty:
        raw_df = raw_df.reset_index()
        df_result, s = calculate_ultima_sheet(raw_df)

        st.markdown(f"#### 📌 {stock_name} (`{stock_code}`) — 현재 상태: **{s['state']}**")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}% (거래량 {s['C1']:,})")
        c2.metric("3M (MM / PM / LM)", f"{s['MM']} / {s['PM']} / {s['LM']}", f"S: {s['S']} | RM: {s['RM']}")
        c3.metric("상단 기준가 (B7) / 조정전환가 (B8)", f"{s['B7']:,}원", f"전환가 {s['B8']:,}원 | 1차 {s['B9']:,}원")
        c4.metric("하단 기준가 (C7) / 반등전환가 (C8)", f"{s['C7']:,}원", f"전환가 {s['C8']:,}원 | 1차 {s['C9']:,}원")

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 일별 수식표 (전체)",
            "🎯 추세 전환일만 보기",
            "📋 상단 요약표 (1~9행 원본)",
            "💾 엑셀 다운로드"
        ])

        with tab1:
            st.caption("과거 일별 데이터의 계산값이 고정되어 일자별 흐름이 안정적으로 유지됩니다.")
            st.dataframe(df_result.iloc[::-1], use_container_width=True, height=520)

        with tab2:
            pos_cols = ['부-반등(L)', '반등(M)', '상-추세(N)', '하-추세(P)', '조정(Q)', '부-조정(R)']
            mask = df_result[pos_cols].notna().any(axis=1)
            st.caption("추세 변곡점이 발생한 일자만 모아봅니다.")
            st.dataframe(df_result[mask].iloc[::-1], use_container_width=True, height=520)

        with tab3:
            st.markdown("##### 🔹 기준가 · 전환가 · 1차가격 · U-Point")
            def fmt_pct(num, den):
                if not num or not den or num < 0.1 or den < 0.1:
                    return "-"
                return f"{(num / den - 1.0) * 100:+.1f}%"

            u_table = pd.DataFrame({
                '구분': ['현재가 대비(1행)', '하추/상추 대비(3행)', '조정/반등 대비(4행)', 'U-Point 목표(5행)', '직전파동(8행)'],
                '부-반등(L)': [fmt_pct(s['B1'], s.get('L9', 0)), '-', '-', f"{s['L5']:,}", '-'],
                '반등(M)': [fmt_pct(s['B1'], s.get('M9', 0)), '-', '-', f"{s.get('M5', '-')}", f"{s['M8']:,}"],
                '상-추세(N)': [fmt_pct(s['B1'], s.get('N9', 0)), '-', '-', f"목표대비 {s['E1']:+.1f}%", f"{s['N8']:,}"],
                '하-추세(P)': [fmt_pct(s['B1'], s.get('P9', 0)), '-', '-', f"목표대비 {s['E2']:+.1f}%", f"{s['P8']:,}"],
                '조정(Q)': [fmt_pct(s['B1'], s.get('Q9', 0)), '-', '-', f"{s.get('Q5', '-')}", f"{s['Q8']:,}"],
                '부-조정(R)': [fmt_pct(s['B1'], s.get('R9', 0)), '-', '-', f"{s['R5']:,}", '-']
            })
            st.table(u_table)

        with tab4:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False, sheet_name=f"{stock_name}_{stock_code}")
            st.download_button(
                label=f"📥 {stock_name}({stock_code}) 계산 결과 엑셀(.xlsx) 다운로드",
                data=output.getvalue(),
                file_name=f"울티마_{stock_name}_{stock_code}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("종목 데이터를 찾을 수 없습니다. 6자리 종목코드나 정확한 종목명을 입력해 주세요.")
