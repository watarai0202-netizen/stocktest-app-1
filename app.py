import streamlit as st
import pandas as pd
import yfinance as yf
import os
import time
from io import BytesIO
import urllib.request

# =========================
# 1. アプリ設定
# =========================
st.set_page_config(page_title="全市場対応スキャナー", layout="wide")
MY_PASSWORD = "stock testa"

# =========================
# 2. 認証機能
# =========================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

# =========================
# 3. GitHub CSV URL
# =========================
GITHUB_CSV_RAW_URL = "https://raw.githubusercontent.com/watarai0202-netizen/stocktest-app-1/main/data_j.csv"

# =========================
# 4. サイドバー設定
# =========================
st.sidebar.title("⚙️ 設定")

if st.sidebar.button("🔄 キャッシュクリア"):
    st.cache_data.clear()
    st.rerun()

target_market = st.sidebar.radio(
    "📊 市場を選択",
    ("プライム", "スタンダード", "グロース"),
    index=0
)

# 速報（10:00）向けフィルター
st.sidebar.subheader("🚀 速報（10:00向け）")
min_trading_value = st.sidebar.slider("💰 最低売買代金 (億円)", 1, 50, 3)
min_rvol5 = st.sidebar.slider("📢 出来高急増度 rvol(5日) (倍)", 0.1, 5.0, 0.5)
require_positive_from_open = st.sidebar.checkbox("✅ 現在値が寄付より上（寄り天抑制）", value=True)

# 本命（継続・翌日）向けフィルター
st.sidebar.subheader("📈 本命（継続・翌日）")
enable_strong_scan = st.sidebar.checkbox("本命フィルターも実行する", value=True)
max_candidates_for_strong = st.sidebar.slider("本命精査する候補上限", 30, 300, 120, step=10)
min_rvol20 = st.sidebar.slider("📢 出来高急増度 rvol(20日) (倍)", 1.0, 5.0, 1.5, step=0.1)
min_close_strength_strong = st.sidebar.slider("🔧 高値圏の強さ(本命) 0-1", 0.0, 1.0, 0.70)
need_trend_or_breakout = st.sidebar.checkbox("✅ トレンド or ブレイク到達 を必須", value=True)

st.sidebar.subheader("🧾 表示")
debug = st.sidebar.checkbox("🧪 デバッグログ表示", value=False)
uploaded_file = st.sidebar.file_uploader("リスト更新（CSV推奨）", type=["csv", "xls", "xlsx"])

# =========================
# 5. ユーティリティ
# =========================
def _market_key(market_type: str) -> str:
    if market_type == "プライム": return "プライム（内国株式）"
    if market_type == "スタンダード": return "スタンダード（内国株式）"
    return "グロース（内国株式）"

def _calc_trading_value_oku(high: float, low: float, close: float, volume: float) -> float:
    tp = (float(high) + float(low) + float(close)) / 3.0
    return (tp * float(volume)) / 1e8

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_url(url: str) -> pd.DataFrame:
    with urllib.request.urlopen(url) as resp: b = resp.read()
    return pd.read_csv(BytesIO(b))

def get_tickers_from_df(df: pd.DataFrame, market_type="プライム"):
    search_key = _market_key(market_type)
    target_df = df[(df["市場・商品区分"] == search_key) & (df["33業種区分"] != "－")]
    tickers, ticker_info = [], {}
    for _, row in target_df.iterrows():
        t = f"{str(row['コード']).strip().replace('.0', '')}.T"
        tickers.append(t)
        ticker_info[t] = [str(row["銘柄名"]), str(row["33業種区分"])]
    return tickers, ticker_info

@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices(batch, period="25d"): 
    return yf.download(batch, period=period, interval="1d", progress=False, group_by="ticker", threads=True)

def safe_close_strength(row) -> float:
    h, l, c = float(row["High"]), float(row["Low"]), float(row["Close"])
    rng = max(h - l, 1e-9)
    return (c - l) / rng

def get_breakout_status(data: pd.DataFrame) -> str:
    if len(data) < 2: return "通常"
    latest = data.iloc[-1]
    curr, hi = float(latest["Close"]), float(latest["High"])
    hist_20 = data.iloc[:-1].tail(20)
    if len(hist_20) < 1: return "通常"
    high_20 = hist_20["High"].max()
    cs = safe_close_strength(latest)
    if curr > high_20: return "🚀20日新高値"
    elif hi > high_20: return "👀ブレイク挑戦"
    elif cs < 0.3: return "⚠️上ヒゲ注意"
    elif cs > 0.9: return "🔥高値引け気配"
    return "順調"

