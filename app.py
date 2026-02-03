{\rtf1\ansi\ansicpg932\cocoartf2867
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
import yfinance as yf\
import requests\
from bs4 import BeautifulSoup\
import re\
import numpy as np  # \uc0\u35336 \u31639 \u29992 \u12395 numpy\u36861 \u21152 \
\
# \uc0\u12506 \u12540 \u12472 \u35373 \u23450 \
st.set_page_config(page_title="\uc0\u26368 \u24375 \u37528 \u26564 \u25277 \u20986 \u12367 \u12435 \u12539 \u25913 ", layout="mobile")\
\
# --- \uc0\u12475 \u12461 \u12517 \u12522 \u12486 \u12451 \u35373 \u23450  ---\
MY_PASSWORD = \'93stock testa\'94 \
st.title("\uc0\u55357 \u56594  \u35469 \u35388 ")\
password = st.text_input("\uc0\u12497 \u12473 \u12527 \u12540 \u12489 \u12434 \u20837 \u21147 \u12375 \u12390 \u12367 \u12384 \u12373 \u12356 ", type="password")\
if password != MY_PASSWORD:\
    st.warning("\uc0\u12497 \u12473 \u12527 \u12540 \u12489 \u12434 \u20837 \u21147 \u12375 \u12390 Enter\u12461 \u12540 \u12434 \u25276 \u12375 \u12390 \u12367 \u12384 \u12373 \u12356 \u12290 ")\
    st.stop()\
\
# --- \uc0\u12513 \u12452 \u12531 \u12450 \u12503 \u12522  ---\
st.title("\uc0\u9889 \u65039  \u12522 \u12450 \u12523 \u12479 \u12452 \u12512 \u24375 \u21218 \u37528 \u26564 \u21028 \u23450 ")\
st.caption("Yahoo!\uc0\u36895 \u22577 \u20516  \'d7 5\u20998 \u36275 \u27083 \u36896 \u20998 \u26512  (Phase 2\u23455 \u35013 \u29256 )")\
\
# --- \uc0\u38306 \u25968 \u23450 \u32681  ---\
\
def get_ranking_data_hybrid(market_code):\
    """Yahoo!\uc0\u12521 \u12531 \u12461 \u12531 \u12464 \u12363 \u12425 \u29694 \u22312 \u20516 \u12434 \u12473 \u12463 \u12524 \u12452 \u12500 \u12531 \u12464 \u65288 Phase 1\u12381 \u12398 \u12414 \u12414 \u65289 """\
    url = f"https://finance.yahoo.co.jp/ranking/tradingValue?market=\{market_code\}&term=daily&area=JP"\
    headers = \{"User-Agent": "Mozilla/5.0"\}\
    \
    try:\
        res = requests.get(url, headers=headers, timeout=10)\
        soup = BeautifulSoup(res.text, 'html.parser')\
        data_list = []\
        rows = soup.select('tbody tr')\
        for row in rows:\
            try:\
                tds = row.select('td')\
                if not tds: continue\
                el_link = tds[1].select_one('a')\
                if not el_link: continue\
                \
                href = el_link.get('href')\
                code = href.split('/')[-1]\
                name = el_link.text\
                price_text = tds[3].get_text(strip=True).replace(',', '')\
                match = re.search(r'[\\d\\.]+', price_text)\
                current_price = float(match.group()) if match else None\
\
                if current_price:\
                    data_list.append(\{"code": code, "name": name, "scraped_current_price": current_price\})\
            except: continue\
        return data_list[:50]\
    except Exception as e:\
        st.error(f"\uc0\u12487 \u12540 \u12479 \u21462 \u24471 \u12456 \u12521 \u12540 : \{e\}")\
        return []\
\
def calculate_vwap_and_status(df_5m, current_realtime_price):\
    """\
    5\uc0\u20998 \u36275 \u12487 \u12540 \u12479 \u12363 \u12425 VWAP\u12392 \u12508 \u12521 \u12486 \u12451 \u12522 \u12486 \u12451 \u12434 \u35336 \u31639 \u12375 \u12289 \
    \uc0\u12522 \u12450 \u12523 \u12479 \u12452 \u12512 \u20385 \u26684 \u12392 \u29031 \u12425 \u12375 \u21512 \u12431 \u12379 \u12390 \u21028 \u23450 \u12434 \u34892 \u12358 AI\u12525 \u12472 \u12483 \u12463 \
    """\
    if df_5m.empty:\
        return None, None, "\uc0\u12487 \u12540 \u12479 \u19981 \u36275 "\
\
    # VWAP\uc0\u35336 \u31639 \
    # (Typical Price * Volume) \uc0\u12398 \u32047 \u31309  / Volume \u12398 \u32047 \u31309 \
    df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3\
    df_5m['VP'] = df_5m['Typical_Price'] * df_5m['Volume']\
    \
    total_vp = df_5m['VP'].sum()\
    total_vol = df_5m['Volume'].sum()\
    \
    if total_vol == 0:\
        return None, None, "\uc0\u20986 \u26469 \u39640 \u12394 \u12375 "\
\
    vwap = total_vp / total_vol\
    \
    # \uc0\u27161 \u28310 \u20559 \u24046 \u65288 \u31777 \u26131 \u30340 \u12394 \u12508 \u12522 \u12531 \u12472 \u12515 \u12540 \u12496 \u12531 \u12489 \u12398 \u12424 \u12358 \u12394 \u12418 \u12398 \u65289 \u12434 VWAP\u12505 \u12540 \u12473 \u12391 \u35336 \u31639 \
    # \uc0\u12371 \u12371 \u12391 \u12399 \u31777 \u26131 \u30340 \u12395 Close\u12398 \u27161 \u28310 \u20559 \u24046 \u12434 \u20351 \u29992 \
    std = df_5m['Close'].std()\
    \
    # \uc0\u30452 \u36817 \u12398 \u12508 \u12521 \u12486 \u12451 \u12522 \u12486 \u12451 \u65288 \u30452 \u36817 3\u26412 \u12398 \u39640 \u20516 -\u23433 \u20516 \u12398 \u24179 \u22343 \u65289 \
    recent_candles = df_5m.tail(3)\
    recent_volatility = (recent_candles['High'] - recent_candles['Low']).mean()\
    price_volatility_ratio = recent_volatility / current_realtime_price * 100 # \uc0\u26666 \u20385 \u12395 \u23550 \u12377 \u12427 \u22793 \u21205 \u29575 (%)\
\
    # --- \uc0\u21028 \u23450 \u12525 \u12472 \u12483 \u12463  (\u12371 \u12371 \u12364 AI\u12398 \u33075 \u12415 \u12381 ) ---\
    \
    # 1. VWAP\uc0\u20054 \u38626 \u29575 \
    vwap_divergence = (current_realtime_price - vwap) / vwap * 100\
    \
    status = ""\
    detail = ""\
\
    # \uc0\u21028 \u23450 A: \u36942 \u29105 \u24863 \u12354 \u12426  (VWAP\u12363 \u12425 \u22823 \u12365 \u12367 \u19978 \u12395 \u20054 \u38626 ) -> \u20363 : +3%\u20197 \u19978 \
    if vwap_divergence > 3.0:\
        status = "\uc0\u9995  \u21152 \u29105 \u12539 \u25276 \u12375 \u30446 \u24453 \u12385 "\
        detail = f"\uc0\u20054 \u38626  +\{vwap_divergence:.1f\}%"\
        \
    # \uc0\u21028 \u23450 B: \u12452 \u12465 \u12452 \u12465 \u12539 \u12502 \u12524 \u12452 \u12463 \u29401 \u12356  (VWAP\u12424 \u12426 \u19978 \u12289 \u12363 \u12388 \u12508 \u12521 \u21454 \u32302 )\
    # \uc0\u20054 \u38626 \u12364 \u36969 \u24230 (0%~3%) \u12363 \u12388  \u22793 \u21205 \u29575 \u12364 \u23567 \u12373 \u12356 (0.3%\u26410 \u28288 \u12394 \u12393 )\
    elif 0 < vwap_divergence <= 3.0:\
        if price_volatility_ratio < 0.3: # \uc0\u27178 \u27178 \u12375 \u12390 \u12356 \u12427 \
            status = "\uc0\u55357 \u56960  \u12502 \u12524 \u12452 \u12463 \u21069 \u20806  (\u27178 \u27178 )"\
            detail = f"Vol \{price_volatility_ratio:.2f\}%"\
        else:\
            status = "\uc0\u55357 \u56520  \u19978 \u26119 \u12488 \u12524 \u12531 \u12489 \u20013 "\
            detail = "\uc0\u38918 \u24373 \u12426 "\
            \
    # \uc0\u21028 \u23450 C: VWAP\u21106 \u12428  (\u35519 \u25972 \u20013 )\
    elif vwap_divergence <= 0:\
        status = "\uc0\u55357 \u56384  VWAP\u25915 \u38450 \u12539 \u30435 \u35222 "\
        detail = f"\uc0\u20054 \u38626  \{vwap_divergence:.1f\}%"\
\
    return vwap, status, detail\
\
\
def analyze_market(market_name, market_slug):\
    """\uc0\u24066 \u22580 \u20998 \u26512 \u23455 \u34892 """\
    if st.button(f'\uc0\u9889 \u65039  \{market_name\}\u12434 \u20998 \u26512 ', key=market_slug):\
        with st.spinner('1. \uc0\u12521 \u12531 \u12461 \u12531 \u12464 \u21462 \u24471 \u20013 ...'):\
            ranking_data = get_ranking_data_hybrid(market_slug)\
            if not ranking_data:\
                st.error("\uc0\u12521 \u12531 \u12461 \u12531 \u12464 \u21462 \u24471 \u22833 \u25943 ")\
                return\
\
        # Phase 1: \uc0\u22987 \u20516 \u27604 \u36611 \
        with st.spinner('2. \uc0\u22987 \u20516 \u12487 \u12540 \u12479 \u12434 \u29031 \u21512 \u20013 ...'):\
            df_rank = pd.DataFrame(ranking_data)\
            codes = df_rank['code'].tolist()\
            yf_codes = [c if c.endswith('.T') else f"\{c\}.T" for c in codes]\
            \
            # \uc0\u26085 \u36275 \u21462 \u24471 \u65288 \u22987 \u20516 \u29992 \u65289 \
            df_daily = yf.download(yf_codes, period="1d", interval="1d", progress=False)\
            \
            # \uc0\u12487 \u12540 \u12479 \u25972 \u24418 \
            try:\
                if isinstance(df_daily.columns, pd.MultiIndex):\
                    open_prices = df_daily.xs('Open', level=0, axis=1).iloc[-1]\
                else:\
                    open_prices = df_daily['Open'].iloc[-1]\
            except:\
                st.error("\uc0\u26666 \u20385 \u12487 \u12540 \u12479 \u25972 \u24418 \u12456 \u12521 \u12540 ")\
                return\
\
            # \uc0\u19968 \u27425 \u36984 \u25244 \u12522 \u12473 \u12488 \u20316 \u25104 \
            pre_results = []\
            for i, row in df_rank.iterrows():\
                try:\
                    code = row['code']\
                    curr_val = row['scraped_current_price']\
                    yf_code = code if code.endswith('.T') else f"\{code\}.T"\
                    open_val = open_prices.get(yf_code)\
\
                    if pd.isna(open_val) or open_val == 0: continue\
                    \
                    rise = (curr_val - open_val) / open_val * 100\
                    pre_results.append(\{\
                        "yf_code": yf_code,\
                        "code": code, \
                        "\uc0\u37528 \u26564 \u21517 ": row['name'],\
                        "\uc0\u23492 \u20184 \u27604 ": rise, \
                        "\uc0\u29694 \u22312 \u20516 ": curr_val\
                    \})\
                except: continue\
\
            # \uc0\u23492 \u20184 \u27604 \u12364 \u39640 \u12356 \u38918 \u12395 \u20006 \u12409 \u26367 \u12360 \
            pre_results.sort(key=lambda x: x["\uc0\u23492 \u20184 \u27604 "], reverse=True)\
            \
            # \uc0\u19978 \u20301 15\u37528 \u26564 \u12395 \u32094 \u12387 \u12390 \u35443 \u32048 \u20998 \u26512  (API\u21046 \u38480 \u12392 \u36895 \u24230 \u32771 \u24942 )\
            top_stocks = pre_results[:15]\
            top_tickers = [x['yf_code'] for x in top_stocks]\
\
        # Phase 2: 5\uc0\u20998 \u36275 \u12487 \u12540 \u12479 \u21462 \u24471 \u12392 \u35443 \u32048 \u21028 \u23450 \
        with st.spinner('3. AI\uc0\u21028 \u23450 \u23455 \u34892 \u20013  (5\u20998 \u36275 \u12539 VWAP\u20998 \u26512 )...'):\
            # \uc0\u12414 \u12392 \u12417 \u12390 5\u20998 \u36275 \u21462 \u24471 \
            try:\
                df_intraday = yf.download(top_tickers, period="1d", interval="5m", progress=False)\
            except Exception as e:\
                st.error(f"\uc0\u35443 \u32048 \u12487 \u12540 \u12479 \u21462 \u24471 \u12456 \u12521 \u12540 : \{e\}")\
                return\
\
            final_results = []\
            \
            for item in top_stocks:\
                ticker = item['yf_code']\
                current_price = item['\uc0\u29694 \u22312 \u20516 ']\
                \
                # \uc0\u20491 \u21029 \u37528 \u26564 \u12398 5\u20998 \u36275 \u25277 \u20986 \
                try:\
                    # MultiIndex\uc0\u12398 \u22580 \u21512 \u12392 Single\u12398 \u22580 \u21512 \u12398 \u20999 \u12426 \u20998 \u12369 \
                    if len(top_tickers) > 1:\
                        # xs\uc0\u12434 \u20351 \u12387 \u12390 \u29305 \u23450 \u12398 \u37528 \u26564 \u12398 \u20840 \u12459 \u12521 \u12512 \u12434 \u21462 \u24471 \u12375 \u12289 \u12459 \u12521 \u12512 \u12398 \u38542 \u23652 \u12434 \u21066 \u38500 \
                        df_single = df_intraday.xs(ticker, axis=1, level=1)\
                    else:\
                        df_single = df_intraday\
\
                    # VWAP\uc0\u12392 \u12473 \u12486 \u12540 \u12479 \u12473 \u35336 \u31639 \
                    vwap, status, detail = calculate_vwap_and_status(df_single, current_price)\
                    \
                    item['AI\uc0\u21028 \u23450 '] = status\
                    item['\uc0\u35443 \u32048 '] = detail\
                    item['VWAP'] = f"\{vwap:,.0f\}" if vwap else "-"\
                    \
                except Exception as e:\
                    item['AI\uc0\u21028 \u23450 '] = "\u21028 \u23450 \u19981 \u33021 "\
                    item['\uc0\u35443 \u32048 '] = "-"\
                    item['VWAP'] = "-"\
                \
                final_results.append(item)\
\
            # \uc0\u34920 \u31034 \u29992 \u12487 \u12540 \u12479 \u12501 \u12524 \u12540 \u12512 \u20316 \u25104 \
            df_res = pd.DataFrame(final_results)\
            \
            # \uc0\u34920 \u31034 \u25972 \u24418 \
            df_display = pd.DataFrame()\
            df_display['\uc0\u12467 \u12540 \u12489 '] = df_res['code']\
            df_display['\uc0\u37528 \u26564 \u21517 '] = df_res['\u37528 \u26564 \u21517 ']\
            df_display['\uc0\u29694 \u22312 \u20516 '] = df_res['\u29694 \u22312 \u20516 '].map(lambda x: f"\{x:,.0f\}")\
            df_display['\uc0\u23492 \u20184 \u27604 '] = df_res['\u23492 \u20184 \u27604 '].map(lambda x: f"+\{x:.2f\}%" if x>0 else f"\{x:.2f\}%")\
            df_display['AI\uc0\u21028 \u23450 '] = df_res['AI\u21028 \u23450 '] # \u12371 \u12371 \u12364 \u26368 \u37325 \u35201 \
            df_display['\uc0\u29366 \u27841 '] = df_res['\u35443 \u32048 ']\
            \
            # \uc0\u12473 \u12479 \u12452 \u12523 \u36969 \u29992 \u65288 \u21028 \u23450 \u12395 \u12424 \u12387 \u12390 \u33394 \u12434 \u22793 \u12360 \u12427 \u12394 \u12393 \u12398 \u39640 \u24230 \u12394 \u34920 \u31034 \u12399 st.dataframe\u12398 column_config\u12391 \u34892 \u12358 \u65289 \
            st.success(f"\{market_name\} \uc0\u12398 \u20998 \u26512 \u23436 \u20102 \u65281 ")\
            st.dataframe(\
                df_display,\
                use_container_width=True,\
                hide_index=True,\
                column_config=\{\
                    "AI\uc0\u21028 \u23450 ": st.column_config.TextColumn(\
                        "AI\uc0\u25512 \u22888 \u12450 \u12463 \u12471 \u12519 \u12531 ",\
                        help="\uc0\u55357 \u56960 =\u12502 \u12524 \u12452 \u12463 \u29401 \u12356 , \u9995 =\u24453 \u27231 , \u55357 \u56384 =\u30435 \u35222 ",\
                        width="medium"\
                    ),\
                    "\uc0\u23492 \u20184 \u27604 ": st.column_config.TextColumn(\
                        "\uc0\u23492 \u20184 \u27604 ",\
                        width="small"\
                    ),\
                \}\
            )\
\
# --- UI\uc0\u12479 \u12502  ---\
t1, t2, t3 = st.tabs(["\uc0\u12503 \u12521 \u12452 \u12512 ", "\u12473 \u12479 \u12531 \u12480 \u12540 \u12489 ", "\u12464 \u12525 \u12540 \u12473 "])\
with t1: analyze_market("\uc0\u12503 \u12521 \u12452 \u12512 ", "prime")\
with t2: analyze_market("\uc0\u12473 \u12479 \u12531 \u12480 \u12540 \u12489 ", "standard")\
with t3: analyze_market("\uc0\u12464 \u12525 \u12540 \u12473 ", "growth")}