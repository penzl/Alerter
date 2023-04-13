# IMPORTS
import copy

import pandas as pd
import sys
from datetime import datetime
import dataframe_image as dfi
import telepot
# import urllib3
from telepot.loop import MessageLoop
# import copy
import emoji
import pickle
#import json
import numpy as np
import yfinance as yf
# from ta.momentum import RSIIndicator, StochasticOscillator
# from ta.trend import SMAIndicator, EMAIndicator
# from ta.volatility import BollingerBands
# import requests
# from urllib.parse import urljoin
from os.path import exists
from ruamel import yaml
import strategies
import indicators
import logging

# uncomment this if its on pythonanywhere
# proxy_url = "http://proxy.server:3128"
# telepot.api._pools = {
#     'default': urllib3.ProxyManager(proxy_url=proxy_url, num_pools=3, maxsize=10, retries=False, timeout=30),
# }
# telepot.api._onetime_pool_spec = (urllib3.ProxyManager, dict(proxy_url=proxy_url, num_pools=1, maxsize=1, retries=False, timeout=30))


def get_data_yahoo(symbol, ta_list=[], ta_list_global=[], last_only=True):
    logging.info("\t\t\t* Getting yahoo data for %s" % symbol)
    dta_day = yf.Ticker(symbol).history(period='2y',
                                        interval='1d', actions=False)[['Open', 'High', 'Low', 'Close', 'Volume']]
    logging.debug("\t\t\t #  Calculating daily change in percentage...")
    dta_day = CHANGE1d(dta_day, "_day")
    dta_day = CHANGE7d(dta_day, "_day")

    list_of_indicators = []
    logging.debug("\t\t\t #  Putting together list of indicators")
    for TA in ta_list_global + list(set(ta_list) - set(ta_list_global)):  # Removing Duplicates in list!
        try:
            list_of_indicators = list_of_indicators + getattr(strategies, TA)(check=True)
        except Exception as e:
            logging.error("Strategy %s probably not defined in strategies.py, "
                          "error %s" % (TA, e))
    list_of_indicators = np.unique(list_of_indicators)
    logging.info("\t\t\t  %s: Calculating indicators: %s" % (symbol, list_of_indicators))
    dta_week = pd.DataFrame()
    if any(ele.endswith('_week') for ele in list_of_indicators):
        dta_week = yf.Ticker(symbol).history(period='1y',
                                             interval='1wk', actions=False)[['Open', 'High', 'Low', 'Close', 'Volume']]
    for indicator in list_of_indicators:
        try:
            if indicator.endswith('_week'):
                dta_week = getattr(indicators, indicator.replace('_week', ''))(dta_week, '_week')
                dta_day[str(indicator)] = dta_week[indicator]  # for some reason it makes it a numpy string...
            elif indicator.endswith('_day'):
                dta_day = getattr(indicators, indicator.replace('_day', ''))(dta_day, '_day')
            else:
                logging.error("Indicator %s has to timeframe selected. MUST end with _day or _week ")
        except Exception as e:
            logging.error("Indicator %s not defined in indicators.py, "
                          "error: %s" % (indicator, e))
    if last_only:
        return dta_day.iloc[-1].round(5).to_dict()
    else:
        return dta_day


def apply_style(column):
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
    alerts_length = len(alrts)
    new_ticker = True
    for count, value in enumerate(alrts):
        age = ", Age: " + convert_seconds((datetime.now() - value["time"]).total_seconds())
        if new_ticker or Long:
            str0 = str0 + "\n\n" + emoji.emojize(':small_blue_diamond:', use_aliases=True) \
                   + value["ticker"].replace("-USD", "").replace("1", "") + ":   " + value["string"]
        else:
            str0 = str0 + "\n\t   " + emoji.emojize(':white_small_square:', use_aliases=True) \
                   + value["string"] + age
        if value["ticker"] == alrts[count + 1]["ticker"] if count < alerts_length - 1 else "":
            new_ticker = False
        else:
            new_ticker = True
    return str0


