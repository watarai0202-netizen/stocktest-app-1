import streamlit as st
import pandas as pd
import yfinance as yf
import os
import time

# --- 1. アプリ設定 ---
st.set_page_config(page_title="全市場対応スキャナー", layout="wide")
MY_PASSWORD = "stock testa"

# --- 2. 認証機能 ---
if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. ファイル読み込み設定 ---
local_file = None
if os.path.exists("data_j.xls"):
    local_file = "data_j.xls"
elif os.path.exists("data_j.xlsx"):
    local_file = "data_j.xlsx"

# --- 4. サイドバー設定 ---
st.sidebar.title("⚙️ 設定")

# 市場選択
target_market = st.sidebar.radio(
    "📊 市場を選択",
    ("プライム", "スタンダード", "グロース"),
    index=0
)

# 抽出モード（プライム用）
# ※スタンダード・グロースの場合は無視されます（自動でTOP5になります）
filter_level = st.sidebar.radio("🔍 抽出モード (プライム用)", ("Lv.2 精鋭 (🔥🚀)", "Lv.3 神7 (TOP 7)"))

# フィルター設定
min_trading_value = st.sidebar.slider("💰 最低売買代金 (億円)", 1, 50, 3)
min_rvol = st.sidebar.slider("📢 出来高急増度 (倍)", 0.1, 5.0, 0.5)

# --- 5. 関数定義 ---
def get_tickers_from_file(file_obj=None, file_path=None, market_type="プライム"):
    try:
        df = None
        if file_obj:
            try: df = pd.read_excel(file_obj, engine='openpyxl')
            except: 
                file_obj.seek(0)
                df = pd.read_excel(file_obj, engine='xlrd')
        elif file_path:
            try: df = pd.read_excel(file_path, engine='openpyxl')
            except: df = pd.read_excel(file_path, engine='xlrd')

        if df is None: return [], {}
            
        search_key = ""
        if market_type == "プライム": search_key = "プライム（内国株式）"
        elif market_type == "スタンダード": search_key = "スタンダード（内国株式）"
        elif market_type == "グロース": search_key = "グロース（内国株式）"
        
        target_df = df[df['市場・商品区分'] == search_key]
        target_df = target_df[target_df['33業種区分'] != '－'] # ETF除外
        
        tickers = []
        ticker_info = {}
        for _, row in target_df.iterrows():
            code = str(row['コード']) + ".T"
            tickers.append(code)
            ticker_info[code] = [row['銘柄名'], row['33業種区分']]
        return tickers, ticker_info
    except Exception:
        return [], {}

# --- 6. メイン画面 ---
st.title(f"⚡️ {target_market}・激辛スキャナー")

# --- 7. 市場天気予報 ---
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")
    try:
        df_m = yf.download(["1570.T"], period="5d", interval="1d", progress=False)
        if len(df_m) > 1:
            latest = df_m.iloc[-1]
            prev = df_m.iloc[-2]
            try:
                curr = float(latest[('Close', '1570.T')])
                op = float(latest[('Open', '1570.T')])
                prev_cl = float(prev[('Close', '1570.T')])
            except:
                curr = float(latest['Close'])
                op = float(latest['Open'])
                prev_cl = float(prev['Close'])

            op_ch = (curr - op)/op*100
            day_ch = (curr - prev_cl)/prev_cl*100

            status = "☁️ 曇り"
            if op_ch > 0.5 and day_ch > 1.0: status = "☀️ 快晴 (🔥 トレンド上昇中)"
            elif op_ch > 1.0: status = "🌤 晴れ (🚀 買い優勢)"
            elif day_ch < -1.0 and op_ch < -0.5: status = "☔️ 土砂降り (📉 暴落警戒)"
            elif day_ch < -0.5: status = "☁️ 雨 (弱い)"

            st.info(f"現在のステータス: **{status}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("現在値", f"{curr:,.0f}円")
            c2.metric("寄付比", f"{op_ch:+.2f}%")
            c3.metric("前日比", f"{day_ch:+.2f}%")
            st.divider()
    except: pass

check_market_condition()

# --- 8. スキャン処理 ---
uploaded_file = st.sidebar.file_uploader("リスト更新", type=["xls", "xlsx"])

tickers = []
info_db = {}
if uploaded_file: tickers, info_db = get_tickers_from_file(file_obj=uploaded_file, market_type=target_market)
elif local_file: tickers, info_db = get_tickers_from_file(file_path=local_file, market_type=target_market)

if tickers and st.button(f'📡 {target_market}をスキャン開始', type="primary"):
    status_area = st.empty()
    bar = st.progress(0)
    results = []
    
    # バッチサイズ30（速度優先）
    batch_size = 30 
    total = len(tickers)
    
    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        prog = min(i / total, 1.0)
        status_area.text(f"データ分析中... {i} / {total} 銘柄完了")
        bar.progress(prog)
        
        try:
            time.sleep(0.05)
            df = yf.download(batch, period="5d", interval="1d", progress=False, group_by='ticker', threads=False)
            
            valid_tickers = [t for t in batch if t in df.columns.levels[0]]
            for t in valid_tickers:
                try:
                    data = df[t].dropna()
                    if len(data) < 2: continue
                    
                    latest, prev = data.iloc[-1], data.iloc[-2]
                    curr, op, vol = latest['Close'], latest['Open'], latest['Volume']
                    
                    val = (curr * vol) / 100000000
                    if val < min_trading_value: continue
                    
                    avg_vol = data['Volume'].mean()
                    if avg_vol == 0: continue
                    rvol = vol / avg_vol
                    if rvol < min_rvol: continue
                    
                    op_ch = (curr - op)/op*100
                    day_ch = (curr - prev['Close'])/prev['Close']*100
                    
                    status, prio = "-", 0
                    if op_ch > 1.0 and day_ch > 2.0: status, prio = "🔥🔥 大陽線", 2
                    elif op_ch > 2.0: status, prio = "🚀 急伸", 1
                    
                    if prio > 0:
                        info = info_db.get(t, ["-", "-"])
                        results.append({
                            "コード": t.replace(".T",""), "銘柄名": info[0], "業種": info[1],
                            "売買代金": val, "寄付比": op_ch, "前日比": day_ch, "現在値": curr,
                            "状態": status, "sort": val
                        })
                except: continue
        except: continue

    bar.progress(100)
    status_area.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values("sort", ascending=False)
        
        # ★ここが変更点：市場によって表示数を制限
        if target_market in ["スタンダード", "グロース"]:
            df_res = df_res.head(5)
            st.markdown(f"### 💎 {target_market}・最強 TOP5")
        else:
            # プライムの場合は設定に従う
            if filter_level == "Lv.3 神7 (TOP 7)": 
                df_res = df_res.head(7)
                st.markdown(f"### 💎 プライム・神7 (TOP 7)")
            else:
                st.success(f"💎 抽出結果: {len(df_res)}件")
        
        show_df = df_res[["状態", "業種", "コード", "銘柄名", "売買代金", "寄付比", "前日比", "現在値"]]
        show_df['寄付比'] = show_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
        show_df['前日比'] = show_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
        show_df['現在値'] = show_df['現在値'].map(lambda x: f"{x:,.0f}")
        show_df['売買代金'] = show_df['売買代金'].map(lambda x: f"{x:.1f}億円")
        
        st.dataframe(show_df, use_container_width=True, hide_index=True, height=800)
    else:
        st.warning(f"{target_market}市場で条件に合う銘柄はありませんでした。")
