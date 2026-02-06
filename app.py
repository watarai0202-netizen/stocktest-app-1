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
# 3. GitHub CSV URL（★ここ重要）
# =========================
GITHUB_CSV_RAW_URL = "https://raw.githubusercontent.com/watarai0202-netizen/stocktest-app-1/main/data_j.csv"

# ローカル保険（任意）
LOCAL_CSV = "data_j.csv" if os.path.exists("data_j.csv") else None

# =========================
# 4. サイドバー設定
# =========================
st.sidebar.title("⚙️ 設定")

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
min_close_strength_fast = st.sidebar.slider("🔧 高値圏の強さ(速報) 0-1", 0.0, 1.0, 0.60)

# 本命（継続・翌日）向けフィルター
st.sidebar.subheader("📈 本命（継続・翌日）")
enable_strong_scan = st.sidebar.checkbox("本命フィルターも実行する", value=True)
max_candidates_for_strong = st.sidebar.slider("本命精査する候補上限（多いと重い）", 30, 300, 120, step=10)
min_rvol20 = st.sidebar.slider("📢 出来高急増度 rvol(20日) (倍)", 1.0, 5.0, 1.5, step=0.1)
min_close_strength_strong = st.sidebar.slider("🔧 高値圏の強さ(本命) 0-1", 0.0, 1.0, 0.70)
need_trend_or_breakout = st.sidebar.checkbox("✅ トレンド or ブレイク到達 を必須", value=True)

# 表示モード
st.sidebar.subheader("🧾 表示")
show_mode = st.sidebar.radio("結果表示", ("A: 速報 + 本命（2テーブル）", "速報のみ"))

debug = st.sidebar.checkbox("🧪 デバッグログ表示", value=False)

# ✅ CSVも受け付ける
uploaded_file = st.sidebar.file_uploader("リスト更新（CSV推奨）", type=["csv", "xls", "xlsx"])


# =========================
# 5. ユーティリティ
# =========================
def _market_key(market_type: str) -> str:
    if market_type == "プライム":
        return "プライム（内国株式）"
    if market_type == "スタンダード":
        return "スタンダード（内国株式）"
    return "グロース（内国株式）"


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """CSV/XLSX/XLS を bytes から読み込む（キャッシュあり）"""
    name = (filename or "").lower()

    if name.endswith(".csv"):
        bio = BytesIO(file_bytes)
        try:
            return pd.read_csv(bio)
        except UnicodeDecodeError:
            bio.seek(0)
            return pd.read_csv(bio, encoding="utf-8-sig")

    # Excel
    bio = BytesIO(file_bytes)
    try:
        return pd.read_excel(bio, engine="openpyxl")
    except Exception:
        bio.seek(0)
        return pd.read_excel(bio, engine="xlrd")


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_url(url: str) -> pd.DataFrame:
    with urllib.request.urlopen(url) as resp:
        b = resp.read()
    filename = url.split("?")[0].split("/")[-1]
    return load_master_from_bytes(b, filename)


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_from_path(path: str) -> pd.DataFrame:
    with open(path, "rb") as f:
        b = f.read()
    return load_master_from_bytes(b, os.path.basename(path))


def get_tickers_from_df(df: pd.DataFrame, market_type="プライム"):
    """必須列チェック＋市場抽出＋ETF除外"""
    if df is None or df.empty:
        return [], {}

    required_cols = ["市場・商品区分", "33業種区分", "コード", "銘柄名"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"銘柄マスターの列名が違います。不足: {missing}\n"
            f"現在の列: {list(df.columns)}\n"
            f"必要列: {required_cols}"
        )

    search_key = _market_key(market_type)

    target_df = df[df["市場・商品区分"] == search_key]
    target_df = target_df[target_df["33業種区分"] != "－"]  # ETF除外

    tickers = []
    ticker_info = {}
    for _, row in target_df.iterrows():
        code = str(row["コード"]).strip()
        if code.endswith(".0"):
            code = code[:-2]
        t = f"{code}.T"
        tickers.append(t)
        ticker_info[t] = [str(row["銘柄名"]), str(row["33業種区分"])]

    return tickers, ticker_info


