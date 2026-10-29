import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from io import BytesIO

# 모바일 화면 최적화 설정
st.set_page_config(
    page_title="간편 교대 매매 분석기 Pro",
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

st.subheader("📈 간편 교대 매매 시스템 (칼날 방어 & 1회 잠금 엔진)")

# 네이버 금융 일별 시세 크롤링 함수
@st.cache_data(ttl=3600)
def get_naver_stock_data(code, count=1250):
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return None, None
        
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
            return None, None
            
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, code
    except Exception as e:
        return None, None

# 주요 종목 빠른 매핑 사전
name_to_code = {
    "삼성전자": "005930",
    "KODEX 코스닥150레버리지": "233740",
    "코스닥150레버리지": "233740",
    "KODEX 200": "069500",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "현대차": "005380"
}

code_to_name = {v: k for k, v in name_to_code.items()}
code_to_name.update({
    "005930": "삼성전자",
    "233740": "KODEX 코스닥150레버리지",
    "069500": "KODEX 200",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "005380": "현대차"
})

def resolve_code_and_name(user_str):
    clean_str = str(user_str).strip()
    if not clean_str:
        return "233740", ""
    
    if clean_str in name_to_code:
        return name_to_code[clean_str], clean_str
    elif clean_str.isdigit():
        code = clean_str.zfill(6)
        name = code_to_name.get(code, f"종목({code})")
        return code, name
    else:
        for k, v in name_to_code.items():
            if clean_str in k:
                return v, k
        return "233740", clean_str

# 🔍 상단 메인 검색 Form
with st.form(key="search_form"):
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        user_input = st.text_input(
            "🔍 조회할 메인 종목 또는 종목코드 입력",
            value="233740",
            placeholder="예: 삼성전자 또는 005930"
        ).strip()
    with col_in2:
        years_back = st.selectbox("조회 기간", options=[1, 2, 3, 5], index=1, format_func=lambda x: f"최근 {x}년")
    with col_in3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        submit_search = st.form_submit_button("🔍 조회하기", use_container_width=True)

stock_code, stock_name = resolve_code_and_name(user_input)

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
                if '격발!' in val_str:
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '장전/대기' in val_str:
                    styles[idx] = 'background-color: #FFF3E0; color: #E65100; font-weight: 900; border: 1px solid #FFB74D;'
                elif '매수완료/잠금' in val_str:
                    styles[idx] = 'background-color: #ECEFF1; color: #455A64; font-weight: bold;'
                elif '입질 실행' in val_str:
                    styles[idx] = 'background-color: #FF8F00; color: #FFFFFF; font-weight: bold;'
                elif '익절 실행' in val_str or '전량 현금화' in val_str:
                    styles[idx] = 'background-color: #1976D2; color: #FFFFFF; font-weight: bold;'
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
    
    opens = pd.to_numeric(df['Open'], errors='coerce').ffill().values
    highs = pd.to_numeric(df['High'], errors='coerce').ffill().values
    lows = pd.to_numeric(df['Low'], errors='coerce').ffill().values
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

    # 최근 5일 평균 거래량 계산 (투매 클라이맥스 감지용)
    vol_ma5 = pd.Series(vols).rolling(5, min_periods=1).mean().values

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    buy_signals = []

    state = 'UP'
    peak = int(closes[0]) if n > 0 else 0
    trough = int(closes[0]) if n > 0 else 0
    first_M = int(closes[0]) if n > 0 else 0
    up_phase = 'M'; down_phase = 'Q'
    M8, N8, P8, Q8 = peak, peak, peak, peak

    # 🔥 [핵심 보강] 차수별 1회 매수 잠금(One-Shot Lock) 및 장전 상태 추적기
    executed_buy_stages = set()   # 현재 하락 사이클에서 이미 매수 완료한 차수 (6, 7, 8, 9, 10)
    executed_sell_stages = set()  # 현재 회복 사이클에서 이미 익절 완료한 차수 (1, 2, 3, 4, 5)
    armed_stage = 0               # S값 도달 후 바닥 확인을 기다리는 장전 차수 (9 또는 10)
    cum_invest_ratio = 0.0        # 실제 집행된 누적 투자 비중

    stage_weights = {6: 0.03, 7: 0.03, 8: 0.03, 9: 0.25, 10: 0.66}

    for i in range(n):
        p = int(round(closes[i]))
        open_p = opens[i]
        high_p = highs[i]
        low_p = lows[i]
        cur_chg = chg[i]
        v_ratio = vol_ratio[i]
        v_spike = (vols[i] >= vol_ma5[i] * 1.4) or (v_ratio >= 1.5)

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

        # ------------------------------------------------------------------
        # 🛡️ [엔진 1] 캔들 하락 둔화 / 반등 확인 트리거 (칼날 잡기 방지)
        # ------------------------------------------------------------------
        candle_range = high_p - low_p
        lower_wick_ratio = (min(p, open_p) - low_p) / candle_range if candle_range > 0 else 0.0
        
        # 칼날 낙하 중인지 판별: 당일 -2% 이상 급락 중이면서 중심선 아래인 경우
        is_falling_knife = (cur_chg <= -0.02) and (p < ema[i])
        
        # 바닥 반등/브레이크 시그널 판별 (아래 4가지 중 1개 이상 만족 시 격발 승인)
        # 1) 양봉 마감 또는 전일 대비 상승 전환 (cur_chg >= 0 또는 p >= open_p)
        # 2) 아래꼬리가 캔들 전체 길이의 35% 이상 달린 밑꼬리 지지 캔들 + 거래량 증가
        # 3) 중심선(7일 EMA) 돌파 회복 (p >= ema[i])
        # 4) 당일 낙폭이 -0.8% 이내로 완전히 멈춘 보합 지지 캔들
        is_rebound_trigger = (
            (cur_chg >= 0.0) or 
            (p >= open_p and cur_chg > -0.015) or 
            (lower_wick_ratio >= 0.35 and v_spike) or 
            (p >= ema[i]) or 
            (cur_chg >= -0.008)
        ) and not is_falling_knife

        # ------------------------------------------------------------------
        # 🛡️ [엔진 2] 장전(Arming) ➔ 격발(Trigger) ➔ 잠금(Lock) 스테이트 머신
        # ------------------------------------------------------------------
        # S값이 0 이상으로 완전 회복되면 매수 잠금 초기화 (새 사이클 준비)
        if s_val >= 0:
            if cum_invest_ratio > 0 or len(executed_buy_stages) > 0:
                sig = "🔵 [5차 최종익절] 전량 현금화 완료 (사이클 초기화)"
                executed_buy_stages.clear()
                armed_stage = 0
                cum_invest_ratio = 0.0
            else:
                sig = "🟢 [관망 대기] S ≥ 0 상단 안전 구간 (현금 100%)"
        else:
            # S값에 따른 목표 매수 차수 계산
            target_buy_stage = 0
            if s_val <= -60 and pm <= -35:
                target_buy_stage = 10
            elif s_val <= -45 and pm <= -25:
                target_buy_stage = 9
            elif s_val <= -35:
                target_buy_stage = 8
            elif s_val <= -30:
                target_buy_stage = 7
            elif s_val <= -25:
                target_buy_stage = 6

            # 9차 또는 10차 도달 시 '장전(Arming)' 상태로 등록 (S값이 살짝 반등해도 장전 유지)
            if target_buy_stage >= 9 and target_buy_stage not in executed_buy_stages:
                armed_stage = max(armed_stage, target_buy_stage)

            # [A] 9차 / 10차 대규모 투하 구간 처리 (장전 후 반등 트리거 확인 시에만 1회 격발)
            if armed_stage in [9, 10] and armed_stage not in executed_buy_stages:
                #もし -60까지 더 내려갔다면 10차로 격상
                if target_buy_stage == 10 and 10 not in executed_buy_stages:
                    armed_stage = 10
                
                if is_rebound_trigger:
                    # 이전 안 산 차수가 있다면 함께 누적 반영
                    for stg in range(6, armed_stage + 1):
                        if stg not in executed_buy_stages:
                            executed_buy_stages.add(stg)
                            cum_invest_ratio = min(1.0, cum_invest_ratio + stage_weights[stg])
                    pct_int = int(round(stage_weights[armed_stage] * 100))
                    cum_int = int(round(cum_invest_ratio * 100))
                    sig = f"🔴 [{armed_stage}차 격발!] 바닥 반등 확인 ➔ 오늘 {pct_int}% 투하 (누적 {cum_int}%)"
                    armed_stage = 0
                    executed_sell_stages.clear()
                else:
                    sig = f"🟠 [{armed_stage}차 장전/대기] 칼날 낙하 중! 절대 매수 금지 (양봉·밑꼬리 대기)"

            # [B] 6~8차 가벼운 입질 구간 처리 (-3% 이상 폭락하는 날은 하루 대기, 각 차수 1회만 실행)
            elif target_buy_stage in [6, 7, 8] and target_buy_stage not in executed_buy_stages:
                if cur_chg <= -0.03:
                    sig = f"🟠 [{target_buy_stage}차 장전/대기] 당일 급락({cur_chg*100:.1f}%) 중 ➔ 진정될 때까지 대기"
                else:
                    for stg in range(6, target_buy_stage + 1):
                        if stg not in executed_buy_stages:
                            executed_buy_stages.add(stg)
                            cum_invest_ratio = min(1.0, cum_invest_ratio + stage_weights[stg])
                    cum_int = int(round(cum_invest_ratio * 100))
                    sig = f"🟡 [{target_buy_stage}차 입질 실행] 3% 매수 (1회 완료 / 누적 {cum_int}%)"
                    executed_sell_stages.clear()

            # [C] 이미 해당 차수를 매수 완료했거나 S값이 반등 중인 구간
            else:
                if len(executed_buy_stages) > 0:
                    max_done = max(executed_buy_stages)
                    # 마이너스 회복 익절 체크 (보유 물량이 있을 때만 1회씩 작동)
                    if s_val >= -5 and 4 not in executed_sell_stages:
                        executed_sell_stages.add(4)
                        cum_invest_ratio = min(cum_invest_ratio, 0.10)
                        sig = "🔵 [4차 익절 실행] S ≥ -5 회복 ➔ 잔여 비중 10%만 남기고 현금화"
                    elif s_val >= -15 and 3 not in executed_sell_stages:
                        executed_sell_stages.add(3)
                        cum_invest_ratio = min(cum_invest_ratio, 0.20)
                        sig = "🔵 [3차 익절 실행] S ≥ -15 회복 ➔ 일부 수익 실현"
                    else:
                        next_stg = max_done + 1
                        next_s = {-6: -25, 7: -30, 8: -35, 9: -45, 10: -60}.get(next_stg, -60)
                        cum_int = int(round(cum_invest_ratio * 100))
                        if max_done < 10:
                            sig = f"🛡️ [{max_done}차 매수완료/잠금] 중복 매수 금지! {next_stg}차(S≤{next_s}) 전까지 대기 (보유 {cum_int}%)"
                        else:
                            sig = f"🛡️ [10차 매수완료/잠금] 모든 매수 종료 ➔ 반등 익절 대기 (보유 {cum_int}%)"
                else:
                    sig = "🟢 [1~5차 관망] 얕은 조정 구간 ➔ 현금 100% 사수"

        invest_pct = f"레버리지 {int(round(cum_invest_ratio * 100))}%"
        cash_pct = f"현금 {100 - int(round(cum_invest_ratio * 100))}%"

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
        'MM': mm_list, 'PM': pm_list, 'LM': lm_list, 'S': s_list, 'RM': rm_list
    })

    summary = {
        'B1': int(closes[-1]), 'C1': int(vols[-1]), 'cur_chg': chg[-1] * 100,
        'MM': mm_list[-1], 'PM': pm_list[-1], 'LM': lm_list[-1], 'S': s_list[-1],
        'current_signal': buy_signals[-1], 'invest_pct': invest_pct, 'cash_pct': cash_pct,
        'invest_ratio': cum_invest_ratio,
        'state': "상승 파동 중" if state == 'UP' else "하락 파동 중"
    }
    return df_out, summary

