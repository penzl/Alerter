import numpy as np
import emoji

f_form = "{:.8g}".format
f_form_short = "{:.5g}".format
perc_form = "{:.1%}".format


#################################################
#        Enter Strategies Below                 #
#        Align with indicators.py!!!            #
#################################################

# Use the template below or use defined strategies as examples:
# def {insert strategy name}(data=None, check=False):
#     if check:
#         return ["{insert indicator 1 name}", "{insert indicator 2 name}", ... ]
#     else:
#         report = [
#             {
#                 "str_label": "Some text you want to see, Price: %.2f ,
#                                  some_parameter = %.1f" % (data["Close"], data["{insert sub-indicator name}"]),
#                 "strategy_label": "{insert some very short label}",
#                 "condition": {Use some condition such as for example: data['RSI_day'] <= 30. Use sub-indicators
#                               from the indicators you named above}
#                 "alert": True if you want to be alerted, False if not.
#             }
#         ]
#         return report


def RSI_SELL_OF(data=None, check=False):
    if check:
        return ["RSI_day"]
    else:
        report = [
            {
                "str_label": "Selloff, Price: %.2f , RSI = %.1f" % (data["Close"], data["RSI_day"]),
                "strategy_label": "rsi < 30",  # TODO: DO I NEED THIS?
                "condition": data['RSI_day'] <= 30,
                "alert": True
            }
        ]
        return report


def RSI_WEEK_SELL_OF(data=None, check=False):
    if check:
        return ["RSI_week"]
    else:
        report = [
            {
                "str_label": "Week Selloff, Price: %.2f , RSI_week = %.1f" % (data["Close"], data['RSI_week']),
                "strategy_label": "week rsi < 50",  # TODO: DO I NEED THIS?
                "condition": data['RSI_week'] <= 50,
                "alert": True
            }
        ]
        return report


def EMA_TREND(data=None, check=False):
    if check:
        return ["EMA31_day", "EMA59_day"]
    else:
        report = [
            {
                "str_label": "EMA trend in grey zone, Price: %.1f, EMA31 = %.1f, EMA59 = %.1f" % (
                    data["Close"], data["EMA31_day"], data["EMA59_day"]),
                "strategy_label": "EMA_trend_grey",
                "condition": 2 * np.abs(
                    (data["EMA31_day"] - data["EMA59_day"]) / (data["EMA31_day"] + data["EMA59_day"])) < 0.01,
                "alert": True
            },
            {
                "str_label": emoji.emojize(':bear:', use_aliases=True) + \
                             "BEAR EMA trend" if (data["EMA31_day"] - data["EMA59_day"]) < 0 \
                    else emoji.emojize(':cow_face:', use_aliases=True) + " BULL EMA trend",
                "strategy_label": 'EMA_trend_negative' if \
                    (data["EMA31_day"] - data["EMA59_day"]) < 0 else 'EMA_trend_positive',
                "condition": True,
                "alert": True
            }
        ]
        return report


def CASH_OUT_RSI(data=None, check=False):
    if check:
        return ["RSI_day", "RSI_week"]
    else:
        report = [
            {
                "str_label": "Cash-out SELL alert " + emoji.emojize(':money_bag:', use_aliases=True) +
                             ", Price: %.5g, RSI = %.1f" % (data["Close"], data["RSI_day"]),
                "strategy_label": "RSI_day > 75",  # TODO: DO I NEED THIS?
                "condition": data['RSI_day'] >= 75,
                "alert": True
            },
            {
                "str_label": "Cash-out SELL alert (week) " + emoji.emojize(':money_bag:', use_aliases=True) +
                             ", Price: %.5g, RSI_week = %.1f" % (data["Close"], data["RSI_week"]),
                "strategy_label": "RSI_week > 60",  # TODO: DO I NEED THIS?
                "condition": data['RSI_week'] >= 70,
                "alert": True
            }
        ]
        return report


def OUT_OF_BBANDS(data=None, check=False):
    if check:
        return ["BB_day"]
    else:
        report = [
            {
                "str_label": "Out Of Bollinger Bands, Price: %.5g , BB_l = %.5g, "
                             "BB_h = %.5g" % (data["Close"], data["BB_high_day"], data["BB_low_day"]),
                "strategy_label": "Out Of Daily Bollinger Bands",  # TODO: DO I NEED THIS?
                "condition": data["BB_low_day"] >= data["Close"] or \
                             data["BB_high_day"] <= data["Close"],
                "alert": True
            }
        ]
        return report


def MA21_ENVELOPE(data=None, check=False):
    if check:
        return ["MA21_week"]
    else:
        report = [
            {
                "str_label": "In Accum. Zone, Price: %.5g is between %.5g and %.5g "
                             "(or below)" % (data["Close"], data["MA21_week"] / 2,
                                             data["MA21_week"] / 1.5),
                "strategy_label": "In Accum. Zone",  # TODO: DO I NEED THIS?
                "condition": data["MA21_week"] / 1.5 >= data["Close"],
                "alert": True
            },
            {
                "str_label": "In Reduc. Zone, Price: %.5g is between %.5g and %.5g "
                             "(or above)" % (data["Close"], data["MA21_week"] * 1.5,
                                             data["MA21_week"] * 2),
                "strategy_label": "In Reduc. Zone",  # TODO: DO I NEED THIS?
                "condition": data["MA21_week"] * 1.5 <= data["Close"],
                "alert": True
            },
            {
                "str_label": "Close to 21W SMA (<2%%), Price: %.5g , "
                             "21W SMA: %.5g" % (data["Close"], data["MA21_week"]),
                "strategy_label": "Close to 21MA",  # TODO: DO I NEED THIS?
                "condition": np.abs((data["Close"] - data["MA21_week"]) / data["MA21_week"]) <= 0.02,
                "alert": True
            }
        ]
        return report


def BullDCA(data=None, check=False):
    if check:
        return ["RSI_week", "RSI_day", "STOCH_day"]
    else:
        report = [
            {
                "str_label": "BullDCA, Price: %.5g, RSI_1d: %.1f, RSI_1w: %1.f,"
                             "Stoch.K: %.1f, Stoch.D: %.1f" % (data["Close"],
                                                               data["RSI_day"],
                                                               data["RSI_week"],
                                                               data["StochK_day"],
                                                               data["StochD_day"]),
                "strategy_label": "BullDCA",  # TODO: DO I NEED THIS?
                "condition": (data["RSI_week"] >= 50) and
                             (data["RSI_day"] <= 50) and
                             (data["StochK_day"] - data["StochD_day"]) >= 0,
                "alert": True
            },
        ]
        return report


def BearDCA(data=None, check=False):
    if check:
        return ["RSI_week", "RSI_day", "STOCH_day"]
    else:
        report = [
            {
                "str_label": "BearDCA, Price: %.5g, RSI_1d: %.1f, RSI_1w: %1.f,"
                             "Stoch.K: %.1f, Stoch.D: %.1f" % (data["Close"],
                                                               data["RSI_day"],
                                                               data["RSI_week"],
                                                               data["StochK_day"],
                                                               data["StochD_day"]),
                "strategy_label": "BearDCA",  # TODO: DO I NEED THIS?
                "condition": (data["RSI_week"] <= 50) and
                             (data["RSI_day"] <= 30) and
                             (data["StochK_day"] - data["StochD_day"]) >= 0,
                "alert": True
            },
        ]
        return report
