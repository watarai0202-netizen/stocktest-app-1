import streamlit as st
import pandas as pd
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

st.title("⚡️ 寄付値上がり率ランキング")
st.caption("出典：StockWeather (銘柄名対応版)")

# --- 関数定義 ---

def get_ranking_stockweather(market_id):
    """
    StockWeatherからランキングを取得
    market_id: 1=東証プライム, 2=東証スタンダード, 3=東証グロース
    """
    # type=2 は「寄付からの値上がり率」
    url = f"https://finance.stockweather.co.jp/contents/ranking.aspx?mkt={market_id}&cat=0000&type=2"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding # 日本語文字化け対策
        
        if res.status_code != 200:
            st.error(f"アクセス拒否 (Status: {res.status_code})")
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        data_list = []
        
        # テーブルデータの解析
        # StockWeatherのテーブル構造: 順位, 銘柄名(コード), 市場, 現在値, 前日比, 寄付比...
        rows = soup.select('table tr')
        
        for row in rows:
            try:
                tds = row.select('td')
                if len(tds) < 6: continue # データ列が足りない行はスキップ
                
                # 1. 銘柄名とコードの抽出
                # 例: "ユニチカ （3103）" という形式になっている
                name_raw = tds[1].get_text(strip=True)
                
                # 全角カッコで分割して、名前とコードを分ける
                if '（' in name_raw:
                    parts = name_raw.split('（')
                    name = parts[0].strip()
                    code = parts[1].replace('）', '').strip()
                else:
                    name = name_raw
                    code = "-"
                
                # 2. 現在値 (3列目)
                price_text = tds[3].get_text(strip=True).replace(',', '')
                
                # 3. 寄付比 (5列目) "+18.90%"
                ratio_text = tds[5].get_text(strip=True)
                
                # 4. データ格納
                data_list.append({ "コード": code, "銘柄名": name, "現在値": price_text,"寄付比": ratio_text })
            except: continue
            
        return data_list[:50] # 上位50件を表示
        
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        return []

def show_market_ranking(market_name, market_id):
    """指定された市場のランキングを表示"""
    if st.button(f'⚡️ {market_name} を更新', key=market_id):
        with st.spinner(f'{market_name}のデータを取得中...'):
            ranking_data = get_ranking_stockweather(market_id)
            
            if ranking_data:
                df = pd.DataFrame(ranking_data)
                
                # データフレームを表示
                st.success(f"取得完了！ ({len(df)}銘柄)")
                
                st.dataframe(df,use_container_width=True,hide_index=True,column_config={"寄付比": st.column_config.TextColumn(
                            "寄付比",help="始値からの上昇率",width="small"),
                        "銘柄名": st.column_config.TextColumn(
                            "銘柄名",width="medium"),})else:st.warning("データが取得できませんでした。")

# --- メイン画面（タブ切り替え） ---
t1, t2, t3 = st.tabs(["プライム", "スタンダード", "グロース"])

with t1:
    st.info("東証プライム：大型・主力株")
    show_market_ranking("プライム", 1)

with t2:
    st.info("東証スタンダード：中堅・老舗株")
    show_market_ranking("スタンダード", 2)

with t3:
    st.info("東証グロース：新興・急騰株")
    show_market_ranking("グロース", 3)
