import streamlit as st
import pandas as pd
import yfinance as yf
import os  # ★追加：ファイルを探すための機能

# --- 設定 ---
st.set_page_config(page_title="全銘柄完全スキャナー", layout="wide")
MY_PASSWORD = "stock testa"

if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- サイドバー設定 ---
st.sidebar.title("⚙️ 激辛フィルター設定")

# 1. 厳選モード
filter_level = st.sidebar.radio(
    "🔍 表示モード",
    ("Lv.3 神7 (TOP 7)", "Lv.2 精鋭 (🔥🚀)", "Lv.1 全表示")
)

# 2. 売買代金フィルター（朝イチ対応版）
min_trading_value = st.sidebar.slider(
    "💰 最低売買代金 (億円)", 
    min_value=1, max_value=50, value=3, step=1,  # ←ここを変更！
    help="【朝9:30目安】3〜5億円あれば合格 【大引け目安】15億円以上"
)

# 3. RVOLフィルター（朝イチ対応版）
min_rvol = st.sidebar.slider(
    "📢 出来高急増度 (倍)",
    min_value=0.1, max_value=5.0, value=0.3, step=0.1,  # ←ここを変更！
    help="【朝9:30目安】0.3倍あれば急増 【大引け目安】1.0倍以上"
)

# ★ここが進化：ファイル自動探索ロジック
st.sidebar.write("---")
uploaded_file = st.sidebar.file_uploader("銘柄リスト更新 (任意)", type=["xls", "xlsx"])

# デフォルト（ない時用）
DEFAULT_DB = {"7203.T": ["トヨタ", "自動車"], "9984.T": ["SBG", "投資"]}

def get_tickers_from_file(file_obj=None, file_path=None):
    """
    アップロードされたファイル(file_obj) または
    GitHubにあるファイル(file_path) から読み込む
    """
    try:
        df = None
        # 1. アップロードファイルがある場合
        if file_obj is not None:
            if file_obj.name.endswith('.xls'):
                try: df = pd.read_excel(file_obj, engine='xlrd')
                except: 
                    file_obj.seek(0)
                    df = pd.read_excel(file_obj, engine='openpyxl')
            else:
                try: df = pd.read_excel(file_obj, engine='openpyxl')
                except:
                    file_obj.seek(0)
                    df = pd.read_excel(file_obj, engine='xlrd')
        
        # 2. GitHub上のファイルがある場合（アップロードがない時）
        elif file_path is not None:
            if file_path.endswith('.xls'):
                df = pd.read_excel(file_path, engine='xlrd')
            else:
                df = pd.read_excel(file_path, engine='openpyxl')

        if df is None: return [], {}
            
        prime_df = df[df['市場・商品区分'] == 'プライム（内国株式）']
        tickers = []
        ticker_info = {}
        for _, row in prime_df.iterrows():
            code = str(row['コード']) + ".T"
            name = row['銘柄名']
            sector = row['33業種区分']
            tickers.append(code)
            ticker_info[code] = [name, sector]
        return tickers, ticker_info
    except Exception as e:
        st.error(f"ファイルエラー: {e}")
        return [], {}

st.title("⚡️ プライム・激辛スキャナー")
st.caption(f"条件: 売買代金 {min_trading_value}億円以上 & 出来高急増 {min_rvol}倍以上")

