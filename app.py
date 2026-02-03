import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・StockWeather版", layout="centered")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

st.title("⚡️ リアルタイム強勢銘柄")
st.caption("出典：StockWeather (寄付からの値上がり率ランキング)")

# --- 関数定義 ---

def get_ranking_stockweather(market_id):
    """
    StockWeatherから『寄付からの値上がり率』を取得
    market_id: 1=プライム, 2=スタンダード, 3=グロース
    """
    url = f"https://finance.stockweather.co.jp/contents/ranking.aspx?mkt={market_id}&cat=0000&type=2"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding # 文字化け対策
        
        if res.status_code != 200:
            st.error(f"アクセス拒否 (Status: {res.status_code})")
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        
        # テーブルデータの解析
        rows = soup.select('table tr')
        
        for row in rows:
            try:
                tds = row.select('td')
                if not tds: continue
                
                # 1. 銘柄名とコード
                name_text = tds[1].get_text(strip=True)
                code_match = re.search(r'（(\d{4})）', name_text)
                if not code_match: continue
                
                code = code_match.group(1)
                name = name_text.split('（')[0].strip()
                
                # 2. 現在値
                price_text = tds[3].get_text(strip=True).replace(',', '')
                current_price = float(price_text)
                
                # 3. 寄付比（StockWeather独自の指標）
                ratio_text = tds[5].get_text(strip=True).replace('%', '').replace('+', '')
                ratio = float(ratio_text)

                data_list.append({
                    "code": code,
                    "name": name,
                    "current_price": current_price,
                    "ratio": ratio
                })
            except: continue
            
        return data_list[:50] # 上位50件
        
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return []

def analyze_market(market_name, market_id):
    """市場を指定して分析"""
    if st.button(f'⚡️ {market_name}を分析', key=market_id):
        with st.spinner(f'{market_name}のデータを取得中...'):
            ranking_data = get_ranking_stockweather(market_id)
            
            if not ranking_data:
                st.error("ランキングの取得に失敗しました。")
                return

        with st.spinner('5分足データで詳細判定中...'):
            df_rank = pd.DataFrame(ranking_data)
            
            # yfinance用にコード変換
            codes = df_rank['code'].tolist()
            yf_codes = [f"{c}.T" for c in codes]
            
            # 5分足取得
            try:
                df_intraday = yf.download(yf_codes, period="1d", interval="5m", progress=False)
            except:
                st.warning("詳細データの取得に失敗しました（ランキングのみ表示します）")
                df_intraday = pd.DataFrame()

            final_results = []
            
            for i, row in df_rank.iterrows():
                yf_code = f"{row['code']}.T"
                
                # AI判定
                status = "-"
                try:
                    if not df_intraday.empty:
                        if len(yf_codes) > 1:
                            df_single = df_intraday.xs(yf_code, axis=1, level=1)
                        else:
                            df_single = df_intraday
                            
                        # VWAP計算
                        typical_price = (df_single['High'] + df_single['Low'] + df_single['Close']) / 3
                        vp = typical_price * df_single['Volume']
                        vwap = vp.sum() / df_single['Volume'].sum()
                        
                        divergence = (row['current_price'] - vwap) / vwap * 100
                        
                        if divergence > 3.0: status = "✋ 加熱"
                        elif 0.5 < divergence <= 3.0: status = "🚀 イケイケ"
                        elif -0.5 <= divergence <= 0.5: status = "⚖️ 攻防"
                        else: status = "📉 失速"
                except: pass

                final_results.append({
                    "銘柄": row['name'],
                    "現在値": row['current_price'],
                    "寄付比": row['ratio'],
                    "AI判定": status
                })

            # 表示
            df_show = pd.DataFrame(final_results)
            # 寄付比順にソート
            df_show = df_show.sort_values(by="寄付比", ascending=False)
            
            df_show['現在値'] = df_show['現在値'].map(lambda x: f"{x:,.0f}")
            df_show['寄付比'] = df_show['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
            
            st.success(f"{market_name} 分析完了！ ({len(df_show)}銘柄)")
            st.dataframe(df_show, use_container_width=True, hide_index=True)

# --- UIタブ ---
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])

with t1:
    analyze_market("プライム", "1")
with t2:
    analyze_market("スタンダード", "2")
with t3:
    analyze_market("グロース", "3")
