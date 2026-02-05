import streamlit as st
import pandas as pd
import yfinance as yf
import os

# --- 1. アプリ設定 ---
st.set_page_config(page_title="最強セクター発掘機", layout="wide")
MY_PASSWORD = "stock testa"  # パスワード

# --- 2. 認証機能 ---
if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. サイドバー設定 ---
st.sidebar.title("⚙️ 設定")

# 抽出モード
filter_level = st.sidebar.radio(
    "🔍 抽出モード",
    ("Lv.2 精鋭 (🔥🚀)", "Lv.3 神7 (TOP 7)")
)

# フィルター設定
min_trading_value = st.sidebar.slider("💰 最低売買代金 (億円)", 1, 50, 5)
min_rvol = st.sidebar.slider("📢 出来高急増度 (倍)", 0.1, 5.0, 0.5)

# --- 4. 関数: Excel読み込み ---
def get_tickers_from_file(file_obj=None, file_path=None):
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
            
        # プライム市場のみ抽出
        prime_df = df[df['市場・商品区分'] == 'プライム（内国株式）']
        tickers = []
        ticker_info = {}
        for _, row in prime_df.iterrows():
            code = str(row['コード']) + ".T"
            tickers.append(code)
            ticker_info[code] = [row['銘柄名'], row['33業種区分']]
        return tickers, ticker_info
    except Exception as e:
        return [], {}

# --- 5. メイン画面構築 ---
st.title("⚡️ 最強セクター＆銘柄スキャナー")

# --- 6. 機能: 市場天気予報 (日経レバ 1570) ---
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")
    try:
        # 日経レバ(1570)を取得
        df_m = yf.download(["1570.T"], period="5d", interval="1d", progress=False)
        
        if len(df_m) > 1:
            latest = df_m.iloc[-1]
            prev = df_m.iloc[-2]
            
            # yfinanceのバージョンによるカラム構造の違いを吸収
            try:
                curr = float(latest[('Close', '1570.T')])
                op = float(latest[('Open', '1570.T')])
                prev_cl = float(prev[('Close', '1570.T')])
            except:
                curr = float(latest['Close'])
                op = float(latest['Open'])
                prev_cl = float(prev['Close'])

            # 変化率
            open_change = (curr - op) / op * 100
            day_change = (curr - prev_cl) / prev_cl * 100

            # 天気判定ロジック
            status = "☁️ 曇り (ヨコヨコ)"
            bg_color = "gray"
            
            if open_change > 0.5 and day_change > 1.0:
                status = "☀️ 快晴 (🔥 トレンド上昇中)"
                bg_color = "red"
            elif open_change > 1.0:
                status = "🌤 晴れ (🚀 買い優勢)"
                bg_color = "orange"
            elif day_change < -1.0 and open_change < -0.5:
                status = "☔️ 土砂降り (📉 暴落警戒)"
                bg_color = "blue"
            elif day_change < -0.5:
                 status = "☁️ 雨 (弱い)"

            # 表示
            st.info(f"現在のステータス: **{status}**")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("現在値", f"{curr:,.0f}円")
            c2.metric("前日比", f"{day_change:+.2f}%")
            c3.metric("寄付比 (今日の強さ)", f"{open_change:+.2f}%")
            
            check = "買い推奨" if open_change > 0 else "様子見推奨"
            c4.metric("判定", check)
            
            if day_change < -1.5:
                st.error("🚨 警告：地合いが悪すぎます！『買い』は慎重に！")
            
            st.divider()
            
    except Exception as e:
        st.warning(f"マーケット情報取得エラー: {e}")

# 最初に天気を表示
check_market_condition()

# --- 7. スキャン処理（バッチ処理版） ---

# ファイル読み込み
local_file = "data_j.xls" if os.path.exists("data_j.xls") else ("data_j.xlsx" if os.path.exists("data_j.xlsx") else None)
uploaded_file = st.sidebar.file_uploader("リスト更新", type=["xls", "xlsx"])

tickers = []
info_db = {}

if uploaded_file:
    tickers, info_db = get_tickers_from_file(file_obj=uploaded_file)
