import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime
import re
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET

# 1. 화면 설정 (MTS 전체화면)
st.set_page_config(page_title="Pro Trader MTS V17", layout="wide", initial_sidebar_state="collapsed")

# 2. 프리미엄 모바일 MTS 전용 CSS
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    
    .stApp { background-color: #0F1218; color: #F1F5F9; }
    .block-container { padding: 0.8rem 0.5rem 0rem 0.5rem !important; max-width: 100% !important; }
    header { visibility: hidden !important; height: 0px !important; }
    
    /* 깔끔한 MTS 주가 상단 레이아웃 */
    .mts-header { padding: 2px 5px; margin-bottom: 5px; }
    .mts-ticker { font-size: 1.1rem; color: #8B95A1; font-weight: 600; }
    .mts-price-row { display: flex; align-items: baseline; margin-top: 2px; }
    .mts-main-price { font-size: 2.3rem; font-weight: 800; letter-spacing: -1px; }
    .mts-sub-change { font-size: 1.1rem; font-weight: 700; margin-left: 10px; }
    
    /* 고성능 AI 판정 박스 스타일 */
    .pattern-box {
        background: linear-gradient(135deg, #191E28, #121621);
        padding: 14px; border-radius: 14px; border: 1px solid #2A3241;
        margin-bottom: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .pattern-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 700; margin-bottom: 8px; }
    
    /* 실시간 뉴스 박스 */
    .news-box {
        background-color: #191E28; padding: 15px; border-radius: 14px; margin-top: 10px; border: 1px solid #2A3241;
    }
    .news-item { margin-bottom: 10px; font-size: 0.95rem; line-height: 1.4; border-bottom: 1px solid #2A3241; padding-bottom: 8px; }
    .news-item a { color: #E5E8EB; text-decoration: none; }
    .news-item a:hover { color: #3182F6; }
    
    button[data-testid="stPopoverButton"] {
        background-color: #222937 !important; color: #FFFFFF !important;
        border: 1px solid #333D4B !important; border-radius: 10px !important; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# 한국 주식 데이터 로드 세팅
@st.cache_data
def load_ticker_db():
    try:
        import FinanceDataReader as fdr
        return fdr.StockListing('KRX')
    except: return None
krx_df = load_ticker_db()

def get_stock_ticker(name):
    name = name.strip()
    if re.match(r'^[a-zA-Z0-9^.]+$', name): return name
    if krx_df is not None and not krx_df.empty:
        match = krx_df[krx_df['Name'] == name]
        if not match.empty:
            code = match.iloc[0]['Code']
            market = str(match.iloc[0]['Market']).upper()
            return f"{code}.KQ" if 'KOSDAQ' in market else f"{code}.KS"
    return name

# 📡 실시간 구글 뉴스 파싱 함수
@st.cache_data(ttl=600) # 10분마다 뉴스 갱신
def get_realtime_news(keyword):
    try:
        enc_kw = urllib.parse.quote(keyword + " 주식 OR 코인 전망")
        url = f"https://news.google.com/rss/search?q={enc_kw}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req)
        root = ET.fromstring(res.read())
        news_list = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            link = item.find('link').text
            # 출처 태그 잘라내기 깔끔하게
            clean_title = title.rsplit(' - ', 1)[0] if ' - ' in title else title
            news_list.append((clean_title, link))
        return news_list
    except:
        return []

# --- 상단 팝오버 설정창 ---
config_pop = st.popover("⚙️ 종목 및 차트 표시 설정 (터치)")

with config_pop:
    st.subheader("종목 변경")
    asset_type = st.radio("자산군", ["주식", "코인 (Crypto)"], horizontal=True)
    if asset_type == "주식":
        user_input = st.text_input("종목명 입력", "삼성전자")
        ticker = get_stock_ticker(user_input)
        y_int = st.selectbox("차트 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=4)
    else:
        coins = {"비트코인(BTC)":"BTC-USD", "이더리움(ETH)":"ETH-USD", "리플(XRP)":"XRP-USD", "솔라나(SOL)":"SOL-USD", "도지코인(DOGE)":"DOGE-USD"}
        selected_coin = st.selectbox("코인 선택", list(coins.keys()))
        user_input = selected_coin
        ticker = coins[selected_coin]
        y_int = st.selectbox("차트 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=2)
        
    st.subheader("지표 선택")
    show_ma = st.checkbox("지수이평선 (EMA 5/20/60)", True)
    show_bb = st.checkbox("볼린저 밴드", True)
    show_ichi = st.checkbox("☁️ 일목균형표 (구름대)", True)
    show_sig = st.checkbox("AI 매매시그널 마커", True)
    show_macd = st.checkbox("하단 MACD 지표", True)
    show_rsi = st.checkbox("하단 RSI 지표", True)

# --- 데이터 다운로드 ---
with st.spinner('MTS 차트 엔진 구동 중...'):
    if y_int in ['1m','5m','15m','1h']: df = yf.download(ticker, period='7d' if y_int=='1m' else '60d', interval=y_int)
    else: df = yf.download(ticker, period='1y', interval=y_int)

if not df.empty:
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    if df.index.tz is not None: df.index = df.index.tz_localize(None)

    # 기본 핵심 기술 지표 계산
    c = df['Close']
    df['EMA5'] = c.ewm(span=5, adjust=False).mean()
    df['EMA20'] = c.ewm(span=20, adjust=False).mean()
    df['EMA60'] = c.ewm(span=60, adjust=False).mean()
    df['BB_std'] = c.rolling(20).std()
    df['BB_up'], df['BB_low'] = df['EMA20'] + (df['BB_std'] * 2), df['EMA20'] - (df['BB_std'] * 2)
    df['MACD'] = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_H'] = df['MACD'] - df['Signal']
    delta = c.diff()
    df['RSI'] = 100 - (100 / (1 + (delta.clip(lower=0).ewm(13).mean() / -delta.clip(upper=0).ewm(13).mean())))
    df['Buy'] = (df['EMA5'] > df['EMA20']) & (df['EMA5'].shift(1) <= df['EMA20'].shift(1))
    df['Sell'] = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))

    # 일목균형표 계산 부활!
    if len(df)>52:
        df['Senkou_A'] = (((df['High'].rolling(9).max()+df['Low'].rolling(9).min())/2 + (df['High'].rolling(26).max()+df['Low'].rolling(26).min())/2)/2).shift(26)
        df['Senkou_B'] = ((df['High'].rolling(52).max()+df['Low'].rolling(52).min())/2).shift(26)
    else: df['Senkou_A'], df['Senkou_B'] = np.nan, np.nan

    # --- 📊 [혁신] 빅데이터 차트 패턴 매칭 인식 엔진 2.0 ---
    pattern_detected = "⏳ 횡보 및 추세 수렴 구간"
    pattern_desc = "현재 뚜렷한 반등/하락 패턴이 완성되지 않았습니다. 지표의 방향성이 정해질 때까지 분할 대응이 유리합니다."
    sc_modifier = 0

    if len(df) > 30:
        recent_lows = df['Low'].iloc[-30:].values
        recent_highs = df['High'].iloc[-30:].values
        current_p = df['Close'].iloc[-1]
        
        # 1. 박스권 돌파 (Box Breakout)
        if current_p > np.max(recent_highs[:-1]) and df['RSI'].iloc[-1] > 55:
            pattern_detected = "🚀 [박스권 상단 돌파] 대시세 초입"
            pattern_desc = "오랜 기간 갇혀있던 저항선을 뚫고 새로운 시세를 분출하고 있습니다. 강한 추세 추종 스캘핑이 유효합니다."
            sc_modifier += 2

        # 2. 역헤드앤숄더 (Inverse Head & Shoulders)
        elif len(recent_lows) >= 21:
            p1 = np.min(recent_lows[:7]); p2 = np.min(recent_lows[7:14]); p3 = np.min(recent_lows[14:21])
            if p2 < p1 and p2 < p3 and current_p > np.max(recent_highs[-10:]):
                pattern_detected = "👑 [역헤드앤숄더] 완벽한 추세 전환"
                pattern_desc = "가장 신뢰도가 높은 바닥 탈출 패턴입니다. 머리(최저점)를 찍고 오른쪽 어깨를 형성하며 강력하게 반등 중입니다."
                sc_modifier += 3

        # 3. W형 패턴 (쌍바닥)
        elif len(recent_lows) >= 20:
            part1 = recent_lows[:10]; part2 = recent_lows[10:20]
            if abs(np.min(part1) - np.min(part2)) / np.min(part1) < 0.015 and current_p > np.min(part2):
                pattern_detected = "📈 [W형 쌍바닥] 강력한 지지선 형성"
                pattern_desc = "바닥을 두 번 튼튼하게 다진 W패턴입니다. 무한매수법 사이클을 새로 진입하거나 물량을 늘리기에 아주 좋은 타점입니다."
                sc_modifier += 2
                
        # 4. M형 패턴 (쌍고점 경고)
        elif len(recent_highs) >= 20:
            part1_h = recent_highs[:10]; part2_h = recent_highs[10:20]
            if abs(np.max(part1_h) - np.max(part2_h)) / np.max(part1_h) < 0.015 and current_p < np.max(part2_h):
                pattern_detected = "📉 [M형 쌍고점] 단기 폭락 위험"
                pattern_desc = "고점을 뚫지 못하고 무너지는 전형적인 천장 패턴입니다. 지지선 이탈 시 매물 폭탄이 나올 수 있으니 즉각 비중을 줄이세요."
                sc_modifier -= 3
                
        # 5. V자 급반등 (V-Shape Recovery)
        elif df['RSI'].iloc[-3] < 30 and df['RSI'].iloc[-1] > 45 and df['EMA5'].iloc[-1] > df['EMA5'].iloc[-2]:
            pattern_detected = "⚡ [V자 급반등] 투매 후 기술적 반등"
            pattern_desc = "과도한 공포로 인한 투매(패닉셀) 물량을 세력이 받아먹고 끌어올리는 V자 급반등 구간입니다."
            sc_modifier += 1

    # 종합 점수 스코어링 계산
    sc = 0
    if df['EMA5'].iloc[-1] > df['EMA20'].iloc[-1]: sc += 1
    else: sc -= 1
    if df['RSI'].iloc[-1] < 35: sc += 1
    elif df['RSI'].iloc[-1] > 65: sc -= 1
    sc += sc_modifier # 패턴 알고리즘 가중치 강력 적용

    # 신호등 배정
    UP_COLOR, DOWN_COLOR, NEUTRAL_COLOR = '#F04452', '#3182F6', '#8B95A1'
    if sc >= 2: c_bg, c_txt, msg = "rgba(240,68,82,0.12)", UP_COLOR, "강력 매수 (Strong Buy)"
    elif sc > 0: c_bg, c_txt, msg = "rgba(240,68,82,0.05)", UP_COLOR, "매수 우위 (Buy)"
    elif sc == 0: c_bg, c_txt, msg = "rgba(139,149,161,0.1)", NEUTRAL_COLOR, "중립 관망 (Hold)"
    elif sc > -2: c_bg, c_txt, msg = "rgba(49,130,246,0.05)", DOWN_COLOR, "매도 우위 (Sell)"
    else: c_bg, c_txt, msg = "rgba(49,130,246,0.12)", DOWN_COLOR, "강력 매도 (Strong Sell)"

    # 주가 정보 추출 및 렌더링
    last = float(c.iloc[-1])
    chg = last - float(c.iloc[-2]) if len(df) > 1 else 0
    chg_pct = (chg/float(c.iloc[-2])) * 100 if chg != 0 else 0
    price_color = UP_COLOR if chg > 0 else DOWN_COLOR if chg < 0 else NEUTRAL_COLOR
    sign = "+" if chg > 0 else ""
    
    price_format = f"{last:,.4f}" if last < 10 else f"{last:,.0f}" if asset_type == "주식" else f"{last:,.2f}"
    chg_format = f"{chg:,.4f}" if last < 10 else f"{chg:,.0f}" if asset_type == "주식" else f"{chg:,.2f}"

    # 상단 정보 영역 표시
    st.markdown(f"""
        <div class="mts-header">
            <div class="mts-ticker">{user_input.split('(')[0]} <span style="font-size:0.8rem; font-weight:normal; color:#6B7684;">({y_int})</span></div>
            <div class="mts-price-row">
                <span class="mts-main-price" style="color: {price_color};">{price_format}</span>
                <span class="mts-sub-change" style="color: {price_color};">{sign}{chg_format} ({sign}{chg_pct:.2f}%)</span>
            </div>
        </div>
        <div class="pattern-box" style="border-left: 5px solid {c_txt};">
            <span class="pattern-badge" style="background-color: {c_bg}; color: {c_txt}; border: 1px solid {c_txt};">{pattern_detected}</span>
            <div style="font-size:1.05rem; font-weight:800; color:{c_txt}; margin-bottom:5px;">AI 최종 의견: {msg}</div>
            <div style="color: #E5E8EB; font-size: 0.9rem; line-height:1.5;">{pattern_desc}</div>
        </div>
    """, unsafe_allow_html=True)

    # 5. 하이 대조군 네온 차트 그리기
    rows = 2; row_h = [0.75, 0.25]
    if show_macd and show_rsi: rows = 4; row_h = [0.55, 0.15, 0.15, 0.15]
    elif show_macd or show_rsi: rows = 3; row_h = [0.6, 0.2, 0.2]
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_h)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, name="Price", 
                                 increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR, 
                                 decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR), row=1, col=1)
    
    # ☁️ 일목균형표 부활
    if show_ichi and pd.notna(df['Senkou_A'].iloc[-1]):
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_A'], line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_B'], fill='tonexty', fillcolor='rgba(0,250,154,0.15)', line=dict(color='rgba(0,0,0,0)'), name="구름대(지지/저항)"), row=1, col=1)
        
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='#4E5968', width=1.2, dash='dash'), name="BB 상단"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='#4E5968', width=1.2, dash='dash'), fill='tonexty', fillcolor='rgba(255,255,255,0.02)', name="BB 하단"), row=1, col=1)
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA5'], line=dict(color='#FFD400', width=1.8), name="EMA 5 (황금선)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00F5A0', width=2.2), name="EMA 20 (생명선)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], line=dict(color='#CC66FF', width=2.0), name="EMA 60 (추세선)"), row=1, col=1)
    if show_sig:
        fig.add_trace(go.Scatter(x=df[df['Buy']].index, y=df[df['Buy']]['Low']*0.98, mode='markers', marker=dict(symbol='triangle-up', size=13, color='#FF0033'), name="매수타점"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell']].index, y=df[df['Sell']]['High']*1.02, mode='markers', marker=dict(symbol='triangle-down', size=13, color='#0066FF'), name="매도타점"), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=[UP_COLOR if r['Close']>=r['Open'] else DOWN_COLOR for _, r in df.iterrows()], name="Volume"), row=2, col=1)
    
    curr = 3
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#A78BFA', width=1.5)), row=curr, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FCD34D', width=1.5)), row=curr, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=np.where(df['MACD_H']>0, UP_COLOR, DOWN_COLOR)), row=curr, col=1)
        curr += 1
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#FF66B2', width=1.8)), row=curr, col=1)
        fig.add_hline(y=70, line_color="#3182F6", line_dash="solid", line_width=1, row=curr, col=1)
        fig.add_hline(y=30, line_color="#F04452", line_dash="solid", line_width=1, row=curr, col=1)

    if y_int in ['1d','1wk']: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    elif y_int in ['1m','5m','15m','1h'] and asset_type == "주식": fig.update_xaxes(rangebreaks=[dict(bounds=[16, 9.5], pattern="hour"), dict(bounds=["sat", "mon"])])

    # 🚨 [혁신 1] 드래그 모드를 무조건 'pan(이동)'으로 고정하여 1손가락 이동, 2손가락 확대를 네이티브로 구현!
    fig.update_layout(
        height=580, 
        template="plotly_dark", 
        dragmode='pan', # 조작 스위치 날려버리고 기본값을 이동으로 고정
        hovermode='x unified', 
        showlegend=False, 
        xaxis_rangeslider_visible=False, 
        margin=dict(l=0, r=40, t=5, b=0), 
        plot_bgcolor='#0F1218', 
        paper_bgcolor='#0F1218'
    )
    
    fig.update_yaxes(side="right", showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False, tickfont=dict(size=10, color='#8B95A1'))
    fig.update_xaxes(showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False, tickfont=dict(size=10, color='#8B95A1'))
    
    st.plotly_chart(fig, use_container_width=True, config={
        'scrollZoom': True,       # 💡 2손가락 핀치 줌 완벽 허용
        'displayModeBar': False,  # 지저분한 메뉴바 영구 삭제
        'doubleClick': 'reset',   # 두 번 터치 시 원래 배율 복귀
        'displaylogo': False
    })

    # --- 📰 [NEW] 실시간 종목 뉴스 & 트렌드 브리핑 엔진 ---
    st.markdown("<h4 style='color:#FFFFFF; margin-top:20px; font-weight:700;'>📰 실시간 시장 동향 브리핑</h4>", unsafe_allow_html=True)
    with st.spinner("최신 뉴스 헤드라인을 수집 중입니다..."):
        news_items = get_realtime_news(user_input.split('(')[0])
        
        if news_items:
            st.markdown('<div class="news-box">', unsafe_allow_html=True)
            for title, link in news_items:
                st.markdown(f'<div class="news-item">🔹 <a href="{link}" target="_blank">{title}</a></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("현재 검색된 주요 실시간 뉴스가 없습니다.")

else: st.error("종목 코드를 읽어올 수 없습니다. 장 마감 여부나 티커를 확인해 주세요.")