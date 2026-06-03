import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np
from datetime import datetime
import re

# 1. 화면 및 테마 설정 (가장 먼저 와야 함)
st.set_page_config(page_title="Pro Trader Dashboard", layout="wide")
st.markdown("""<style>.stApp{background-color:#0b0f19;color:#e2e8f0;} div[data-testid="metric-container"]{background-color:#1e293b;border:1px solid #334155;padding:10px;border-radius:8px;} .ai-box{padding:15px;border-radius:12px;border:2px solid #334155;height:100%;}</style>""", unsafe_allow_html=True)
st.title("⚡ Pro Trader Dashboard (V12 - 국내 전 종목 무제한 검색)")

if 'memos' not in st.session_state: st.session_state['memos'] = []

# 🚨 [핵심 해결] FinanceDataReader를 이용해 코스피/코스닥 2000여 개 전 종목 리스트 1회 로드
@st.cache_data
def load_ticker_db():
    try:
        import FinanceDataReader as fdr
        # KRX(한국거래소) 전체 상장 종목 리스트 가져오기
        return fdr.StockListing('KRX')
    except Exception as e:
        return None

krx_df = load_ticker_db()

# 한글 이름 -> 티커 변환 함수
def get_ticker(name):
    name = name.strip()
    if re.match(r'^[a-zA-Z0-9^.]+$', name): return name
    
    # fdr 데이터베이스에서 종목명 검색
    if krx_df is not None and not krx_df.empty:
        match = krx_df[krx_df['Name'] == name]
        if not match.empty:
            code = match.iloc[0]['Code']
            market = str(match.iloc[0]['Market']).upper()
            return f"{code}.KQ" if 'KOSDAQ' in market else f"{code}.KS"
            
    return name # 검색 안 되면 입력값 그대로 반환

# --- 사이드바 메뉴 ---
st.sidebar.title("⚙️ 설정")

# 종목 검색창
user_input = st.sidebar.text_input("종목 (예: 삼성전자, 에코프로, QQQ)", "삼성전자")
ticker = get_ticker(user_input)

# 만약 fdr DB에 없는 한글을 쳤을 경우 경고
if re.search(r'[가-힣]', user_input) and ticker == user_input:
    st.sidebar.warning("⚠️ 상장 폐지되었거나 이름을 잘못 입력하셨습니다. (예: '현대자동차' -> '현대차')")

intervals = {"1분":"1m", "5분":"5m", "15분":"15m", "1시간":"1h", "1일":"1d", "1주":"1wk", "1개월":"1mo", "1년":"1y"}
selected_interval = st.sidebar.selectbox("⏱️ 주기", list(intervals.keys()), index=4)
y_int = intervals[selected_interval]

