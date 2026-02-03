import streamlit as st
import pandas as pd
import yfinance as yf

# ページ設定
st.set_page_config(page_title="最強銘柄スキャナー・完全分析", layout="wide")

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

st.title("⚡️ プライム市場・詳細分析スキャナー")
st.caption("前日比 × 寄付比 × テーマ で「強い株」の理由を解剖")

# --- 銘柄データベース（コード, 銘柄名, テーマ） ---
# ここに「備考」として表示したいテーマを登録しています
STOCK_DB = {
    # --- 半導体・ハイテク ---
    "8035.T": ["東エレク", "半導体製造装置/AI"],
    "6920.T": ["レーザーテック", "EUV/半導体検査"],
    "6146.T": ["ディスコ", "半導体切断/生成AI"],
    "6857.T": ["アドバンテスト", "半導体テスタ/AI"],
    "7735.T": ["スクリン", "ウエハ洗浄"],
    "6723.T": ["ルネサス", "車載半導体"],
    "6526.T": ["ソシオネクスト", "先端SoC/設計"],
    "6315.T": ["TOWA", "半導体モールディング"],
    "6871.T": ["日本マイクロ", "メモリ/プローブカード"],
    "6525.T": ["KOKUSAI", "成膜装置"],
    "6758.T": ["ソニーG", "画像センサ/エンタメ"],
    "6501.T": ["日立", "重電/IT/インフラ"],
    "6701.T": ["NEC", "防衛/サイバー/生体認証"],
    "6702.T": ["富士通", "DX/スパコン"],
    "6954.T": ["ファナック", "FA/ロボット"],
    "6861.T": ["キーエンス", "FAセンサ/高収益"],
    "6273.T": ["SMC", "空圧機器/FA"],
    "6981.T": ["村田製", "電子部品/スマホ"],
    "6762.T": ["TDK", "電池/電子部品"],
    "6971.T": ["京セラ", "電子部品/太陽光"],
    "6923.T": ["スタンレー", "自動車照明"],
    
    # --- 電線・非鉄・素材 ---
    "5802.T": ["住友電工", "電線/送電網/データセンター"],
    "5803.T": ["フジクラ", "光ファイバ/生成AI"],
    "5801.T": ["古河電工", "電線/インフラ"],
    "5713.T": ["住友鉱", "金/銅/ニッケル"],
    "5711.T": ["三菱マ", "銅/セメント"],
    "5726.T": ["大阪チタ", "チタン/航空機"],
    "5727.T": ["東邦チタ", "チタン/スポンジチタン"],
    "3436.T": ["SUMCO", "シリコンウエハ"],
    "5401.T": ["日本製鉄", "鉄鋼/USスチール"],
    "5411.T": ["JFE", "鉄鋼大手"],
    "5406.T": ["神戸鋼", "鉄鋼/アルミ/機械"],
    "4063.T": ["信越化学", "塩ビ/ウエハ世界一"],
    "4005.T": ["住友化学", "総合化学/農薬"],
    
    # --- 自動車・重工 ---
    "7203.T": ["トヨタ", "自動車/全固体電池"],
    "7267.T": ["ホンダ", "自動車/二輪/EV"],
    "7201.T": ["日産自", "自動車/EV"],
    "7270.T": ["SUBARU", "北米好調/四駆"],
    "7011.T": ["三菱重工", "防衛/原発/ガスタービン"],
    "7012.T": ["川崎重工", "防衛/二輪/ロボット"],
    "7013.T": ["IHI", "航空エンジン/防衛"],
    "6301.T": ["コマツ", "建機/鉱山機械"],
    
    # --- 金融・商社 ---
    "8306.T": ["三菱UFJ", "メガバンク/金利上昇"],
    "8316.T": ["三井住友", "メガバンク/海外展開"],
    "8411.T": ["みずほ", "メガバンク/法人"],
    "8766.T": ["東京海上", "損保/政策株売却"],
    "8630.T": ["SOMPO", "損保/ビッグモーター"],
    "8058.T": ["三菱商事", "総合商社/資源/自社株買い"],
    "8001.T": ["伊藤忠", "総合商社/非資源"],
    "8031.T": ["三井物産", "総合商社/エネルギー"],
    "8002.T": ["丸紅", "総合商社/穀物/電力"],
    
    # --- インフラ・海運 ---
    "9101.T": ["日本郵船", "海運/コンテナ"],
    "9104.T": ["商船三井", "海運/エネルギー輸送"],
    "9107.T": ["川崎汽船", "海運/還元期待"],
    "9501.T": ["東電HD", "電力/原発再稼働"],
    "9503.T": ["関西電力", "電力/原発"],
    "9432.T": ["NTT", "通信/IOWN"],
    "9433.T": ["KDDI", "通信/ローソン"],
    "9984.T": ["ソフトバンクG", "AI投資/ARM"],
    
    # --- その他主力 ---
    "9983.T": ["ファストリ", "ユニクロ/円安メリット"],
    "3382.T": ["セブン&アイ", "コンビニ/買収思惑"],
    "7974.T": ["任天堂", "ゲーム/Switch後継機"],
    "4661.T": ["OLC", "ディズニー/インバウンド"],
    "4502.T": ["武田薬品", "医薬品/配当"],
    "4568.T": ["第一三共", "がん治療薬(ADC)"],
    "4385.T": ["メルカリ", "フリマアプリ/US"],
    "6098.T": ["リクルート", "人材/Indeed"],
    "2413.T": ["エムスリー", "医療DX"],
    "1925.T": ["大和ハウス", "住宅/データセンター"],
    "8801.T": ["三井不動産", "不動産/金利"],
    "8802.T": ["三菱地所", "不動産/丸の内"]
}

