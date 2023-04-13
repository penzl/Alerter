from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands

#################################################
#        Put the required indicators below      #
#        Align with strategies.py!!!            #
#################################################

# Template:
# def {insert indicator name} (dta, timeframe):
#     dta["{insert sub-indicator 1 name}" + timeframe] = .....
#     dta["{insert sub-indicator 2 name}" + timeframe] = .....
#       .
#       .
#       .
#     return dta


def RSI(dta, timeframe):
    dta["RSI" + timeframe] = RSIIndicator(close=dta['Close'], window=14).rsi()
    return dta


def STOCH(dta, timeframe):
    stoch = StochasticOscillator(high=dta['High'],
                                 close=dta['Close'],
                                 low=dta['Low'],
                                 window=14,
                                 smooth_window=3)
    dta["StochK" + timeframe], dta["StochD" + timeframe] = stoch.stoch(), stoch.stoch_signal()
    return dta


def MA21(dta, timeframe):
    dta["MA21" + timeframe] = SMAIndicator(close=dta['Close'], window=21).sma_indicator()
    return dta


def BB(dta, timeframe):
    dta["BB_high" + timeframe] = BollingerBands(close=dta['Close'], window=21, window_dev=2).bollinger_hband()
    dta["BB_low" + timeframe] = BollingerBands(close=dta['Close'], window=21, window_dev=2).bollinger_lband()
    return dta


def EMA31(dta, timeframe):
    dta["EMA31" + timeframe] = EMAIndicator(close=dta['Close'], window=31).ema_indicator()
    return dta


def EMA59(dta, timeframe):
    dta["EMA59" + timeframe] = EMAIndicator(close=dta['Close'], window=59).ema_indicator()
    return dta
