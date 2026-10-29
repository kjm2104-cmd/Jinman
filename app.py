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

# 모바일 가독성 및 표 칸 넓이 최적화 CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; }
    table dataframe, th, td { font-size: 0.82rem !important; padding: 4px 5px !important; }
</style>
""", unsafe_allow_html=True)

st.subheader("📈 간편 교대 매매 시스템 ([매수 추천]·[매도 추천] 표준화)")

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
                styles[idx] = 'color: #D32F2F; font-weight: bold;' if curr_close > prev_close else ('color: #1976D2; font-weight: bold;' if curr_close < prev_close else 'color: #111111;')
            
            elif col_name == '거래량(E)':
                try:
                    curr_vol = float(val)
                    prev_vol = float(df_full.iloc[row.name - 1]['거래량(E)']) if row.name > 0 else curr_vol
                    vol_diff_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                    
                    if vol_diff_ratio >= 0:
                        ratio = min(1.0, vol_diff_ratio / 1.0)
                        r = 255; g = int(240 - ratio * 180); b = int(240 - ratio * 180)
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: {"#B71C1C" if ratio > 0.3 else "#222222"}; font-weight: bold; white-space: nowrap; text-align: right;'
                    else:
                        ratio = min(1.0, abs(vol_diff_ratio) / 0.5)
                        r = int(240 - ratio * 180); g = int(240 - ratio * 180); b = 255
                        styles[idx] = f'background-color: rgb({r}, {g}, {b}); color: {"#0D47A1" if ratio > 0.3 else "#222222"}; font-weight: bold; white-space: nowrap; text-align: right;'
                except:
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
                except:
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
                except:
                    pass

            elif col_name == '매수신호':
                val_str = str(val)
                if '매수 추천' in val_str:
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif val_str == '대기':
                    styles[idx] = 'background-color: #FFF3E0; color: #E65100; font-weight: 900; border: 1px solid #FFB74D; white-space: nowrap;'
                elif val_str == '추가매수금지':
                    styles[idx] = 'background-color: #ECEFF1; color: #455A64; font-weight: bold; white-space: nowrap;'
                elif '매도 추천' in val_str:
                    styles[idx] = 'background-color: #1976D2; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif val_str == '손실중(버티기)':
                    styles[idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold; white-space: nowrap;'
                elif val_str == '관망':
                    styles[idx] = 'color: #2E7D32; font-weight: bold; white-space: nowrap;'
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
    vol_ma5 = pd.Series(vols).rolling(5, min_periods=1).mean().values

    mm_list, pm_list, lm_list, s_list, rm_list = [], [], [], [], []
    buy_signals = []

    state = 'UP'
    peak = int(closes[0]) if n > 0 else 0
    trough = int(closes[0]) if n > 0 else 0
    first_M = int(closes[0]) if n > 0 else 0
    up_phase = 'M'; down_phase = 'Q'
    M8, N8, P8, Q8 = peak, peak, peak, peak

    stage_weights = {1: 0.03, 2: 0.03, 3: 0.03, 4: 0.07, 5: 0.07, 6: 0.30, 7: 0.47}
    
    executed_stages = set()
    cum_invest_ratio = 0.0
    avg_buy_price = 0.0
    last_buy_index = -99

    for i in range(n):
        p = int(round(closes[i]))
        open_p = opens[i]
        high_p = highs[i]
        low_p = lows[i]
        cur_chg = chg[i]
        v_ratio = vol_ratio[i]
        v_spike = (vols[i] >= vol_ma5[i] * 1.2) or (v_ratio >= 1.3)

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

        candle_range = high_p - low_p
        lower_wick_ratio = (min(p, open_p) - low_p) / candle_range if candle_range > 0 else 0.0
        is_falling_knife = (cur_chg <= -0.025) and (p < ema[i])

        is_trigger_ready = (v_spike or lower_wick_ratio >= 0.3 or cur_chg >= -0.015) and not is_falling_knife

        target_stage = 0
        if s_val <= -55: target_stage = 7
        elif s_val <= -52: target_stage = 6
        elif s_val <= -49: target_stage = 5
        elif s_val <= -42: target_stage = 4
        elif s_val <= -35: target_stage = 3
        elif s_val <= -30: target_stage = 2
        elif s_val <= -25: target_stage = 1

        if s_val >= 0:
            if cum_invest_ratio > 0 or len(executed_stages) > 0:
                is_in_profit = (p > avg_buy_price) if avg_buy_price > 0 else True
                if is_in_profit:
                    sig = "매도 추천"
                    executed_stages.clear()
                    cum_invest_ratio = 0.0
                    avg_buy_price = 0.0
                    last_buy_index = -99
                else:
                    sig = "손실중(버티기)"
            else:
                sig = "관망"
        else:
            is_cooldown_passed = (i - last_buy_index >= 2) or (target_stage > max(executed_stages, default=0))

            if target_stage > 0 and target_stage not in executed_stages:
                if is_trigger_ready and is_cooldown_passed:
                    added_weight = 0.0
                    for stg in range(1, target_stage + 1):
                        if stg not in executed_stages:
                            executed_stages.add(stg)
                            added_weight += stage_weights[stg]
                    
                    if added_weight > 0:
                        if cum_invest_ratio == 0:
                            avg_buy_price = p
                        else:
                            old_ratio = cum_invest_ratio
                            cum_invest_ratio = min(1.0, cum_invest_ratio + added_weight)
                            avg_buy_price = (avg_buy_price * old_ratio + p * added_weight) / cum_invest_ratio

                    last_buy_index = i
                    # 🔥 7차는 강력매수 추천, 1~6차는 X차 매수 추천으로 표시
                    if target_stage == 7:
                        sig = "7차 강력매수 추천"
                    else:
                        sig = f"{target_stage}차 매수 추천"
                else:
                    sig = "대기"
            else:
                if len(executed_stages) > 0:
                    max_done = max(executed_stages)
                    is_in_profit = (p > avg_buy_price) if avg_buy_price > 0 else False

                    if s_val >= -15 and is_in_profit and cum_invest_ratio > 0:
                        sig = "매도 추천"
                        executed_stages.clear()
                        cum_invest_ratio = 0.0
                        avg_buy_price = 0.0
                        last_buy_index = -99
                    elif s_val >= -15 and not is_in_profit:
                        sig = "손실중(버티기)"
                    else:
                        sig = "추가매수금지"
                else:
                    sig = "관망"

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
        '매수신호': buy_signals,
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
        
        if "매수 추천" in cur_sig:
            action_title = f"🔴 [{cur_sig}] ➔ 거래량 유입 및 지지 확인 완료! 오늘 매수를 실행하세요"
            action_desc = "하락 진정세와 함께 거래량이 유입되었습니다. 정해진 비중만큼 과감하게 매수를 진행하세요!"
            badge_color = "#D32F2F"
        elif cur_sig == "대기":
            action_title = f"🟠 [대기] ➔ 거래량 유입 및 하락 진정을 기다리는 중입니다"
            action_desc = "S값 조건은 도달했으나 쿨다운(간격) 대기 중이거나 거래량이 부족하므로 매수를 보류하세요."
            badge_color = "#E65100"
        elif cur_sig == "추가매수금지":
            action_title = f"🛡️ [추가매수금지] ➔ 해당 단계 매수 완료! 뇌동매매 금지"
            action_desc = "이미 현 단계 매수를 마쳤습니다. 다음 조건까지 내려가기 전에는 손가락을 잠그고 관망하세요."
            badge_color = "#455A64"
        elif cur_sig == "매도 추천":
            action_title = f"🔵 [{cur_sig}] ➔ 평단가 대비 진짜 수익권입니다! 수익을 실현하세요"
            action_desc = "바닥을 탈출해 평단가 위로 올라왔습니다. 원칙에 따라 분할 매도하여 현금을 확보하세요."
            badge_color = "#1976D2"
        elif cur_sig == "손실중(버티기)":
            action_title = f"🛡️ [손실중(버티기)] ➔ S값은 회복되었으나 손실 중이므로 홀딩합니다"
            action_desc = "지표상 회복 구간에 진입했으나 내 평단가보다 낮으므로 익절하지 않고 안전하게 버팁니다."
            badge_color = "#2E7D32"
        else:
            action_title = f"🟢 [관망] ➔ -25% 안전 구간입니다"
            action_desc = "어설픈 하락이나 요동(휩쏘) 장세에서는 매수를 자제하고 현금 100%를 유지하세요."
            badge_color = "#2E7D32"

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 6px solid {badge_color}; padding: 16px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin: 0; color: {badge_color}; font-size: 1.15rem;">{action_title}</h3>
            <p style="margin: 8px 0 0 0; color: #222222; font-size: 0.95rem; line-height: 1.4;">
                <b>S값: <code>{current_s_val}</code> (고점대비 PM: {s['PM']}%)</b> | 💡 {action_desc}
            </p>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 실제낙폭(PM)", f"S: {s['S']}", f"PM: {s['PM']}% / LM: {s['LM']}%")
        c3.metric("현재 누적 투입 비중", s['invest_pct'])
        c4.metric("보호 중인 현금 비중", s['cash_pct'])

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 표", "🎯 새로운 7단계 가이드", "💼 보유 포트폴리오", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 [X차 매수 추천], [매도 추천] 등 직관적인 표준 용어가 적용된 마스터 표입니다.")
            df_rev = df_result.iloc[::-1]
            st.dataframe(style_table(df_rev, df_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 🎯 [새로운 7단계 맞춤형 매매 가이드]")
            guide_data = [
                {"구분": "🟢 관망", "조건": "S ≥ -20 ( ~ -25)", "비중": "0%", "행동 가이드": "안전 구간 ➔ 현금 100% 사수 (매수 없음)"},
                {"구분": "🟡 1차 매수 추천", "조건": "S ≤ -25 + 거래량/지지 + 쿨다운", "비중": "3%", "행동 가이드": "하락 초입 ➔ 가벼운 입질 매수"},
                {"구분": "🟡 2차 매수 추천", "조건": "S ≤ -30 + 거래량/지지 + 쿨다운", "비중": "3%", "행동 가이드": "하락 진행 ➔ 두 번째 입질 매수"},
                {"구분": "🟡 3차 매수 추천", "조건": "S ≤ -35 + 거래량/지지 + 쿨다운", "비중": "3%", "행동 가이드": "하락 심화 ➔ 세 번째 입질 매수"},
                {"구분": "🟠 4차 매수 추천", "조건": "S ≤ -42 + 거래량/지지 + 쿨다운", "비중": "7%", "행동 가이드": "공포 진입 ➔ 7% 비중 확대 매수"},
                {"구분": "🟠 5차 매수 추천", "조건": "S ≤ -49 + 거래량/지지 + 쿨다운", "비중": "7%", "행동 가이드": "깊은 공포 ➔ 7% 추가 비중 매수"},
                {"구분": "🔴 6차 매수 추천", "조건": "S ≤ -52 + 거래량/지지 + 쿨다운", "비중": "30%", "행동 가이드": "🔥 **[화력 집중]** 30% 대규모 물량 매수"},
                {"구분": "🔴 7차 강력매수 추천", "조건": "S ≤ -55 + 거래량/지지 + 쿨다운", "비중": "47% (잔여 전액)", "행동 가이드": "🚨 **[최후 승부수]** 남은 현금 올인 강력매수"},
                {"구분": "🔵 매도 추천", "조건": "S값 회복 + **현재가 > 평단가**", "비중": "현금화", "행동 가이드": "진짜 수익권일 때만 깔끔하게 분할 매도"},
                {"구분": "🛡️ 손실중(버티기)", "조건": "S값 회복 + **현재가 ≤ 평단가**", "비중": "홀딩 유지", "행동 가이드": "아직 마이너스이므로 익절하지 않고 버팀"},
                {"구분": "🔒 추가매수금지", "조건": "매수 완료 후 다음 조건 미달성", "비중": "잠금", "행동 가이드": "추가 매수를 막고 뇌동매매 방지"},
            ]
            st.dataframe(pd.DataFrame(guide_data), use_container_width=True)

        with tab3:
            st.markdown("##### 💼 실전 보유 포트폴리오 다중 종목 성과 분석기")
            st.caption("보유 종목 칸에 **종목명**이나 **6자리 코드**를 입력하고 **[🔍 조회]** 버튼을 누르시면 현재가가 반영됩니다.")

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
