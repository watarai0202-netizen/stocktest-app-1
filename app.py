import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
import numpy as np  # 計算用にnumpy追加

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・改", layout="mobile")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

# --- メインアプリ ---
st.title("⚡️ リアルタイム強勢銘柄判定")
st.caption("Yahoo!速報値 × 5分足構造分析 (Phase 2実装版)")

# --- 関数定義 ---

def get_ranking_data_hybrid(market_code):
    """Yahoo!ランキングから現在値をスクレイピング（Phase 1そのまま）"""
    url = f"https://finance.yahoo.co.jp/ranking/tradingValue?market={market_code}&term=daily&area=JP"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        rows = soup.select('tbody tr')
        for row in rows:
            try:
                tds = row.select('td')
                if not tds: continue
                el_link = tds[1].select_one('a')
                if not el_link: continue
                
                href = el_link.get('href')
                code = href.split('/')[-1]
                name = el_link.text
                price_text = tds[3].get_text(strip=True).replace(',', '')
                match = re.search(r'[\d\.]+', price_text)
                current_price = float(match.group()) if match else None

                if current_price:
                    data_list.append({"code": code, "name": name, "scraped_current_price": current_price})
            except: continue
        return data_list[:50]
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return []

def calculate_vwap_and_status(df_5m, current_realtime_price):
    """
    5分足データからVWAPとボラティリティを計算し、
    リアルタイム価格と照らし合わせて判定を行うAIロジック
    """
    if df_5m.empty:
        return None, None, "データ不足"

    # VWAP計算
    # (Typical Price * Volume) の累積 / Volume の累積
    df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3
    df_5m['VP'] = df_5m['Typical_Price'] * df_5m['Volume']
    
    total_vp = df_5m['VP'].sum()
    total_vol = df_5m['Volume'].sum()
    
    if total_vol == 0:
        return None, None, "出来高なし"

    vwap = total_vp / total_vol
    
    # 標準偏差（簡易的なボリンジャーバンドのようなもの）をVWAPベースで計算
    # ここでは簡易的にCloseの標準偏差を使用
    std = df_5m['Close'].std()
    
    # 直近のボラティリティ（直近3本の高値-安値の平均）
    recent_candles = df_5m.tail(3)
    recent_volatility = (recent_candles['High'] - recent_candles['Low']).mean()
    price_volatility_ratio = recent_volatility / current_realtime_price * 100 # 株価に対する変動率(%)

    # --- 判定ロジック (ここがAIの脳みそ) ---
    
    # 1. VWAP乖離率
    vwap_divergence = (current_realtime_price - vwap) / vwap * 100
    
    status = ""
    detail = ""

    # 判定A: 過熱感あり (VWAPから大きく上に乖離) -> 例: +3%以上
    if vwap_divergence > 3.0:
        status = "✋ 加熱・押し目待ち"
        detail = f"乖離 +{vwap_divergence:.1f}%"
        
    # 判定B: イケイケ・ブレイク狙い (VWAPより上、かつボラ収縮)
    # 乖離が適度(0%~3%) かつ 変動率が小さい(0.3%未満など)
    elif 0 < vwap_divergence <= 3.0:
        if price_volatility_ratio < 0.3: # 横横している
            status = "🚀 ブレイク前兆 (横横)"
            detail = f"Vol {price_volatility_ratio:.2f}%"
        else:
            status = "📈 上昇トレンド中"
            detail = "順張り"
            
    # 判定C: VWAP割れ (調整中)
    elif vwap_divergence <= 0:
        status = "👀 VWAP攻防・監視"
        detail = f"乖離 {vwap_divergence:.1f}%"

    return vwap, status, detail


