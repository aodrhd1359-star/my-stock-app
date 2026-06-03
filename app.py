import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime, timedelta
import re
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET

try:
    from pykrx import stock as krx
    HAS_PYKRX = True
except ImportError:
    HAS_PYKRX = False

# 1. 화면 설정
st.set_page_config(page_title="Pro Trader MTS V19", layout="wide", initial_sidebar_state="collapsed")

# 2. MTS 전용 CSS (디자인 강화)
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    
    .stApp { background-color: #0F1218; color: #F1F5F9; }
    .block-container { padding: 0.8rem 0.5rem 0rem 0.5rem !important; max-width: 100% !important; }
    header { visibility: hidden !important; height: 0px !important; }
    
    .mts-header { padding: 2px 5px; margin-bottom: 5px; }
    .mts-ticker { font-size: 1.1rem; color: #8B95A1; font-weight: 600; }
    .mts-price-row { display: flex; align-items: baseline; margin-top: 2px; }
    .mts-main-price { font-size: 2.3rem; font-weight: 800; letter-spacing: -1px; }
    
    .pattern-box { background: linear-gradient(135deg, #191E28, #121621); padding: 14px; border-radius: 14px; border: 1px solid #2A3241; margin-bottom: 12px; }
    .pattern-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 700; margin-bottom: 8px; }
    
    .macro-box { background-color: #191E28; border-radius: 12px; padding: 10px; border: 1px solid #2A3241; text-align: center; margin-bottom:10px; }
    .macro-title { color: #8B95A1; font-size: 0.85rem; font-weight: 600; }
    .macro-val { color: #FFF; font-size: 1.3rem; font-weight: 800; margin: 3px 0; }
    
    .fund-box { display: flex; justify-content: space-between; background-color: #191E28; padding: 10px 15px; border-radius: 10px; margin-bottom: 10px; }
    .fund-item { text-align: center; }
    .fund-label { font-size: 0.8rem; color: #8B95A1; }
    .fund-val { font-size: 1rem; font-weight: 700; color: #E5E8EB; }
    
    .news-box { background-color: #191E28; padding: 12px; border-radius: 12px; margin-top: 8px; border: 1px solid #2A3241; }
    .news-item { margin-bottom: 8px; font-size: 0.9rem; line-height: 1.4; border-bottom: 1px solid #2A3241; padding-bottom: 6px; }
    .news-item a { color: #E5E8EB; text-decoration: none; }
    
    button[data-testid="stPopoverButton"] { background-color: #222937 !important; color: #FFFFFF !important; border: 1px solid #333D4B !important; border-radius: 10px !important; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_ticker_db():
    try:
        import FinanceDataReader as fdr
        return fdr.StockListing('KRX')
    except: return None
krx_df = load_ticker_db()

def get_stock_code(name):
    name = name.strip()
    if krx_df is not None and not krx_df.empty:
        match = krx_df[krx_df['Name'] == name]
        if not match.empty: return match.iloc[0]['Code']
    return None

@st.cache_data(ttl=600)
def get_premium_news(keyword):
    try:
        search_query = keyword + " (site:hankyung.com OR site:mk.co.kr OR site:sedaily.com OR site:fnnews.com)"
        enc_kw = urllib.parse.quote(search_query)
        url = f"https://news.google.com/rss/search?q={enc_kw}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req)
        root = ET.fromstring(res.read())
        news_list = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            link = item.find('link').text
            clean_title = title.rsplit(' - ', 1)[0] if ' - ' in title else title
            news_list.append((clean_title, link))
        return news_list
    except: return []

@st.cache_data(ttl=3600)
def get_financials(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "PER": info.get('trailingPE', 0),
            "PBR": info.get('priceToBook', 0),
            "ROE": info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            "MarketCap": info.get('marketCap', 0)
        }
    except: return None

# --- 상단 팝오버 메뉴 ---
config_pop = st.popover("🧭 매크로 시황 및 종목 설정")

with config_pop:
    app_mode = st.radio("화면 모드", ["🌍 글로벌 매크로 보드", "📈 개별 종목 차트"], horizontal=True)
    st.markdown("---")
    if app_mode == "📈 개별 종목 차트":
        asset_type = st.radio("자산군", ["주식", "코인 (Crypto)"], horizontal=True)
        if asset_type == "주식":
            user_input = st.text_input("종목명 입력", "삼성전자")
            raw_code = get_stock_code(user_input)
            ticker = f"{raw_code}.KS" if raw_code else user_input
            y_int = st.selectbox("차트 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=4)
        else:
            coins = {"비트코인(BTC)":"BTC-USD", "이더리움(ETH)":"ETH-USD", "리플(XRP)":"XRP-USD", "솔라나(SOL)":"SOL-USD"}
            selected_coin = st.selectbox("코인 선택", list(coins.keys()))
            user_input = selected_coin
            ticker = coins[selected_coin]
            y_int = st.selectbox("차트 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=2)
            raw_code = None

# ==========================================
# 🌍 화면 1: 글로벌 매크로 종합 시황 보드
# ==========================================
if app_mode == "🌍 글로벌 매크로 보드":
    st.markdown("<h3 style='color:#FFF; font-weight:800; margin-bottom:5px;'>🌍 AI 매크로 & 환율 브리핑</h3>", unsafe_allow_html=True)
    
    macro_tickers = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "원/달러 환율": "KRW=X", "미 10년물 국채": "^TNX", "VIX (공포지수)": "^VIX", "비트코인": "BTC-USD"}
    
    with st.spinner("글로벌 매크로 데이터 분석 중..."):
        m_data = yf.download(list(macro_tickers.values()), period="5d")
    
    if not m_data.empty:
        c1, c2, c3 = st.columns(3)
        cols = [c1, c2, c3, c1, c2, c3]
        
        # 최신 데이터 추출
        macro_vals = {}
        for idx, (name, t) in enumerate(macro_tickers.items()):
            try:
                close_prices = m_data['Close'][t].dropna()
                if len(close_prices) >= 2:
                    last, prev = close_prices.iloc[-1], close_prices.iloc[-2]
                    chg, pct = last - prev, (last - prev) / prev * 100
                    macro_vals[name] = {"last": last, "chg": chg, "pct": pct}
                    
                    color = "#F04452" if chg > 0 else "#3182F6" if chg < 0 else "#8B95A1"
                    sign = "+" if chg > 0 else ""
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="macro-box">
                            <div class="macro-title">{name}</div>
                            <div class="macro-val" style="color:{color};">{last:,.2f}</div>
                            <div style="color:{color}; font-size:0.85rem; font-weight:700;">{sign}{chg:,.2f} ({sign}{pct:.2f}%)</div>
                        </div>
                        """, unsafe_allow_html=True)
            except: pass
            
        # 🤖 AI 환율 및 매크로 대응 전략 알고리즘
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        if "원/달러 환율" in macro_vals and "미 10년물 국채" in macro_vals and "VIX (공포지수)" in macro_vals:
            krw = macro_vals["원/달러 환율"]["last"]
            tnx = macro_vals["미 10년물 국채"]["last"]
            vix = macro_vals["VIX (공포지수)"]["last"]
            
            cause_txt, strategy_txt, alert_color = "", "", "#3182F6"
            
            if krw > 1370 and tnx > 4.3:
                cause_txt = "현재 **원/달러 환율 상승(원화 약세)**의 주된 원인은 **미국 국채 10년물 금리의 고공행진**입니다. 미국의 금리 인하 기대감이 후퇴하면서 글로벌 자금이 안전자산인 달러로 쏠리고 있습니다."
                strategy_txt = "🚨 **[방어적 현금 확보]** 강달러 국면에서는 외인들의 국내 증시 이탈이 가속화됩니다. 신규 투자를 보류하고 현금 비중을 늘리며, 미국 달러 자산(미국 주식/ETF) 비중을 확대하는 것이 유리합니다."
                alert_color = "#F04452"
            elif krw < 1320 and tnx < 4.0:
                cause_txt = "현재 **원/달러 환율 하락(원화 강세)**은 **미국 국채 금리 안정화**에 기인합니다. 위험자산 선호 심리가 살아나며 외국인 자금이 국내 및 신흥국 증시로 유입되기 좋은 환경입니다."
                strategy_txt = "🚀 **[공격적 비중 확대]** 시장에 유동성이 공급되는 훈풍 국면입니다. 낙폭이 컸던 우량주나 성장주를 중심으로 분할 매수 사이클을 공격적으로 가동해 수익률을 극대화하세요."
                alert_color = "#00F5A0"
            elif vix > 25:
                cause_txt = "환율 여부와 관계없이 현재 **VIX(공포지수)가 위험 수위**를 넘었습니다. 시장에 지정학적 리스크나 돌발 악재가 반영되어 패닉셀이 나오고 있습니다."
                strategy_txt = "⚡ **[리스크 관리 최우선]** 변동성이 극심하므로 단기 스캘핑 외의 스윙/장기 투자는 보류하세요. 바닥이 확인될 때까지 관망하는 것이 최고의 투자입니다."
                alert_color = "#FFD400"
            else:
                cause_txt = f"현재 환율은 **{krw:,.1f}원**으로 박스권에서 안정적인 횡보 흐름을 보이고 있습니다. 거시경제의 큰 충격 없이 개별 기업의 실적과 이슈에 따라 움직이는 장세입니다."
                strategy_txt = "⚖️ **[종목 장세 대응]** 매크로의 영향력이 적으므로, 재무가 탄탄하고 차트 패턴이 좋은 개별 종목 발굴에 집중하세요. 정해둔 원칙대로 기계적인 매매를 이어가면 됩니다."
                
            st.markdown(f"""
            <div class="pattern-box" style="border-left: 5px solid {alert_color};">
                <div style="font-size:1.1rem; font-weight:800; color:{alert_color}; margin-bottom:8px;">🧠 AI 매크로 분석 & 투자 전략</div>
                <div style="color: #E5E8EB; font-size: 0.95rem; line-height:1.5; margin-bottom:8px;">💡 <b>환율 변동 원인:</b> {cause_txt}</div>
                <div style="color: #FFF; font-size: 0.95rem; line-height:1.5;">🎯 <b>대응 전략:</b> {strategy_txt}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("<h4 style='color:#FFF; font-weight:700;'>📰 실시간 시장 동향 (메이저 경제지)</h4>", unsafe_allow_html=True)
    macro_news = get_premium_news("미국 증시 OR 환율 전망")
    if macro_news:
        st.markdown('<div class="news-box">', unsafe_allow_html=True)
        for title, link in macro_news:
            st.markdown(f'<div class="news-item">🔹 <a href="{link}" target="_blank">{title}</a></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📈 화면 2: 개별 종목 차트 & 재무/뉴스 분석
# ==========================================
else:
    with st.spinner('MTS 차트 & 재무 엔진 구동 중...'):
        if y_int in ['1m','5m','15m','1h']: df = yf.download(ticker, period='7d' if y_int=='1m' else '60d', interval=y_int)
        else: df = yf.download(ticker, period='1y', interval=y_int)
        fund_data = get_financials(ticker) if asset_type == "주식" else None

    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        if df.index.tz is not None: df.index = df.index.tz_localize(None)

        c = df['Close']
        df['EMA5'], df['EMA20'], df['EMA60'] = c.ewm(span=5, adjust=False).mean(), c.ewm(span=20, adjust=False).mean(), c.ewm(span=60, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + (c.diff().clip(lower=0).ewm(13).mean() / -c.diff().clip(upper=0).ewm(13).mean())))
        
        # 기술적 분석 (차트)
        tech_sc = (1 if df['EMA5'].iloc[-1] > df['EMA20'].iloc[-1] else -1) + (1 if df['RSI'].iloc[-1] < 35 else -1 if df['RSI'].iloc[-1] > 65 else 0)
        pattern_txt = "특이 패턴 없음. 지표 방향성 탐색 중."
        
        if len(df) > 30:
            if df['Close'].iloc[-1] > np.max(df['High'].iloc[-30:-1].values) and df['RSI'].iloc[-1] > 55:
                pattern_txt, tech_sc = "🚀 박스권 상단 돌파 (대시세 초입)", tech_sc + 2
            elif df['RSI'].iloc[-3] < 30 and df['RSI'].iloc[-1] > 45:
                pattern_txt, tech_sc = "⚡ V자 급반등 (투매 후 매수세 유입)", tech_sc + 1

        # 기본적 분석 (재무제표) 및 융합 시나리오 생성
        fund_txt, fund_sc = "재무 데이터가 없거나 코인 종목입니다. 차트와 수급 위주로 대응하세요.", 0
        if fund_data and fund_data["PER"] > 0:
            per, pbr, roe = fund_data["PER"], fund_data["PBR"], fund_data["ROE"]
            if per < 10 and roe > 10:
                fund_txt = f"PER {per:.1f}배, ROE {roe:.1f}%로 실적 대비 매우 저평가된 우량 상태입니다."
                fund_sc = 2
            elif per > 40:
                fund_txt = f"PER {per:.1f}배로 실적 대비 주가가 다소 고평가(과열)된 상태입니다."
                fund_sc = -1
            else:
                fund_txt = f"PER {per:.1f}배로 업종 평균 수준의 적정 가치를 유지하고 있습니다."
                fund_sc = 1

        total_sc = tech_sc + fund_sc
        UP_COLOR, DOWN_COLOR, NEUTRAL_COLOR = '#F04452', '#3182F6', '#8B95A1'
        
        if total_sc >= 3: c_bg, c_txt, msg, action = "rgba(240,68,82,0.12)", UP_COLOR, "🔥 강력 매수 (저평가+차트호전)", "재무적 가치와 차트 타이밍이 완벽하게 일치합니다. 비중을 실어 진입하기 좋은 최적의 타점입니다."
        elif total_sc > 0: c_bg, c_txt, msg, action = "rgba(240,68,82,0.05)", UP_COLOR, "📈 매수 우위", "하방 경직성이 확보되었습니다. 무리하지 않는 선에서 분할 매수(무한매수) 접근이 유효합니다."
        elif total_sc == 0: c_bg, c_txt, msg, action = "rgba(139,149,161,0.1)", NEUTRAL_COLOR, "⚖️ 중립 관망", "재무와 차트의 신호가 엇갈리거나 모멘텀이 부족합니다. 확실한 방향성이 나올 때까지 대기하세요."
        else: c_bg, c_txt, msg, action = "rgba(49,130,246,0.12)", DOWN_COLOR, "❄️ 매도 및 리스크 관리", "차트가 꺾인 상태이며 밸류에이션 부담도 있습니다. 수익 중이라면 차익 실현을, 손실 중이라면 비중 축소를 권장합니다."

        last = float(c.iloc[-1])
        chg = last - float(c.iloc[-2]) if len(df) > 1 else 0
        chg_pct = (chg/float(c.iloc[-2])) * 100 if chg != 0 else 0
        price_color = UP_COLOR if chg > 0 else DOWN_COLOR if chg < 0 else NEUTRAL_COLOR
        sign = "+" if chg > 0 else ""
        price_format = f"{last:,.4f}" if last < 10 else f"{last:,.0f}" if asset_type == "주식" else f"{last:,.2f}"

        # 렌더링
        st.markdown(f"""
            <div class="mts-header">
                <div class="mts-ticker">{user_input.split('(')[0]} <span style="font-size:0.8rem; font-weight:normal; color:#6B7684;">({y_int})</span></div>
                <div class="mts-price-row">
                    <span class="mts-main-price" style="color: {price_color};">{price_format}</span>
                    <span class="mts-sub-change" style="color: {price_color};">{sign}{chg:,.0f} ({sign}{chg_pct:.2f}%)</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if fund_data and fund_data["PER"] > 0:
            st.markdown(f"""
            <div class="fund-box">
                <div class="fund-item"><div class="fund-label">PER</div><div class="fund-val">{fund_data['PER']:.2f}배</div></div>
                <div class="fund-item"><div class="fund-label">PBR</div><div class="fund-val">{fund_data['PBR']:.2f}배</div></div>
                <div class="fund-item"><div class="fund-label">ROE</div><div class="fund-val">{fund_data['ROE']:.2f}%</div></div>
                <div class="fund-item"><div class="fund-label">시가총액</div><div class="fund-val">{fund_data['MarketCap']/1000000000000:,.1f}조</div></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="pattern-box" style="border-left: 5px solid {c_txt};">
                <span class="pattern-badge" style="background-color: {c_bg}; color: {c_txt}; border: 1px solid {c_txt};">{msg}</span>
                <div style="color: #E5E8EB; font-size: 0.9rem; line-height:1.5; margin-bottom:5px;">📊 <b>차트 판정:</b> {pattern_txt}</div>
                <div style="color: #E5E8EB; font-size: 0.9rem; line-height:1.5; margin-bottom:8px;">🏢 <b>재무 판정:</b> {fund_txt}</div>
                <div style="color: #FFF; font-size: 0.95rem; line-height:1.5;">🎯 <b>AI 최종 대응방안:</b> {action}</div>
            </div>
        """, unsafe_allow_html=True)

        # 차트 그리기 (기존과 동일하게 네이티브 터치/줌 적용)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, 
                                     increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR, 
                                     decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00F5A0', width=2.0)), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=[UP_COLOR if r['Close']>=r['Open'] else DOWN_COLOR for _, r in df.iterrows()]), row=2, col=1)
        
        if y_int in ['1d','1wk']: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig.update_layout(height=450, template="plotly_dark", dragmode='pan', hovermode='x unified', showlegend=False, xaxis_rangeslider_visible=False, margin=dict(l=0, r=40, t=5, b=0), plot_bgcolor='#0F1218', paper_bgcolor='#0F1218')
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False, 'doubleClick': 'reset'})

        # 뉴스 브리핑
        news_items = get_premium_news(user_input.split('(')[0])
        if news_items:
            st.markdown('<div class="news-box">', unsafe_allow_html=True)
            for title, link in news_items:
                st.markdown(f'<div class="news-item">🔹 <a href="{link}" target="_blank">{title}</a></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    else: st.error("종목 코드를 읽어올 수 없습니다.")