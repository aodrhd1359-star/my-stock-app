import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime
import re

# 1. 화면 설정 (사이드바 기본 숨김 처리로 모바일 화면 극대화!)
st.set_page_config(page_title="Pro Trader MTS", layout="wide", initial_sidebar_state="collapsed")

# 2. 극한의 모바일 MTS UI 전용 CSS
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    
    /* 화면 전체 여백 및 스트림릿 기본 UI 강제 삭제 */
    .stApp { background-color: #0b0f19; color: #F1F5F9; }
    .block-container { padding: 1rem 0.5rem 0rem 0.5rem !important; max-width: 100% !important; }
    header { visibility: hidden !important; height: 0px !important; }
    div[data-testid="stDecoration"] { display: none; }
    
    /* 가격 표시 HTML 전용 스타일 */
    .mts-box { padding: 5px 10px; margin-bottom: 5px; }
    .mts-title { font-size: 1.1rem; color: #8B95A1; font-weight: 600; margin-bottom: 2px; }
    .mts-price { font-size: 2.2rem; font-weight: 800; color: #FFFFFF; letter-spacing: -1px; }
    .mts-change { font-size: 1.1rem; font-weight: 700; margin-left: 8px; }
    .ai-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 700; margin-top: 5px; }
    
    /* 폰에서 보기 싫은 스크롤바 숨김 */
    ::-webkit-scrollbar { width: 0px; background: transparent; }
    </style>
    """, unsafe_allow_html=True)

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

# --- 사이드바 (서랍 메뉴) 설정 ---
st.sidebar.title("⚙️ 트레이딩 설정")
asset_type = st.sidebar.radio("자산 종류", ["📈 주식", "🪙 코인"], horizontal=True)

if asset_type == "📈 주식":
    user_input = st.sidebar.text_input("종목명", "삼성전자")
    ticker = get_stock_ticker(user_input)
    y_int = st.sidebar.selectbox("⏱️ 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=4)
else:
    coins = {"비트코인":"BTC-USD", "이더리움":"ETH-USD", "리플":"XRP-USD", "솔라나":"SOL-USD", "도지":"DOGE-USD"}
    selected_coin = st.sidebar.selectbox("코인 선택", list(coins.keys()))
    user_input = selected_coin
    ticker = coins[selected_coin]
    y_int = st.sidebar.selectbox("⏱️ 주기", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=2)

st.sidebar.markdown("---")
show_ma = st.sidebar.checkbox("이평선 (EMA)", True)
show_bb = st.sidebar.checkbox("볼린저 밴드", True)
show_sig = st.sidebar.checkbox("매매 타점 시그널", True)
show_macd = st.sidebar.checkbox("MACD", True)
show_rsi = st.sidebar.checkbox("RSI", True)

# --- 데이터 수집 및 계산 ---
with st.spinner('로딩 중...'):
    if y_int in ['1m','5m','15m','1h']: df = yf.download(ticker, period='7d' if y_int=='1m' else '60d', interval=y_int)
    else: df = yf.download(ticker, period='1y', interval=y_int)

if not df.empty:
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    if df.index.tz is not None: df.index = df.index.tz_localize(None)

    c = df['Close']
    df['EMA5'], df['EMA20'], df['EMA60'] = c.ewm(span=5).mean(), c.ewm(span=20).mean(), c.ewm(span=60).mean()
    df['BB_std'] = c.rolling(20).std()
    df['BB_up'], df['BB_low'] = df['EMA20'] + (df['BB_std'] * 2), df['EMA20'] - (df['BB_std'] * 2)
    
    df['MACD'] = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_H'] = df['MACD'] - df['Signal']
    
    delta = c.diff()
    df['RSI'] = 100 - (100 / (1 + (delta.clip(lower=0).ewm(13).mean() / -delta.clip(upper=0).ewm(13).mean())))
    
    df['Buy'] = (df['EMA5'] > df['EMA20']) & (df['EMA5'].shift(1) <= df['EMA20'].shift(1))
    df['Sell'] = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))

    sc, rsn = 0, []
    if pd.notna(df['EMA20'].iloc[-1]):
        if df['EMA5'].iloc[-1]>df['EMA20'].iloc[-1]: sc+=1; rsn.append("단기 상승세")
        else: sc-=1; rsn.append("단기 하락세")
    if pd.notna(df['RSI'].iloc[-1]):
        if df['RSI'].iloc[-1]<35: sc+=1; rsn.append("RSI 침체")
        elif df['RSI'].iloc[-1]>65: sc-=1; rsn.append("RSI 과열")

    UP_COLOR = '#F04452'
    DOWN_COLOR = '#3182F6'
    NEUTRAL_COLOR = '#8B95A1'

    c_bg, c_txt, msg = ("rgba(240,68,82,0.15)", UP_COLOR, "🔥 적극 매수") if sc>=2 else ("rgba(240,68,82,0.05)", UP_COLOR, "매수 우위") if sc>0 else ("rgba(139,149,161,0.1)", NEUTRAL_COLOR, "관망 (중립)") if sc==0 else ("rgba(49,130,246,0.05)", DOWN_COLOR, "매도 우위") if sc>-2 else ("rgba(49,130,246,0.15)", DOWN_COLOR, "❄️ 적극 매도")
    
    last = float(c.iloc[-1])
    chg = last - float(c.iloc[-2]) if len(df)>1 else 0
    chg_pct = (chg/float(c.iloc[-2])) * 100 if chg!=0 else 0
    price_color = UP_COLOR if chg > 0 else DOWN_COLOR if chg < 0 else NEUTRAL_COLOR
    sign = "+" if chg > 0 else ""
    
    price_format = f"{last:,.4f}" if last < 10 else f"{last:,.0f}" if asset_type == "📈 주식" else f"{last:,.2f}"
    chg_format = f"{chg:,.4f}" if last < 10 else f"{chg:,.0f}" if asset_type == "📈 주식" else f"{chg:,.2f}"

    # 3. 모바일 최적화 상단 UI (군더더기 싹 제거)
    st.markdown(f"""
        <div class="mts-box">
            <div class="mts-title">{user_input.split('(')[0]} <span style="font-size:0.8rem; font-weight:normal;">({y_int})</span></div>
            <div>
                <span class="mts-price" style="color: {price_color};">{price_format}</span>
                <span class="mts-change" style="color: {price_color};">{sign}{chg_format} ({sign}{chg_pct:.2f}%)</span>
            </div>
            <div class="ai-badge" style="background-color: {c_bg}; color: {c_txt}; border: 1px solid {c_txt};">
                AI 시그널: {msg}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4. 차트 렌더링 (여백 0)
    rows = 2; row_h = [0.75, 0.25]
    if show_macd and show_rsi: rows=4; row_h=[0.5, 0.15, 0.15, 0.2]
    elif show_macd or show_rsi: rows=3; row_h=[0.6, 0.2, 0.2]
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_h)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, 
                                 increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR, 
                                 decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR), row=1, col=1)
    
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='rgba(255,255,255,0.1)', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='rgba(255,255,255,0.1)', dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.02)'), row=1, col=1)
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA5'], line=dict(color='#F59E0B', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#10B981', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], line=dict(color='#8B5CF6', width=1.5)), row=1, col=1)
    if show_sig:
        fig.add_trace(go.Scatter(x=df[df['Buy']].index, y=df[df['Buy']]['Low']*0.99, mode='markers', marker=dict(symbol='triangle-up', size=10, color=UP_COLOR)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell']].index, y=df[df['Sell']]['High']*1.01, mode='markers', marker=dict(symbol='triangle-down', size=10, color=DOWN_COLOR)), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=[UP_COLOR if row['Close']>=row['Open'] else DOWN_COLOR for _, row in df.iterrows()]), row=2, col=1)
    
    curr = 3
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#A78BFA', width=1)), row=curr, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FCD34D', width=1)), row=curr, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=np.where(df['MACD_H']>0, UP_COLOR, DOWN_COLOR)), row=curr, col=1)
        curr+=1
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#F472B6', width=1)), row=curr, col=1)
        fig.add_hline(y=70, line_color=DOWN_COLOR, line_dash="dash", row=curr, col=1)
        fig.add_hline(y=30, line_color=UP_COLOR, line_dash="dash", row=curr, col=1)

    if y_int in ['1d','1wk']: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    elif y_int in ['1m','5m','15m','1h'] and asset_type == "📈 주식": fig.update_xaxes(rangebreaks=[dict(bounds=[16, 9.5], pattern="hour"), dict(bounds=["sat", "mon"])])

    # 🚨 모바일 꽉 찬 화면 레이아웃
    fig.update_layout(
        height=580, 
        template="plotly_dark", 
        dragmode='pan', 
        hovermode='x unified', 
        showlegend=False, 
        xaxis_rangeslider_visible=False, 
        margin=dict(l=0, r=40, t=5, b=0), # 불필요한 상하좌우 여백 완전 제거
        plot_bgcolor='#0b0f19', 
        paper_bgcolor='#0b0f19'
    )
    
    fig.update_yaxes(side="right", showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False, tickfont=dict(size=10))
    fig.update_xaxes(showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False, tickfont=dict(size=10))
    
    st.plotly_chart(fig, use_container_width=True, config={
        'scrollZoom': True, 
        'displayModeBar': False, 
        'doubleClick': 'reset',
        'displaylogo': False
    })

    # AI 상세 분석표를 접이식(Expander)으로 깔끔하게 숨김
    with st.expander("🤖 AI 상세 분석 근거 보기"):
        st.write(" • " + "\n • ".join(rsn))
        st.caption(f"RSI: {df['RSI'].iloc[-1]:.1f} / 볼린저 밴드 대비 위치: {'상단' if last>df['BB_up'].iloc[-1] else '하단' if last<df['BB_low'].iloc[-1] else '안정'}")

else: st.error("종목 데이터를 불러올 수 없습니다.")