def scan():
    # --- ファイル読み込みの優先順位決定 ---
    tickers = []
    info_db = {}
    
    # 1. PC/GitHubにあるファイルをチェック
    local_file = None
    if os.path.exists("data_j.xls"):
        local_file = "data_j.xls"
    elif os.path.exists("data_j.xlsx"):
        local_file = "data_j.xlsx"

    # 2. 読み込み実行
    if uploaded_file is not None:
        # 手動アップロードがあればそっち優先（月1更新用）
        tickers, info_db = get_tickers_from_file(file_obj=uploaded_file)
        st.success(f"📂 手動ファイルを読み込みました: {len(tickers)} 銘柄")
    
    elif local_file is not None:
        # 手動がなければ、GitHub上のファイルを使う
        tickers, info_db = get_tickers_from_file(file_path=local_file)
        st.info(f"📂 自動読み込み完了 ({local_file}): {len(tickers)} 銘柄")
        
    else:
        # どっちもない場合
        tickers = list(DEFAULT_DB.keys())
        info_db = DEFAULT_DB
        st.warning("⚠️ 銘柄リストが見つかりません。PCからGitHubに 'data_j.xls' をアップロードしてください。")

    if st.button('📡 スキャン開始', type="primary"):
        status_area = st.empty()
        bar = st.progress(0)
        status_area.text(f"データ取得中... ({len(tickers)}銘柄)")
        
        try:
            df = yf.download(tickers, period="5d", interval="1d", progress=False, group_by='ticker')
            
            bar.progress(50)
            status_area.text("激辛フィルタリング中...")
            
            results = []
            valid_tickers = [t for t in tickers if t in df.columns.levels[0]]
            
            for i, ticker in enumerate(valid_tickers):
                if i % 100 == 0: bar.progress(50 + int(40 * i / len(valid_tickers)))

                try:
                    data = df[ticker].dropna()
                    if len(data) < 5: continue

                    latest = data.iloc[-1]
                    prev = data.iloc[-2]
                    
                    curr = latest['Close']
                    op = latest['Open']
                    vol = latest['Volume']
                    prev_close = prev['Close']
                    
                    avg_vol = data['Volume'].mean()
                    if avg_vol == 0: continue
                    rvol = vol / avg_vol 
                    trading_value = (curr * vol) / 100000000

                    if trading_value < min_trading_value: continue
                    if rvol < min_rvol: continue
                    if pd.isna(curr) or pd.isna(op) or prev_close == 0: continue
                    
                    open_change = (curr - op) / op * 100
                    day_change = (curr - prev_close) / prev_close * 100
                    
                    status = "-"
                    priority = 0
                    
                    if open_change > 1.0 and day_change > 2.0:
                        status = "🔥🔥 大陽線"
                        priority = 3
                    elif open_change > 2.0:
                        status = "🚀 急伸"
                        priority = 2
                    elif day_change > 0.5 and open_change > 0:
                        status = "📈 堅調"
                        priority = 1
                    
                    if priority == 0: continue
                    if filter_level == "Lv.2 精鋭 (🔥🚀)" and priority == 1: continue

                    info = info_db.get(ticker, ["不明", "-"])
                    
                    results.append({
                        "コード": ticker.replace(".T", ""),
                        "銘柄名": info[0],
                        "売買代金": trading_value,
                        "RVOL": rvol,
                        "寄付比": open_change,
                        "前日比": day_change,
                        "現在値": curr,
                        "状態": status,
                        "業種": info[1],
                        "sort_key": trading_value
                    })
                    
                except: continue

            bar.progress(100)
            status_area.empty()
            
            if results:
                df_res = pd.DataFrame(results)
                df_res = df_res.sort_values(by="sort_key", ascending=False)
                
                if filter_level == "Lv.3 神7 (TOP 7)":
                    df_res = df_res.head(7)
                
                df_res = df_res.head(50)

                st.success(f"💎 厳選完了: {len(df_res)}件 (売買代金順)")
                
                show_df = df_res[[
                    "状態", "コード", "銘柄名", "売買代金", "RVOL", "寄付比", "前日比", "現在値", "業種"
                ]].copy()
                
                show_df['寄付比'] = show_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['前日比'] = show_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['現在値'] = show_df['現在値'].map(lambda x: f"{x:,.0f}")
                show_df['売買代金'] = show_df['売買代金'].map(lambda x: f"{x:.1f}億円")
                show_df['RVOL'] = show_df['RVOL'].map(lambda x: f"{x:.2f}倍")
                
                st.dataframe(show_df, use_container_width=True, hide_index=True, height=800)
            else:
                st.warning("条件が厳しすぎました。フィルターを緩めてください。")

        except Exception as e:
            st.error(f"エラー: {e}")

scan()
