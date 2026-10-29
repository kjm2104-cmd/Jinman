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

st.subheader("📈 간편 교대 매매 시스템 (7단계 자동 금액 계산기 탑재)")

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
                    'Date': dt, 'Open': float(vals[1]), 'High': float(vals[2]),
                    'Low': float(vals[3]), 'Close': float(vals[4]), 'Volume': float(vals[5])
                })
        
        if not data: return None, None
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, code
    except:
        return None, None

name_to_code = {
    "코스피지수": "KOSPI", "코스닥지수": "KOSDAQ",
    "삼성전자": "005930", "KODEX 코스닥150레버리지": "233740", "코스닥150레버리지": "233740",
    "KODEX 200": "069500", "SK하이닉스": "000660", "LG에너지솔루션": "373220", "현대차": "005380"
}
code_to_name = {v: k for k, v in name_to_code.items()}

def resolve_code_and_name(user_str):
    clean_str = str(user_str).strip()
    if not clean_str: return "233740", ""
    if clean_str in name_to_code: return name_to_code[clean_str], clean_str
    if clean_str.isdigit():
        code = clean_str.zfill(6)
        return code, code_to_name.get(code, f"종목({code})")
    for k, v in name_to_code.items():
        if clean_str in k: return v, k
    return "233740", clean_str

with st.form(key="search_form"):
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        user_input = st.text_input("🔍 조회할 메인 종목 또는 종목코드 입력", value="233740").strip()
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
                styles[idx] = 'font-weight: bold; text-align: right;'
            elif col_name == 'S':
                try:
                    s_num = float(val)
                    if s_num > 0:
                        styles[idx] = 'color: #B71C1C; font-weight: 900; padding: 2px 6px; border-radius: 8px;'
                    elif s_num < 0:
                        styles[idx] = 'color: #0D47A1; font-weight: 900; padding: 2px 6px; border-radius: 8px;'
                except: pass
            elif col_name == '매수신호':
                val_str = str(val)
                if '진입 구간' in val_str:
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
                elif val_str == '대기':
                    styles[idx] = 'background-color: #FFF3E0; color: #E65100; font-weight: 900; white-space: nowrap;'
                elif val_str == '매도 추천':
                    styles[idx] = 'background-color: #1976D2; color: #FFFFFF; font-weight: 900; white-space: nowrap;'
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

        target_stage = 0
        if s_val <= -55: target_stage = 7
        elif s_val <= -52: target_stage = 6
        elif s_val <= -49: target_stage = 5
        elif s_val <= -42: target_stage = 4
        elif s_val <= -35: target_stage = 3
        elif s_val <= -30: target_stage = 2
        elif s_val <= -25: target_stage = 1

        if target_stage in [1, 2, 3]:
            is_trigger_ready = (cur_chg >= -0.035) and not is_falling_knife
        else:
            is_trigger_ready = (v_spike or lower_wick_ratio >= 0.3 or cur_chg >= -0.015) and not is_falling_knife

        if s_val >= 0:
            if s_val >= -15: sig = "매도 추천"
            else: sig = "관망"
        else:
            is_cooldown_passed = (i - last_buy_index >= 1)

            if target_stage > 0:
                if is_trigger_ready and is_cooldown_passed:
                    last_buy_index = i
                    if target_stage == 7: sig = "7차 바닥 진입 구간"
                    else: sig = f"{target_stage}차 진입 구간"
                else: sig = "대기"
            else: sig = "관망"

        mm_list.append(mm); pm_list.append(pm); lm_list.append(lm)
        s_list.append(s_val); rm_list.append(0); buy_signals.append(sig)

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
        'B1': int(closes[-1]), 'cur_chg': chg[-1] * 100,
        'PM': pm_list[-1], 'LM': lm_list[-1], 'S': s_list[-1],
        'current_signal': buy_signals[-1]
    }
    return df_out, summary

kospi_df, _ = get_naver_stock_data("KOSPI", count=5)
kosdaq_df, _ = get_naver_stock_data("KOSDAQ", count=5)

kospi_val = int(kospi_df['Close'].iloc[-1]) if kospi_df is not None and not kospi_df.empty else 0
kospi_chg = ((kospi_df['Close'].iloc[-1] / kospi_df['Close'].iloc[-2]) - 1.0) * 100 if kospi_df is not None and len(kospi_df) >= 2 else 0.0

kosdaq_val = int(kosdaq_df['Close'].iloc[-1]) if kosdaq_df is not None and not kosdaq_df.empty else 0
kosdaq_chg = ((kosdaq_df['Close'].iloc[-1] / kosdaq_df['Close'].iloc[-2]) - 1.0) * 100 if kosdaq_df is not None and len(kosdaq_df) >= 2 else 0.0

