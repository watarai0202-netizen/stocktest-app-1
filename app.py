import streamlit as st
import pandas as pd
import yfinance as yf
import os
import time
from io import BytesIO

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
# 3. 銘柄マスター（CSV運用）
# =========================
# ★ここを差し替え！
GITHUB_CSV_RAW_URL = "https://raw.githubusercontent.com/watarai0202-netizen/stocktest-app-1/main/data_j.csv"

# =========================
# 4. サイドバー設定
# =========================
st.sidebar.title("⚙️ 設定")

target_market = st.sidebar.radio(
    "📊 市場を選択",
    ("プライム", "スタンダード", "グロース"),
    index=0
)

filter_level = st.sidebar.radio("🔍 抽出モード", ("Lv.2 精鋭 (🔥🚀)", "Lv.3 神7 (TOP 7)"))

min_trading_value = st.sidebar.slider("💰 最低売買代金 (億円)", 1, 50, 3)
min_rvol = st.sidebar.slider("📢 出来高急増度 (倍)", 0.1, 5.0, 0.5)

debug = st.sidebar.checkbox("🧪 デバッグログ表示", value=False)

# CSVアップロードで一時上書き（GitHub更新前のテスト用）
uploaded_csv = st.sidebar.file_uploader("リスト更新（CSV）", type=["csv"])


# =========================
# 5. 関数定義
# =========================
def _market_key(market_type: str) -> str:
    if market_type == "プライム":
        return "プライム（内国株式）"
    if market_type == "スタンダード":
        return "スタンダード（内国株式）"
    return "グロース（内国株式）"


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_csv_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    """
    CSVのbytesをDataFrameへ。
    文字コードは utf-8 / utf-8-sig を想定して吸収。
    """
    bio = BytesIO(file_bytes)
    try:
        df = pd.read_csv(bio)
        return df
    except UnicodeDecodeError:
        bio.seek(0)
        df = pd.read_csv(bio, encoding="utf-8-sig")
        return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_csv_from_path(path: str) -> pd.DataFrame:
    with open(path, "rb") as f:
        b = f.read()
    return load_master_csv_from_bytes(b)


@st.cache_data(ttl=3600, show_spinner=False)
def load_master_csv_from_url(url: str) -> pd.DataFrame:
    # pandasのread_csv(url)でも良いが、bytesに寄せると扱いが安定
    import urllib.request
    with urllib.request.urlopen(url) as resp:
        b = resp.read()
    return load_master_csv_from_bytes(b)


def get_tickers_from_df(df: pd.DataFrame, market_type="プライム"):
    """
    CSVの列名は以下を要求:
      - 市場・商品区分
      - 33業種区分
      - コード
      - 銘柄名
    """
    if df is None or df.empty:
        return [], {}

    required_cols = ["市場・商品区分", "33業種区分", "コード", "銘柄名"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSVに必要な列がありません: {missing}\n"
            f"現在の列: {list(df.columns)}\n"
            f"必要列: {required_cols}"
        )

    search_key = _market_key(market_type)

    target_df = df[df["市場・商品区分"] == search_key]
    target_df = target_df[target_df["33業種区分"] != "－"]  # ETF除外

    tickers = []
    ticker_info = {}

    for _, row in target_df.iterrows():
        code_raw = str(row["コード"]).strip()

        # もし "1301.0" みたいに入ってきた場合の保険
        if code_raw.endswith(".0"):
            code_raw = code_raw[:-2]

        t = f"{code_raw}.T"
        tickers.append(t)
        ticker_info[t] = [str(row["銘柄名"]), str(row["33業種区分"])]

    return tickers, ticker_info


@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices(batch, period="5d"):
    """
    yfinance取得キャッシュ（同じバッチを連打しても再取得しない）
    """
    return yf.download(
        batch,
        period=period,
        interval="1d",
        progress=False,
        group_by="ticker",
        threads=True
    )


# =========================
# 6. メイン画面
# =========================
st.title(f"⚡️ {target_market}・激辛スキャナー")


# =========================
# 7. 市場天気予報
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
#    優先順位: アップロードCSV > GitHub CSV > ローカルCSV
# =========================
tickers = []
info_db = {}
master_source = "未取得"

