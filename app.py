import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime
import re

# 1. 화면 및 테마 설정 (반응형 모바일 최적화)
st.set_page_config(page_title="Pro Trader Dashboard", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    
    .stApp { background-color: #0F1218; color: #F1F5F9; }
    
    div[data-testid="metric-container"] {
        background-color: #191E28; border: none; padding: 15px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-size: 0.85rem !important; }
    div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.4rem !important; }
    
    .ai-box {
        background: linear-gradient(145deg, #191E28, #13171F);
        padding: 15px; border-radius: 12px; border: 1px solid #2A3241; height: 100%;
    }

    /* 🚨 스마트폰 화면(너비 768px 이하)일 때만 발동하는 반응형 마법 🚨 */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.2rem !important;
            padding-right: 0.2rem !important;
            padding-bottom: 1rem !important;
        }
        div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .ai-box h2 { font-size: 1.5rem !important; margin: 5px 0 !important; }
        .ai-box p { font-size: 0.85rem !important; line-height: 1.4 !important; }
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ Pro Trader (V14 - 모바일 단타 최적화)")

if 'memos' not in st.session_state: st.session_state['memos'] = []

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

# --- 사이드바: 모드 선택 (주식 vs 코인) ---
st.sidebar.title("⚙️ 트레이딩 설정")
asset_type = st.sidebar.radio("자산 종류", ["📈 주식 (Stock)", "🪙 코인 (Crypto)"], horizontal=True)

if asset_type == "📈 주식 (Stock)":
    user_input = st.sidebar.text_input("종목명 (예: 삼성전자, QQQ)", "삼성전자")
    ticker = get_stock_ticker(user_input)
    default_interval = 4 # 1일(1d)
else:
    coin_dict = {
        "비트코인 (BTC)": "BTC-USD", "이더리움 (ETH)": "ETH-USD", 
        "리플 (XRP)": "XRP-USD", "솔라나 (SOL)": "SOL-USD", "도지코인 (DOGE)": "DOGE-USD"
    }
    selected_coin = st.sidebar.selectbox("주요 코인 선택", list(coin_dict.keys()) + ["직접 입력(예: ADA-USD)"])
    if selected_coin == "직접 입력(예: ADA-USD)":
        user_input = st.sidebar.text_input("코인 티커 입력", "ADA-USD")
        ticker = user_input.strip().upper()
    else:
        user_input = selected_coin
        ticker = coin_dict[selected_coin]
    default_interval = 2 # 15분(15m) 단타 기본값

intervals = {"1분":"1m", "5분":"5m", "15분":"15m", "1시간":"1h", "1일":"1d", "1주":"1wk", "1개월":"1mo", "1년":"1y"}
selected_interval = st.sidebar.selectbox("⏱️ 주기", list(intervals.keys()), index=default_interval)
y_int = intervals[selected_interval]

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("시작일", pd.to_datetime("2021-01-01"))
end_date = col_d2.date_input("종료일", pd.to_datetime("today"))

st.sidebar.markdown("---")
# 단타용 지수이평선(EMA) 강제 적용 안내
st.sidebar.caption("※ 단타 모드 최적화를 위해 단순이평선(SMA) 대신 반응이 빠른 **지수이평선(EMA)**이 차트에 적용됩니다.")
show_bb = st.sidebar.checkbox("볼린저 밴드", True)
show_ichi = st.sidebar.checkbox("일목균형표", False) # 폰에서는 복잡할 수 있어 기본 False
show_sig = st.sidebar.checkbox("매매 시그널", True)
show_macd = st.sidebar.checkbox("MACD", True)
show_rsi = st.sidebar.checkbox("RSI", True)

with st.spinner(f'[{user_input}] 데이터 분석 중...'):
    if y_int in ['1m','5m','15m','1h']: df = yf.download(ticker, period='7d' if y_int=='1m' else '60d', interval=y_int)
    elif y_int == '1y': df = yf.download(ticker, period='max', interval='1mo')
    else: df = yf.download(ticker, start=start_date, end=end_date, interval=y_int)

if not df.empty:
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    if df.index.tz is not None: df.index = df.index.tz_localize(None)
    if y_int == '1y': df = df.resample('YS').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()

    c = df['Close']
    
    # 🚨 단기 트레이딩 핵심: SMA 대신 EMA(지수이동평균) 사용
    df['EMA5'] = c.ewm(span=5, adjust=False).mean()
    df['EMA20'] = c.ewm(span=20, adjust=False).mean()
    df['EMA60'] = c.ewm(span=60, adjust=False).mean()
    
    # 볼린저 밴드
    df['BB_std'] = c.rolling(20).std()
    df['BB_up'] = df['EMA20'] + (df['BB_std'] * 2)
    df['BB_low'] = df['EMA20'] - (df['BB_std'] * 2)
    
    if len(df)>52:
        df['Senkou_A'] = (((df['High'].rolling(9).max()+df['Low'].rolling(9).min())/2 + (df['High'].rolling(26).max()+df['Low'].rolling(26).min())/2)/2).shift(26)
        df['Senkou_B'] = ((df['High'].rolling(52).max()+df['Low'].rolling(52).min())/2).shift(26)
    else: df['Senkou_A'], df['Senkou_B'] = np.nan, np.nan

    # MACD & RSI
    df['MACD'] = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_H'] = df['MACD'] - df['Signal']
    
    delta = c.diff()
    df['RSI'] = 100 - (100 / (1 + (delta.clip(lower=0).ewm(13).mean() / -delta.clip(upper=0).ewm(13).mean())))
    
    # EMA 타점 시그널 (5선과 20선의 골든/데드크로스)
    df['Buy'] = (df['EMA5'] > df['EMA20']) & (df['EMA5'].shift(1) <= df['EMA20'].shift(1))
    df['Sell'] = (df['EMA5'] < df['EMA20']) & (df['EMA5'].shift(1) >= df['EMA20'].shift(1))

    # AI 스코어링 (단기 반응형)
    sc, rsn = 0, []
    if pd.notna(df['EMA20'].iloc[-1]):
        if df['EMA5'].iloc[-1]>df['EMA20'].iloc[-1]: sc+=1; rsn.append("🟢 EMA(지수이평) 단기 상승 돌파")
        else: sc-=1; rsn.append("🔴 EMA(지수이평) 단기 하락 꺾임")
    if pd.notna(df['EMA60'].iloc[-1]):
        if c.iloc[-1]>df['EMA60'].iloc[-1]: sc+=1; rsn.append("🟢 장기(60선) 추세 지지")
        else: sc-=1; rsn.append("🔴 장기(60선) 추세 이탈")
    if pd.notna(df['MACD'].iloc[-1]):
        if df['MACD'].iloc[-1]>df['Signal'].iloc[-1]: sc+=1; rsn.append("🟢 숏텀 MACD 수급 우위")
        else: sc-=1; rsn.append("🔴 숏텀 MACD 매도 우위")
    if pd.notna(df['RSI'].iloc[-1]):
        if df['RSI'].iloc[-1]<35: sc+=1; rsn.append("🟢 단기 낙폭과대 (스캘핑 기회)")
        elif df['RSI'].iloc[-1]>65: sc-=1; rsn.append("🔴 단기 과열 (차익실현 주의)")
        else: rsn.append("⚪ 수급 횡보")

    UP_COLOR = '#F04452'
    DOWN_COLOR = '#3182F6'
    NEUTRAL_COLOR = '#8B95A1'

    c_bg, c_txt, msg = ("rgba(240,68,82,0.1)", UP_COLOR, "🔥 스캘핑 매수") if sc>=3 else ("rgba(240,68,82,0.05)", UP_COLOR, "매수 우위") if sc>0 else ("rgba(139,149,161,0.1)", NEUTRAL_COLOR, "관망 (중립)") if sc==0 else ("rgba(49,130,246,0.05)", DOWN_COLOR, "매도 우위") if sc>-3 else ("rgba(49,130,246,0.1)", DOWN_COLOR, "❄️ 즉각 매도")
    
    last = float(c.iloc[-1])
    chg = last - float(c.iloc[-2]) if len(df)>1 else 0
    rsi_val = float(df['RSI'].iloc[-1]) if pd.notna(df['RSI'].iloc[-1]) else 50.0

    st.markdown("---")
    
    # 모바일에서 AI 박스와 가격정보가 위아래로 깔끔하게 떨어지도록 컬럼 비율 재조정
    c1, c2 = st.columns([1, 1.2])
    with c1: 
        st.markdown(f'<div class="ai-box" style="border-color: {c_bg};"><div style="color:#8B95A1; font-size:0.8rem; font-weight:bold; margin-bottom:5px;">🤖 AI 스캘핑 판정</div><div style="color:{c_txt}; font-size:1.6rem; font-weight:800; margin-bottom:8px;">{msg}</div><div style="color:#B0B8C1; font-size:0.9rem; line-height:1.5;">{"<br>".join(rsn)}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True) # 간격 띄우기
        r1, r2 = st.columns(2)
        # 코인 가격은 달러 표기이므로 소수점 포맷 조정
        price_format = f"{last:,.4f}" if last < 10 else f"{last:,.2f}"
        r1.metric("종목명", f"{user_input.split('(')[0]}", f"{df.index[-1].strftime('%m/%d %H:%M')}")
        r2.metric("현재가", price_format, f"{chg:,.2f} ({(chg/float(c.iloc[-2])*100 if chg!=0 else 0):.2f}%)")
        
        r3, r4 = st.columns(2)
        r3.metric("현재 RSI", f"{rsi_val:.1f}")
        r4.metric("볼린저 밴드", "상단 (매도타점)" if last>df['BB_up'].iloc[-1] else "하단 (매수타점)" if last<df['BB_low'].iloc[-1] else "밴드 내 안정")

    st.markdown("<br>", unsafe_allow_html=True)
    
    rows = 2; row_h = [0.75, 0.25]
    if show_macd and show_rsi: rows=4; row_h=[0.5, 0.15, 0.15, 0.2]
    elif show_macd or show_rsi: rows=3; row_h=[0.55, 0.2, 0.25]
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_h)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, name="Price", 
                                 increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR, 
                                 decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR), row=1, col=1)
    
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='rgba(255,255,255,0.2)', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='rgba(255,255,255,0.2)', dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.03)'), row=1, col=1)
    if show_ichi and pd.notna(df['Senkou_A'].iloc[-1]):
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_A'], line=dict(color='rgba(0,0,0,0)'), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_B'], fill='tonexty', fillcolor='rgba(0,250,154,0.08)', line=dict(color='rgba(0,0,0,0)')), row=1, col=1)
    
    # SMA가 아닌 빠른 EMA 차트 적용
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA5'], line=dict(color='#F59E0B', width=1.5), name='EMA 5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#10B981', width=2), name='EMA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], line=dict(color='#8B5CF6', width=2), name='EMA 60'), row=1, col=1)
    
    if show_sig:
        fig.add_trace(go.Scatter(x=df[df['Buy']].index, y=df[df['Buy']]['Low']*0.99, mode='markers', marker=dict(symbol='triangle-up', size=14, color=UP_COLOR)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell']].index, y=df[df['Sell']]['High']*1.01, mode='markers', marker=dict(symbol='triangle-down', size=14, color=DOWN_COLOR)), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=[UP_COLOR if row['Close']>=row['Open'] else DOWN_COLOR for _, row in df.iterrows()]), row=2, col=1)
    
    curr = 3
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#A78BFA')), row=curr, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FCD34D')), row=curr, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=np.where(df['MACD_H']>0, UP_COLOR, DOWN_COLOR)), row=curr, col=1)
        curr+=1
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#F472B6')), row=curr, col=1)
        fig.add_hline(y=70, line_color=DOWN_COLOR, line_dash="dash", row=curr, col=1)
        fig.add_hline(y=30, line_color=UP_COLOR, line_dash="dash", row=curr, col=1)

    if y_int == '1y': fig.update_xaxes(dtick="M12", tickformat="%Y")
    elif y_int in ['1d','1wk']: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    elif y_int in ['1m','5m','15m','1h']: fig.update_xaxes(rangebreaks=[dict(bounds=[16, 9.5], pattern="hour"), dict(bounds=["sat", "mon"])])

    # 🚨 모바일 스크롤에 맞춘 컴팩트한 높이(550px) 및 여백 최소화
    fig.update_layout(
        height=550, 
        template="plotly_dark", 
        dragmode='pan', 
        hovermode='x unified', 
        showlegend=False, 
        xaxis_rangeslider_visible=False, 
        margin=dict(l=0, r=40, t=10, b=10), # 모바일 여백 극단적 압축
        plot_bgcolor='#0F1218', 
        paper_bgcolor='#0F1218'
    )
    
    fig.update_yaxes(side="right", showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False)
    fig.update_xaxes(showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False)
    
    st.plotly_chart(fig, use_container_width=True, config={
        'scrollZoom': True, 
        'displayModeBar': False, 
        'doubleClick': 'reset',
        'displaylogo': False
    })
else: st.error("데이터 오류. 티커(종목명)를 다시 확인해 주세요.")

m1, m2 = st.columns([4, 1])
with m1: memo = st.text_input("메모", label_visibility="collapsed", placeholder="타점과 매매 이유를 남겨보세요.")
with m2: 
    if st.button("저장", use_container_width=True) and memo:
        st.session_state['memos'].insert(0, f"**[{datetime.now().strftime('%m/%d %H:%M')}]** {memo}")
for m in st.session_state['memos']: st.info(m)