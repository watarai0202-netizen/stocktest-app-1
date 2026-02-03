import streamlit as st
import pandas as pd
import yfinance as yf

# ページ設定
st.set_page_config(page_title="最強銘柄スキャナー", layout="wide")

# --- パスワード認証 ---
MY_PASSWORD = "stock testa" 
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 認証")
    pwd = st.text_input("パスワード", type="password")
    if pwd == MY_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    st.stop()

st.title("⚡️ 全自動マーケットスキャナー")
st.caption("クラウド稼働版：主要激動銘柄を一斉監視")

# --- 監視リスト ---
TARGET_STOCKS = {
    "グロース・新興": [
        "5253.T", "5032.T", "9166.T", "5595.T", "5892.T", "2160.T", "4592.T", 
        "4478.T", "4483.T", "7342.T", "7779.T", "9552.T", "9553.T", "5574.T", 
        "3133.T", "7014.T", "6254.T", "6298.T", "6228.T", "3993.T", "3903.T",
        "4565.T", "4169.T", "4165.T", "4443.T", "4011.T", "4425.T", "4385.T",
        "2934.T", "2936.T", "4485.T", "4477.T", "4475.T", "4490.T", "4436.T",
        "7071.T", "7370.T", "7366.T", "7359.T", "7383.T", "9229.T", "9219.T", 
        "9252.T", "9204.T", "9246.T", "9270.T", "9278.T", "9218.T", "4894.T", 
        "4893.T", "4887.T", "4882.T", "4880.T", "4888.T", "4575.T", "5240.T", 
        "5243.T", "5244.T", "5246.T", "5247.T", "5248.T", "5250.T", "5586.T", 
        "5588.T", "5591.T", "5592.T", "4594.T", "4591.T", "4563.T", "4588.T"
    ],
    "スタンダード・材料": [
        "6890.T", "2782.T", "7564.T", "2702.T", "6324.T", "4970.T", "3854.T",
        "6425.T", "7163.T", "6613.T", "5809.T", "3778.T", "3350.T", "2330.T",
        "6855.T", "6961.T", "7716.T", "7721.T", "7729.T", "7769.T", "6622.T",
        "6625.T", "6630.T", "6632.T", "6638.T", "3825.T", "3810.T", "3624.T",
        "3323.T", "2370.T", "4572.T", "4579.T", "4564.T", "2134.T", "2323.T",
        "5721.T", "3041.T", "3121.T", "6659.T", "6696.T", "6731.T", "6736.T",
        "6779.T", "6835.T", "6836.T", "6840.T", "6862.T", "6866.T", "6897.T"
    ],
    "プライム・主力": [
        "6920.T", "8035.T", "6146.T", "6857.T", "7735.T", "6526.T", "6758.T",
        "9984.T", "8306.T", "7203.T", "9101.T", "8058.T", "7011.T", "4063.T",
        "6723.T", "6902.T", "6367.T", "6501.T", "6762.T", "6954.T", "6981.T",
        "4568.T", "4519.T", "4502.T", "3382.T", "6098.T", "4661.T", "9432.T",
        "8316.T", "8411.T", "8766.T", "8001.T", "8031.T", "9104.T", "9107.T",
        "7012.T", "7013.T", "5401.T", "2914.T", "4503.T", "4507.T", "4523.T"
    ]
}

def scan_ranking(category, tickers):
    if st.button(f'📡 {category} をスキャン', key=category):
        # プレースホルダー作成
        msg = st.empty()
        msg.text("データ収集中...")
        
        try:
            # yfinanceで一括取得
            df = yf.download(tickers, period="1d", interval="1d", progress=False, group_by='ticker')
            
            msg.text("ランキング生成中...")
            
            results = []
            for ticker in tickers:
                try:
                    # データがあるか確認
                    if ticker not in df.columns.levels[0]:
                        continue
                    
                    # データを抽出
                    data = df[ticker].iloc[-1]
                    curr = data['Close']
                    op = data['Open']
                    
                    if pd.isna(curr) or pd.isna(op) or op == 0:
                        continue
                    
                    # 寄付比（始値からの上昇率）
                    change = (curr - op) / op * 100
                    
                    # 判定
                    status = ""
                    if change > 5.0: status = "🔥🔥 急騰"
                    elif change > 3.0: status = "🚀 強い"
                    elif change > 1.0: status = "📈 堅調"
                    elif change < -2.0: status = "📉 弱い"
                    else: status = "-"

                    results.append({
                        "コード": ticker.replace(".T", ""),
                        "現在値": curr,
                        "寄付比": change,
                        "判定": status
                    })
                except:
                    continue
            
            # ランキング表示
            rank_df = pd.DataFrame(results)
            if not rank_df.empty:
                rank_df = rank_df.sort_values(by="寄付比", ascending=False)
                # 上昇しているものだけ表示
                rank_df = rank_df[rank_df['寄付比'] > 0]
                
                # 表示用に整形
                show_df = pd.DataFrame()
                show_df['コード'] = rank_df['コード']
                show_df['寄付比'] = rank_df['寄付比'].map(lambda x: f"+{x:.2f}%")
                show_df['現在値'] = rank_df['現在値'].map(lambda x: f"{x:,.0f}")
                show_df['判定'] = rank_df['判定']
                
                msg.empty() # メッセージを消す
                st.success(f"スキャン完了！上昇銘柄: {len(show_df)}件")
                st.dataframe(show_df, use_container_width=True, hide_index=True)
            else:
                msg.empty()
                st.warning("現在、上昇している銘柄はありません。")
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- メイン画面 ---
t1, t2, t3 = st.tabs(["🚀 グロース", "🏢 スタンダード", "🦁 プライム"])
with t1: scan_ranking("グロース・新興", TARGET_STOCKS["グロース・新興"])
with t2: scan_ranking("スタンダード・材料", TARGET_STOCKS["スタンダード・材料"])
with t3: scan_ranking("プライム・主力", TARGET_STOCKS["プライム・主力"])
