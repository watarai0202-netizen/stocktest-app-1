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
LOCAL_CSV = "data_j.csv" if os.path.exists("data_j.csv") else None

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
show_mode = st.sidebar.radio("結果表示", ("A: 速報 + 本命（2テーブル）", "速報のみ"))
debug = st.sidebar.checkbox("🧪 デバッグログ表示", value=False)
uploaded_file = st.sidebar.file_uploader("リスト更新（CSV推奨）", type=["csv", "xls", "xlsx"])

# =========================
# 5. ユーティリティ
# =========================
def _market_key(market_type: str) -> str:
    if market_type == "プライム": return "プライム（内国株式）"
    if market_type == "スタンダード": return "スタンダード（内国株式）"
    return "グロース（内国株式）"

def _fmt_oku_yen(x: float) -> str:
    return f"{float(x):,.0f}億円"

def _calc_trading_value_oku(high: float, low: float, close: float, volume: float) -> float:
    tp = (float(high) + float(low) + float(close)) / 3.0
    return (tp * float(volume)) / 1e8

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = (filename or "").lower()
    bio = BytesIO(file_bytes)
    if name.endswith(".csv"):
        try: return pd.read_csv(bio)
        except: bio.seek(0); return pd.read_csv(bio, encoding="utf-8-sig")
    try: return pd.read_excel(bio, engine="openpyxl")
    except: bio.seek(0); return pd.read_excel(bio, engine="xlrd")

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_url(url: str) -> pd.DataFrame:
    with urllib.request.urlopen(url) as resp: b = resp.read()
    filename = url.split("?")[0].split("/")[-1]
    return load_master_from_bytes(b, filename)

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_path(path: str) -> pd.DataFrame:
    with open(path, "rb") as f: b = f.read()
    return load_master_from_bytes(b, os.path.basename(path))

def get_tickers_from_df(df: pd.DataFrame, market_type="プライム"):
    if df is None or df.empty: return [], {}
    required_cols = ["市場・商品区分", "33業種区分", "コード", "銘柄名"]
    search_key = _market_key(market_type)
    target_df = df[(df["市場・商品区分"] == search_key) & (df["33業種区分"] != "－")]
    tickers, ticker_info = [], {}
    for _, row in target_df.iterrows():
        code = str(row["コード"]).strip().replace(".0", "")
        t = f"{code}.T"
        tickers.append(t)
        ticker_info[t] = [str(row["銘柄名"]), str(row["33業種区分"])]
    return tickers, ticker_info

@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices(batch, period="20d"): # 新高値判定のため20dに拡張
    return yf.download(batch, period=period, interval="1d", progress=False, group_by="ticker", threads=True)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices_long(batch, period="3mo"):
    return yf.download(batch, period=period, interval="1d", progress=False, group_by="ticker", threads=False)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_1570_prices(period="3mo"):
    return yf.download(["1570.T"], period=period, interval="1d", progress=False, group_by="ticker", threads=False)

def safe_close_strength(row) -> float:
    h, l, c = float(row["High"]), float(row["Low"]), float(row["Close"])
    rng = max(h - l, 1e-9)
    return (c - l) / rng

def get_breakout_status(data: pd.DataFrame) -> str:
    """新高値やブレイク状態を判定する"""
    if len(data) < 2: return "通常"
    latest = data.iloc[-1]
    curr = float(latest["Close"])
    hi = float(latest["High"])
    
    # 過去20日高値（当日除く）
    hist_20 = data.iloc[:-1].tail(20)
    if len(hist_20) < 10: return "通常"
    high_20 = hist_20["High"].max()
    
    # ステータス判定
    cs = safe_close_strength(latest)
    
    if curr > high_20:
        return "🚀20日新高値"
    elif hi > high_20:
        return "👀ブレイク挑戦"
    elif cs < 0.3:
        return "⚠️上ヒゲ注意"
    elif cs > 0.9:
        return "🔥高値引け気配"
    return "順調"

def bc_filters(data: pd.DataFrame):
    if data is None or len(data) < 20: return False, {}
    latest = data.iloc[-1]
    vol20 = data["Volume"].rolling(20).mean().iloc[-1]
    if pd.isna(vol20) or float(vol20) <= 0: return False, {}
    rvol20_val = float(latest["Volume"]) / float(vol20)
    cs = safe_close_strength(latest)
    ma5 = data["Close"].rolling(5).mean().iloc[-1]
    ma25 = data["Close"].rolling(25).mean().iloc[-1]
    trend_up = (not pd.isna(ma5)) and (not pd.isna(ma25)) and (float(ma5) > float(ma25)) and (float(latest["Close"]) > float(ma25))
    prev_20_high = data["High"].rolling(20).max().shift(1).iloc[-1]
    breakout_reach = False
    if not pd.isna(prev_20_high): breakout_reach = float(latest["Close"]) > float(prev_20_high) * 0.995
    details = {"rvol20": rvol20_val, "close_strength": cs, "trend_up": trend_up, "breakout": breakout_reach}
    return True, details

