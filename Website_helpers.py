from flask import Flask, render_template, request
import yfinance as yf
import numpy as np
import json
import pandas as pd
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands
import datetime
from scipy import stats
from scipy.signal import argrelextrema
from Website_constants import *

app = Flask(__name__)
app.config["DEBUG"] = True

with open(path_to_config, 'r') as f:
    config = json.load(f)
values = list(config.keys())


def make_pct_changes(values):
    pct_changes = []
    d_changes = []
    for cnt, value in enumerate(values):
        try:
            d_change = yf.Ticker(value).history(period='5d',
                                                interval='1d')[['Close']].pct_change().iat[-1, 0] * 100
            d_changes.append(d_change)
            d_change = str(round(d_change, 2)) + "%"
            dw = yf.Ticker(value).history(period='3wk', interval='1wk')[['Close']]
            dw = dw.drop(dw.index[[-2]])
            wk_change = str(round(dw.pct_change().iat[-1, 0] * 100, 2)) + "%"

        except:
            d_change, wk_change = "nan%", "nan%"
        pct_changes.append(
            value.replace("-USD", "").replace("-EUR", "").replace("1", "") + ": " + d_change + "(" + wk_change + ")")
    return {"pct_changes": pct_changes, "d_changes": d_changes}


def create_all_data(dropdown_value):
    df = yf.Ticker(dropdown_value).history(period='5y', interval='1d')[['Open', 'High', 'Low', 'Close', 'Volume']]
    df["RSI"] = RSIIndicator(close=df['Close'], window=14).rsi()
    with open(path_to_messages, encoding="utf8") as f:
        messages_usdt = f.read()
    # print(messages_usdt)

    # Generate weekly data
    dw = df.asfreq('W-SUN', method='pad')
    dw.index = dw.index.shift(-6, freq='D')
    price_today = df.iloc[[-1]]
    if df.iloc[[-1]].index[0].dayofweek != 6:
        price_today.index = price_today.index.shift(-price_today.index[0].dayofweek, freq='D')
        dw = pd.concat([dw, price_today], ignore_index=False, axis=0)
        # dw["EMA21"] = dw["Close"].rolling(window=10, min_periods=1).mean()

    # Generate daily Indicators
    df["RSI"] = RSIIndicator(close=df['Close'], window=14).rsi()
    df["RSI_low"] = RSIIndicator(close=df['Low'], window=14).rsi()
    df["RSI_high"] = RSIIndicator(close=df['High'], window=14).rsi()
    stoch = StochasticOscillator(high=df['High'],
                                 close=df['Close'],
                                 low=df['Low'],
                                 window=14,
                                 smooth_window=3)
    df["Stoch"], df["StochSig"] = stoch.stoch(), stoch.stoch_signal()
    df["BB_high"] = BollingerBands(close=df['Close'], window=21, window_dev=2).bollinger_hband()
    df["BB_low"] = BollingerBands(close=df['Close'], window=21, window_dev=2).bollinger_lband()
    df["dEMA31"] = EMAIndicator(close=df['Close'], window=31).ema_indicator()
    df["dEMA59"] = EMAIndicator(close=df['Close'], window=59).ema_indicator()
    # Generate weekly indicators
    dw["EMA21"] = EMAIndicator(close=dw['Close'], window=21).ema_indicator()
    dw["MA21"] = SMAIndicator(close=dw['Close'], window=21).sma_indicator()
    dw["MA50"] = SMAIndicator(close=dw['Close'], window=50).sma_indicator()
    dw["MA200"] = SMAIndicator(close=dw['Close'], window=200).sma_indicator()
    dw["RSI_w"] = RSIIndicator(close=dw['Close'], window=14).rsi()
    dw["BB_high_w"] = BollingerBands(close=dw['Close'], window=21, window_dev=2).bollinger_hband()
    dw["BB_low_w"] = BollingerBands(close=dw['Close'], window=21, window_dev=2).bollinger_lband()

    # Append weekly to daily with padding
    df_all = df.asfreq('d')
    df_all["RSI_w"] = dw["RSI_w"]
    df_all["RSI_w"] = df_all["RSI_w"].interpolate(method='linear')
    df_all["MA21"] = dw["MA21"]
    df_all["MA21"] = df_all["MA21"].interpolate(method='linear')
    df_all["EMA21"] = dw["EMA21"]
    df_all["EMA21"] = df_all["EMA21"].interpolate(method='linear')
    df_all["MA50"] = dw["MA50"]
    df_all["MA50"] = df_all["MA50"].interpolate(method='linear')
    df_all["MA200"] = dw["MA200"]
    df_all["MA200"] = df_all["MA200"].interpolate(method='linear')
    df_all["BB_high_w"] = dw["BB_high_w"]
    df_all["BB_high_w"] = df_all["BB_high_w"].interpolate(method='linear')
    df_all["BB_low_w"] = dw["BB_low_w"]
    df_all["BB_low_w"] = df_all["BB_low_w"].interpolate(method='linear')

    trend_list = config[dropdown_value][1:]
    trends = []
    for i, trend in enumerate(trend_list):
        if trend[1] == "Exp":
            x1, y1 = pd.Timestamp(trend[2]).value, np.log(trend[3])
            x2, y2 = pd.Timestamp(trend[4]).value, np.log(trend[5])
        else:
            x1, y1 = pd.Timestamp(trend[2]).value, trend[3]
            x2, y2 = pd.Timestamp(trend[4]).value, trend[5]
        m = (y2 - y1) / (x2 - x1)
        if trend[6] == "AllRange":
            res_x = pd.date_range(start=df.index[0], end=df.index[-1] + datetime.timedelta(days=10))
        else:
            res_x = pd.date_range(start=trend[6][0], end=df.index[-1] + datetime.timedelta(days=10))
        if trend[1] == "Exp":
            res = np.exp(m * (np.array(res_x.values.tolist()) - x1) + y1)
        else:
            res = m * (np.array(res_x.values.tolist()) - x1) + y1
        trends.extend([res_x.values.tolist(), res.tolist(), trend[0], trend[8]])

    occurances = np.where((df_all['RSI'].values <= 30) | (df_all['RSI_low'].values <= 30) |
                          (df_all['RSI_high'].values <= 30))
    df_Selloff = df_all["Close"][occurances[0]]
    occurances = np.where((df_all['RSI_w'].values >= 50) &
                          ((df_all['RSI'].values <= 50) | (df_all['RSI_low'].values <= 50) | (
                                  df_all['RSI_high'].values <= 50))
                          & (df_all['Stoch'].values - df_all['StochSig'].values > 0))
    df_BullDCA = df_all["Close"][occurances[0]]
    occurances = np.where((df_all['RSI_w'].values <= 50) &
                          ((df_all['RSI'].values <= 30) | (df_all['RSI_low'].values <= 30) | (
                                  df_all['RSI_high'].values <= 30))
                          & (df_all['Stoch'].values - df_all['StochSig'].values > 0))
    df_BearDCA = df_all["Close"][occurances[0]]
    occurances = np.where(
        (df_all['RSI'].values >= 75) | (df_all['RSI_low'].values >= 75) | (df_all['RSI_high'].values >= 75))
    df_Cashout = df_all["Close"][occurances[0]]
    occurances = np.where((df_all['RSI_w'].values >= 70) & (df_all['RSI'].values >= 65)
                          & (df_all['Stoch'].values - df_all['StochSig'].values > 0))
    df_SellDCA = df_all["Close"][occurances[0]]

    # Calculate volume profile
    try:
        kde_factor1, kde_factor2, order_vol, order_sh = config[dropdown_value][0][3]
    except:
        kde_factor1, kde_factor2, order_vol, order_sh = 0.03, 0.04, 6, 6
        print(order_sh)

    y_volProf, x_volProf = np.histogram(df.Close.values,
                                        bins=np.linspace(df.Close.values.min(), df.Close.values.max(),
                                                         num=100,
                                                         endpoint=True),
                                        weights=df.Volume)
    volume = df['Volume']
    close = df['Close']
    kde_factor1 = 0.03
    num_samples = 500
    kde_vol = stats.gaussian_kde(close, weights=volume, bw_method=kde_factor1)
    xr_vol = np.linspace(close.min(), close.max(), num_samples)
    kdy2_vol = kde_vol(xr_vol)
    kdy2_vol = kdy2_vol / kdy2_vol.max() * y_volProf.max()

    # Calculate Short levels profile

    # ilocs_min = argrelextrema(df.Low.values, np.less_equal, order=5)[0]
    ilocs_max = argrelextrema(df.High.values, np.greater_equal, order=5)[0]
    levels = np.array([])
    for i, j in enumerate(df.iloc[ilocs_max].High):
        levels = np.append(levels, (0.5 * j, 0.666666667 * j, 0.75 * j, 1 * j))
    levels = levels[np.logical_and(levels > df.Low.min(), levels >= 0.1 * df.Close[-1])]
    dataset = pd.DataFrame({'Column1': levels, 'Column2': np.ones(len(levels))})
    y_ShProf, x_ShProf = np.histogram(dataset.Column1,
                                      bins=np.linspace(dataset.Column1.min(), dataset.Column1.max(), num=100,
                                                       endpoint=True),
                                      weights=dataset.Column2)

    num_samples = 500
    kde_sh = stats.gaussian_kde(dataset.Column1, weights=dataset.Column2, bw_method=kde_factor2)
    xr1_sh = np.linspace(dataset.Column1.min(), dataset.Column1.max(), num_samples)
    kdy1_sh = kde_sh(xr1_sh)
    kdy1_sh = kdy1_sh / kdy1_sh.max() * y_volProf.max()

    # Resistance lines:
    locs1 = argrelextrema(kdy1_sh, np.greater_equal, order=order_sh)[0]
    locs2 = argrelextrema(kdy2_vol, np.less_equal, order=order_vol)[0]
    resist_out = []
    for l in locs1:
        for b in locs2:
            if np.abs(xr1_sh[l] - xr_vol[b]) < xr1_sh[l] * 0.03:
                resist_out.append((xr1_sh[l] + xr_vol[b]) / 2)

    # Strategies
    strategies = {
        "x_Selloff": df_Selloff.index.values.tolist(),
        "y_Selloff": df_Selloff.values.tolist(),
        "x_BullDCA": df_BullDCA.index.values.tolist(),
        "y_BullDCA": df_BullDCA.values.tolist(),
        "x_BearDCA": df_BearDCA.index.values.tolist(),
        "y_BearDCA": df_BearDCA.values.tolist(),
        "x_Cashout": df_Cashout.index.values.tolist(),
        "y_Cashout": df_Cashout.values.tolist(),
        "x_SellDCA": df_SellDCA.index.values.tolist(),
        "y_SellDCA": df_SellDCA.values.tolist(),
    }

    daily = {"name": dropdown_value,
             "x_daily": df.index.values.tolist(),
             "y_daily": df.to_numpy().tolist()}
    weekly = {"x": df_all.index.values.tolist(),
              "RSI_w": df_all["RSI_w"].to_numpy().tolist(),
              "BB_high_w": df_all["BB_high_w"].to_numpy().tolist(),
              "BB_low_w": df_all["BB_low_w"].to_numpy().tolist(),
              "MA21": df_all["MA21"].to_numpy().tolist(),
              "EMA21": df_all["EMA21"].to_numpy().tolist(),
              "MA50": df_all["MA50"].to_numpy().tolist(),
              "MA200": df_all["MA200"].to_numpy().tolist(),
              }
    vol_prof = {
        "xVolProf": x_volProf[:-1].tolist(),
        "yVolProf": y_volProf.tolist(),
        "xVolProfStat": xr_vol.tolist(),
        "yVolProfStat": kdy2_vol.tolist(),
        "xShProf": x_ShProf[:-1].tolist(),
        "yShProf": y_ShProf.tolist(),
        "xShProfStat": xr1_sh.tolist(),
        "yShProfStat": kdy1_sh.tolist(),
        "resistances": resist_out,
    }
    values_reduced = [values[i].replace("-USD", "").replace("-EUR", "").replace("1", "") for i in range(len(values))]
    return daily, weekly, trends, strategies, \
           {"tickers": values, "tickersShort": values_reduced}, {"alerts": messages_usdt}, vol_prof