# =========================
# 6. 市場天気予報 (1570.T)
# =========================
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")
    try:
        df_m = fetch_prices(["1570.T"], period="3mo")
        if df_m is None or df_m.empty: return
        
        # マルチインデックス対策
        data = df_m["1570.T"] if "1570.T" in df_m.columns.levels[0] else df_m
        data = data.dropna()
        if len(data) < 2: return
        
        latest, prev = data.iloc[-1], data.iloc[-2]
        curr, op, prev_cl = float(latest["Close"]), float(latest["Open"]), float(prev["Close"])
        
        op_ch = (curr - op) / op * 100
        day_ch = (curr - prev_cl) / prev_cl * 100
        
        # 売買代金（温度）の計算
        tv_today = _calc_trading_value_oku(latest["High"], latest["Low"], latest["Close"], latest["Volume"])
        tv_avg20 = data.apply(lambda r: _calc_trading_value_oku(r['High'], r['Low'], r['Close'], r['Volume']), axis=1).iloc[:-1].tail(20).mean()
        tv_ratio = tv_today / tv_avg20
        
        updown = "上昇" if day_ch >= 0 else "下落"
        heat = "活況" if tv_ratio >= 1.15 else "閑散" if tv_ratio <= 0.90 else "普通"
        
        if updown == "上昇" and heat == "活況": status, color = "☀️ 買い優勢", "blue"
        elif updown == "下落" and heat == "活況": status, color = "☔️ 売り優勢", "red"
        else: status, color = f"⛅️ {updown}({heat})", "green"
        
        st.info(f"統合ステータス: **{status}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("寄付比", f"{op_ch:+.2f}%")
        c2.metric("前日比", f"{day_ch:+.2f}%")
        c3.metric("売買温度", f"{tv_ratio:.2f}x", heat)
    except Exception as e:
        if debug: st.warning(f"天気予報エラー: {e}")

# メイン実行前に天気を表示
check_market_condition()

# =========================
# 7. スキャン実行
# =========================
if uploaded_file:
    df_master = pd.read_csv(uploaded_file)
else:
    df_master = load_master_from_url(GITHUB_CSV_RAW_URL)

tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)

st.markdown("### 🔎 スキャン")
if st.button(f"📡 {target_market}をスキャン開始", type="primary"):
    status_area = st.empty()
    bar = st.progress(0)
    fast_results = []
    batch_size = 30
    total = len(tickers)

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        bar.progress(min(i / total, 1.0))
        status_area.text(f"スキャン中... {i} / {total}")
        try:
            df = fetch_prices(batch)
            if df is None or df.empty: continue
            if not isinstance(df.columns, pd.MultiIndex): df = pd.concat({batch[0]: df}, axis=1)
            
            for t in batch:
                if t not in df.columns.levels[0]: continue
                data = df[t].dropna()
                if len(data) < 20: continue
                latest, prev = data.iloc[-1], data.iloc[-2]
                curr, op, vol = float(latest["Close"]), float(latest["Open"]), float(latest["Volume"])
                
                val = (curr * vol) / 1e8
                if val < min_trading_value: continue
                
                avg_vol5 = data["Volume"].tail(5).mean()
                rvol5 = vol / avg_vol5 if avg_vol5 > 0 else 0
                if rvol5 < min_rvol5: continue
                
                op_ch = (curr - op) / op * 100
                if require_positive_from_open and op_ch <= 0: continue
                
                day_ch = (curr - float(prev["Close"])) / float(prev["Close"]) * 100
                stat = get_breakout_status(data)
                info = info_db.get(t, ["-", "-"])
                
                fast_results.append({
                    "ステータス": stat, "コード": t.replace(".T", ""), "銘柄名": info[0], "業種": info[1],
                    "売買代金": val, "rvol5": rvol5, "寄付比": op_ch, "前日比": day_ch, "現在値": curr, "ticker": t
                })
        except: continue

    bar.progress(1.0); status_area.empty()

    if fast_results:
        df_fast = pd.DataFrame(fast_results).sort_values("売買代金", ascending=False)
        st.markdown("## 🚀 速報（10:00向け）")
        show_fast = df_fast.copy()
        show_fast["売買代金"] = show_fast["売買代金"].map(lambda x: f"{x:.1f}億円")
        show_fast["rvol5"] = show_fast["rvol5"].map(lambda x: f"{x:.2f}")
        show_fast["寄付比"] = show_fast["寄付比"].map(lambda x: f"{x:+.2f}%")
        show_fast["前日比"] = show_fast["前日比"].map(lambda x: f"{x:+.2f}%")
        show_fast["現在値"] = show_fast["現在値"].map(lambda x: f"{x:,.0f}")
        st.dataframe(show_fast.drop(columns=["ticker"]), use_container_width=True, hide_index=True)

        if enable_strong_scan:
            st.markdown("## 📈 本命（継続・翌日）")
            strong_results = []
            cand_tickers = df_fast.head(max_candidates_for_strong)["ticker"].tolist()
            
            for t in cand_tickers:
                # 既に取得済みの25日データで本命判定
                data_l = fetch_prices([t], period="3mo")[t].dropna()
                vol20 = data_l["Volume"].rolling(20).mean().iloc[-1]
                rvol20 = float(data_l["Volume"].iloc[-1]) / vol20 if vol20 > 0 else 0
                cs = safe_close_strength(data_l.iloc[-1])
                
                if rvol20 >= min_rvol20 and cs >= min_close_strength_strong:
                    row = df_fast[df_fast["ticker"] == t].iloc[0].to_dict()
                    row.update({"rvol20": rvol20, "本命強度": cs})
                    strong_results.append(row)
            
            if strong_results:
                df_st = pd.DataFrame(strong_results)
                show_st = df_st.copy()
                show_st["売買代金"] = show_st["売買代金"].map(lambda x: f"{x:.1f}億円")
                show_st["rvol20"] = show_st["rvol20"].map(lambda x: f"{x:.2f}")
                show_st["本命強度"] = show_st["本命強度"].map(lambda x: f"{x:.2f}")
                show_st["現在値"] = show_st["現在値"].map(lambda x: f"{x:,.0f}")
                st.dataframe(show_st[["ステータス", "コード", "銘柄名", "売買代金", "rvol20", "本命強度", "現在値"]], use_container_width=True, hide_index=True)
