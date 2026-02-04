import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

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
st.sidebar.info("JPXの「東証上場銘柄一覧」をアップロードすると、プライム全銘柄を対象にします。")

uploaded_file = st.sidebar.file_uploader("銘柄リスト (data_j.xls)", type=["xls", "xlsx"])

# デフォルト（手動厳選リスト）
DEFAULT_DB = {
    "8035.T": ["東エレク", "半導体"], "6920.T": ["レーザーテック", "半導体"],
    "6146.T": ["ディスコ", "半導体"], "7011.T": ["三菱重工", "防衛"],
    "7203.T": ["トヨタ", "自動車"], "8306.T": ["三菱UFJ", "銀行"],
    "9984.T": ["ソフトバンクG", "AI"], "9983.T": ["ファストリ", "小売"],
    "9101.T": ["日本郵船", "海運"], "4063.T": ["信越化学", "化学"],
    # ...（容量削減のため省略しますが、ファイルがない時はこれらが動きます）
}

def get_tickers_from_file(file):
    """JPXのエクセルからプライム銘柄を抽出"""
    try:
        df = pd.read_excel(file)
        # プライム市場のみ抽出
        prime_df = df[df['市場・商品区分'] == 'プライム（内国株式）']
        tickers = []
        ticker_info = {}
        
        for _, row in prime_df.iterrows():
            code = str(row['コード']) + ".T"
            name = row['銘柄名']
            sector = row['33業種区分']
            tickers.append(code)
            ticker_info[code] = [name, sector] # テーマの代わりに業種を入れる
            
        return tickers, ticker_info
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {e}")
        return [], {}

st.title("⚡️ プライム全銘柄・完全抽出スキャナー")
st.caption("🔥🚀📈 の銘柄のみを表示（それ以外は除外）")

def scan():
    # 1. 対象銘柄の決定
    if uploaded_file is not None:
        tickers, info_db = get_tickers_from_file(uploaded_file)
        st.success(f"📂 ファイル読み込み完了: プライム {len(tickers)} 銘柄をスキャンします")
    else:
        tickers = list(DEFAULT_DB.keys())
        info_db = DEFAULT_DB
        st.warning("⚠️ ファイル未アップロード: デフォルトの厳選リストのみスキャンします")

    if st.button('📡 全市場スキャン開始', type="primary"):
        status_area = st.empty()
        bar = st.progress(0)
        
        # yfinanceは大量の銘柄を一括ダウンロードすると速い
        status_area.text(f"データ取得中... ({len(tickers)}銘柄)")
        
        try:
            # 5日分取得
            # ※1000銘柄以上あると時間がかかるため、バッチ処理推奨ですが、
            # yfinanceは自動でマルチスレッド処理してくれます。
            df = yf.download(tickers, period="5d", interval="1d", progress=False, group_by='ticker')
            
            bar.progress(50)
            status_area.text("分析＆フィルタリング中...")
            
            results = []
            valid_tickers = [t for t in tickers if t in df.columns.levels[0]]
            
            for i, ticker in enumerate(valid_tickers):
                try:
                    # 進捗バー更新（重いので）
                    if i % 100 == 0:
                        bar.progress(50 + int(40 * i / len(valid_tickers)))

                    # 情報取得
                    info = info_db.get(ticker, ["不明", "-"])
                    name = info[0]
                    theme = info[1]

                    data = df[ticker].dropna()
                    if len(data) < 2: continue

                    # 最新データ（今日）と前日データ
                    latest = data.iloc[-1]
                    prev = data.iloc[-2]
                    
                    curr = latest['Close']
                    op = latest['Open']
                    prev_close = prev['Close']
                    
                    if pd.isna(curr) or pd.isna(op) or prev_close == 0: continue
                    
                    # 計算
                    open_change = (curr - op) / op * 100
                    day_change = (curr - prev_close) / prev_close * 100
                    
                    # --- 判定ロジック ---
                    status = "-"
                    priority = 0 # 並び替え用スコア
                    
                    if open_change > 1.0 and day_change > 2.0:
                        status = "🔥🔥 大陽線"
                        priority = 3
                    elif open_change > 2.0:
                        status = "🚀 急伸"
                        priority = 2
                    elif day_change > 0.5 and open_change > 0:
                        status = "📈 堅調"
                        priority = 1
                    
                    # 【重要】フィルター：地味な銘柄はリストに入れない
                    if priority == 0:
                        continue
                        
                    results.append({
                        "コード": ticker.replace(".T", ""),
                        "銘柄名": name,
                        "寄付比": open_change,
                        "前日比": day_change,
                        "現在値": curr,
                        "状態": status,
                        "業種/テーマ": theme,
                        "sort_key": priority # 並び替え用
                    })
                    
                except: continue

            bar.progress(100)
            status_area.empty()
            
            if results:
                # 優先度順（🔥 > 🚀 > 📈）かつ 寄付比順 にソート
                df_res = pd.DataFrame(results)
                df_res = df_res.sort_values(by=["sort_key", "寄付比"], ascending=[False, False])
                
                st.balloons()
                st.success(f"検出完了！ 今日の有望株: {len(df_res)}件 / 対象 {len(tickers)}件")
                
                # 表示用データフレーム
                show_df = df_res[[
                    "状態", "コード", "銘柄名", "寄付比", "前日比", "現在値", "業種/テーマ"
                ]].copy()
                
                show_df['寄付比'] = show_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['前日比'] = show_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['現在値'] = show_df['現在値'].map(lambda x: f"{x:,.0f}")
                
                st.dataframe(
                    show_df,
                    use_container_width=True,
                    hide_index=True,
                    height=800 # 一覧を長く表示
                )
            else:
                st.warning("現在、上昇トレンド（📈以上）の銘柄は1つもありません。")

        except Exception as e:
            st.error(f"エラースキャン中に問題が発生しました: {e}")

scan()
