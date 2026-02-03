import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・みんかぶ版", layout="centered")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

# --- メインアプリ ---
st.title("⚡️ リアルタイム強勢銘柄")
st.caption("みんかぶランキング × 5分足構造分析")

# --- 関数定義 ---

def get_ranking_minkabu(market_slug):
    """
    みんかぶから売買代金ランキングを取得
    market_slug: 'prime', 'standard', 'growth'
    """
    # みんかぶのURLパラメータ設定
    url = f"https://minkabu.jp/ranking/stock/turnover?market={market_slug}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            st.error(f"みんかぶアクセスエラー (Status: {res.status_code})")
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        
        # テーブルを取得
        rows = soup.select('table tbody tr')
        
        if not rows:
            st.warning("ランキング表が見つかりませんでした。")
            return []

        for row in rows:
            try:
                # 銘柄コードの抽出 (/stock/xxxx)
                link_el = row.select_one('a[href^="/stock/"]')
                if not link_el: continue
                
                href = link_el.get('href')
                code_match = re.search(r'/stock/(\d+)', href)
                if not code_match: continue
                code = code_match.group(1)
                
                # 銘柄名
                name = link_el.text.strip()
                
                # 現在値（tdの並び順から推定）
                # みんかぶのテーブル構造: 順位, 銘柄名, 現在値, 前日比, ...
                tds = row.select('td')
                if len(tds) < 3: continue
                
                price_text = tds[2].get_text(strip=True).replace(',', '')
                price_match = re.search(r'[\d\.]+', price_text)
                
                if price_match:
                    current_price = float(price_match.group())
                else:
                    continue

                data_list.append({
                    "code": code, 
                    "name": name, 
                    "scraped_current_price": current_price
                })
            except: continue
            
        return data_list[:50]
        
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return []

def calculate_vwap_and_status(df_5m, current_realtime_price):
    """AIロジック"""
    if df_5m.empty: return None, None, "データ不足"
    
    df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3
    df_5m['VP'] = df_5m['Typical_Price'] * df_5m['Volume']
    total_vp = df_5m['VP'].sum()
    total_vol = df_5m['Volume'].sum()
    
    if total_vol == 0: return None, None, "出来高なし"
    vwap = total_vp / total_vol
    
    vwap_divergence = (current_realtime_price - vwap) / vwap * 100
    
    status = ""
    detail = ""

    if vwap_divergence > 3.0:
        status = "✋ 加熱感"
        detail = f"+{vwap_divergence:.1f}%"
    elif 0.5 < vwap_divergence <= 3.0:
        status = "🚀 トレンド"
        detail = "順張り"
    elif -0.5 <= vwap_divergence <= 0.5:
        status = "⚖️ 攻防"
        detail = "様子見"
    elif vwap_divergence < -0.5:
        status = "📉 軟調"
        detail = f"{vwap_divergence:.1f}%"

    return vwap, status, detail

def analyze_market(market_name, market_slug):
    """市場分析実行"""
    if st.button(f'⚡️ {market_name}を分析', key=market_slug):
        
        # 1. ランキング取得 (みんかぶから)
        with st.spinner(f'みんかぶから{market_name}ランキングを取得中...'):
            ranking_data = get_ranking_minkabu(market_slug)
            
            if not ranking_data:
                st.error("ランキングデータの取得に失敗しました。")
                return

        # 2. データ取得
        with st.spinner('詳細分析を実行中...'):
            df_rank = pd.DataFrame(ranking_data)
            codes = df_rank['code'].tolist()
            yf_codes = [c if c.endswith('.T') else f"{c}.T" for c in codes]
            
            try:
                # yfinanceで一括取得
                df_daily = yf.download(yf_codes, period="1d", interval="1d", progress=False)
                df_intraday = yf.download(yf_codes, period="1d", interval="5m", progress=False)
            except:
                st.error("株価APIの通信に失敗しました。")
                return

            final_results = []
            
            # 始値
            try:
                if isinstance(df_daily.columns, pd.MultiIndex):
                    open_prices = df_daily.xs('Open', level=0, axis=1).iloc[-1]
                else:
                    open_prices = df_daily['Open'].iloc[-1]
            except: open_prices = {}

            # ループ処理
            for i, row in df_rank.iterrows():
                try:
                    code = row['code']
                    name = row['name']
                    curr_val = row['scraped_current_price']
                    yf_code = code if code.endswith('.T') else f"{code}.T"
                    
                    open_val = open_prices.get(yf_code)

                    if pd.isna(open_val) or open_val == 0: continue
                    
                    rise = (curr_val - open_val) / open_val * 100
                    
                    # AI判定
                    status = "-"
                    detail = "-"
                    try:
                        if len(yf_codes) > 1:
                            df_single = df_intraday.xs(yf_code, axis=1, level=1)
                        else:
                            df_single = df_intraday
                        _, status, detail = calculate_vwap_and_status(df_single, curr_val)
                    except: pass

                    final_results.append({
                        "銘柄名": name,
                        "寄付比": rise, 
                        "現在値": curr_val,
                        "AI判定": status,
                        "詳細": detail
                    })
                except: continue

            # 結果表示
            if final_results:
                df_res = pd.DataFrame(final_results)
                df_res = df_res.sort_values(by="寄付比", ascending=False)
                
                df_show = pd.DataFrame()
                df_show['銘柄'] = df_res['銘柄名']
                df_show['寄付比'] = df_res['寄付比'].map(lambda x: f"+{x:.2f}%" if x>0 else f"{x:.2f}%")
                df_show['現在値'] = df_res['現在値'].map(lambda x: f"{x:,.0f}")
                df_show['AI判定'] = df_res['AI判定']
                df_show['詳細'] = df_res['詳細']
                
                st.success(f"分析完了！ ({len(df_show)}銘柄)")
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.warning("データが見つかりませんでした。")

# --- UIタブ ---
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])
with t1: analyze_market("プライム", "prime")
with t2: analyze_market("スタンダード", "standard")
with t3: analyze_market("グロース", "growth")