def scan_market():
    if st.button('📡 市場をスキャンする', type="primary"):
        msg = st.empty()
        bar = st.progress(0)
        
        tickers = list(STOCK_DB.keys())
        msg.text(f"データ取得中... 対象: {len(tickers)}銘柄")
        
        try:
            # period="5d" にして前日終値を確実に取得する
            df = yf.download(tickers, period="5d", interval="1d", progress=False, group_by='ticker')
            
            bar.progress(50)
            msg.text("上昇率分析中...")
            
            results = []
            for ticker in tickers:
                try:
                    info = STOCK_DB.get(ticker)
                    name = info[0]
                    theme = info[1]
                    
                    if ticker not in df.columns.levels[0]: continue
                    
                    # データの抽出
                    data = df[ticker].dropna()
                    if len(data) < 2: continue # データ不足
                    
                    # 今日のデータ
                    today = data.iloc[-1]
                    curr = today['Close']
                    op = today['Open']
                    
                    # 前日のデータ（終値）
                    yesterday = data.iloc[-2]
                    prev_close = yesterday['Close']
                    
                    if pd.isna(curr) or pd.isna(op) or op == 0 or prev_close == 0: continue
                    
                    # 計算
                    # 1. 寄付比 (Open -> Current)
                    open_change = (curr - op) / op * 100
                    
                    # 2. 前日比 (Prev Close -> Current)
                    day_change = (curr - prev_close) / prev_close * 100
                    
                    # 判定ロジック
                    status = ""
                    # 両方とも大きくプラスなら「全面高」
                    if open_change > 1.0 and day_change > 2.0:
                        status = "🔥🔥 大陽線"
                    # 寄付比が大きい＝今日強い
                    elif open_change > 2.0:
                        status = "🚀 急伸"
                    # 前日比はプラスだが寄付比マイナス＝寄り天（ギャップアップ後の失速）
                    elif day_change > 0 and open_change < -0.5:
                        status = "⚠️ 失速"
                    # 地味に強い
                    elif day_change > 0.5 and open_change > 0:
                        status = "📈 堅調"
                    elif day_change < -1.0:
                        status = "📉 軟調"
                    else:
                        status = "-"

                    results.append({
                        "コード": ticker.replace(".T", ""),
                        "銘柄名": name,
                        "寄付比": open_change,
                        "前日比": day_change,
                        "現在値": curr,
                        "備考 (テーマ)": theme,
                        "状態": status
                    })
                except: continue
            
            bar.progress(100)
            
            # ランキング表示
            rank_df = pd.DataFrame(results)
            if not rank_df.empty:
                # デフォルトは寄付比順（デイトレ重視）
                rank_df = rank_df.sort_values(by="寄付比", ascending=False)
                # 前日比がプラスのものに絞る（強い株探し）
                rank_df = rank_df[rank_df['前日比'] > 0]
                
                show_df = pd.DataFrame()
                show_df['コード'] = rank_df['コード']
                show_df['銘柄名'] = rank_df['銘柄名']
                # 値上がり率を見やすく整形
                show_df['寄付比'] = rank_df['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['前日比'] = rank_df['前日比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                show_df['現在値'] = rank_df['現在値'].map(lambda x: f"{x:,.0f}")
                show_df['備考 (テーマ)'] = rank_df['備考 (テーマ)']
                show_df['状態'] = rank_df['状態']
                
                msg.empty()
                bar.empty()
                st.success(f"分析完了！強勢銘柄: {len(show_df)}件")
                
                st.dataframe(
                    show_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "備考 (テーマ)": st.column_config.TextColumn("備考 (テーマ)", width="medium"),
                        "寄付比": st.column_config.TextColumn("寄付比", help="朝の始値からの上昇率"),
                        "前日比": st.column_config.TextColumn("前日比", help="昨日の終値からの上昇率"),
                    }
                )
            else:
                msg.empty()
                bar.empty()
                st.warning("現在、上昇トレンドの銘柄は見つかりませんでした。")
                
        except Exception as e:
            st.error(f"エラー: {e}")

# --- メイン実行 ---
scan_market()