try:
    if uploaded_csv is not None:
        b = uploaded_csv.read()
        df_master = load_master_csv_from_bytes(b)
        tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
        master_source = f"アップロード: {uploaded_csv.name}"

    elif GITHUB_CSV_RAW_URL:
        df_master = load_master_csv_from_url(GITHUB_CSV_RAW_URL)
        tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
        master_source = "GitHub(CSV)"

    elif LOCAL_CSV:
        df_master = load_master_csv_from_path(LOCAL_CSV)
        tickers, info_db = get_tickers_from_df(df_master, market_type=target_market)
        master_source = f"ローカル: {LOCAL_CSV}"

    else:
        st.error("銘柄マスターがありません。CSVをアップロードするか、GitHubのraw URLを設定してください。")

except Exception as e:
    st.error("銘柄マスター(CSV)の読み込みに失敗しました。CSVの列名や文字コードを確認してください。")
    if debug:
        st.exception(e)

st.sidebar.caption(f"📌 マスター参照元: {master_source}")
st.sidebar.caption(f"📌 対象銘柄数(市場抽出後): {len(tickers)}")


# =========================
# 9. スキャン処理
# =========================
if tickers and st.button(f"📡 {target_market}をスキャン開始", type="primary"):
    status_area = st.empty()
    bar = st.progress(0)
    results = []

    total = len(tickers)

    # バッチ回数を減らした方が速いことが多いので60を基本に
    batch_size = 60 if total >= 60 else total
    period = "5d"

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        prog = min(i / total, 1.0)
        status_area.text(f"データ分析中... {i} / {total} 銘柄完了")
        bar.progress(prog)

        try:
            time.sleep(0.02)
            df = fetch_prices(batch, period=period)
            if df is None or df.empty:
                continue

            # MultiIndex想定（ticker→OHLCV）
            if not isinstance(df.columns, pd.MultiIndex):
                # 単一Ticker返却の保険
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

                    val = (curr * vol) / 100000000  # 億円
                    if val < min_trading_value:
                        continue

                    avg_vol = float(data["Volume"].mean())
                    if avg_vol <= 0:
                        continue

                    rvol = vol / avg_vol
                    if rvol < min_rvol:
                        continue

                    op_ch = (curr - op) / op * 100
                    day_ch = (curr - float(prev["Close"])) / float(prev["Close"]) * 100

                    status, prio = "-", 0
                    if op_ch > 1.0 and day_ch > 2.0:
                        status, prio = "🔥🔥 大陽線", 2
                    elif op_ch > 2.0:
                        status, prio = "🚀 急伸", 1

                    if prio > 0:
                        info = info_db.get(t, ["-", "-"])
                        results.append({
                            "コード": t.replace(".T", ""),
                            "銘柄名": info[0],
                            "業種": info[1],
                            "売買代金": val,
                            "寄付比": op_ch,
                            "前日比": day_ch,
                            "現在値": curr,
                            "状態": status,
                            "sort": val
                        })

                except Exception as e:
                    if debug:
                        st.write(f"[{t}] データ処理エラー: {e}")
                    continue

        except Exception as e:
            if debug:
                st.write(f"バッチ取得エラー({i}-{i+batch_size}): {e}")
            continue

    bar.progress(100)
    status_area.empty()

    if results:
        df_res = pd.DataFrame(results).sort_values("sort", ascending=False)

        if filter_level == "Lv.3 神7 (TOP 7)":
            df_res = df_res.head(7)
            st.markdown(f"### 💎 {target_market}・神7 (TOP 7)")
        else:
            st.success(f"💎 {target_market} 抽出結果: {len(df_res)}件")

        show_df = df_res[["状態", "コード", "銘柄名", "売買代金", "寄付比", "前日比", "現在値"]].copy()
        show_df["寄付比"] = show_df["寄付比"].map(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
        show_df["前日比"] = show_df["前日比"].map(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
        show_df["現在値"] = show_df["現在値"].map(lambda x: f"{x:,.0f}")
        show_df["売買代金"] = show_df["売買代金"].map(lambda x: f"{x:.1f}億円")

        st.dataframe(show_df, use_container_width=True, hide_index=True, height=800)
    else:
        st.warning(f"{target_market}市場で条件に合う銘柄はありませんでした。")