@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices(batch, period="5d"):
    """yfinance取得をキャッシュして高速化"""
    return yf.download(
        batch,
        period=period,
        interval="1d",
        progress=False,
        group_by="ticker",
        threads=True
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices_long(batch, period="3mo"):
    """本命フィルター用（候補だけ長めデータ）"""
    return yf.download(
        batch,
        period=period,
        interval="1d",
        progress=False,
        group_by="ticker",
        threads=True
    )


def safe_close_strength(row) -> float:
    """(Close-Low)/(High-Low) 0〜1。High==Low対策あり"""
    h = float(row["High"])
    l = float(row["Low"])
    c = float(row["Close"])
    rng = max(h - l, 1e-9)
    return (c - l) / rng


def bc_filters(data: pd.DataFrame):
    """
    本命（継続・翌日）フィルター判定
    - rvol20
    - trend_up (5MA>25MA かつ Close>25MA)
    - breakout_reach (Closeが直近20日高値に近い/超え)
    - close_strength（高値圏引け）
    """
    if data is None or len(data) < 30:
        return False, {}

    latest = data.iloc[-1]

    # rvol20
    vol20 = data["Volume"].rolling(20).mean().iloc[-1]
    if pd.isna(vol20) or float(vol20) <= 0:
        return False, {}
    rvol20_val = float(latest["Volume"]) / float(vol20)

    # close strength
    cs = safe_close_strength(latest)

    # trend (5MA/25MA)
    ma5 = data["Close"].rolling(5).mean().iloc[-1]
    ma25 = data["Close"].rolling(25).mean().iloc[-1]
    trend_up = (not pd.isna(ma5)) and (not pd.isna(ma25)) and (float(ma5) > float(ma25)) and (float(latest["Close"]) > float(ma25))

    # breakout reach（直近20日高値）
    prev_20_high = data["High"].rolling(20).max().shift(1).iloc[-1]
    breakout_reach = False
    if not pd.isna(prev_20_high):
        breakout_reach = float(latest["Close"]) > float(prev_20_high) * 0.995  # 0.5%手前からOK

    details = {
        "rvol20": rvol20_val,
        "close_strength": cs,
        "trend_up": trend_up,
        "breakout": breakout_reach
    }
    return True, details


# =========================
# 6. メイン画面
# =========================
st.title(f"⚡️ {target_market}・激辛スキャナー")

# =========================
# 7. 市場天気予報（1570）
# =========================
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")
    try:
        df_m = fetch_prices(["1570.T"], period="5d")
        if df_m is None or df_m.empty:
            return

        if isinstance(df_m.columns, pd.MultiIndex):
            s = df_m["1570.T"].dropna()
            if len(s) < 2:
                return
            latest = s.iloc[-1]
            prev = s.iloc[-2]
            curr = float(latest["Close"])
            op = float(latest["Open"])
            prev_cl = float(prev["Close"])
        else:
            s = df_m.dropna()
            if len(s) < 2:
                return
            latest = s.iloc[-1]
            prev = s.iloc[-2]
            curr = float(latest["Close"])
            op = float(latest["Open"])
            prev_cl = float(prev["Close"])

        op_ch = (curr - op) / op * 100
        day_ch = (curr - prev_cl) / prev_cl * 100

        status = "☁️ 曇り"
        if op_ch > 0.5 and day_ch > 1.0:
            status = "☀️ 快晴 (🔥 トレンド上昇中)"
        elif op_ch > 1.0:
            status = "🌤 晴れ (🚀 買い優勢)"
        elif day_ch < -1.0 and op_ch < -0.5:
            status = "☔️ 土砂降り (📉 暴落警戒)"
        elif day_ch < -0.5:
            status = "☁️ 雨 (弱い)"

        st.info(f"現在のステータス: **{status}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("現在値", f"{curr:,.0f}円")
        c2.metric("寄付比", f"{op_ch:+.2f}%")
        c3.metric("前日比", f"{day_ch:+.2f}%")
        st.divider()

    except Exception as e:
        if debug:
            st.warning(f"天気予報取得エラー: {e}")

check_market_condition()

# =========================
# 8. 銘柄マスター読み込み
# =========================
tickers = []
info_db = {}
master_source = "未取得"
df_master = None

try:
    if uploaded_file is not None:
        b = uploaded_file.read()
        df_master = load_master_from_bytes(b, uploaded_file.name)
        tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
        master_source = f"アップロード: {uploaded_file.name}"
    else:
        if GITHUB_CSV_RAW_URL:
            df_master = load_master_from_url(GITHUB_CSV_RAW_URL)
            tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
            master_source = "GitHub(CSV)"
        elif LOCAL_CSV:
            df_master = load_master_from_path(LOCAL_CSV)
            tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
            master_source = f"ローカル: {LOCAL_CSV}"
        else:
            st.error("銘柄マスターがありません。CSVをアップロードするか、GitHub raw URLを設定してください。")
            st.stop()

except Exception as e:
    st.error("銘柄マスターの読み込みに失敗しました。CSV列名や文字コード、URLを確認してください。")
    if debug:
        st.exception(e)
    st.stop()

st.sidebar.caption(f"📌 マスター参照元: {master_source}")
st.sidebar.caption(f"📌 対象銘柄数(市場抽出後): {len(tickers)}")

if df_master is not None and len(tickers) == 0:
    st.error("銘柄リストが0件です。CSVの市場表記やETF除外条件の結果、対象が無い可能性があります。")
    if debug:
        st.write(df_master["市場・商品区分"].value_counts().head(10))
        st.write(df_master["33業種区分"].value_counts().head(10))
    st.stop()

# =========================
# 9. スキャン（速報 → 本命）
# =========================
st.markdown("### 🔎 スキャン")
st.caption("🚀 速報は“今強い”を拾う（10:00向け）。📈 本命は速報候補から“継続/翌日期待”を絞る。")

if st.button(f"📡 {target_market}をスキャン開始", type="primary"):
    status_area = st.empty()
    bar = st.progress(0)

    # --- 速報（全銘柄を5dで見る） ---
    fast_results = []
    batch_size = 30  # あなたの運用方針を維持
    total = len(tickers)

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        prog = min(i / total, 1.0)
        status_area.text(f"速報スキャン中... {i} / {total} 銘柄完了")
        bar.progress(prog)

        try:
            time.sleep(0.02)
            df = fetch_prices(batch, period="5d")
            if df is None or df.empty:
                continue

            if not isinstance(df.columns, pd.MultiIndex):
                df = pd.concat({batch[0]: df}, axis=1)

            available = set(df.columns.levels[0].tolist())
            valid_tickers = [t for t in batch if t in available]

            for t in valid_tickers:
                try:
                    data = df[t].dropna()
                    if len(data) < 2:
                        continue

                    latest = data.iloc[-1]
                    prev = data.iloc[-2]

                    curr = float(latest["Close"])
                    op = float(latest["Open"])
                    vol = float(latest["Volume"])

                    # 流動性（億円）
                    val = (curr * vol) / 100000000
                    if val < min_trading_value:
                        continue

                    # rvol(5d)
                    avg_vol5 = float(data["Volume"].mean())
                    if avg_vol5 <= 0:
                        continue
                    rvol5 = vol / avg_vol5
                    if rvol5 < min_rvol5:
                        continue

                    # 価格変化
                    op_ch = (curr - op) / op * 100
                    day_ch = (curr - float(prev["Close"])) / float(prev["Close"]) * 100

                    # 寄り天抑制（任意）
                    if require_positive_from_open and op_ch <= 0:
                        continue

                    # “高値圏の強さ”（速報は緩めでOK）
                    cs_fast = safe_close_strength(latest)
                    if cs_fast < min_close_strength_fast:
                        continue

                    # 状態ラベル（速報用）
                    status = "🚀 速報"
                    if op_ch > 1.0 and day_ch > 2.0:
                        status = "🔥🔥 速報強"
                    elif op_ch > 2.0:
                        status = "🚀 急伸"

                    info = info_db.get(t, ["-", "-"])
                    fast_results.append({
                        "状態": status,
                        "コード": t.replace(".T", ""),
                        "銘柄名": info[0],
                        "売買代金": val,
                        "rvol5": rvol5,
                        "寄付比": op_ch,
                        "前日比": day_ch,
                        "現在値": curr,
                        "高値圏(速報)": cs_fast,
                        "sort": val
                    })

                except Exception as e:
                    if debug:
                        st.write(f"[速報:{t}] エラー: {e}")
                    continue

        except Exception as e:
            if debug:
                st.write(f"速報バッチ取得エラー({i}-{i+batch_size}): {e}")
            continue

    bar.progress(100)
    status_area.empty()

    # 表示：速報
    st.markdown("## 🚀 速報（10:00向け）")
    if fast_results:
        df_fast = pd.DataFrame(fast_results).sort_values("sort", ascending=False)

        # 表示用整形
        show_fast = df_fast[["状態", "コード", "銘柄名", "売買代金", "rvol5", "寄付比", "前日比", "現在値", "高値圏(速報)"]].copy()
        show_fast["売買代金"] = show_fast["売買代金"].map(lambda x: f"{x:.1f}億円")
        show_fast["rvol5"] = show_fast["rvol5"].map(lambda x: f"{x:.2f}")
        show_fast["寄付比"] = show_fast["寄付比"].map(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
        show_fast["前日比"] = show_fast["前日比"].map(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
        show_fast["現在値"] = show_fast["現在値"].map(lambda x: f"{x:,.0f}")
        show_fast["高値圏(速報)"] = show_fast["高値圏(速報)"].map(lambda x: f"{x:.2f}")

        st.success(f"速報ヒット: {len(df_fast)}件")
        st.dataframe(show_fast, use_container_width=True, hide_index=True, height=520)
    else:
        st.warning("速報条件に合う銘柄はありませんでした。")

    # 速報のみなら終了
    if show_mode == "速報のみ" or (not enable_strong_scan) or (not fast_results):
        st.stop()

    # --- 本命（速報候補だけを3moで精査） ---
    st.markdown("## 📈 本命（継続・翌日）")
    st.caption("速報候補から、rvol20・トレンド・ブレイク到達・高値圏の強さで“残るやつ”だけを抽出します。")

    # 候補を絞って重さを管理（売買代金上位から）
    df_fast_sorted = pd.DataFrame(fast_results).sort_values("sort", ascending=False)
    df_fast_cand = df_fast_sorted.head(int(max_candidates_for_strong)).copy()

    cand_tickers = [f"{c}.T" for c in df_fast_cand["コード"].tolist()]

    status_area = st.empty()
    bar = st.progress(0)

    strong_results = []

    # 候補は多くても数百なので、まとめて取得（必要なら分割）
    status_area.text(f"本命精査データ取得中... 候補 {len(cand_tickers)} 銘柄")
    try:
        df_long = fetch_prices_long(cand_tickers, period="3mo")
    except Exception as e:
        st.error("本命用の株価取得に失敗しました（yfinance側の一時不調の可能性）。")
        if debug:
            st.exception(e)
        st.stop()

    bar.progress(30)
    status_area.text("本命判定中...")

    if df_long is None or df_long.empty:
        st.warning("本命用データが空でした。時間をおいて再実行してください。")
        st.stop()

    if not isinstance(df_long.columns, pd.MultiIndex):
        df_long = pd.concat({cand_tickers[0]: df_long}, axis=1)

    available_long = set(df_long.columns.levels[0].tolist())

    total_cand = len(cand_tickers)
    for idx, t in enumerate(cand_tickers):
        prog = 30 + int(70 * (idx / max(total_cand, 1)))
        bar.progress(min(prog, 100))

        if t not in available_long:
            continue

        try:
            data = df_long[t].dropna()
            ok, d = bc_filters(data)
            if not ok:
                continue

            # 閾値適用
            if d["rvol20"] < min_rvol20:
                continue
            if d["close_strength"] < min_close_strength_strong:
                continue

            if need_trend_or_breakout and not (d["trend_up"] or d["breakout"]):
                continue

            # 元の速報行を引き継ぎ
            row_fast = df_fast_cand[df_fast_cand["コード"] == t.replace(".T", "")].iloc[0].to_dict()

            # 本命評価を付加
            row_fast["rvol20"] = d["rvol20"]
            row_fast["高値圏(本命)"] = d["close_strength"]
            row_fast["トレンド"] = "✅" if d["trend_up"] else "-"
            row_fast["ブレイク"] = "✅" if d["breakout"] else "-"

            # スコア例：流動性×注目度（並び替え用）
            row_fast["sort_strong"] = float(row_fast["売買代金"]) * float(d["rvol20"])
            row_fast["状態"] = "📈 本命"
            strong_results.append(row_fast)

        except Exception as e:
            if debug:
                st.write(f"[本命:{t}] エラー: {e}")
            continue

    bar.progress(100)
    status_area.empty()

    if strong_results:
        df_strong = pd.DataFrame(strong_results).sort_values("sort_strong", ascending=False)

        show_strong = df_strong[
            ["状態", "コード", "銘柄名", "売買代金", "rvol5", "rvol20", "寄付比", "前日比", "現在値",
             "トレンド", "ブレイク", "高値圏(速報)", "高値圏(本命)"]
        ].copy()

        show_strong["売買代金"] = show_strong["売買代金"].map(lambda x: f"{float(x):.1f}億円")
        show_strong["rvol5"] = show_strong["rvol5"].map(lambda x: f"{float(x):.2f}")
        show_strong["rvol20"] = show_strong["rvol20"].map(lambda x: f"{float(x):.2f}")