def message_reader_combine_alerts(messages2):
    str0 = "Combined alerts:"
    alert_kinds = list(np.unique([iii["label"] for iii in messages2]))
    if 'show_change' in alert_kinds: alert_kinds.remove('show_change')
    for count, alert_kind in enumerate(alert_kinds):
        str_new = "\n\n" + emoji.emojize(':small_blue_diamond:', use_aliases=True) + alert_kind + ": "
        check_if_empty = False
        for _, value in enumerate(messages2):
            if alert_kind in value["label"]:
                str_new = str_new + "\n\t" + emoji.emojize(':white_small_square:', use_aliases=True) \
                          + value["ticker"].replace("-USD", "").replace("1",
                                                                 "")
                check_if_empty = True
        if check_if_empty:
            str0 = str0 + str_new
    return str0


class AlertList:
    def __init__(self, config):
        self.ticker_list = config["TICKERS"].keys()
        self.config = config

    def show_me_the_money_joined(self):
        ticker_dict = {}
        for symbol in self.ticker_list:
            try:
                ticker_dict[symbol] = get_data_yahoo(symbol, ta_list=self.config["TICKERS"][symbol]["ta_list"],
                                                     ta_list_global=self.config["SETTINGS"]["ta_list_global"])
            except Exception as e:
                logging.error("\t\t\t* Couldn't get data for %s, error: %s" % (symbol, e))
        # pd.set_option('display.max_columns', None)
        # logging.debug(pd.DataFrame.from_dict(ticker_dict, orient='index'))
        return ticker_dict


