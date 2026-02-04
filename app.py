import streamlit as st
import pandas as pd
import yfinance as yf

# --- 設定 ---
st.set_page_config(page_title="全銘柄完全スキャナー", layout="wide")
MY_PASSWORD = "stock testa"

# --- 認証 ---
if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- サイドバー：設定 ---
st.sidebar.title("⚙️ スキャン設定")

# ★ここが新機能：厳選レベルの選択
filter_level = st.sidebar.radio(
    "🔍 厳選モード",
    ("Lv.3 神7 (TOP 7)", "Lv.2 精鋭 (🔥🚀のみ)", "Lv.1 全表示 (📈含む)")
)

uploaded_file = st.sidebar.file_uploader("銘柄リスト (data_j.xls)", type=["xls", "xlsx"])

# デフォルト（手動厳選リスト）
DEFAULT_DB = {
    "8035.T": ["東エレク", "半導体"], "6920.T": ["レーザーテック", "半導体"],
    "6146.T": ["ディスコ", "半導体"], "7011.T": ["三菱重工", "防衛"],
    "7203.T": ["トヨタ", "自動車"], "8306.T": ["三菱UFJ", "銀行"],
    "9984.T": ["ソフトバンクG", "AI"], "9983.T": ["ファストリ", "小売"],
    "9101.T": ["日本郵船", "海運"], "4063.T": ["信越化学", "化学"],
}

def get_tickers_from_file(file):
    try:
        # xlrdかopenpyxlで読み込み
        if file.name.endswith('.xls'):
            df = pd.read_excel(file, engine='xlrd')
        else:
            df = pd.read_excel(file, engine='openpyxl')
            
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
        st.error(f"ファイル読み込みエラー: {e}")
        return [], {}

st.title("⚡️ プライム全銘柄・完全抽出スキャナー")

# UIの表示をモードによって変える
if filter_level == "Lv.3 神7 (TOP 7)":
    st.caption("🏆 今日の主役級「7銘柄」だけを表示します")
elif filter_level == "Lv.2 精鋭 (🔥🚀のみ)":
    st.caption("🔥🚀 勢いがある銘柄のみを表示（地味な上げは除外）")
else:
    st.caption("📈 全ての上昇銘柄を表示（数が多いので注意）")

def scan():
    if uploaded_file is not None:
        tickers, info_db = get_tickers_from_file(uploaded_file)
        st.success(f"📂 ファイル読み込み: プライム {len(tickers)} 銘柄")
    else:
        tickers = list(DEFAULT_DB.keys())
        info_db = DEFAULT_DB
        st.warning("⚠️ デフォルトリストを使用中")

    if st.button('📡 スキャン開始', type="primary"):
        status_area = st.empty()
        bar = st.progress(0)
        
        status_area.text(f"データ取得中... ({len(tickers)}銘柄)")
        
        try:
            # データ取得
            df = yf.download(tickers, period="5d", interval="1d", progress=False, group_by='ticker')
            
            bar.progress(50)
            status_area.text("分析中...")
            
            results = []
            valid_tickers = [t for t in tickers if t in df.columns.levels[0]]
            
            for i, ticker in enumerate(valid_tickers):
                if i % 100 == 0: bar.progress(50 + int(40 * i / len(valid_tickers)))

                try:
                    info = info_db.get(ticker, ["不明", "-"])
                    name = info[0]
                    theme = info[1]

                    data = df[ticker].dropna()
                    if len(data) < 2: continue

                    latest = data.iloc[-1]
                    prev = data.iloc[-2]
                    
                    curr = latest['Close']
                    op = latest['Open']
                    prev_close = prev['Close']
                    
                    if pd.isna(curr) or pd.isna(op) or prev_close == 0: continue
                    
                    open_change = (curr - op) / op * 100
                    day_change = (curr - prev_close) / prev_close * 100
                    
                    # --- 判定ロジック ---
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
                    
                    # 足切りフィルター
                    if priority == 0: continue
                    
                    # Lv.2の時は「堅調」を捨てる
                    if filter_level == "Lv.2 精鋭 (🔥🚀のみ)" and priority == 1:
                        continue
                        
                    results.append({
                        "コード": ticker.replace(".T", ""),
                        "銘柄名": name,
                        "寄付比": open_change,
                        "前日比": day_change,
                        "現在値": curr,
                        "状態": status,
                        "業種": theme,
                        "sort_key": open_change # 寄付比（勢い）でソート
                    })
                    
                except: continue

            bar.progress(100)
            status_area.empty()
            
            if results:
                df_res = pd.DataFrame(results)
                # 勢い順に並び替え
                df_res = df_res.sort_values(by="sort_key", ascending=False)
                
                # Lv.3なら上位7つに絞る
                if filter_level == "Lv.3 神7 (TOP 7)":
                    df_res = df_res.head(7)
                    st.balloons()
                    st.success(f"💎 選ばれし {len(df_res)} 銘柄を抽出しました")
                else:
                    st.success(f"検出完了: {len(df_res)}件")
                
                # 表示の整形
                show_df = df_res[["状態", "コード", "銘柄名", "寄付比", "前日比", "現在値", "業種"]].copy()
                show_df['寄付比'] = show_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['前日比'] = show_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['現在値'] = show_df['現在値'].map(lambda x: f"{x:,.0f}")
                
                st.dataframe(show_df, use_container_width=True, hide_index=True, height=800)
            else:
                st.warning("条件に合う銘柄はありませんでした。")

        except Exception as e:
            st.error(f"エラー: {e}")

scan()