def analyze_market(market_name, market_slug):
    """市場分析実行"""
    if st.button(f'⚡️ {market_name}を分析', key=market_slug):
        with st.spinner('1. ランキング取得中...'):
            ranking_data = get_ranking_data_hybrid(market_slug)
            if not ranking_data:
                st.error("ランキング取得失敗")
                return

        # Phase 1: 始値比較
        with st.spinner('2. 始値データを照合中...'):
            df_rank = pd.DataFrame(ranking_data)
            codes = df_rank['code'].tolist()
            yf_codes = [c if c.endswith('.T') else f"{c}.T" for c in codes]
            
            # 日足取得（始値用）
            df_daily = yf.download(yf_codes, period="1d", interval="1d", progress=False)
            
            # データ整形
            try:
                if isinstance(df_daily.columns, pd.MultiIndex):
                    open_prices = df_daily.xs('Open', level=0, axis=1).iloc[-1]
                else:
                    open_prices = df_daily['Open'].iloc[-1]
            except:
                st.error("株価データ整形エラー")
                return

            # 一次選抜リスト作成
            pre_results = []
            for i, row in df_rank.iterrows():
                try:
                    code = row['code']
                    curr_val = row['scraped_current_price']
                    yf_code = code if code.endswith('.T') else f"{code}.T"
                    open_val = open_prices.get(yf_code)

                    if pd.isna(open_val) or open_val == 0: continue
                    
                    rise = (curr_val - open_val) / open_val * 100
                    pre_results.append({
                        "yf_code": yf_code,
                        "code": code, 
                        "銘柄名": row['name'],
                        "寄付比": rise, 
                        "現在値": curr_val
                    })
                except: continue

            # 寄付比が高い順に並べ替え
            pre_results.sort(key=lambda x: x["寄付比"], reverse=True)
            
            # 上位15銘柄に絞って詳細分析 (API制限と速度考慮)
            top_stocks = pre_results[:15]
            top_tickers = [x['yf_code'] for x in top_stocks]

        # Phase 2: 5分足データ取得と詳細判定
        with st.spinner('3. AI判定実行中 (5分足・VWAP分析)...'):
            # まとめて5分足取得
            try:
                df_intraday = yf.download(top_tickers, period="1d", interval="5m", progress=False)
            except Exception as e:
                st.error(f"詳細データ取得エラー: {e}")
                return

            final_results = []
            
            for item in top_stocks:
                ticker = item['yf_code']
                current_price = item['現在値']
                
                # 個別銘柄の5分足抽出
                try:
                    # MultiIndexの場合とSingleの場合の切り分け
                    if len(top_tickers) > 1:
                        # xsを使って特定の銘柄の全カラムを取得し、カラムの階層を削除
                        df_single = df_intraday.xs(ticker, axis=1, level=1)
                    else:
                        df_single = df_intraday

                    # VWAPとステータス計算
                    vwap, status, detail = calculate_vwap_and_status(df_single, current_price)
                    
                    item['AI判定'] = status
                    item['詳細'] = detail
                    item['VWAP'] = f"{vwap:,.0f}" if vwap else "-"
                    
                except Exception as e:
                    item['AI判定'] = "判定不能"
                    item['詳細'] = "-"
                    item['VWAP'] = "-"
                
                final_results.append(item)

            # 表示用データフレーム作成
            df_res = pd.DataFrame(final_results)
            
            # 表示整形
            df_display = pd.DataFrame()
            df_display['コード'] = df_res['code']
            df_display['銘柄名'] = df_res['銘柄名']
            df_display['現在値'] = df_res['現在値'].map(lambda x: f"{x:,.0f}")
            df_display['寄付比'] = df_res['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
            df_display['AI判定'] = df_res['AI判定'] # ここが最重要
            df_display['状況'] = df_res['詳細']
            
            # スタイル適用（判定によって色を変えるなどの高度な表示はst.dataframeのcolumn_configで行う）
            st.success(f"{market_name} の分析完了！")
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "AI判定": st.column_config.TextColumn(
                        "AI推奨アクション",
                        help="🚀=ブレイク狙い, ✋=待機, 👀=監視",
                        width="medium"
                    ),
                    "寄付比": st.column_config.TextColumn(
                        "寄付比",
                        width="small"
                    ),
                }
            )

# --- UIタブ ---
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])
with t1: analyze_market("プライム", "prime")
with t2: analyze_market("スタンダード", "standard")
with t3: analyze_market("グロース", "growth")