if stock_code:
    days_count = years_back * 250
    with st.spinner(f"[{stock_name} ({stock_code})] 네이버 금융에서 데이터를 불러오는 중입니다..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=days_count)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_indicator_sheet(raw_df)

        current_s_val = s['S']
        cur_sig = s['current_signal']
        
        if "진입 구간" in cur_sig: badge_color = "#D32F2F"
        elif cur_sig == "대기": badge_color = "#E65100"
        elif cur_sig == "매도 추천": badge_color = "#1976D2"
        else: badge_color = "#2E7D32"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{stock_name} 현재가", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 / 낙폭(PM)", f"S: {s['S']}", f"PM: {s['PM']}%")
        c3.metric("코스피(KOSPI) 지수", f"{kospi_val:,}", f"{kospi_chg:+.2f}%")
        c4.metric("코스닥(KOSDAQ) 지수", f"{kosdaq_val:,}", f"{kosdaq_chg:+.2f}%")

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 표", "🎯 7단계 가이드 & 자동금액 계산기", "💼 보유 포트폴리오", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 1~3차 선제적 진입 및 코스피·코스닥 지수가 상단에 연동된 실전 마스터 표입니다.")
            df_rev = df_result.iloc[::-1]
            st.dataframe(style_table(df_rev, df_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 🎯 [새로운 7단계 매매 가이드 & 총 자산별 구간별 투입 금액 자동 계산기]")
            st.caption("아래에 **총 투자 예정 금액(시드머니)**을 입력하시면, 7단계 구간별로 투입해야 할 정확한 금액이 자동으로 계산됩니다!")

            # 🔥 총 시드머니 입력 슬라이더 및 숫자 입력 박스
            total_seed = st.number_input("💰 총 투자 예정 금액 (원)", min_value=100000, max_value=10000000000, value=30000000, step=1000000, format="%d")

            # 7단계 비중 정의 (3%, 3%, 3%, 7%, 7%, 30%, 47%)
            guide_rows = [
                {"단계": "🟢 관망", "조건": "S ≥ -20", "비중": 0.0, "행동 가이드": "안전 구간 ➔ 현금 100% 사수"},
                {"단계": "🟡 1차 진입 구간", "조건": "S ≤ -25", "비중": 0.03, "행동 가이드": "하락 초입 ➔ 1차 입질 매수"},
                {"단계": "🟡 2차 진입 구간", "조건": "S ≤ -30", "비중": 0.03, "행동 가이드": "하락 진행 ➔ 2차 입질 매수"},
                {"단계": "🟡 3차 진입 구간", "조건": "S ≤ -35", "비중": 0.03, "행동 가이드": "하락 심화 ➔ 3차 입질 매수"},
                {"단계": "🟠 4차 진입 구간", "조건": "S ≤ -42", "비중": 0.07, "행동 가이드": "공포 진입 ➔ 4차 비중 확대 매수"},
                {"단계": "🟠 5차 진입 구간", "조건": "S ≤ -49", "비중": 0.07, "행동 가이드": "깊은 공포 ➔ 5차 추가 비중 매수"},
                {"단계": "🔴 6차 진입 구간", "조건": "S ≤ -52", "비중": 0.30, "행동 가이드": "🔥 **[화력 집중]** 6차 대규모 물량 매수"},
                {"단계": "🔴 7차 바닥 진입 구간", "조건": "S ≤ -55", "비중": 0.47, "행동 가이드": "🚨 **[최후 승부수]** 잔여 전액 강력매수"},
            ]

            calc_data = []
            for row in guide_rows:
                amt = int(total_seed * row["비중"])
                calc_data.append({
                    "매수 단계": row["단계"],
                    "S값 조건": row["조건"],
                    "투입 비중": f"{int(row['비중']*100)}%",
                    "자동 계산 투입금액": f"{amt:,}원",
                    "행동 가이드": row["행동 가이드"]
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
                        item["confirmed_code"] = c; item["confirmed_name"] = n
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
                    if st.button("❌", key=f"del_mp_{item['id']}"): items_to_delete.append(item)

                total_invested_all += item["qty"] * item["avg_price"]
                total_eval_all += item["qty"] * live_curr_price

            if items_to_delete:
                for itm in items_to_delete: st.session_state.my_portfolio_items.remove(itm)
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
                df_result.to_excel(writer, index=False, sheet_name="Trading_System")
            st.download_button(label="📥 매매전략 엑셀 다운로드", data=output.getvalue(), file_name=f"전략_{stock_code}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
