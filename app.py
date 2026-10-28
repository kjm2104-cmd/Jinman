import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from io import BytesIO

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="간편 교대 매매 분석기 Pro+++++",
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

st.subheader("📈 간편 교대 매매 시스템 (엔터 검색 최적화 버전)")

# 네이버 금융 일별 시세 크롤링 함수
@st.cache_data(ttl=3600)
def get_naver_stock_data(code, count=1250):
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return None
        
        from xml.etree import ElementTree as ET
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
            return None
            
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        return None

# 종목 이름/코드 매핑 사전 (자주 쓰는 주요 종목 빠른 검색 지원)
name_to_code = {
    "삼성전자": "005930",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
    "KODEX 200": "069500",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "현대차": "005380"
}

# 🔍 엔터 입력 및 버튼 클릭이 매끄럽게 작동하도록 Form 구조 적용
with st.form(key="search_form"):
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        user_input = st.text_input(
            "🔍 조회할 종목 또는 종목코드 입력",
            value="233740",
            placeholder="예: 삼성전자 또는 005930"
        ).strip()
    with col_in2:
        years_back = st.selectbox("조회 기간", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
    with col_in3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submit_search = st.form_submit_button("🔍 조회하기", use_container_width=True)

# 입력값 파싱 (종목 이름으로 입력한 경우 코드로 자동 변환)
if user_input in name_to_code:
    stock_code = name_to_code[user_input]
    stock_name = user_input
elif user_input.isdigit():
    stock_code = user_input.zfill(6)
    stock_name = "삼성전자" if stock_code == "005930" else ("KODEX 코스닥150레버리지" if stock_code == "233740" else f"종목코드 {stock_code}")
else:
    # 부분 일치 검색 지원
    found = False
    for k, v in name_to_code.items():
        if user_input in k:
            stock_code = v
            stock_name = k
            found = True
            break
    if not found:
        stock_code = "233740"
        stock_name = "KODEX 코스닥150레버리지"

def r10(val):
    return int(np.floor(val / 10.0 + 0.5) * 10)

def style_table(df_target, df_full):
    cols_grad = ['MM', 'PM', 'LM', 'RM']
    col_bounds = {}
    for c in cols_grad:
        if c in df_full.columns:
            vals = pd.to_numeric(df_full[c], errors='coerce')
            col_bounds[c] = (vals.min(), vals.max())

    def color_styler(row_idx, row):
        styles = [''] * len(row)
        curr_close = row.get('종가(B)', 0)
        prev_close = df_full.iloc[row_idx - 1].get('종가(B)', 0) if row_idx > 0 else None

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
                val_str = str(val)
                if '7차 최종' in val_str or '7차 풀베팅' in val_str or '5차 최종익절' in val_str: 
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '매수' in val_str: 
                    styles[idx] = 'background-color: #D32F2F; color: #FFFFFF; font-weight: bold;'
                elif '익절' in val_str: 
                    styles[idx] = 'background-color: #E3F2FD; color: #0D47A1; font-weight: bold;'
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

    return df_target.style.apply(lambda row: color_styler(row.name, row), axis=1).format({'종가(B)': '{:,}', '중심선(D)': '{:,}', '거래량(E)': '{:,}', '거래비율(F)': '{:.2f}'}, na_rep="-")

def calculate_indicator_sheet(df_raw):
    df = df_raw.copy().reset_index()
    
    closes = pd.to_numeric(df['Close'], errors='coerce').ffill().values
    vols = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).values
    dates = pd.to_datetime(df['Date']).values
    n = len(closes)

    chg = np.zeros(n)
    chg[1:] = (closes[1:] / np.where(closes[:-1] == 0, 1, closes[:-1])) - 1.0
    ema = np.zeros(n); ema[0] = closes[0]
    for i in range(1, n): ema[i] = round((ema[i - 1] * 6.0 + closes[i]) / 7.0)

    vol_ratio = np.zeros(n)
    vol_ratio[1:] = np.round(vols[1:] / np.where(vols[:-1] == 0, 1, vols[:-1]), 2)

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    buy_signals = []

    state = 'UP'
    peak = int(closes[0]) if n > 0 else 0
    trough = int(closes[0]) if n > 0 else 0
    first_M = int(closes[0]) if n > 0 else 0
    up_phase = 'M'; down_phase = 'Q'
    M8, N8, P8, Q8 = peak, peak, peak, peak

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
                state = 'DOWN'; trough = p
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

        # 7단계 매수 / 마이너스 회복 5분할 익절 신호 체계
        if s_val <= -45:
            sig = "🔥 7차 매수 (풀베팅 / 누적 100%)"
            invest_pct = "레버리지 100% (2,700만)"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 1.0
        elif s_val <= -35:
            sig = "🚨 6차 매수 (누적 85%)"
            invest_pct = "레버리지 85%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.85
        elif s_val <= -25:
            sig = "⚠️ 5차 매수 (누적 65%)"
            invest_pct = "레버리지 65%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.65
        elif s_val <= -18:
            sig = "⚠️ 4차 매수 (누적 45%)"
            invest_pct = "레버리지 45%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.45
        elif s_val <= -12:
            sig = "🔍 3차 매수 (누적 30%)"
            invest_pct = "레버리지 30%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.30
        elif s_val <= -7:
            sig = "🔍 2차 매수 (누적 15%)"
            invest_pct = "레버리지 15%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.15
        elif s_val <= -3:
            sig = "🔍 1차 매수 (5%)"
            invest_pct = "레버리지 5%"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.05
        elif s_val >= 0:
            sig = "🔥 5차 최종익절 (전량 현금화 완료)"
            invest_pct = "레버리지 0% (현금 100%)"
            cash_pct = "현금 300만 포함 총 3,000만+"
            invest_ratio = 0.0
        elif s_val >= -5:
            sig = "✨ 4차 익절 (누적 80% 현금화)"
            invest_pct = "레버리지 20% 잔여"
            cash_pct = "현금 80%"
            invest_ratio = 0.20
        elif s_val >= -15:
            sig = "✨ 3차 익절 (누적 60% 현금화)"
            invest_pct = "레버리지 40% 잔여"
            cash_pct = "현금 60%"
            invest_ratio = 0.40
        elif s_val >= -25:
            sig = "✨ 2차 익절 (누적 40% 현금화)"
            invest_pct = "레버리지 60% 잔여"
            cash_pct = "현금 40%"
            invest_ratio = 0.60
        elif s_val >= -35:
            sig = "✨ 1차 익절 (누적 20% 현금화)"
            invest_pct = "레버리지 80% 잔여"
            cash_pct = "현금 20%"
            invest_ratio = 0.80
        else:
            sig = "중립 대기 구간"
            invest_pct = "기존 비중 유지"
            cash_pct = "현금 300만 (안전금고)"
            invest_ratio = 0.50

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
        'invest_ratio': invest_ratio,
        'state': "상승 파동 중" if state == 'UP' else "하락 파동 중"
    }
    return df_out, summary