start_date = st.sidebar.date_input("시작일", pd.to_datetime("2021-01-01"))
end_date = st.sidebar.date_input("종료일", pd.to_datetime("today"))

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
        if df['MA5'].iloc[-1]>df['MA20'].iloc[-1]: sc+=1; rsn.append("🟢 단기: 상승세")
        else: sc-=1; rsn.append("🔴 단기: 하락세")
    if pd.notna(df['MA60'].iloc[-1]):
        if c.iloc[-1]>df['MA60'].iloc[-1]: sc+=1; rsn.append("🟢 장기: 60선 지지")
        else: sc-=1; rsn.append("🔴 장기: 60선 이탈")
    if pd.notna(df['MACD'].iloc[-1]):
        if df['MACD'].iloc[-1]>df['Signal'].iloc[-1]: sc+=1; rsn.append("🟢 모멘텀: 매수 우위")
        else: sc-=1; rsn.append("🔴 모멘텀: 매도 우위")
    if pd.notna(df['RSI'].iloc[-1]):
        if df['RSI'].iloc[-1]<40: sc+=1; rsn.append("🟢 RSI: 침체 (반등 기대)")
        elif df['RSI'].iloc[-1]>65: sc-=1; rsn.append("🔴 RSI: 과열 (고점 주의)")
        else: rsn.append("⚪ RSI: 중립")

    c_bg, c_txt, msg = ("rgba(239,68,68,0.1)","#ef4444","🔥 강력 매수") if sc>=3 else ("rgba(248,113,113,0.1)","#f87171","매수 우위") if sc>0 else ("rgba(148,163,184,0.1)","#94a3b8","관망") if sc==0 else ("rgba(96,165,250,0.1)","#60a5fa","매도 우위") if sc>-3 else ("rgba(59,130,246,0.1)","#3b82f6","❄️ 강력 매도")
    
    last = float(c.iloc[-1])
    chg = last - float(c.iloc[-2]) if len(df)>1 else 0
    rsi_val = float(df['RSI'].iloc[-1]) if pd.notna(df['RSI'].iloc[-1]) else 50.0

    c1, c2 = st.columns([1.5, 2])
    with c1: st.markdown(f'<div class="ai-box" style="background:{c_bg}; border-color:{c_txt};"><h4 style="color:#94a3b8; margin:0;">🤖 AI 판정</h4><h2 style="color:{c_txt}; margin:10px 0;">{msg}</h2><p style="color:#cbd5e1; margin:0;">{"<br>".join(rsn)}</p></div>', unsafe_allow_html=True)
    with c2:
        r1, r2 = st.columns(2)
        r1.metric("종목", f"{user_input.upper()} ({ticker})", f"{df.index[-1].strftime('%m/%d %H:%M')}")
        r2.metric("현재가", f"{last:,.2f}", f"{chg:,.2f} ({(chg/float(c.iloc[-2])*100 if chg!=0 else 0):.2f}%)")
        r3, r4 = st.columns(2)
        r3.metric("RSI", f"{rsi_val:.1f}")
        r4.metric("볼린저 밴드", "상단 돌파" if last>df['BB_up'].iloc[-1] else "하단 이탈" if last<df['BB_low'].iloc[-1] else "밴드 내")

    st.markdown("---")
    
    rows = 2; row_h = [0.75, 0.25]
    if show_macd and show_rsi: rows=4; row_h=[0.5, 0.15, 0.15, 0.2]
    elif show_macd or show_rsi: rows=3; row_h=[0.55, 0.2, 0.25]
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.015, row_heights=row_h)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=c, name="Price", increasing_line_color='#ef4444', increasing_fillcolor='#ef4444', decreasing_line_color='#3b82f6', decreasing_fillcolor='#3b82f6'), row=1, col=1)
    
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='rgba(255,255,255,0.4)', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='rgba(255,255,255,0.4)', dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.05)'), row=1, col=1)
    if show_ichi and pd.notna(df['Senkou_A'].iloc[-1]):
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_A'], line=dict(color='rgba(0,0,0,0)'), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Senkou_B'], fill='tonexty', fillcolor='rgba(0,250,154,0.1)', line=dict(color='rgba(0,0,0,0)')), row=1, col=1)
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#fbbf24', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#34d399', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#93c5fd', width=2)), row=1, col=1)
    if show_sig:
        fig.add_trace(go.Scatter(x=df[df['Buy']].index, y=df[df['Buy']]['Low']*0.99, mode='markers', marker=dict(symbol='triangle-up', size=14, color='#ef4444')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell']].index, y=df[df['Sell']]['High']*1.01, mode='markers', marker=dict(symbol='triangle-down', size=14, color='#3b82f6')), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=['#ef4444' if row['Close']>=row['Open'] else '#3b82f6' for _, row in df.iterrows()]), row=2, col=1)
    
    curr = 3
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#60a5fa')), row=curr, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#f59e0b')), row=curr, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=np.where(df['MACD_H']>0, '#ef4444', '#3b82f6')), row=curr, col=1)
        curr+=1
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#c084fc')), row=curr, col=1)
        fig.add_hline(y=70, line_color="#3b82f6", line_dash="dash", row=curr, col=1)
        fig.add_hline(y=30, line_color="#ef4444", line_dash="dash", row=curr, col=1)

    if y_int == '1y': fig.update_xaxes(dtick="M12", tickformat="%Y")
    elif y_int in ['1d','1wk']: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    elif y_int in ['1m','5m','15m','1h']: fig.update_xaxes(rangebreaks=[dict(bounds=[16, 9.5], pattern="hour"), dict(bounds=["sat", "mon"])])

    fig.update_layout(height=700, template="plotly_dark", dragmode='pan', hovermode='x unified', showlegend=False, xaxis_rangeslider_visible=False, margin=dict(l=10, r=50, t=10, b=10), plot_bgcolor='#0b0f19', paper_bgcolor='#0b0f19')
    fig.update_yaxes(side="right", showgrid=True, gridcolor='#1e293b', zeroline=False)
    fig.update_xaxes(showgrid=True, gridcolor='#1e293b', zeroline=False)
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
else: st.error("데이터 오류. 장이 닫혀있거나 종목명을 다시 확인해 주세요.")

m1, m2 = st.columns([4, 1])
with m1: memo = st.text_input("메모", label_visibility="collapsed", placeholder="여기에 매매 기록을 남겨보세요.")
with m2: 
    if st.button("저장", use_container_width=True) and memo:
        st.session_state['memos'].insert(0, f"**[{datetime.now().strftime('%m/%d %H:%M')}]** {memo}")
for m in st.session_state['memos']: st.info(m)