import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime
import re

# 1. 화면 및 테마 설정 (모바일 최적화 & 세련된 UI)
st.set_page_config(page_title="Pro Trader Dashboard", layout="wide")

st.markdown("""
    <style>
    /* 트렌디한 프리텐다드 폰트 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    * { font-family: 'Pretendard', sans-serif !important; }
    
    /* 전체 배경 및 텍스트 색상 부드럽게 */
    .stApp { background-color: #0F1218; color: #F1F5F9; }
    
    /* 상단 정보 박스 (둥글고 세련된 느낌) */
    div[data-testid="metric-container"] {
        background-color: #191E28; 
        border: none; 
        padding: 15px 20px; 
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 라벨 텍스트 색상 */
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-size: 0.9rem !important; }
    /* 메인 숫자 텍스트 */
    div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.6rem !important; }
    
    h1, h2, h3 { color: #FFFFFF !important; font-weight: 800; margin-bottom: 0; padding-bottom: 0; }
    hr { border-color: #2A3241; margin: 15px 0; }
    
    /* AI 분석 박스 프리미엄 디자인 */
    .ai-box {
        background: linear-gradient(145deg, #191E28, #13171F);
        padding: 20px; 
        border-radius: 16px;
        border: 1px solid #2A3241;
        height: 100%;
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ Pro Trader (V13 - 모바일 UI/UX 최적화)")

if 'memos' not in st.session_state: st.session_state['memos'] = []

@st.cache_data
def load_ticker_db():
    try:
        import FinanceDataReader as fdr
        return fdr.StockListing('KRX')
    except Exception as e:
        return None

krx_df = load_ticker_db()

def get_ticker(name):
    name = name.strip()
    if re.match(r'^[a-zA-Z0-9^.]+$', name): return name
    if krx_df is not None and not krx_df.empty:
        match = krx_df[krx_df['Name'] == name]
        if not match.empty:
            code = match.iloc[0]['Code']
            market = str(match.iloc[0]['Market']).upper()
            return f"{code}.KQ" if 'KOSDAQ' in market else f"{code}.KS"
    return name

st.sidebar.title("⚙️ 설정")
user_input = st.sidebar.text_input("종목 (예: 삼성전자, QQQ)", "삼성전자")
ticker = get_ticker(user_input)

if re.search(r'[가-힣]', user_input) and ticker == user_input:
    st.sidebar.warning("⚠️ 종목명을 다시 확인해 주세요.")

intervals = {"1분":"1m", "5분":"5m", "15분":"15m", "1시간":"1h", "1일":"1d", "1주":"1wk", "1개월":"1mo", "1년":"1y"}
selected_interval = st.sidebar.selectbox("⏱️ 주기", list(intervals.keys()), index=4)
y_int = intervals[selected_interval]

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("시작일", pd.to_datetime("2021-01-01"))
end_date = col_d2.date_input("종료일", pd.to_datetime("today"))

show_ma = st.sidebar.checkbox("이평선", True)
show_bb = st.sidebar.checkbox("볼린저 밴드", True)
show_ichi = st.sidebar.checkbox("일목균형표", True)
show_sig = st.sidebar.checkbox("매매 시그널", True)
show_macd = st.sidebar.checkbox("MACD", True)
show_rsi = st.sidebar.checkbox("RSI", True)

with st.spinner(f'[{user_input}] 데이터 분석 중...'):
    if y_int in ['1m','5m','15m','1h']: df = yf.download(ticker, period='60d' if y_int!='1m' else '7d', interval=y_int)
    elif y_int == '1y': df = yf.download(ticker, period='max', interval='1mo')
    else: df = yf.download(ticker, start=start_date, end=end_date, interval=y_int)

if not df.empty:
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    if df.index.tz is not None: df.index = df.index.tz_localize(None)
    if y_int == '1y': df = df.resample('YS').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()

    c = df['Close']
    df['MA5'], df['MA20'], df['MA60'] = c.rolling(5).mean(), c.rolling(20).mean(), c.rolling(60).mean()
    df['BB_up'], df['BB_low'] = df['MA20'] + c.rolling(20).std()*2, df['MA20'] - c.rolling(20).std()*2
    
    if len(df)>52:
        df['Senkou_A'] = (((df['High'].rolling(9).max()+df['Low'].rolling(9).min())/2 + (df['High'].rolling(26).max()+df['Low'].rolling(26).min())/2)/2).shift(26)
        df['Senkou_B'] = ((df['High'].rolling(52).max()+df['Low'].rolling(52).min())/2).shift(26)
    else: df['Senkou_A'], df['Senkou_B'] = np.nan, np.nan

    df['MACD'] = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_H'] = df['MACD'] - df['Signal']
    
    delta = c.diff()
    df['RSI'] = 100 - (100 / (1 + (delta.clip(lower=0).ewm(13).mean() / -delta.clip(upper=0).ewm(13).mean())))
    
    df['Buy'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
    df['Sell'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))

    sc, rsn = 0, []
    if pd.notna(df['MA20'].iloc[-1]):
        if df['MA5'].iloc[-1]>df['MA20'].iloc[-1]: sc+=1; rsn.append("🟢 단기 추세 안정적")
        else: sc-=1; rsn.append("🔴 단기 추세 꺾임")
    if pd.notna(df['MA60'].iloc[-1]):
        if c.iloc[-1]>df['MA60'].iloc[-1]: sc+=1; rsn.append("🟢 중장기 지지선 위")
        else: sc-=1; rsn.append("🔴 중장기 지지선 이탈")
    if pd.notna(df['MACD'].iloc[-1]):
        if df['MACD'].iloc[-1]>df['Signal'].iloc[-1]: sc+=1; rsn.append("🟢 매수 모멘텀 우세")
        else: sc-=1; rsn.append("🔴 매도 모멘텀 우세")
    if pd.notna(df['RSI'].iloc[-1]):
        if df['RSI'].iloc[-1]<40: sc+=1; rsn.append("🟢 단기 과낙폭 (반등 기대)")
        elif df['RSI'].iloc[-1]>65: sc-=1; rsn.append("🔴 단기 과열 (조정 주의)")
        else: rsn.append("⚪ 수급 안정적")

    # 세련된 핀테크 컬러 코드 적용 (Toss, 토스증권 등에서 쓰는 트렌디한 색상)
    UP_COLOR = '#F04452'   # 산뜻한 레드
    DOWN_COLOR = '#3182F6' # 청량한 블루
    NEUTRAL_COLOR = '#8B95A1' # 부드러운 그레이

    c_bg, c_txt, msg = ("rgba(240,68,82,0.1)", UP_COLOR, "🔥 적극 매수") if sc>=3 else ("rgba(240,68,82,0.05)", UP_COLOR, "매수 우위") if sc>0 else ("rgba(139,149,161,0.1)", NEUTRAL_COLOR, "관망 (중립)") if sc==0 else ("rgba(49,130,246,0.05)", DOWN_COLOR, "매도 우위") if sc>-3 else ("rgba(49,130,246,0.1)", DOWN_COLOR, "❄️ 적극 매도")
    
    last = float(c.iloc[-1])
    chg = last - float(c.iloc[-2]) if len(df)>1 else 0
    rsi_val = float(df['RSI'].iloc[-1]) if pd.notna(df['RSI'].iloc[-1]) else 50.0

    st.markdown("---")
    
    # 모바일에 맞춘 상단 UI 배치
    c1, c2 = st.columns([1, 1.2])
    with c1: 
        st.markdown(f'<div class="ai-box" style="border-color: {c_bg};"><div style="color:#8B95A1; font-size:0.9rem; font-weight:bold; margin-bottom:8px;">🤖 AI 실시간 판정</div><div style="color:{c_txt}; font-size:1.8rem; font-weight:800; margin-bottom:12px;">{msg}</div><div style="color:#B0B8C1; font-size:0.95rem; line-height:1.6;">{"<br>".join(rsn)}</div></div>', unsafe_allow_html=True)
    with c2:
        r1, r2 = st.columns(2)
        r1.metric("종목명", f"{user_input.upper()}", f"{df.index[-1].strftime('%m/%d %H:%M')}")
        r2.metric("현재가", f"{last:,.2f}", f"{chg:,.2f} ({(chg/float(c.iloc[-2])*100 if chg!=0 else 0):.2f}%)")
        r3, r4 = st.columns(2)
        r3.metric("현재 RSI", f"{rsi_val:.1f}")
        r4.metric("밴드 위치", "상단 과열" if last>df['BB_up'].iloc[-1] else "하단 침체" if last<df['BB_low'].iloc[-1] else "안정 구간")

    st.markdown("<br>", unsafe_allow_html=True)
    
    rows = 2; row_h = [0.75, 0.25]
    if show_macd and show_rsi: rows=4; row_h=[0.5, 0.15, 0.15, 0.2]
    elif show_macd or show_rsi: rows=3; row_h=[0.55, 0.2, 0.25]
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_h)
    
    # 캔들차트 색상 변경
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, name="Price", 
                                 increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR, 
                                 decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR), row=1, col=1)
    
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='rgba(255,255,255,0.2)', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='rgba(255,255,255,0.2)', dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.03)'), row=1, col=1)
    if show_ichi and pd.notna(df['Senkou_A'].iloc[-1]):
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_A'], line=dict(color='rgba(0,0,0,0)'), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_B'], fill='tonexty', fillcolor='rgba(0,250,154,0.08)', line=dict(color='rgba(0,0,0,0)')), row=1, col=1)
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#F59E0B', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#10B981', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#8B5CF6', width=2)), row=1, col=1)
    if show_sig:
        fig.add_trace(go.Scatter(x=df[df['Buy']].index, y=df[df['Buy']]['Low']*0.99, mode='markers', marker=dict(symbol='triangle-up', size=12, color=UP_COLOR)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell']].index, y=df[df['Sell']]['High']*1.01, mode='markers', marker=dict(symbol='triangle-down', size=12, color=DOWN_COLOR)), row=1, col=1)
        
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

    # 차트 모바일 최적화 레이아웃 설정
    fig.update_layout(
        height=650, # 모바일 한 화면에 들어오도록 약간 축소
        template="plotly_dark", 
        dragmode='pan', # 기본 조작을 패닝(좌우 이동)으로 고정
        hovermode='x unified', 
        showlegend=False, 
        xaxis_rangeslider_visible=False, 
        margin=dict(l=5, r=40, t=10, b=10), # 모바일 여백 최소화
        plot_bgcolor='#0F1218', 
        paper_bgcolor='#0F1218'
    )
    
    fig.update_yaxes(side="right", showgrid=True, gridcolor='#1E2532', zeroline=False, fixedrange=False)
    fig.update_xaxes(showgrid=True, gridcolor='#1E2532', zeroline=False)
    
    # 모바일 터치 민감도 및 거슬리는 메뉴바 숨김 처리
    st.plotly_chart(fig, use_container_width=True, config={
        'scrollZoom': True, 
        'displayModeBar': False, # 상단 자잘한 아이콘 메뉴 완전히 숨김
        'doubleClick': 'reset'
    })
else: st.error("데이터 오류. 장이 닫혀있거나 종목명을 다시 확인해 주세요.")

m1, m2 = st.columns([4, 1])
with m1: memo = st.text_input("메모", label_visibility="collapsed", placeholder="매매 기록을 남겨보세요.")
with m2: 
    if st.button("저장", use_container_width=True) and memo:
        st.session_state['memos'].insert(0, f"**[{datetime.now().strftime('%m/%d %H:%M')}]** {memo}")
for m in st.session_state['memos']: st.info(m)