class BotStarter:
    def __init__(self, TELEPOT_BOT, CHAT_ID, LABEL, LOC_STRING):
        self.bot = telepot.Bot(TELEPOT_BOT)
        self.chat_id = CHAT_ID
        #self.PA_USERNAME = PA_USERNAME
        #self.PA_API_TOKEN = PA_API_TOKEN
        self.LABEL = LABEL
        self.LOC_STRING = LOC_STRING

    def loop_this(self):
        logging.info("\t- Checking crypto and stocks and doing TA ...")
        logging.debug("\t\to Loading config from %s" % (self.LOC_STRING + 'config.yml'))
        with open(self.LOC_STRING + 'config.yml',
                  'r') as f:  # TODO: make a config loading function that checks the form
            config = yaml.safe_load(f)
        ticker_list = list(config["TICKERS"].keys())
        logging.info("\t\to Tickers = " + str(ticker_list))

        # Read Old Alert Data
        if exists(self.LOC_STRING + "messages_" + self.LABEL + ".pickle"):
            with open(self.LOC_STRING + "messages_" + self.LABEL + ".pickle", 'rb') as handle2:
                alerts = pickle.load(handle2)
                logging.info("\t\to Loaded old alerts from pickle file: "
                             "%s" % (self.LOC_STRING + "messages_" + self.LABEL + ".pickle"))
        else:
            logging.info("\t\to Making Empty Alerts List ...")
            alerts = []
        logging.debug("Alerts = " + str(alerts))

        logging.info("\t\to Doing TA:")
        full_data = AlertList(config).show_me_the_money_joined()

        # with open(self.LOC_STRING + "output_" + self.LABEL + ".json", 'w') as handle2:
        #     json.dump(full_data, handle2, sort_keys=True, indent=4)
        #     logging.info("\t\to Saved TA output to json: "
        #                  "%s" % (self.LOC_STRING + "output_" + self.LABEL + ".json"))

        with open(self.LOC_STRING + "output_" + self.LABEL + ".yml", 'w') as handle2:
            yaml.dump(full_data, handle2, indent=4, default_flow_style=False)
            logging.info("\t\to Saved TA output to json: "
                         "%s" % (self.LOC_STRING + "output_" + self.LABEL + ".yml"))

        logging.info("\t\to Doing Strategy analysis...")
        alerts = self.check_strategy(config, full_data, alerts)

        with open(self.LOC_STRING + "messages_" + self.LABEL + ".pickle", 'wb') as handle2:
            pickle.dump(alerts, handle2)
            logging.info("\t\to Saved Alerts to pickle: "
                         "%s" % (self.LOC_STRING + "messages_" + self.LABEL + ".pickle"))
        with open(self.LOC_STRING + "messages_" + self.LABEL + ".txt", "w", encoding='utf-8') as text_file:
            text_file.write(message_reader(alerts))
            logging.info("\t\to Saved Alerts to pickle: "
                         "%s" % (self.LOC_STRING + "messages_" + self.LABEL + ".txt"))
        return True

    def start_telegram_bot(self):
        def handle_bot(msg):  #TODO: check all the commands!
            content_type, chat_type, chat_id = telepot.glance(msg)
            logging.info("! TELEGRAM BOT ! : Responding to a text in telegram chat...")
            #logging.info(str(chat_type))
            # print(content_type, chat_type)
            if content_type == 'text':
                # bot.sendMessage(chat_id, msg['text'])
                if msg['text'] == "/sendpics":
                    self.bot.sendMessage(chat_id, "here it is:")
                    with open(self.LOC_STRING + "dataframe_" + self.LABEL + ".pickle", 'rb') as handle2:
                        dfi.export(pickle.load(handle2).style.apply(apply_style)
                                   , "mytablelist_" + self.LABEL + ".png")
                    self.bot.sendPhoto(chat_id, photo=open('mytablelist_' + self.LABEL + '.png', 'rb'))
                if msg['text'] == "/alive":
                    self.bot.sendMessage(chat_id, "... and kicking!")
                if msg['text'] == "/alerts":
                    self.bot.sendMessage(chat_id, "Active alerts:")
                    with open(self.LOC_STRING + "messages_" + self.LABEL + ".pickle", 'rb') as handle:
                        alerts_bot = pickle.load(handle)
                    if len(alerts_bot) == 0:
                        self.bot.sendMessage(chat_id, "No *" + self.LABEL + " alerts, bro!")
                    else:
                        self.bot.sendMessage(chat_id, message_reader(alerts_bot))
                        self.bot.sendMessage(chat_id, message_reader_combine_alerts(alerts_bot))
                if msg['text'] == "/longalerts":
                    self.bot.sendMessage(chat_id, "Active alerts:")
                    with open(self.LOC_STRING + "messages_" + self.LABEL + ".pickle", 'rb') as handle:
                        alerts_bot = pickle.load(handle)
                    if len(alerts_bot) == 0:
                        self.bot.sendMessage(chat_id, "No *" + self.LABEL + " alerts, bro!")
                    else:
                        self.bot.sendMessage(chat_id, message_reader(alerts_bot, Long=True))
                        self.bot.sendMessage(chat_id, message_reader_combine_alerts(alerts_bot))
                if msg['text'] == "/showpairs":
                    with open(self.LOC_STRING + 'config.yml', 'r') as f:
                        config = yml.load(f)
                        # list_USDT = [config[key][0] for key in config.keys()] with tradingview

                    self.bot.sendMessage(chat_id, "Current " + self.LABEL + " pairlist: " + str(list(config.keys())))

                if msg['text'] == "/senddata":
                    with open(self.LOC_STRING + "output_" + self.LABEL + ".json") as f:
                        lines = f.read()
                    self.bot.sendMessage(chat_id, lines)

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
                           "\n\t /senddata - Sends the current dataframe of analysis" \
                           "\n\t /removemessages - remove old messages, start from scratch" \
                           "\n\t /help - This message"
                    self.bot.sendMessage(chat_id, str0)
                if msg['text'] == "/removemessages":
                    self.bot.sendMessage(chat_id, "Removing all old messages (" + self.LABEL + ")!")
                    with open(self.LOC_STRING + "messages_" + self.LABEL + ".pickle", 'wb') as handle2:
                        pickle.dump([], handle2)
                        logging.info("saved empty messages")

        MessageLoop(self.bot, handle_bot).run_as_thread()
        logging.info("\t- Telegram bot started! (Send /help in the app to get more info!)")

    def send_message(self, text):
        self.bot.sendMessage(self.chat_id, text)

    def alert_creator(self, condition, value, strategy_label, str_label, previous_messages,
                      messages, alert=True):

        msg_dict = {
            "ticker": value,
            "label": strategy_label,
            "string": str_label,
            "time": datetime.now()
        }
        if condition:
            if [msg_dict["ticker"], msg_dict["label"]] not \
                    in [[part["ticker"], part["label"]] for part in previous_messages]:
                # if msg[:3] not in [part[:3] for part in previous_messages]:
                print()
                if alert:
                    self.bot.sendMessage(self.chat_id,
                                         emoji.emojize(':heavy_exclamation_mark:', use_aliases=True) +
                                         value.replace("-USD", "").replace("1", "") + ": " + str_label,
                                         disable_notification=False)
                    logging.info("\t\t\t\t\t-> Sending Alert! ")
                    logging.debug("\t\t\t\t\tMessage: " + str(msg_dict))
                    # print("NEW Message: " + str(msg))
            else:
                indx = [[part["ticker"], part["label"]] for part in
                        previous_messages].index([msg_dict["ticker"], msg_dict["label"]])
                msg_dict["time"] = previous_messages[indx]["time"]
                if alert:
                    logging.info("\t\t\t\t\t-> Alert already active... ")
                logging.debug("\t\t\t\t\tMessage: " + str(msg_dict))

            messages.append(msg_dict)

        elif [msg_dict["ticker"], msg_dict["label"]] \
                in [[part["ticker"], part["label"]] for part in previous_messages]:
            indx = [[part["ticker"], part["label"]] for part in
                    previous_messages].index([msg_dict["ticker"], msg_dict["label"]])
            timestamp = previous_messages[indx]["time"]
            if (datetime.now() - timestamp).total_seconds() / 60 < 60 * 8:
                logging.info("Appending old message: " + str(previous_messages[indx]))
                msg_dict["string"] = msg_dict["string"] + " (Not Active)"
                msg_dict["time"] = timestamp
                messages.append(msg_dict)
        return messages

    def check_strategy(self, config, output_data, previous_messages):
        messages = []
        ta_list_global = config["SETTINGS"]["ta_list_global"]

        for count, value in enumerate(config["TICKERS"].keys()):
            dta = output_data[value]
            logging.info("\t\t\t* %s:" % value)
            if 1:
                logging.debug("\t\t\t\tAdding Daily and Weekly Changes for %s" % value)
                try:
                    reports = SHOW_CHANGE(dta)
                    for report in reports:
                        logging.debug(
                            "\t\t\t\t-%s - Condition: %s" % (report["strategy_label"], str(report["condition"])))
                        messages = self.alert_creator(report["condition"], value,
                                                      report["strategy_label"],
                                                      report["str_label"],
                                                      previous_messages,
                                                      messages,
                                                      alert=report["alert"])
                except Exception as e:
                    logging.error("Error with Daily and Weekly Changes  --->  %s " % e)
                ta_list = config["TICKERS"][value]["ta_list"]
                for TA in ta_list_global + list(set(ta_list) - set(ta_list_global)):
                    logging.debug("\t\t\t * Checking strategy '%s' for '%s'" % (TA, value))
                    try:
                        reports = getattr(strategies, TA)(dta)
                        for report in reports:
                            logging.info(
                                "\t\t\t\t-%s - Condition: %s" % (report["strategy_label"], str(report["condition"])))
                            messages = self.alert_creator(report["condition"], value,
                                                          report["strategy_label"],
                                                          report["str_label"],
                                                          previous_messages,
                                                          messages,
                                                          alert=report["alert"])
                    except Exception as e:
                        logging.error(" Error with Strategy '%s'  --->  %s " % (TA, e))
                trends = config["TICKERS"][value]["trends"]
                if trends is not None:
                    for trend in list(trends.keys()):
                        logging.debug("\t\t\t * Checking trend '%s' for '%s'" % (trend, value))
                        reports = TrendChecker(trend, trends[trend], dta, value)
                        for report in reports:
                            logging.info(
                                "\t\t\t\t-%s - Condition: %s" % (report["strategy_label"], str(report["condition"])))
                            messages = self.alert_creator(report["condition"], value,
                                                          report["strategy_label"],
                                                          report["str_label"],
                                                          previous_messages,
                                                          messages,
                                                          alert=report["alert"])
        return messages