# 데이터 로드 처리
if stock_code:
    days_count = years_back * 250
    with st.spinner(f"[{stock_name} ({stock_code})] 네이버 금융에서 데이터를 불러오는 중입니다..."):
        raw_df = get_naver_stock_data(stock_code, count=days_count)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_indicator_sheet(raw_df)

        current_s_val = s['S']
        if current_s_val <= -3:
            action_title = "📉 [하락장 매수 모드]"
            action_desc = f"현재 S값({current_s_val})이 하락 구간입니다. 7단계 매수 플랜에 맞춰 비중별로 매수를 진행하세요."
            badge_color = "#D32F2F"
        elif current_s_val >= -35:
            action_title = "📈 [상승장 익절 모드]"
            action_desc = f"현재 S값({current_s_val})이 마이너스 회복 구간입니다. S값 회복 5분할 익절 규칙에 따라 현금화를 실행하세요."
            badge_color = "#1976D2"
        else:
            action_title = "⚖️ [중립 관망 모드]"
            action_desc = f"현재 S값({current_s_val})은 대기 구간입니다. 다음 신호를 기다리세요."
            badge_color = "#555555"

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 5px solid {badge_color}; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
            <h4 style="margin: 0; color: {badge_color};">{action_title} ➔ <b>{s['current_signal']}</b></h4>
            <p style="margin: 8px 0 0 0; color: #333333; font-size: 0.95rem;">
                <b>[실전 가이드]</b> {action_desc}<br>
                추천 포트폴리오 비중 ➔ <b>{s['invest_pct']}</b> ({s['cash_pct']})
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 💼 [종목코드 완벽 분리형 총자산 대시보드]
        with st.expander(f"💼 [자산 관리] '{stock_name} ({stock_code})' 수량 및 실시간 총자산 대시보드", expanded=True):
            col_as1, col_as2 = st.columns(2)
            with col_as1:
                user_safe_cash = st.number_input("고정 안전금고 현금 (원)", min_value=0, value=3000000, step=500000, format="%d", key="safe_cash_input")
            with col_as2:
                st.info(f"현재 조회 중인 종목(`{stock_code}`)의 매매일지 수량만 정확히 반영됩니다.")

            # 매매일지 기반 보유 수량 계산 (엄격한 종목코드 매칭)
            total_shares = 0
            if 'trade_logs' in st.session_state and st.session_state.trade_logs:
                for lg in st.session_state.trade_logs:
                    g = lg.get('구분', '')
                    item_name = str(lg.get('종목', ''))
                    
                    # 💡 핵심: 매매일지 기록에 현재 조회 중인 6자리 종목코드가 포함된 경우만 수량 합산
                    if stock_code not in item_name:
                        continue

                    try:
                        qty = int(lg.get('수량', 0))
                    except:
                        qty = 0
                    
                    if '매수' in g:
                        total_shares += qty
                    elif '익절' in g or '청산' in g:
                        total_shares = max(0, total_shares - qty)

            # 주식 평가금액 = 현재가(B1) * 현재 종목 보유 수량
            current_stock_value = s['B1'] * total_shares
            total_net_asset = current_stock_value + user_safe_cash
            stock_weight = (current_stock_value / total_net_asset) * 100 if total_net_asset > 0 else 0
            cash_weight = (user_safe_cash / total_net_asset) * 100 if total_net_asset > 0 else 0

            c_w1, c_w2, c_w3, c_w4 = st.columns(4)
            c_w1.metric(f"{stock_name} 보유 수량", f"{total_shares:,}주")
            c_w2.metric("주식 평가금액", f"{current_stock_value:,}원", f"{stock_weight:.1f}%")
            c_w3.metric("안전금고 현금", f"{user_safe_cash:,}원", f"{cash_weight:.1f}%")
            c_w4.metric("종목 총자산 평가액", f"{total_net_asset:,}원")

            st.progress(stock_weight / 100.0, text=f"({stock_name}) 총자산 기준 주식 비중: {stock_weight:.1f}% / 현금 비중: {cash_weight:.1f}%")

        # 핵심 가격 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 지표", f"S: {s['S']}", f"MM:{s['MM']} / LM:{s['LM']}")
        c3.metric("포트폴리오 비중", s['invest_pct'])
        c4.metric("안전 대기 현금", s['cash_pct'])

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 통합 표", "🎯 실시간 매매 가이드", "📝 매매일지 (영구 저장)", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 S값 기준 [7단계 매수] 및 [마이너스 회복 5분할 익절]이 통합 반영된 마스터 표입니다.")
            df_rev = df_result.iloc[::-1]
            st.dataframe(style_table(df_rev, df_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 📉 [1단계] 실전 7단계 매수 플랜 (현금 300만 원 고정)")
            buy_guide_data = [
                {"단계": "1차 매수", "S값 조건": "S ≤ -3", "투입 비중": "5% (135만)", "누적 금액": "135만", "설명": "하락 초입 가볍게 입질"},
                {"단계": "2차 매수", "S값 조건": "S ≤ -7", "투입 비중": "10% (270만)", "누적 금액": "405만", "설명": "조정 시 추가 비중 확대"},
                {"단계": "3차 매수", "S값 조건": "S ≤ -12", "투입 비중": "15% (405만)", "누적 금액": "810만", "설명": "하락세 깊어질 때 물량 확보"},
                {"단계": "4차 매수", "S값 조건": "S ≤ -18", "투입 비중": "15% (405만)", "누적 금액": "1,215만", "설명": "중간 지점 비중 안정적 채우기"},
                {"단계": "5차 매수", "S값 조건": "S ≤ -25", "투입 비중": "20% (540만)", "누적 금액": "1,755만", "설명": "깊은 조정 구간 굵직하게 싣기"},
                {"단계": "6차 매수", "S값 조건": "S ≤ -35", "투입 비중": "20% (540만)", "누적 금액": "2,295만", "설명": "공포 확산 바닥권 대규모 담기"},
                {"단계": "7차 풀베팅", "S값 조건": "S ≤ -45", "투입 비중": "15% (405만)", "누적 금액": "2,700만", "설명": "[최종 바닥] 분할 매수 한도 소진 (현금 300만 고정)"},
            ]
            st.dataframe(pd.DataFrame(buy_guide_data), use_container_width=True)

            st.markdown("---")
            st.markdown("##### 📈 [2단계] 마이너스 회복 구간 5분할 익절 가이드")
            st.info("마이너스 회복 구간(-35 ~ 0) 진입 시 아래 S값 조건에 따라 단계별 현금화를 실행하세요.")

            current_s = float(s['S'])
            
            def get_minus_status(min_s):
                return "🟢 도달 완료 (실행)" if current_s >= min_s else "⚪ 대기 중"

            sell_guide_data = [
                {"단계": "1차 익절 (20% 현금화)", "S값 회복 조건": "S ≥ -35", "진행 상태": get_minus_status(-35), "설명": "지하 탈출 첫 번째 반등 시"},
                {"단계": "2차 익절 (20% 현금화)", "S값 회복 조건": "S ≥ -25", "진행 상태": get_minus_status(-25), "설명": "완만한 회복세 진입 시"},
                {"단계": "3차 익절 (20% 현금화)", "S값 회복 조건": "S ≥ -15", "진행 상태": get_minus_status(-15), "설명": "중립 구간 향해 상승 시"},
                {"단계": "4차 익절 (20% 현금화)", "S값 회복 조건": "S ≥ -5", "진행 상태": get_minus_status(-5), "설명": "마이너스 터널 끝자락 도달 시"},
                {"단계": "5차 최종 (잔여 20%)", "S값 회복 조건": "S ≥ 0 (기준선)", "진행 상태": get_minus_status(0), "설명": "[전량 현금화 완료] 현금 300만 원과 함께 다음 폭락장 대기"},
            ]
            st.dataframe(pd.DataFrame(sell_guide_data), use_container_width=True)

        with tab3:
            st.markdown("##### 📝 실시간 모바일 매매일지 (브라우저 세션 저장)")
            
            if 'trade_logs' not in st.session_state:
                st.session_state.trade_logs = []

            with st.form("trade_log_form"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    t_date = st.date_input("거래 일자", datetime.today())
                    t_종목 = st.text_input("종목명", value=f"{stock_name} ({stock_code})")
                    t_qty = st.number_input("거래 수량 (주)", min_value=0, value=100, step=1)
                with col_f2:
                    t_type = st.selectbox("매매 구분", ["레버리지 1~2차 매수 (5%~10%)", "레버리지 3~4차 매수 (15%)", "레버리지 5~6차 매수 (20%)", "레버리지 7차 풀베팅", "마이너스 회복 1~2차 익절", "마이너스 회복 3~5차 익절", "전량 청산 및 현금화", "현금 입금(+)", "현금 출금(-)"])
                    t_price = st.number_input("체결 가격 / 입출금액 (원)", min_value=0, value=int(s['B1']), step=100)
                
                t_amt = st.number_input("투자 금액 / 변동 금액 (원)", min_value=0, value=3000000, step=100000)
                t_memo = st.text_input("메모", placeholder="특이사항이나 매매 사유 입력")
                
                submitted = st.form_submit_button("매매일지 저장하기")
                if submitted:
                    new_log = {
                        "일자": str(t_date), "종목": t_종목, "구분": t_type,
                        "수량": t_qty, "체결가": f"{t_price:,}원", "투자금": f"{t_amt:,}원", "메모": t_memo
                    }
                    st.session_state.trade_logs.insert(0, new_log)
                    st.success("매매일지에 수량과 내역이 안전하게 저장되었습니다!")

            if st.session_state.trade_logs:
                st.markdown("---")
                st.markdown("##### 📋 저장된 매매일지 내역 및 개별 삭제")
                
                log_df = pd.DataFrame(st.session_state.trade_logs)
                st.dataframe(log_df, use_container_width=True)

                col_del1, col_del2 = st.columns([2, 1])
                with col_del1:
                    del_idx = st.selectbox("삭제할 내역 번호 선택", options=range(len(st.session_state.trade_logs)), format_func=lambda x: f"[{x}] {st.session_state.trade_logs[x]['일자']} | {st.session_state.trade_logs[x]['종목']} | {st.session_state.trade_logs[x]['구분']} ({st.session_state.trade_logs[x]['수량']}주)")
                with col_del2:
                    if st.button("🗑️ 선택한 내역 삭제"):
                        removed = st.session_state.trade_logs.pop(del_idx)
                        st.success(f"[{removed['종목']}] 내역이 삭제되었습니다.")
                        st.rerun()

                if st.button("🗑️ 매매일지 전체 초기화"):
                    st.session_state.trade_logs = []
                    st.rerun()
            else:
                st.info("아직 저장된 매매일지가 없습니다.")

        with tab4:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False, sheet_name="Trading_System")
            st.download_button(
                label=f"📥 {stock_name}({stock_code}) 매매전략 엑셀 다운로드",
                data=output.getvalue(),
                file_name=f"모바일분석기_{stock_code}_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("종목 데이터를 불러오지 못했습니다. 올바른 6자리 종목코드(예: 233740, 005930)를 입력해 주세요.")
