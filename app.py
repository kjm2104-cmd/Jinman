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

st.subheader("📈 간편 교대 매매 시스템 (직관적 10단계 시그널 대시보드)")

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
                if '10차' in val_str or '9차' in val_str: 
                    styles[idx] = 'background-color: #B71C1C; color: #FFFFFF; font-weight: 900;'
                elif '매수' in val_str or '입질' in val_str: 
                    styles[idx] = 'background-color: #FF8F00; color: #FFFFFF; font-weight: bold;'
                elif '익절' in val_str: 
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

        # 🔥 직관적인 10단계 시그널 명칭 부여
        if s_val <= -60:
            sig = "🔴 [10차] 풀베팅 (바닥 -60% / 현금소진)"
            invest_pct = "레버리지 100%"
            cash_pct = "현금 소진"
            invest_ratio = 1.0
        elif s_val <= -45:
            sig = "🔴 [9차] 대규모 투하 (비중 25%)"
            invest_pct = "레버리지 49%"
            cash_pct = "현금 관리"
            invest_ratio = 0.49
        elif s_val <= -35:
            sig = "🟡 [8차] 가벼운 입질 (3%)"
            invest_pct = "레버리지 9%"
            cash_pct = "현금 관리"
            invest_ratio = 0.09
        elif s_val <= -30:
            sig = "🟡 [7차] 가벼운 입질 (3%)"
            invest_pct = "레버리지 6%"
            cash_pct = "현금 관리"
            invest_ratio = 0.06
        elif s_val <= -25:
            sig = "🟡 [6차] 첫 번째 입질 (3%)"
            invest_pct = "레버리지 3%"
            cash_pct = "현금 관리"
            invest_ratio = 0.03
        elif s_val <= -20:
            sig = "🟢 [1~5차] 철저한 관망 (0%)"
            invest_pct = "레버리지 0% (관망)"
            cash_pct = "현금 100% 사수"
            invest_ratio = 0.0
        elif s_val >= 0:
            sig = "🔵 [익절] 전량 현금화 완료"
            invest_pct = "레버리지 0%"
            cash_pct = "현금 100%"
            invest_ratio = 0.0
        else:
            sig = "🟢 [1~5차] 관망 대기 (0%)"
            invest_pct = "기존 비중 유지"
            cash_pct = "현금 100% 사수"
            invest_ratio = 0.0

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