def TrendChecker(trend_name, settings, data, ticker):
    try:
        if settings["kind"] == "Exp":
            x1, y1 = pd.Timestamp(settings['coordinate1'][0]).value, np.log(settings['coordinate1'][1])
            x2, y2 = pd.Timestamp(settings['coordinate2'][0]).value, np.log(settings['coordinate2'][1])
            m = (y2 - y1) / (x2 - x1)
            res = np.exp(m * (pd.Timestamp.now().value - x1) + y1)
        elif settings["kind"] == "Lin":
            x1, y1 = pd.Timestamp(settings['coordinate1'][0]).value, settings['coordinate1'][1]
            x2, y2 = pd.Timestamp(settings['coordinate2'][0]).value, settings['coordinate2'][1]
            m = (y2 - y1) / (x2 - x1)
            res = m * (pd.Timestamp.now().value - x1) + y1
        else:
            logging.error("Trend kind is not Exp or Lin")
            return []
        report = [
            {
                "str_label": "Closing to (<2%%), %s" % trend_name +
                             emoji.emojize(':chart_with_upwards_trend:', use_aliases=True)
                             + ", Price: %.5g, Trend Price: %.5g" % (data["Close"], res),
                "strategy_label": "Closing to %s" % trend_name,  # TODO: DO I NEED THIS?
                "condition": np.abs((data["Close"] - res) / data["Close"]) <= 0.02,
                "alert": True
            },
            {
                "str_label": "Crossed -> %s" % trend_name +
                             emoji.emojize(':chart_with_upwards_trend:', use_aliases=True)
                             + ", Price: %.5g, Trend Price: %.5g" % (data["Close"], res),
                "strategy_label": "Crossed below %s" % trend_name if settings["alert_condition"] == "Alert_Below"
                else "Crossed above %s" % trend_name,  # TODO: DO I NEED THIS?
                "condition": data["Close"] <= res if settings["alert_condition"] == "Alert_Below"
                else data["Close"] >= res,
                "alert": True
            },
        ]
        return report
    except Exception as e:
        logging.error("Some issue with the trend %s for ticker %s" % (trend_name, ticker))
        logging.error(e)
        return []