# =========================
# 6. 市場天気予報
# =========================
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")
    try:
        df_m = fetch_prices(["1570.T"], period="5d")
        if df_m is None or df_m.empty: return
        s = df_m["1570.T"].dropna() if isinstance(df_m.columns, pd.MultiIndex) else df_m.dropna()
        if len(s) < 2: return
        latest, prev = s.iloc[-1], s.iloc[-2]
        curr, op, prev_cl = float(latest["Close"]), float(latest["Open"]), float(prev["Close"])
        op_ch, day_ch = (curr - op) / op * 100, (curr - prev_cl) / prev_cl * 100
        
        # 売買代金温度
        df_tv = fetch_1570_prices(period="3mo")
        tv = df_tv["1570.T"].dropna() if isinstance(df_tv.columns, pd.MultiIndex) else df_tv.dropna()
        tv_latest, tv_prev = tv.iloc[-1], tv.iloc[-2]
        tv_today = _calc_trading_value_oku(tv_latest["High"], tv_latest["Low"], tv_latest["Close"], tv_latest["Volume"])
        tv_yday = _calc_trading_value_oku(tv_prev["High"], tv_prev["Low"], tv_prev["Close"], tv_prev["Volume"])
        tv_avg20 = (((tv["High"] + tv["Low"] + tv["Close"]) / 3.0) * tv["Volume"] / 1e8).iloc[:-1].tail(20).mean()
        tv_ratio = tv_today / tv_avg20
        
        updown = "上昇" if day_ch >= 0 else "下落"
        heat = "活況" if tv_ratio >= 1.15 else "閑散" if tv_ratio <= 0.90 else "普通"
        merged = "☀️ 買い優勢" if updown=="上昇" and heat=="活況" else "☔️ 売り優勢" if updown=="下落" and heat=="活況" else f"⛅️ {updown}({heat})"
        st.info(f"統合ステータス: **{merged}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("寄付比", f"{op_ch:+.2f}%")
        c2.metric("前日比", f"{day_ch:+.2f}%")
        c3.metric("売買温度", f"{tv_ratio:.2f}x", heat)
    except: st.warning("天気予報の取得に失敗しました。")

check_market_condition()

# =========================
# 7. スキャン
# =========================
tickers, info_db = [], {}
if uploaded_file:
    df_master = load_master_from_bytes(uploaded_file.read(), uploaded_file.name)
    tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
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
            df = fetch_prices(batch, period="20d") # 20日間の最高値を見るために期間を20dに
            if df is None or df.empty: continue
            if not isinstance(df.columns, pd.MultiIndex): df = pd.concat({batch[0]: df}, axis=1)
            
            for t in batch:
                if t not in df.columns.levels[0]: continue
                data = df[t].dropna()
                if len(data) < 2: continue
                latest, prev = data.iloc[-1], data.iloc[-2]
                curr, op, vol = float(latest["Close"]), float(latest["Open"]), float(latest["Volume"])
                
                # 基本フィルター
                val = (curr * vol) / 1e8
                if val < min_trading_value: continue
                avg_vol5 = data["Volume"].tail(5).mean()
                rvol5 = vol / avg_vol5 if avg_vol5 > 0 else 0
                if rvol5 < min_rvol5: continue
                op_ch = (curr - op) / op * 100
                day_ch = (curr - float(prev["Close"])) / float(prev["Close"]) * 100
                if require_positive_from_open and op_ch <= 0: continue
                
                # ★【新設】ステータス判定
                stat = get_breakout_status(data)
                
                info = info_db.get(t, ["-", "-"])
                fast_results.append({
                    "ステータス": stat, # 高値圏の代わりにこれを入れる
                    "コード": t.replace(".T", ""),
                    "銘柄名": info[0],
                    "業種": info[1],
                    "売買代金": val,
                    "rvol5": rvol5,
                    "寄付比": op_ch,
                    "前日比": day_ch,
                    "現在値": curr,
                    "sort": val
                })
        except: continue

    bar.progress(1.0); status_area.empty()

    if fast_results:
        st.markdown("## 🚀 速報（10:00向け）")
        df_fast = pd.DataFrame(fast_results).sort_values("sort", ascending=False)
        show_fast = df_fast[["ステータス", "コード", "銘柄名", "業種", "売買代金", "rvol5", "寄付比", "前日比", "現在値"]].copy()
        # フォーマット適用
        show_fast["売買代金"] = show_fast["売買代金"].map(lambda x: f"{x:.1f}億円")
        show_fast["rvol5"] = show_fast["rvol5"].map(lambda x: f"{x:.2f}")
        show_fast["寄付比"] = show_fast["寄付比"].map(lambda x: f"{x:+.2f}%")
        show_fast["前日比"] = show_fast["前日比"].map(lambda x: f"{x:+.2f}%")
        show_fast["現在値"] = show_fast["現在値"].map(lambda x: f"{x:,.0f}")
        st.dataframe(show_fast, use_container_width=True, hide_index=True, height=500)

        # 本命スキャン
        if enable_strong_scan:
            st.markdown("## 📈 本命（継続・翌日）")
            cand_tickers = [f"{c}.T" for c in df_fast.head(max_candidates_for_strong)["コード"]]
            strong_results = []
            for j in range(0, len(cand_tickers), 30):
                sub = cand_tickers[j:j+30]
                df_long = fetch_prices_long(sub)
                if not isinstance(df_long.columns, pd.MultiIndex): df_long = pd.concat({sub[0]: df_long}, axis=1)
                for t in sub:
                    if t not in df_long.columns.levels[0]: continue
                    data_l = df_long[t].dropna()
                    ok, d = bc_filters(data_l)
                    if ok and d["rvol20"] >= min_rvol20 and d["close_strength"] >= min_close_strength_strong:
                        if need_trend_or_breakout and not (d["trend_up"] or d["breakout"]): continue
                        row = df_fast[df_fast["コード"]==t.replace(".T","")].iloc[0].to_dict()
                        row.update({"rvol20": d["rvol20"], "本命強度": d["close_strength"], "トレンド": "✅" if d["trend_up"] else "-", "ブレイク": "✅" if d["breakout"] else "-"})
                        strong_results.append(row)
            
            if strong_results:
                df_st = pd.DataFrame(strong_results)
                st.dataframe(df_st[["ステータス", "コード", "銘柄名", "売買代金", "rvol20", "トレンド", "ブレイク", "本命強度", "現在値"]], use_container_width=True, hide_index=True)
    else:
        st.warning("ヒットなし")
