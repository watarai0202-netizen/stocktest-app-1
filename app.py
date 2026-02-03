import streamlit as st
import pandas as pd
import yfinance as yf

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・Scanner", layout="centered")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

st.title("⚡️ リアルタイム・スキャナー")
st.caption("主要アクティブ銘柄を一斉スキャンして独自ランキングを作成")

# --- 監視対象：デイトレ・短期資金が集まりやすい約80銘柄 ---
# ※ここを増やせば監視対象が広がります
TICKERS_LIST = [
    # --- 半導体・ハイテク ---
    "6920.T", "8035.T", "6146.T", "6857.T", "7735.T", "6526.T", "6758.T", "6723.T",
    # --- 銀行・金融 ---
    "8306.T", "8316.T", "8411.T", "8766.T", "8591.T",
    # --- 海運・商社・重工 ---
    "9101.T", "9104.T", "9107.T", "8058.T", "8001.T", "8031.T", "7011.T", "7012.T", "7013.T",
    # --- 自動車・機械 ---
    "7203.T", "7267.T", "6367.T", "6902.T", "6501.T",
    # --- グロース・人気株 ---
    "5253.T", "5032.T", "9166.T", "5595.T", "5892.T", "2160.T", "4592.T",
    "4478.T", "4483.T", "7342.T", "7779.T", "9552.T", "9553.T", "5574.T",
    "3133.T", "7014.T", "6254.T", "6298.T", "6228.T", "3993.T", "3903.T",
    # --- その他大型・材料株 ---
    "9984.T", "9983.T", "7974.T", "6098.T", "4661.T", "3436.T", "3498.T",
    "9501.T", "4502.T", "4568.T", "2914.T", "3382.T", "4385.T", "4755.T"
]

def analyze_and_rank():
    if st.button('⚡️ 市場をスキャンしてランキング作成'):
        with st.spinner(f'{len(TICKERS_LIST)}銘柄を一括分析中...'):
            try:
                # yfinanceのバルクダウンロード機能（高速）
                # これなら1回のリクエストで済むので速い
                df = yf.download(TICKERS_LIST, period="1d", interval="1d", progress=False)
                
                # データの整形
                # 最新の「始値」と「現在値（終値）」を取得
                try:
                    current_prices = df['Close'].iloc[-1]
                    open_prices = df['Open'].iloc[-1]
                except:
                    # MultiIndexの場合の対応
                    current_prices = df.xs('Close', axis=1, level=0).iloc[-1]
                    open_prices = df.xs('Open', axis=1, level=0).iloc[-1]

                ranking_data = []

                for ticker in TICKERS_LIST:
                    try:
                        # 銘柄ごとのデータを抽出
                        curr = current_prices.get(ticker)
                        op = open_prices.get(ticker)

                        if pd.isna(curr) or pd.isna(op) or op == 0:
                            continue
                        
                        # 上昇率（寄付比）の計算
                        change_pct = (curr - op) / op * 100
                        
                        # 簡易AI判定
                        status = ""
                        if change_pct > 3.0: status = "🔥 急騰"
                        elif change_pct > 1.0: status = "🚀 強い"
                        elif change_pct < -1.0: status = "📉 弱い"
                        else: status = "⚖️ 揉み合い"

                        ranking_data.append({
                            "コード": ticker.replace(".T", ""),
                            "現在値": curr,
                            "寄付比": change_pct,
                            "判定": status
                        })
                    except: continue

                # ランキング作成（寄付比が高い順に並べる）
                df_rank = pd.DataFrame(ranking_data)
                
                if not df_rank.empty:
                    df_rank = df_rank.sort_values(by="寄付比", ascending=False)
                    
                    # 表示用に整形
                    df_show = pd.DataFrame()
                    df_show['コード'] = df_rank['コード']
                    df_show['寄付比'] = df_rank['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                    df_show['現在値'] = df_rank['現在値'].map(lambda x: f"{x:,.0f}")
                    df_show['状態'] = df_rank['判定']
                    
                    # 上位30銘柄を表示
                    st.success("スキャン完了！ 本日の強勢銘柄ランキング")
                    st.dataframe(df_show, use_container_width=True, hide_index=True)
                else:
                    st.error("データが取得できませんでした。")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

analyze_and_rank()