if stock_code:
    days_count = years_back * 250
    with st.spinner(f"[{stock_name} ({stock_code})] 네이버 금융에서 데이터를 불러오는 중입니다..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=days_count)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_indicator_sheet(raw_df)

        current_s_val = s['S']
        cur_sig = s['current_signal']
        
        # 🔥 직관적 신호등 배너 (장전 / 격발 / 잠금 / 관망 완벽 구분)
        if "격발!" in cur_sig:
            action_title = "🔴 [격발 승인!] 바닥 및 반등 확인 완료 ➔ 오늘 매수 실행하세요!"
            action_desc = "칼날 낙하가 멈추고 반등/지지 시그널이 포착되었습니다. 정해진 비중만큼 오늘 장 마감 전 매수하세요!"
            badge_color = "#D32F2F"
        elif "장전/대기" in cur_sig:
            action_title = "🟠 [장전 완료 / 매수 대기!] S값은 도달했으나 아직 칼날이 떨어지는 중입니다!"
            action_desc = "10월 20~21일 같은 연속 급락 함정 구간입니다! 절대 오늘 사지 마시고 양봉이나 아래꼬리가 나올 때까지 현금을 꽉 쥐고 기다리세요."
            badge_color = "#E65100"
        elif "매수완료/잠금" in cur_sig:
            action_title = "🛡️ [해당 차수 매수 완료 & 잠금] 추가 매수 금지 구간입니다!"
            action_desc = "이미 현 단계 매수를 마쳤습니다. 주가가 옆으로 기거나 조금 더 빠져도 연달아 사지 마시고 다음 차수까지 굳건히 관망하세요."
            badge_color = "#455A64"
        elif "입질 실행" in cur_sig:
            action_title = "🟡 [6~8차 입질 실행] 가볍게 3%만 담으세요!"
            action_desc = "하락세가 진행 중입니다. 오늘 딱 3% 비중만 가볍게 매수하고 다음날부터는 자동으로 잠금(대기) 상태로 전환됩니다."
            badge_color = "#FF8F00"
        elif "익절" in cur_sig:
            action_title = "🔵 [상승 회복 & 익절] 수익을 챙기고 현금을 확보하세요!"
            action_desc = "바닥을 탈출해 S값이 회복 중입니다. 원칙에 따라 분할 익절하여 계좌에 현금을 쌓으세요."
            badge_color = "#1976D2"
        else:
            action_title = "🟢 [안전 관망] 1~5차 얕은 조정 구간입니다. 현금 100% 사수!"
            action_desc = "어설픈 하락이나 요동(휩쏘) 장세에서는 절대 지갑을 열지 마세요."
            badge_color = "#2E7D32"

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 6px solid {badge_color}; padding: 18px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin: 0; color: {badge_color}; font-size: 1.15rem;">{action_title}</h3>
            <p style="margin: 10px 0 0 0; color: #222222; font-size: 0.98rem; line-height: 1.5;">
                <b>현재 S값: <code>S = {current_s_val}</code> (고점대비 PM: {s['PM']}%)</b> | 오늘 신호 ➔ <b>{cur_sig}</b><br>
                💡 <b>[행동 지침]</b> {action_desc}
            </p>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 실제낙폭(PM)", f"S: {s['S']}", f"PM: {s['PM']}% / LM: {s['LM']}%")
        c3.metric("현재 누적 투입 비중", s['invest_pct'])
        c4.metric("보호 중인 현금 비중", s['cash_pct'])

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 통합 표", "🎯 3단계 방어 엔진 설명", "💼 실전 보유 포트폴리오 계산기", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 [장전/대기 🟠] ➔ [격발 🔴] ➔ [매수완료/잠금 🛡️] 시스템이 적용되어 연속 매수와 칼날 잡기를 자동으로 막아줍니다.")
            df_rev = df_result.iloc[::-1]
            st.dataframe(style_table(df_rev, df_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 🛡️ 10월 20~21일 급락 함정을 막아주는 「3단계 방어 알고리즘」")
            engine_guide = [
                {"신호 배지": "🟠 [장전/대기]", "작동 조건": "S ≤ -45 도달 + 주가 급락 진행 중", "행동 지침": "절대 매수 금지! 지하실로 칼날이 떨어지는 중이므로 현금 보존"},
                {"신호 배지": "🔴 [격발!]", "작동 조건": "장전 상태에서 첫 양봉 / 밑꼬리+거래량 / 하락 멈춤 발생", "행동 지침": "바닥 다지기 확인 완료! 당일 종가에 배정된 비중(9차 25%, 10차 66%) 과감히 투하"},
                {"신호 배지": "🛡️ [매수완료/잠금]", "작동 조건": "해당 차수 매수를 1회 실행한 다음 날부터 자동 발동", "행동 지침": "다음 날 S값이 또 -45 이하라도 중복 매수 원천 차단 (다음 차수 전까지 강제 휴식)"},
                {"신호 배지": "🟡 [입질 실행]", "작동 조건": "S ≤ -25 / -30 / -35 도달 시 (급락일 제외)", "행동 지침": "6~8차 각 3%씩 딱 한 번만 가볍게 입질 후 즉시 잠금 전환"},
            ]
            st.dataframe(pd.DataFrame(engine_guide), use_container_width=True)

            st.markdown("---")
            st.markdown("##### 📉 [-60 확장형] 10단계 비중 배분표")
            buy_guide_data = [
                {"단계": "1~5차", "S값 조건": "S ≥ -20", "실제낙폭(PM) 조건": "무관", "투입 비중": "0% (관망)", "누적 비중": "0%"},
                {"단계": "6차", "S값 조건": "S ≤ -25", "실제낙폭(PM) 조건": "당일 -3% 이상 급락 아닐 것", "투입 비중": "3%", "누적 비중": "3%"},
                {"단계": "7차", "S값 조건": "S ≤ -30", "실제낙폭(PM) 조건": "당일 -3% 이상 급락 아닐 것", "투입 비중": "3%", "누적 비중": "6%"},
                {"단계": "8차", "S값 조건": "S ≤ -35", "실제낙폭(PM) 조건": "당일 -3% 이상 급락 아닐 것", "투입 비중": "3%", "누적 비중": "9%"},
                {"단계": "9차", "S값 조건": "S ≤ -45", "실제낙폭(PM) 조건": "PM ≤ -25% + 반등 트리거 확인", "투입 비중": "25%", "누적 비중": "34%"},
                {"단계": "10차", "S값 조건": "S ≤ -60", "실제낙폭(PM) 조건": "PM ≤ -35% + 반등 트리거 확인", "투입 비중": "66%", "누적 비중": "100%"},
            ]
            st.dataframe(pd.DataFrame(buy_guide_data), use_container_width=True)

        with tab3:
            st.markdown("##### 💼 실전 보유 포트폴리오 다중 종목 성과 분석기")
            st.caption("보유 종목 칸에 **종목명**이나 **6자리 코드**를 입력하고 **[🔍 조회]** 버튼을 누르시면, 네이버 금융 실시간 현재가가 반영되어 총 손익이 계산됩니다.")

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

            if not st.session_state.my_portfolio_items:
                st.info("등록된 보유 종목이 없습니다. [➕ 보유 종목 추가하기] 버튼을 눌러 종목을 추가해 주세요.")
            else:
                for idx, item in enumerate(st.session_state.my_portfolio_items):
                    cols = st.columns([1.6, 0.9, 0.9, 0.9, 1.1, 0.5])
                    with cols[0]:
                        item["input_val"] = st.text_input(f"종목명/코드 {idx+1}", value=item["input_val"], placeholder="예: 005930", key=f"mp_input_{item['id']}")
                    with cols[1]:
                        st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
                        if st.button("🔍 조회", key=f"btn_search_{item['id']}"):
                            c, n = resolve_code_and_name(item["input_val"])
                            item["confirmed_code"] = c
                            item["confirmed_name"] = n
                            st.rerun()
                    with cols[2]:
                        item["qty"] = st.number_input(f"수량 {idx+1}", min_value=0, value=item["qty"], step=1, key=f"mp_qty_{item['id']}")
                    with cols[3]:
                        item["avg_price"] = st.number_input(f"평단가 {idx+1}", min_value=0, value=item["avg_price"], step=10, key=f"mp_price_{item['id']}")
                    
                    live_df, _ = get_naver_stock_data(item["confirmed_code"], count=5)
                    live_curr_price = int(live_df['Close'].iloc[-1]) if live_df is not None and not live_df.empty else item["avg_price"]

                    with cols[4]:
                        disp_name = item["confirmed_name"] if item["confirmed_name"] else "종목 미조회"
                        st.markdown(f"<div style='font-size: 0.75rem; color: #555; margin-bottom: 1px;'><b>{disp_name}</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 1.0rem; font-weight: bold; color: #D32F2F;'>{live_curr_price:,}원</div>", unsafe_allow_html=True)

                    with cols[5]:
                        st.markdown("<div style='margin-top: 22px;'></div>", unsafe_allow_html=True)
                        if st.button("❌", key=f"del_mp_{item['id']}"):
                            items_to_delete.append(item)

                    inv_amt = item["qty"] * item["avg_price"]
                    eval_amt = item["qty"] * live_curr_price
                    total_invested_all += inv_amt
                    total_eval_all += eval_amt

            if items_to_delete:
                for itm in items_to_delete:
                    st.session_state.my_portfolio_items.remove(itm)
                st.rerun()

            st.markdown("---")
            st.markdown("##### 📊 포트폴리오 최종 합계 요약")

            total_pl = total_eval_all - total_invested_all
            total_pl_rate = (total_eval_all / total_invested_all - 1.0) * 100 if total_invested_all > 0 else 0

            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("전체 총 투자원금", f"{total_invested_all:,}원")
            fc2.metric("전체 총 평가금액", f"{total_eval_all:,}원", f"{total_pl_rate:+.2f}%")
            fc3.metric("전체 총 평가 손익", f"{total_pl:,}원", f"{'수익' if total_pl >= 0 else '손실'}")

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
        st.error("종목 데이터를 불러오지 못했습니다. 올바른 종목명이나 6자리 종목코드를 입력해 주세요.")
