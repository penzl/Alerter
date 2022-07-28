# IMPORTS
import pandas as pd
from datetime import datetime
import dataframe_image as dfi
import telepot
from telepot.loop import MessageLoop
import copy
import emoji
import pickle
import json
import numpy as np
import yfinance as yf
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands
import requests
from urllib.parse import urljoin
from os.path import exists


def get_data_yahoo(symbol, kline_size):
    if kline_size == '1d':
        dta = yf.Ticker(symbol).history(period='1y',
                                        interval='1d', actions=False)[['Open', 'High', 'Low', 'Close', 'Volume']]
    if kline_size == '1W':
        dt_day = yf.Ticker(symbol).history(period='1y',
                                           interval='1d', actions=False)[['Open', 'High', 'Low', 'Close', 'Volume']]
        dta = dt_day.asfreq('W-SUN', method='pad')
        dta.index = dta.index.shift(-6, freq='D')
        price_today = dt_day.iloc[[-1]]
        price_today.index = price_today.index.shift(-price_today.index[0].dayofweek, freq='D')
        dta = pd.concat([dta, price_today], ignore_index=False, axis=0)

    dta["RSI"] = RSIIndicator(close=dta['Close'], window=14).rsi()
    stoch = StochasticOscillator(high=dta['High'],
                                 close=dta['Close'],
                                 low=dta['Low'],
                                 window=14,
                                 smooth_window=3)
    dta["StochK"], dta["StochD"] = stoch.stoch(), stoch.stoch_signal()
    dta["MA21"] = SMAIndicator(close=dta['Close'], window=21).sma_indicator()
    dta["BB_high"] = BollingerBands(close=dta['Close'], window=21, window_dev=2).bollinger_hband()
    dta["BB_low"] = BollingerBands(close=dta['Close'], window=21, window_dev=2).bollinger_lband()
    dta["EMA31"] = EMAIndicator(close=dta['Close'], window=31).ema_indicator()
    dta["EMA59"] = EMAIndicator(close=dta['Close'], window=59).ema_indicator()
    return dta


def apply_style(column):
    # return [col_data['positive_cell'] if True else col_data['negative_cell']
    # for val in column]
    if "rsi" in column.name:
        return ["color:green" if float(val) < 40 else "color:black" for val in column]
    if "hist_ch" in column.name:
        return ["color:green" if float(val.strip('%')) > 0 else "color:black" for val in column]
    else:
        return ["color:black" for val in column]


def convert_seconds(seconds):
    seconds_in_day = 60 * 60 * 24
    seconds_in_hour = 60 * 60
    seconds_in_minute = 60
    days = seconds // seconds_in_day
    hours = (seconds - (days * seconds_in_day)) // seconds_in_hour
    minutes = (seconds - (days * seconds_in_day) - (hours * seconds_in_hour)) // seconds_in_minute
    if seconds < seconds_in_hour:
        return "%dmin" % (minutes)
    if seconds < seconds_in_day:
        return "%dh, %dmin" % (hours, minutes)
    else:
        return "%dd, %dh, %dmin" % (days, hours, minutes)


def message_reader(alrts, Long=False):
    str0 = ""
    alrts = [alrt for alrt in alrts if alrt[2] != 'EMA_trend_negative' and alrt[2] != 'EMA_trend_positive']
    lngth = len(alrts)
    for count, value in enumerate(alrts):
        age = ", Age: " + convert_seconds((datetime.now() - value[4]).total_seconds())
        next_tckr = alrts[count + 1][0] if count < lngth - 1 else ""
        if value[2] == "pct_changes":
            if next_tckr == value[0] or Long:
                str0 = str0 + "\n\n" + emoji.emojize(':small_blue_diamond:', use_aliases=True) \
                       + value[0].replace("-USD", "").replace("1", "") + ":   " + value[3]
        else:
            str0 = str0 + "\n\t" + emoji.emojize(':white_small_square:', use_aliases=True) \
                   + value[3] + age
        # prev_val = copy.deepcopy(value)
    return str0