elif local_file:
    tickers, info_db = get_tickers_from_file(file_path=local_file)

# ボタンが押されたら実行
if tickers and st.button('📡 スキャン開始', type="primary"):
    status_area = st.empty()
    bar = st.progress(0)
    results = []
    
    # ★ここが重要：100件ずつ処理（サーバー落ち回避）
    batch_size = 100
    total_tickers = len(tickers)
    
    # 0から最後まで、100刻みでループ
    for i in range(0, total_tickers, batch_size):
        # 今回処理する100個を取り出す
        batch = tickers[i : i + batch_size]
        
        # 進捗表示
        progress_percent = min(i / total_tickers, 1.0)
        status_area.text(f"データ分析中... {i} / {total_tickers} 銘柄完了")
        bar.progress(progress_percent)
        
        try:
            # ダウンロード（threads=False で安定化）
            df = yf.download(batch, period="5d", interval="1d", progress=False, group_by='ticker', threads=False)
            
            # 取得できた銘柄だけ抽出
            valid_tickers = [t for t in batch if t in df.columns.levels[0]]
            
            for t in valid_tickers:
                try:
                    data = df[t].dropna()
                    if len(data) < 2: continue
                    
                    latest = data.iloc[-1]
                    prev = data.iloc[-2]
                    
                    curr = latest['Close']
                    op = latest['Open']
                    vol = latest['Volume']
                    
                    # 売買代金チェック
                    val = (curr * vol) / 100000000
                    if val < min_trading_value: continue
                    
                    # RVOLチェック
                    avg_vol = data['Volume'].mean()
                    if avg_vol == 0: continue
                    rvol = vol / avg_vol
                    if rvol < min_rvol: continue
                    
                    # 強さ判定
                    op_ch = (curr - op) / op * 100
                    day_ch = (curr - prev['Close']) / prev['Close'] * 100
                    
                    status = "-"
                    prio = 0
                    
                    if op_ch > 1.0 and day_ch > 2.0:
                        status = "🔥🔥 大陽線"
                        prio = 2
                    elif op_ch > 2.0:
                        status = "🚀 急伸"
                        prio = 1
                    
                    # 条件合致ならリストに追加
                    if prio > 0:
                        info = info_db.get(t, ["不明", "-"])
                        results.append({
                            "コード": t.replace(".T",""),
                            "銘柄名": info[0],
                            "業種": info[1],
                            "売買代金": val,
                            "寄付比": op_ch,
                            "前日比": day_ch,
                            "現在値": curr,
                            "状態": status,
                            "sort": val # 売買代金順に並べる用
                        })
                except: continue
        except: continue

    # ループ終了
    bar.progress(100)
    status_area.empty()
    
    if results:
        # ★ここで全銘柄をまとめてランキング化
        df_res = pd.DataFrame(results)
        df_res = df_res.sort_values("sort", ascending=False)
        
        # セクターランキング表示
        st.markdown("### 🏆 今、資金が入っている「最強業種」TOP5")
        top_sectors = df_res['業種'].value_counts().head(5)
        
        cols = st.columns(5)
        for i, (sec, cnt) in enumerate(top_sectors.items()):
            cols[i].metric(f"No.{i+1}", f"{sec}", f"{cnt}銘柄")
        
        st.divider()

        # リスト表示（神7 or 全表示）
        if filter_level == "Lv.3 神7 (TOP 7)":
            df_res = df_res.head(7)
            st.success(f"💎 選ばれし7銘柄 (神7)")
        else:
            st.success(f"💎 抽出結果: {len(df_res)}件")
        
        # 見やすく整形
        show_df = df_res[["状態", "業種", "コード", "銘柄名", "売買代金", "寄付比", "前日比", "現在値"]]
        show_df['寄付比'] = show_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
        show_df['前日比'] = show_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
        show_df['現在値'] = show_df['現在値'].map(lambda x: f"{x:,.0f}")
        show_df['売買代金'] = show_df['売買代金'].map(lambda x: f"{x:.1f}億円")
        
        st.dataframe(show_df, use_container_width=True, hide_index=True, height=800)
    else:
        st.warning("該当なし。市場が弱いか、条件が厳しすぎます。")
