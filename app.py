# =========================
# 7. 市場天気予報（1570：価格＋売買代金温度）
# =========================
def check_market_condition():
    st.markdown("### 🌡 マーケット天気予報 (日経レバ 1570)")

    try:
        # --- 価格（寄付比・前日比） ---
        df_m = fetch_prices(["1570.T"], period="5d")
        if df_m is None or df_m.empty:
            st.warning("1570データが取得できませんでした。")
            return

        if isinstance(df_m.columns, pd.MultiIndex):
            s = df_m["1570.T"].dropna()
        else:
            s = df_m.dropna()

        if len(s) < 2:
            st.warning("1570データが不足しています。")
            return

        latest = s.iloc[-1]
        prev = s.iloc[-2]

        curr = float(latest["Close"])
        op = float(latest["Open"])
        prev_cl = float(prev["Close"])

        op_ch = (curr - op) / op * 100
        day_ch = (curr - prev_cl) / prev_cl * 100

        # --- 売買代金温度（近似：Typical Price × Volume）---
        tv_ratio = None
        tv_today = None
        tv_avg20 = None
        tv_ch_pct = None

        try:
            df_tv = fetch_1570_prices(period="3mo")
            if df_tv is not None and (not df_tv.empty):
                if isinstance(df_tv.columns, pd.MultiIndex):
                    tv = df_tv["1570.T"].dropna()
                else:
                    tv = df_tv.dropna()

                if len(tv) >= 6:
                    tv_latest = tv.iloc[-1]
                    tv_prev = tv.iloc[-2]

                    # Typical Price × Volume（億円）
                    tv_today = _calc_trading_value_oku(
                        tv_latest["High"], tv_latest["Low"], tv_latest["Close"], tv_latest["Volume"]
                    )
                    tv_yday = _calc_trading_value_oku(
                        tv_prev["High"], tv_prev["Low"], tv_prev["Close"], tv_prev["Volume"]
                    )
                    tv_ch_pct = (tv_today - tv_yday) / tv_yday * 100 if tv_yday > 0 else 0.0

                    # 直近20日平均（今日を除いて平均）
                    tail = tv.tail(21).copy()
                    tail["TV"] = (((tail["High"] + tail["Low"] + tail["Close"]) / 3.0) * tail["Volume"]) / 1e8

                    if len(tail) >= 7:
                        tv_avg20 = float(tail["TV"].iloc[:-1].mean())
                    else:
                        tv_avg20 = float(tail["TV"].mean())

                    tv_ratio = (tv_today / tv_avg20) if (tv_avg20 and tv_avg20 > 0) else None
        except Exception as e:
            if debug:
                st.warning(f"売買代金温度の取得に失敗: {e}")

        # =========================
        # 統合ステータス（方向×熱量）
        # =========================
        direction = "リスクオン" if day_ch >= 0 else "リスクオフ"

        heat = "普通"
        if tv_ratio is not None:
            if tv_ratio >= 1.15:
                heat = "活況"
            elif tv_ratio <= 0.90:
                heat = "冷え"
            else:
                heat = "普通"

        if direction == "リスクオン":
            if heat == "活況":
                merged = "☀️ リスクオン（活況）"
            elif heat == "冷え":
                merged = "🌤 リスクオン（冷え）"
            else:
                merged = "⛅️ リスクオン（普通）"
        else:
            if heat == "活況":
                merged = "☔️ リスクオフ（活況）"
            elif heat == "冷え":
                merged = "☁️ リスクオフ（冷え）"
            else:
                merged = "🌧 リスクオフ（普通）"

        note = ""
        if direction == "リスクオフ" and heat == "活況":
            note = "（投げ / ヘッジ増の可能性）"
        elif direction == "リスクオン" and heat == "冷え":
            note = "（薄い上げ：継続性注意）"
        elif direction == "リスクオフ" and heat == "冷え":
            note = "（閑散の下げ：様子見多め）"

        st.info(f"統合ステータス: **{merged}** {note}")

        # =========================
        # 表示（上段：価格、下段：売買代金温度）
        # =========================
        c1, c2, c3 = st.columns(3)
        c1.metric("現在値", f"{curr:,.0f}円")
        c2.metric("寄付比", f"{op_ch:+.2f}%")
        c3.metric("前日比", f"{day_ch:+.2f}%")

        st.markdown("#### 💹 1570 売買代金温度（近似）")

        if tv_ratio is None or tv_today is None or tv_avg20 is None or tv_ch_pct is None:
            st.warning("売買代金温度を算出できませんでした（データ不足/取得失敗）。")
        else:
            t1, t2, t3 = st.columns(3)
            t1.metric("売買代金（今日）", _fmt_oku_yen(tv_today), f"{tv_ch_pct:+.1f}%（前日比）")
            t2.metric("平均比（直近20日）", f"{tv_ratio:.2f}x", f"平均 {_fmt_oku_yen(tv_avg20)}")
            t3.metric("読み方", f"{direction} × {heat}", "方向=前日比 / 熱量=平均比")

        st.divider()

    except Exception as e:
        if debug:
            st.warning(f"天気予報取得エラー: {e}")
        else:
            st.warning("天気予報の取得に失敗しました。")