def message_reader_combine_alerts(messages2):
    str0 = "Combined alerts:"
    alert_kinds = ["rsi < 30", "rsi > 70", "1w_rsi > 50 & 1d_rsi < 50 & 1d_hist_ch>0",
                   "1w_rsi < 50 & 1d_rsi < 30 & 1d_hist_ch>0", "close_to_", "crossed_",
                   "in_accum_zone", "in_reduc_zone", "close_2_21MA", "out_of_BB",
                   "EMA_trend_grey","EMA_trend_positive","EMA_trend_negative"]
    alert_text = ["Sellof (RSI<30)", "Cash-out (RSI>70)", "BullDCA", "BearDCA", "Close to trend",
                  "Crossed trend", "In Accum. Zone", "In Reduc. Zone", "Close to 21W SMA (<2%)",
                  "Out of Bollinger Bands", "EMA trend is changing","Bullish trend","Bearish trend"]
    for count, alert_kind in enumerate(alert_kinds):
        str_new = "\n\n" + emoji.emojize(':small_blue_diamond:', use_aliases=True) + alert_text[count] + ": "
        check_if_empty = False
        for _, value in enumerate(messages2):
            if alert_kind in value[2]:
                str_new = str_new + "\n\t" + emoji.emojize(':white_small_square:', use_aliases=True) \
                          + value[0].replace("-USD", "").replace("1",
                                                                 "")  # + ": " + value[3].replace(value[0] + ",", '') + age
                check_if_empty = True
        if check_if_empty:
            str0 = str0 + str_new
    return str0


class AlertList:
    def __init__(self, ticker_list, timeframes):
        self.ticker_list = ticker_list
        self.timeframes = timeframes

    def show_me_the_money_joined(self, verbosity=False):
        f_form = "{:.8g}".format
        f_form_sh = "{:.3g}".format
        perc_form = "{:.1%}".format
        # make daily and weekly data [only works for day and week]

        for kline_size in self.timeframes:
            columns = ['Symb', 'close', kline_size + '_ch',
                       kline_size + '_rsi', kline_size + '_Stoch.K', kline_size + '_Stoch.D', kline_size + '_MA21',
                       kline_size + '_BBl', kline_size + '_BBh', kline_size + '_EMA31', kline_size + '_EMA59']
            dataframe = pd.DataFrame(
                columns=columns)
            if verbosity:
                print("TIMEFRAME: " + kline_size)
            index = self.timeframes.index(kline_size)
            # for [symbol,screener,exchange] in symbol_list: for tradingview
            for symbol in self.ticker_list:
                if verbosity:
                    print(symbol)
                # new_df = create_data(symbol, kline_size, save=True, verbosity=False)
                # data = get_data_trading_view(symbol, screener, exchange, kline_size, verbosity=True)
                # dataframe_new = pd.DataFrame(
                #     [[symbol,
                #       f_form(data['close']),
                #       perc_form(data['change']/100),
                #       f_form_sh(data['RSI']),
                #       f_form_sh(data['Stoch.D']),
                #       f_form_sh(data['Stoch.K']-data['Stoch.D'])]],
                #     columns=columns)
                try:
                    data = get_data_yahoo(symbol, kline_size)
                    dataframe_new = pd.DataFrame(
                        [[symbol,
                          f_form(data['Close'][-1]),
                          perc_form((data['Close'][-1] - data['Close'][-2]) / data['Close'][-2]),
                          f_form_sh(data['RSI'][-1]),
                          f_form_sh(data['StochK'][-1]),
                          f_form_sh(data['StochD'][-1]),
                          f_form_sh(data['MA21'][-1]),
                          f_form_sh(data["BB_low"][-1]),
                          f_form_sh(data["BB_high"][-1]),
                          f_form_sh(data["EMA31"][-1]),
                          f_form_sh(data["EMA59"][-1])
                          ]],
                        columns=columns)
                except Exception as e:
                    print("Error1: Couldn't get data for " + symbol)
                    print(e)
                    dataframe_new = pd.DataFrame(
                        [[symbol,
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          f_form(np.nan),
                          ]],
                        columns=columns)
                dataframe = pd.concat([dataframe, dataframe_new], ignore_index=True)

            if index == 0:
                dataframe_full = dataframe
            else:
                for i in columns[1:]:
                    dataframe_full[i] = dataframe[i]

        pd.set_option('display.max_columns', None)
        if verbosity:
            print(dataframe_full)
        return dataframe_full


