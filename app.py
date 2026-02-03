import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
import numpy as np

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・改", layout="centered")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

# --- メインアプリ ---
st.title("⚡️ リアルタイム強勢銘柄判定")
st.caption("Yahoo!速報値 × 5分足構造分析 (Anti-Block Ver.)")

# --- 関数定義 ---

def get_ranking_data_hybrid(market_code):
    """Yahoo!ランキング取得（ブロック回避・デバッグ機能付き）"""
    url = f"https://finance.yahoo.co.jp/ranking/tradingValue?market={market_code}&term=daily&area=JP"
    
    # 【重要】本物のブラウザになりすますためのヘッダー情報
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        # もしアクセス拒否されたら、ステータスコードを表示する
        if res.status_code != 200:
            st.error(f"アクセスが拒否されました (Status: {res.status_code})")
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        
        # データの抽出
        rows = soup.select('tbody tr')
        
        # もしデータが空なら、デバッグ情報を表示（ページタイトルを確認）
        if not rows:
            page_title = soup.title.string if soup.title else "タイトル取得不能"
            st.warning(f"HTMLは取得できましたが、データが見つかりません。")
            st.info(f"取得したページタイトル: {page_title}")
            return []

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
        st.error(f"通信エラー: {e}")
        return []

def calculate_vwap_and_status(df_5m, current_realtime_price):
    """AIロジック（変更なし）"""
    if df_5m.empty: return None, None, "データ不足"
    
    df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3
    df_5m['VP'] = df_5m['Typical_Price'] * df_5m['Volume']
    
    total_vp = df_5m['VP'].sum()
    total_vol = df_5m['Volume'].sum()
    
    if total_vol == 0: return None, None, "出来高なし"

    vwap = total_vp / total_vol
    
    recent_candles = df_5m.tail(3)
    recent_volatility = (recent_candles['High'] - recent_candles['Low']).mean()
    price_volatility_ratio = recent_volatility / current_realtime_price * 100 
    
    vwap_divergence = (current_realtime_price - vwap) / vwap * 100
    
    status = ""
    detail = ""

    if vwap_divergence > 3.0:
        status = "✋ 加熱・押し目待ち"
        detail = f"乖離 +{vwap_divergence:.1f}%"
    elif 0 < vwap_divergence <= 3.0:
        if price_volatility_ratio < 0.3:
            status = "🚀 ブレイク前兆 (横横)"
            detail = f"Vol {price_volatility_ratio:.2f}%"
        else:
            status = "📈 上昇トレンド中"
            detail = "順張り"
    elif vwap_divergence <= 0:
        status = "👀 VWAP攻防・監視"
        detail = f"乖離 {vwap_divergence:.1f}%"

    return vwap, status, detail

def analyze_market(market_name, market_slug):
    """市場分析実行"""
    if st.button(f'⚡️ {market_name}を分析', key=market_slug):
        
        # 1. ランキング取得
        with st.spinner('1. ランキング取得中...'):
            ranking_data = get_ranking_data_hybrid(market_slug)
            if not ranking_data:
                st.error("ランキングデータの取得に失敗しました。")
                return

        # 2. 始値比較
        with st.spinner('2. 始値データを照合中...'):
            df_rank = pd.DataFrame(ranking_data)
            codes = df_rank['code'].tolist()
            yf_codes = [c if c.endswith('.T') else f"{c}.T" for c in codes]
            
            df_daily = yf.download(yf_codes, period="1d", interval="1d", progress=False)
            
            try:
                if isinstance(df_daily.columns, pd.MultiIndex):
                    open_prices = df_daily.xs('Open', level=0, axis=1).iloc[-1]
                else:
                    open_prices = df_daily['Open'].iloc[-1]
            except:
                st.error("株価データ整形エラー")
                return

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

            pre_results.sort(key=lambda x: x["寄付比"], reverse=True)
            top_stocks = pre_results[:15]
            top_tickers = [x['yf_code'] for x in top_stocks]

        # 3. AI判定
        with st.spinner('3. AI判定実行中...'):
            try:
                df_intraday = yf.download(top_tickers, period="1d", interval="5m", progress=False)
            except Exception as e:
                st.error(f"詳細データ取得エラー: {e}")
                return

            final_results = []
            for item in top_stocks:
                ticker = item['yf_code']
                current_price = item['現在値']
                try:
                    if len(top_tickers) > 1:
                        df_single = df_intraday.xs(ticker, axis=1, level=1)
                    else:
                        df_single = df_intraday
                    vwap, status, detail = calculate_vwap_and_status(df_single, current_price)
                    item['AI判定'] = status
                    item['詳細'] = detail
                except:
                    item['AI判定'] = "判定不能"
                    item['詳細'] = "-"
                final_results.append(item)

            df_display = pd.DataFrame(final_results)
            df_show = pd.DataFrame()
            df_show['コード'] = df_display['code']
            df_show['銘柄名'] = df_display['銘柄名']
            df_show['現在値'] = df_display['現在値'].map(lambda x: f"{x:,.0f}")
            df_show['寄付比'] = df_display['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
            df_show['AI判定'] = df_display['AI判定']
            df_show['詳細'] = df_display['詳細']
            
            st.success(f"{market_name} の分析完了！")
            st.dataframe(
                df_show,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "AI判定": st.column_config.TextColumn("AI推奨アクション", width="medium"),
                    "寄付比": st.column_config.TextColumn("寄付比", width="small"),
                }
            )

# --- UIタブ ---
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])
with t1: analyze_market("プライム", "prime")
with t2: analyze_market("スタンダード", "standard")
with t3: analyze_market("グロース", "growth")
