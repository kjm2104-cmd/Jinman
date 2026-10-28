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
    page_title="모바일 주식 분석기",
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

st.subheader("📈 모바일 주식 분석기 (시소 교대 매매 시스템)")

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
        prev_close = df_full.iloc[row_idx - 1]['종가(B)'] if row_idx > 0 else None

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
                if '10차' in str(val): styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '8차' in str(val) or '9차' in str(val): styles[idx] = 'background-color: #D32F2F; color: #FFFFFF; font-weight: bold;'
                elif '6차' in str(val) or '7차' in str(val): styles[idx] = 'background-color: #FFCDD2; color: #B71C1C; font-weight: bold;'
                elif '4차' in str(val) or '5차' in str(val): styles[idx] = 'background-color: #FFE0B2; color: #E65100; font-weight: bold;'
                elif '1차' in str(val) or '2차' in str(val) or '3차' in str(val): styles[idx] = 'background-color: #FFF9C4; color: #F57F17; font-weight: bold;'
                elif '스위칭' in str(val): styles[idx] = 'background-color: #E3F2FD; color: #0D47A1; font-weight: bold;'
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

    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format({'종가(B)': '{:,}', '중심선(D)': '{:,}', '거래량(E)': '{:,}', '거래비율(F)': '{:.2f}'})

def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index(drop=True)
    closes = df['Close'].astype(float).values
    vols = df['Volume'].astype(float).values
    dates = pd.to_datetime(df['Date']).values
    n = len(closes)

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / closes[:-1]) - 1.0
    ema = np.zeros(n); ema[0] = closes[0]
    for i in range(1, n): ema[i] = round((ema[i - 1] * 6.0 + closes[i]) / 7.0)

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    buy_signals = []

    state = 'UP'
    peak = int(closes[0]); trough = int(closes[0])
    first_M = int(closes[0]); first_Q = int(closes[0])
    up_phase = 'M'; down_phase = 'Q'
    M8, N8, P8, Q8 = int(closes[0]), int(closes[0]), int(closes[0]), int(closes[0])

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
                state = 'DOWN'; trough = p; first_Q = p
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

        if s_val <= -50:
            sig = "🔥 10차 풀베팅 (바닥)"
            invest_pct = "레버리지 100% (3,000만)"
            cash_pct = "현금 0원"
        elif s_val <= -40:
            sig = "🚨 8~9차 매수"
            invest_pct = "레버리지 80~90%"
            cash_pct = "현금 10~20%"
        elif s_val <= -30:
            sig = "⚠️ 6~7차 매수"
            invest_pct = "레버리지 60~70%"
            cash_pct = "현금 30~40%"
        elif s_val <= -20:
            sig = "⚠️ 4~5차 매수"
            invest_pct = "레버리지 40~50%"
            cash_pct = "현금 50~60%"
        elif s_val <= -10:
            sig = "🔍 1~3차 입질"
            invest_pct = "레버리지 10~30%"
            cash_pct = "현금 70~90%"
        elif s_val >= 20:
            sig = "🔄 인버스 스위칭"
            invest_pct = "인버스 50% (최대 1,500만)"
            cash_pct = "현금 50% (안전 보유)"
        else:
            sig = "대기 및 관망"
            invest_pct = "중립 구간"
            cash_pct = "현금 대기"

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
            if 'Date' not in raw_df.columns: raw_df.rename(columns={raw_df.columns[0]: 'Date'}, inplace=True)
            if 'Close' not in raw_df.columns and '종가' in raw_df.columns: raw_df.rename(columns={'종가': 'Close', '거래량': 'Volume'}, inplace=True)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_indicator_sheet(raw_df)

        # 🚨 [상단 핵심 액션 배너] 오늘의 매매 지시등
        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 5px solid #1976D2; padding: 12px 15px; border-radius: 4px; margin-bottom: 15px;">
            <h4 style="margin: 0; color: #0D47A1;">🎯 오늘의 매매 지시등: <b>{s['current_signal']}</b></h4>
            <p style="margin: 5px 0 0 0; color: #333333; font-size: 0.95rem;">
                현재 상태: <b>{s['state']}</b> | 추천 포트폴리오 비중 ➔ <b>{s['invest_pct']}</b> ({s['cash_pct']})
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 핵심 가격 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 지표", f"S: {s['S']}", f"MM:{s['MM']} / LM:{s['LM']}")
        c3.metric("목표 포트폴리오 비중", s['invest_pct'])
        c4.metric("안전 대기 현금", s['cash_pct'])

        tab1, tab2, tab3 =
