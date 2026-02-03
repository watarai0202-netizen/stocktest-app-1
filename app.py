import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re

# ページ設定
st.set_page_config(page_title="最強銘柄抽出くん・株探Ver", layout="centered")

# --- セキュリティ設定 ---
MY_PASSWORD = "stock testa" 
st.title("🔒 認証")
password = st.text_input("パスワードを入力してください", type="password")
if password != MY_PASSWORD:
    st.warning("パスワードを入力してEnterキーを押してください。")
    st.stop()

# --- メインアプリ ---
st.title("⚡️ リアルタイム強勢銘柄")
st.caption("株探ランキング × 5分足構造分析")

# --- 関数定義 ---

def get_ranking_kabutan(market_type):
    """
    株探（Kabutan）から売買代金ランキングを取得
    market_type: '1'=Prime, '2'=Standard, '3'=Growth
    """
    url = f"https://kabutan.jp/ranking/?mode=1&market={market_type}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        # 株探もブロックする場合の対策
        if res.status_code != 200:
            st.error(f"株探アクセスエラー (Status: {res.status_code})")
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        
        # 株探のテーブル構造に合わせて解析
        # <table class="stock_table">
        table = soup.select_one('table.stock_table')
        if not table:
            return []
            
        rows = table.select('tbody tr')
        
        for row in rows:
            try:
                tds = row.select('td')
                if len(tds) < 4: continue
                
                # コードと名称 (2列目)
                el_link = tds[1].select_one('a')
                if not el_link: continue
                
                # リンクからコード抽出 (/stock/?code=xxxx)
                href = el_link.get('href')
                code_match = re.search(r'code=(\d+)', href)
                if not code_match: continue
                code = code_match.group(1)
                
                name = el_link.text
                
                # 現在値 (4列目)
                price_text = tds[3].get_text(strip=True).replace(',', '')
                # '1234.5' などを抽出
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
    """AIロジック（変更なし）"""
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
        status = "✋ 加熱感あり"
        detail = f"乖離 +{vwap_divergence:.1f}%"
    elif 0.5 < vwap_divergence <= 3.0:
        status = "📈 上昇トレンド"
        detail = "順張り"
    elif -0.5 <= vwap_divergence <= 0.5:
        status = "⚖️ VWAP付近"
        detail = "攻防中"
    elif vwap_divergence < -0.5:
        status = "📉 弱含み"
        detail = f"乖離 {vwap_divergence:.1f}%"

    return vwap, status, detail

def analyze_market(market_name, market_type_id):
    """市場分析実行"""
    if st.button(f'⚡️ {market_name}を分析', key=market_type_id):
        
        # 1. ランキング取得 (株探から)
        with st.spinner(f'株探から{market_name}ランキングを取得中...'):
            ranking_data = get_ranking_kabutan(market_type_id)
            
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
            
            # 始値の取得処理
            try:
                if isinstance(df_daily.columns, pd.MultiIndex):
                    open_prices = df_daily.xs('Open', level=0, axis=1).iloc[-1]
                else:
                    open_prices = df_daily['Open'].iloc[-1]
            except:
                open_prices = {}

            # ループ処理
            for i, row in df_rank.iterrows():
                try:
                    code = row['code']
                    name = row['name']
                    curr_val = row['scraped_current_price']
                    yf_code = code if code.endswith('.T') else f"{code}.T"
                    
                    open_val = open_prices.get(yf_code)

                    # 始値が取れない、または0の場合はスキップ
                    if pd.isna(open_val) or open_val == 0: 
                        continue
                    
                    # 寄付比計算
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
                
                st.success(f"分析完了！ ({len(df_show)}銘柄)")
                st.dataframe(
                    df_show,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("条件に合う銘柄が見つかりませんでした（APIの遅延の可能性があります）。")

# --- UIタブ ---
# 株探の市場コード: 1=プライム, 2=スタンダード, 3=グロース
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])
with t1: analyze_market("プライム", "1")
with t2: analyze_market("スタンダード", "2")
with t3: analyze_market("グロース", "3")