class BotStarter:
    def __init__(self, TELEPOT_BOT, CHAT_ID,
                 use_local_config_or_pythonanywhere, PA_USERNAME, PA_API_TOKEN, LABEL):
        # self.binance_client = None
        self.bot = telepot.Bot(TELEPOT_BOT)
        # self.bot_btc = telepot.Bot(TELEPOT_BOT_TEST)
        self.chat_id = CHAT_ID
        # self.chat_id_btc = CHAT_ID_TEST
        self.use_local_config_or_pythonanywhere = use_local_config_or_pythonanywhere
        self.PA_USERNAME = PA_USERNAME
        self.PA_API_TOKEN = PA_API_TOKEN
        self.LABEL = LABEL

    def loop_this(self):
        if self.use_local_config_or_pythonanywhere:
            with open('config.json', 'r') as f:
                config = json.load(f)
                # list_USDT = [config[key][0] for key in config.keys()] with tradingview
        else:
            config = self.get_config_from_pythonanywhere()
        ticker_list = list(config.keys())
        timeframes = ['1W', '1d']

        #### Read Data ####
        if exists("messages_" + self.LABEL + ".pickle"):
            with open("messages_" + self.LABEL + ".pickle", 'rb') as handle2:
                alerts = pickle.load(handle2)
                print("Read messages")
        else:
            print("... making fresh messages list...")
            alerts = []

        #### Start Loop ####

        print("##### Looking for alerts... #####")
        if 1:
            ''' Open pairlists here, so i can update them via Telegram ... '''
            print("Ticker List:")
            print(ticker_list)

            full_data = AlertList(ticker_list, timeframes).show_me_the_money_joined()

            with open("dataframe_" + self.LABEL + ".pickle", 'wb') as handle2:
                pickle.dump(full_data, handle2)
                print("saved messages")

            print("Sending data to telegram!")
            # bot.sendMessage(chat_id, "-----  Checking for Buy signals! -----", disable_notification=True)

            alerts = self.check_strategy(ticker_list, full_data, timeframes, alerts)

            with open("messages_" + self.LABEL + ".pickle", 'wb') as handle2:
                pickle.dump(alerts, handle2)
                print("saved messages")
            self.put_messages_to_pythonanywhere(alerts)
            # except:
            #    print("Error, trying again in 15 min")
            # cont = False

        # except:
        #    print("Error occured... retrying")
        return None

    def get_config_from_pythonanywhere(self):
        username = self.PA_USERNAME
        api_token = self.PA_API_TOKEN
        pythonanywhere_host = "www.pythonanywhere.com"
        api_base = "https://{pythonanywhere_host}/api/v0/user/{username}/".format(
            pythonanywhere_host=pythonanywhere_host,
            username=username,
        )
        resp = requests.get(
            urljoin(api_base, "files/path/home/penzl/mysite/config.json".format(username=username)),
            headers={"Authorization": "Token {api_token}".format(api_token=api_token)}
        )
        return json.loads(resp.content.decode('utf-8'))

    def put_messages_to_pythonanywhere(self, alrt):
        username = self.PA_USERNAME
        api_token = self.PA_API_TOKEN
        pythonanywhere_host = "www.pythonanywhere.com"
        api_base = "https://{pythonanywhere_host}/api/v0/user/{username}/".format(
            pythonanywhere_host=pythonanywhere_host,
            username=username,
        )
        resp = requests.post(
            urljoin(api_base, "files/path/home/penzl/mysite/messages.txt".format(username=username)),
            files={"content": message_reader(alrt) + "\n\n" + message_reader_combine_alerts(alrt)},
            headers={"Authorization": "Token {api_token}".format(api_token=api_token)}
        )
        if resp.status_code == 200 or resp.status_code == 201:
            print("Messages posted on Pythonanywhere server...")
        else:
            print("ERROR: Messages NOT posted on Pythonanywhere server...")
        return None

    def start_telegram_bot(self):
        def handle_bot(msg):
            content_type, chat_type, chat_id = telepot.glance(msg)
            print(content_type, chat_type)
            if content_type == 'text':
                # bot.sendMessage(chat_id, msg['text'])
                if msg['text'] == "/sendpics":
                    self.bot.sendMessage(chat_id, "here it is:")
                    with open("dataframe_" + self.LABEL + ".pickle", 'rb') as handle2:
                        dfi.export(pickle.load(handle2).style.apply(apply_style)
                                   , "mytablelist_" + self.LABEL + ".png")
                    self.bot.sendPhoto(chat_id, photo=open('mytablelist_' + self.LABEL + '.png', 'rb'))
                if msg['text'] == "/alive":
                    self.bot.sendMessage(chat_id, "... and kicking!")
                if msg['text'] == "/alerts":
                    self.bot.sendMessage(chat_id, "http://penzl.pythonanywhere.com/\nActive alerts:")
                    with open("messages_" + self.LABEL + ".pickle", 'rb') as handle:
                        alerts_bot = pickle.load(handle)
                    if len(alerts_bot) == 0:
                        self.bot.sendMessage(chat_id, "No *" + self.LABEL + " alerts, bro!")
                    else:
                        self.bot.sendMessage(chat_id, message_reader(alerts_bot))
                        self.bot.sendMessage(chat_id, message_reader_combine_alerts(alerts_bot))
                if msg['text'] == "/longalerts":
                    self.bot.sendMessage(chat_id, "http://penzl.pythonanywhere.com/\nActive alerts:")
                    with open("messages_" + self.LABEL + ".pickle", 'rb') as handle:
                        alerts_bot = pickle.load(handle)
                    if len(alerts_bot) == 0:
                        self.bot.sendMessage(chat_id, "No *" + self.LABEL + " alerts, bro!")
                    else:
                        self.bot.sendMessage(chat_id, message_reader(alerts_bot, Long=True))
                        self.bot.sendMessage(chat_id, message_reader_combine_alerts(alerts_bot))
                if msg['text'] == "/showpairs":
                    if self.use_local_config_or_pythonanywhere:
                        with open('config.json', 'r') as f:
                            config = json.load(f)
                            # list_USDT = [config[key][0] for key in config.keys()] with tradingview
                    else:
                        config = self.get_config_from_pythonanywhere()
                    self.bot.sendMessage(chat_id, "Current " + self.LABEL + " pairlist: " + str(list(config.keys())))

                if msg['text'] == "/help":
                    str0 = "Strategies: \n" \
                           "\n Selloff: \n\t - RSI < 30" \
                           "\n\t - Checked separately for each timeframe (1w, 1d)" \
                           "\n BullDCA: \n\t - 1w_RSI > 50 & 1d_RSI < 50 & 1d Stoch Diff >0" \
                           "\n BearDCA: \n\t - 1w_RSI < 50 & 1d_RSI < 30 & 1d Stoch Diff>0 " \
                           "\n Cash-out SELL alert: \n\t - RSI > 75" \
                           "\n\t - Checked separately for each timeframe (1w, 1d)" \
                           "\n SELL DCA: \n\t - 1w_RSI > 70 & 1d_RSI > 65" \
                           "\n\n Commands: \n\t /sendpics - Send all Pair Data in picture format " \
                           "\n\t /alive - Check if bot is alive \n\t /alerts -Show all current active alerts" \
                           "\n\t /longalerts -Show all current active alerts - long version" \
                           "\n\t /showpairs - shows current pairlist" \
                           "\n\t /removemessages - remove old messages, start from scratch" \
                           "\n\t /help - This message"
                    self.bot.sendMessage(chat_id, str0)
                if msg['text'] == "/removemessages":
                    self.bot.sendMessage(chat_id, "Removing all old messages (" + self.LABEL + ")!")
                    with open("messages_" + self.LABEL + ".pickle", 'wb') as handle2:
                        pickle.dump([], handle2)
                        print("saved empty messages")

        MessageLoop(self.bot, handle_bot).run_as_thread()
        print('Bot is listening for /sendpics and /alive and /alerts...')

    def alert_creator(self, condition, value, kline_size, strategy_label, str_label, previous_messages,
                      messages, alert=True):

        msg = [value, kline_size, strategy_label, str_label,
               datetime.now()
               ]
        if condition:
            if msg[:3] not in [part[:3] for part in previous_messages]:
                if alert:
                    self.bot.sendMessage(self.chat_id,
                                         emoji.emojize(':heavy_exclamation_mark:', use_aliases=True) +
                                         value.replace("-USD", "").replace("1", "") + ": " + str_label,
                                         disable_notification=False)
                    print("NEW Message: " + str(msg))
            else:
                indx = [part[:3] for part in previous_messages].index(msg[:3])
                msg[4] = previous_messages[indx][4]
                print("Still Active Message: " + str(msg))

            messages.append(msg)

        elif msg[:3] in [part[:3] for part in previous_messages]:
            indx = [part[:3] for part in previous_messages].index(msg[:3])
            timestamp = previous_messages[indx][4]
            if (datetime.now() - timestamp).total_seconds() / 60 < 60 * 8:
                print("Appending old message: " + str(previous_messages[indx]))
                messages.append([value, kline_size, strategy_label, str_label + " (Not Active)", timestamp])
        return messages

    def check_strategy(self, symbol_list, dataframe, timeframes, previous_messages):
        messages = []
        f_form_sh = "{:.5g}".format
        if self.use_local_config_or_pythonanywhere:
            with open('config.json', 'r') as f:
                config = json.load(f)
                # list_USDT = [config[key][0] for key in config.keys()] with tradingview
        else:
            config = self.get_config_from_pythonanywhere()
        config_list = list(config)

        # for count, [value,_,_] in enumerate(symbol_list): for trading view
        # symbol_sh = [symbol_list[i].replace("-USD", "").replace("-EUR", "").replace("1", "") for i in range(len(values))]
        for count, value in enumerate(symbol_list):
            if 1:
                d_change, w_change, price = dataframe["1d_ch"][count], dataframe["1W_ch"][count], f_form_sh(
                    float(dataframe["close"][count]))
                if float(d_change.strip("%")) > 0:
                    d_change = d_change + emoji.emojize(':evergreen_tree:', use_aliases=True)
                else:
                    d_change = d_change + emoji.emojize(':red_triangle_pointed_down:', use_aliases=True)
                if float(w_change.strip("%")) > 0:
                    w_change = w_change + emoji.emojize(':evergreen_tree:', use_aliases=True)
                else:
                    w_change = w_change + emoji.emojize(':red_triangle_pointed_down:', use_aliases=True)
                trend_str = ", trend bearish" if (float(dataframe["1d_EMA31"][count]) -
                                                      float(dataframe["1d_EMA59"][count])) < 0 else ", trend bullish"
                str_label = price + ", " + d_change + " (week: " + w_change + ")" + trend_str
                messages = self.alert_creator(True, value, "None",
                                              "pct_changes", str_label, previous_messages, messages,
                                              alert=False)
                for kline_size in timeframes:
                    '''
                    Strategy 1
                    '''
                    # str_label = "BullBuy: " + value + ", " + kline_size + ", Price: " + dataframe["close"][count] \
                    #             + ", HCH: " + dataframe[kline_size + "_hist_ch"][count] \
                    #             + ", RSI = " + dataframe[kline_size + "_rsi"][count]
                    # strategy_label = "hist_ch>0 & rsi < 40"
                    #
                    # condition = float(dataframe[kline_size + "_hist_ch"][count].strip("%")) >= 0 and float(
                    #     dataframe[kline_size + "_rsi"][count]) <= 40
                    #
                    # messages = alert_creator(bot, chat_id, condition, value, kline_size,
                    #                          strategy_label, str_label, previous_messages, messages)

                    '''
                    Strategy 2
                    '''
                    str_label = "Selloff," + kline_size + " Price: " \
                                + dataframe["close"][count] + ", RSI = " + dataframe[kline_size + "_rsi"][count]
                    strategy_label = "rsi < 30"

                    condition = float(dataframe[kline_size + "_rsi"][count]) <= 30
                    messages = self.alert_creator(condition, value, kline_size,
                                                  strategy_label, str_label, previous_messages, messages)

                    '''
                    Sell Strategy 1
                    '''
                    str_label = "Cash-out SELL alert " + emoji.emojize(':money_bag:', use_aliases=True) + "," + \
                                kline_size + " Price: " \
                                + dataframe["close"][count] + ", RSI = " + dataframe[kline_size + "_rsi"][count]
                    strategy_label = "rsi > 70"

                    condition = float(dataframe[kline_size + "_rsi"][count]) >= 75

                    messages = self.alert_creator(condition, value, kline_size,
                                                  strategy_label, str_label, previous_messages, messages)

                '''
                Strategy 3 -- not checked for all kline_size
                If weekly RSI > 50:
                        if daily RSI <50 and histogram change positive:
                            BUY ALERT
                '''
                str_label = "BullDCA," + " Price: " + dataframe["close"][count] \
                            + ", 1w_RSI = " + dataframe["1W_rsi"][count] \
                            + ", 1d_RSI = " + dataframe["1d_rsi"][count] \
                            + ", 1d_Stoch.K: " + dataframe["1d_Stoch.K"][count] \
                            + ", 1d_Stoch.D: " + dataframe["1d_Stoch.D"][count]

                strategy_label = "1w_rsi > 50 & 1d_rsi < 50 & 1d_hist_ch>0"
                condition = float(dataframe["1W_rsi"][count]) >= 50 \
                            and float(dataframe["1d_rsi"][count]) <= 50 \
                            and float(dataframe["1d_Stoch.K"][count]) - float(dataframe["1d_Stoch.D"][count]) >= 0

                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, str_label, previous_messages, messages)

                '''
                Strategy 4 -- not checked for all kline_size
                If weekly RSI < 50:
                        if daily RSI <30 and histogram change positive:
                            BUY ALERT
                '''
                str_label = "BearDCA," + " Price: " + dataframe["close"][count] \
                            + ", 1w_RSI = " + dataframe["1W_rsi"][count] \
                            + ", 1d_RSI = " + dataframe["1d_rsi"][count] \
                            + ", 1d_Stoch.K: " + dataframe["1d_Stoch.K"][count] \
                            + ", 1d_Stoch.D: " + dataframe["1d_Stoch.D"][count]

                strategy_label = "1w_rsi < 50 & 1d_rsi < 30 & 1d_hist_ch>0"

                condition = float(dataframe["1W_rsi"][count]) <= 50 \
                            and float(dataframe["1d_rsi"][count]) <= 30 \
                            and float(dataframe["1d_Stoch.K"][count]) - \
                            float(dataframe["1d_Stoch.D"][count]) >= 0

                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, str_label, previous_messages, messages)
                '''
                Sell Strategy 2 -- not checked for all kline_size
                If weekly RSI > 70:
                        if daily RSI <30:
                            SELL ALERT
                '''
                # str_label = "SELL DCA " + emoji.emojize(':money_bag:', use_aliases=True) + ":"\
                #             + value + ", Price: " + dataframe["close"][count] \
                #             + ", 1w_RSI = " + dataframe["1W_rsi"][count] \
                #             + ", 1d_RSI = " + dataframe["1d_rsi"][count] \
                #             + ", 1d_Stoch.K: " + dataframe["1d_Stoch.K"][count] \
                #             + ", 1d_Stoch.D: " + dataframe["1d_Stoch_D"][count]
                # strategy_label = "1w_rsi < 50 & 1d_rsi < 30 & 1d_hist_ch>0"
                #
                # condition = float(dataframe["1W_rsi"][count]) >= 70 \
                #             and float(dataframe["1d_rsi"][count]) >= 65
                #
                # messages = alert_creator(bot, chat_id, condition, value, "1d",
                #                          strategy_label, str_label, previous_messages, messages,
                #                                          dataframe["1d_ch"][count],dataframe["1W_ch"][count])

                '''
                Check Trendlines [2% close]
                '''
                trend_list = config[config_list[count]][1:]
                for trend in trend_list:
                    if trend[1] == "Exp":
                        x1, y1 = pd.Timestamp(trend[2]).value, np.log(trend[3])
                        x2, y2 = pd.Timestamp(trend[4]).value, np.log(trend[5])
                    else:
                        x1, y1 = pd.Timestamp(trend[2]).value, trend[3]
                        x2, y2 = pd.Timestamp(trend[4]).value, trend[5]
                    m = (y2 - y1) / (x2 - x1)
                    if trend[1] == "Exp":
                        res = np.exp(m * (pd.Timestamp.now().value - x1) + y1)
                    else:
                        res = m * (pd.Timestamp.now().value - x1) + y1

                    str_label = "Closing to (<2%) " + trend[0] + emoji.emojize(':chart_with_upwards_trend:',
                                                                               use_aliases=True) + "," \
                                + " Price: " + f_form_sh(float(dataframe["close"][count])) + \
                                ", Trend Price: " + "{:.3g}".format(res)
                    strategy_label = "close_to_" + trend[0]
                    condition = np.abs(
                        (float(dataframe["close"][count]) - res) / float(dataframe["close"][count])) <= 0.02
                    messages = self.alert_creator(condition, value, "1d",
                                                  strategy_label, str_label, previous_messages, messages)
                '''
                Check Trendlines [Crossing]
                '''
                trend_list = config[config_list[count]][1:]
                for trend in trend_list:
                    if trend[1] == "Exp":
                        x1, y1 = pd.Timestamp(trend[2]).value, np.log(trend[3])
                        x2, y2 = pd.Timestamp(trend[4]).value, np.log(trend[5])
                    else:
                        x1, y1 = pd.Timestamp(trend[2]).value, trend[3]
                        x2, y2 = pd.Timestamp(trend[4]).value, trend[5]
                    m = (y2 - y1) / (x2 - x1)
                    if trend[1] == "Exp":
                        res = np.exp(m * (pd.Timestamp.now().value - x1) + y1)
                    else:
                        res = m * (pd.Timestamp.now().value - x1) + y1

                    str_label = "Crossed -> " + trend[0] + emoji.emojize(':chart_with_upwards_trend:',
                                                                         use_aliases=True) + "," \
                                + " Price: " + f_form_sh(float(dataframe["close"][count])) + \
                                ", Trend Price: " + "{:.3g}".format(res)
                    strategy_label = "crossed_" + trend[0]
                    if trend[7] == "Alert_Below":
                        condition = float(dataframe["close"][count]) <= res
                    if trend[7] == "Alert_Above":
                        condition = float(dataframe["close"][count]) >= res
                    messages = self.alert_creator(condition, value, "1d",
                                                  strategy_label, str_label, previous_messages, messages)
                '''
                Check MA21 Envelope [Crossing]
                '''
                str_label = "In Accum. Zone," + " Price: " + f_form_sh(float(dataframe["close"][count])) + \
                            " is between " + f_form_sh(float(dataframe["1W_MA21"][count]) / 2) + " and " + \
                            f_form_sh(float(dataframe["1W_MA21"][count]) / 1.5) + " (or below)"
                strategy_label = "in_accum_zone"

                condition = float(dataframe["1W_MA21"][count]) / 1.5 >= float(dataframe["close"][count])

                messages = self.alert_creator(condition, value, "1W",
                                              strategy_label, str_label, previous_messages, messages)
                '''
                Check MA21 Envelope [Crossing]
                '''
                str_label = "In Reduc. Zone," + " Price: " + f_form_sh(float(dataframe["close"][count])) + \
                            " is between " + f_form_sh(float(dataframe["1W_MA21"][count]) * 1.5) + " and " + \
                            f_form_sh(float(dataframe["1W_MA21"][count]) * 2) + " (or above)"
                strategy_label = "in_reduc_zone"

                condition = float(dataframe["1W_MA21"][count]) * 1.5 <= float(dataframe["close"][count])

                messages = self.alert_creator(condition, value, "1W",
                                              strategy_label, str_label, previous_messages, messages)
                '''
                Check MA21 Envelope [2% Close]
                '''
                # str_label = "Close to 21W SMA (<2%): " + value + ", Price: " + f_form_sh(float(dataframe["close"][count])) + \
                #             ", 21W SMA: " + f_form_sh(float(dataframe["1W_MA21"][count])/2)
                # strategy_label = "close_2_21MA"
                #
                # condition = np.abs((float(dataframe["close"][count]) - float(dataframe["1W_MA21"][count])) / float(dataframe["close"][count])) <= 0.02
                #
                # messages = alert_creator(bot, chat_id, condition, value, "1W",
                #                          strategy_label, str_label, previous_messages, messages)
                '''
                BollingerBands
                '''
                str_label = "Out Of Bollinger Bands, " + " Price: " \
                            + dataframe["close"][count] + ", BB_l = " + dataframe["1d_BBl"][count] + \
                            ", BB_h = " + dataframe["1d_BBh"][count]
                strategy_label = "out_of_BB"

                condition = float(dataframe["1d_BBl"][count]) >= float(dataframe["close"][count]) or \
                            float(dataframe["1d_BBh"][count]) <= float(dataframe["close"][count])
                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, str_label, previous_messages, messages, alert=False)
                '''
                EMA trend switch
                '''
                str_label = "EMA trend in grey zone: " + value + ", " + ", Price: " \
                            + dataframe["close"][count] + ", EMA31 = " + dataframe["1d_EMA31"][count] + \
                            ", EMA59 = " + dataframe["1d_EMA59"][count]
                strategy_label = "EMA_trend_grey"
                condition = 2 * np.abs(
                    (float(dataframe["1d_EMA31"][count]) - float(dataframe["1d_EMA59"][count]))
                    / (float(dataframe["1d_EMA31"][count]) + float(dataframe["1d_EMA59"][count]))) < 0.01
                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, str_label, previous_messages, messages)

                '''
                EMA trend positive
                '''
                strategy_label = "EMA_trend_positive"
                condition = ", trend bullish" == trend_str
                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, trend_str, previous_messages, messages)
                '''
                EMA trend negative
                '''
                strategy_label = "EMA_trend_negative"
                condition = ", trend bearish" == trend_str
                messages = self.alert_creator(condition, value, "1d",
                                              strategy_label, trend_str, previous_messages, messages)

            # except:
            #    print("Couldnt check strategy for " + value)
        # print(messages)
        return messages