def SHOW_CHANGE(data=None):
    d_change = "%.1f%%" % data["CHANGE1d_day"] + emoji.emojize(':evergreen_tree:', use_aliases=True) \
        if data["CHANGE1d_day"] >= 0.0 \
        else "%.1f%%" % data["CHANGE1d_day"] + emoji.emojize(':red_triangle_pointed_down:', use_aliases=True)
    w_change = "%.1f%%" % data["CHANGE7d_day"] + emoji.emojize(':evergreen_tree:', use_aliases=True) \
        if data["CHANGE7d_day"] >= 0.0 \
        else "%.1f%%" % data["CHANGE7d_day"] + emoji.emojize(':red_triangle_pointed_down:', use_aliases=True)
    report = [
        {
            "str_label": "%.5g" % data["Close"] + ", " + d_change + " (week: " + w_change + ")",
            "strategy_label": "show_change",  # TODO: DO I NEED THIS?
            "condition": True,
            "alert": False
        }
    ]
    return report


def CHANGE1d(dta, timeframe):
    dta["CHANGE1d" + timeframe] = 100 * round((dta['Close'][-1] - dta['Close'][-2]) / dta['Close'][-2], 5)
    return dta


def CHANGE7d(dta, timeframe):
    dta["CHANGE7d" + timeframe] = 100 * round((dta['Close'][-1] - dta['Close'][-8]) / dta['Close'][-8], 5)
    return dta