if stock_code:
    days_count = years_back * 250
    with st.spinner(f"[{stock_name} ({stock_code})] 네이버 금융에서 데이터를 불러오는 중입니다..."):
        raw_df, _ = get_naver_stock_data(stock_code, count=days_count)

    if raw_df is not None and not raw_df.empty:
        df_result, s = calculate_indicator_sheet(raw_df)

        current_s_val = s['S']
        
        # 🔥 한눈에 띄는 직관적 신호등 상태 배너 디자인
        if current_s_val <= -45:
            action_title = "🚨 [긴급] 9~10차 대규모 투하 / 풀베팅 구간!"
            action_desc = "시장 패닉 공포 구간입니다. 거래량 폭증 및 하락 둔화(아래꼬리)를 확인하고 비중을 크게 실어주세요!"
            badge_color = "#D32F2F" # Red
        elif current_s_val <= -25:
            action_title = "⚠️ [주의] 6~8차 가벼운 입질(각 3%) 구간"
            action_desc = "하락세가 깊어지고 있습니다. 2일 연속 마감 조건을 확인하며 3%씩 가볍게 낚싯대를 던지세요."
            badge_color = "#FF8F00" # Orange
        elif current_s_val >= -20 and current_s_val < 0:
            action_title = "🟢 [안전] 1~5차 철저한 관망 구간"
            action_desc = "얕은 조정이나 휩쏘(요동) 장세입니다. 절대 사지 말고 현금 100%를 굳건히 지키세요!"
            badge_color = "#2E7D32" # Green
        else:
            action_title = "📈 [상승] 익절 및 현금화 구간"
            action_desc = "마이너스 회복 구간입니다. 분할 익절 원칙에 따라 이익을 실현하고 현금을 챙기세요."
            badge_color = "#1976D2" # Blue

        st.markdown(f"""
        <div style="background-color: #F8F9FA; border-left: 6px solid {badge_color}; padding: 18px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin: 0; color: {badge_color}; font-size: 1.2rem;">{action_title}</h3>
            <p style="margin: 10px 0 0 0; color: #222222; font-size: 1.0rem; line-height: 1.4;">
                <b>현재 S값: <code>S = {current_s_val}</code></b> | 현재 신호 ➔ <b>{s['current_signal']}</b><br>
                💡 <b>[오늘의 행동 지침]</b> {action_desc}
            </p>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가 (B1)", f"{s['B1']:,}원", f"{s['cur_chg']:+.2f}%")
        c2.metric("S값 지표", f"S: {s['S']}", f"MM:{s['MM']} / LM:{s['LM']}")
        c3.metric("기준 지표 상태", s['state'])
        c4.metric("추천 현금 비중", s['cash_pct'])

        tab1, tab2, tab3, tab4 = st.tabs(["📊 매수·매도 통합 표", "🎯 한눈에 보는 매매 가이드", "💼 실전 보유 포트폴리오 계산기", "💾 엑셀 다운로드"])

        with tab1:
            st.caption("📈 S값 기준 10단계 매수신호등 시스템이 색상과 함께 마스터 표에 반영되어 있습니다.")
            df_rev = df_result.iloc[::-1]
            st.dataframe(style_table(df_rev, df_result), use_container_width=True, height=520)

        with tab2:
            st.markdown("##### 🚦 신호등 체계로 보는 10단계 실전 매수 마스터 플랜")
            buy_guide_data = [
                {"신호등 색상": "🟢 초록불 (관망)", "단계": "1~5차 매수", "S값 조건": "S ≥ -20", "투입 비중": "0% (대기)", "행동 지침": "얕은 조정·요동 장세 무시 / 현금 100% 사수"},
                {"신호등 색상": "🟡 노란불 (입질)", "단계": "6차 매수", "S값 조건": "S ≤ -25", "투입 비중": "3%", "행동 지침": "2일 연속 마감 확인 후 첫 번째 가벼운 입질"},
                {"신호등 색상": "🟡 노란불 (입질)", "단계": "7차 매수", "S값 조건": "S ≤ -30", "투입 비중": "3%", "행동 지침": "공포가 누적될 때 두 번째 입질"},
                {"신호등 색상": "🟡 노란불 (입질)", "단계": "8차 매수", "S값 조건": "S ≤ -35", "투입 비중": "3%", "행동 지침": "하락 밴드 깊어지는 구간 마지막 가벼운 입질"},
                {"신호등 색상": "🔴 빨간불 (투하)", "단계": "9차 매수", "S값 조건": "S ≤ -45", "투입 비중": "25%", "행동 지침": "[1차 투하] 거래량 폭증 + 하락 둔화 시 25% 투입"},
                {"신호등 색상": "🔴 빨간불 (풀베팅)", "단계": "10차 매수", "S값 조건": "S ≤ -60", "투입 비중": "66%", "행동 지침": "[최종 방어] -60 패닉 공포 구간 모든 현금 소진"},
            ]
            st.dataframe(pd.DataFrame(buy_guide_data), use_container_width=True)

            st.markdown("---")
            st.markdown("##### 💡 [핵심 요약 규칙]")
            st.info("• **🟢 초록불(관망)**: 절대 사지 말고 쉬는 구간입니다.\n• **🟡 노란불(입질)**: 3%씩 가볍게 맛만 보는 구간입니다.\n• **🔴 빨간불(투하)**: 바닥권에서 화력을 집중해 물량을 쓸어 담는 구간입니다.")

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

            st.markdown("---")
            if total_pl_rate <= -10:
                st.warning(f"📉 전체 포트폴리오 종합 수익률이 **{total_pl_rate:.2f}%**입니다. 신호등 가이드에 맞춰 냉정하게 자금을 관리하세요.")
            elif total_pl_rate >= 5:
                st.info(f"📈 전체 포트폴리오 종합 수익률이 **{total_pl_rate:.2f}%**로 상승 구간입니다. 익절 가이드에 맞춰 단계별 현금화를 검토해 보세요.")
            else:
                st.success(f"⚖️ 전체 포트폴리오가 안정적인 보합/횡보 구간에 있습니다. (종합 수익률: **{total_pl_rate:.2f}%**)")

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
