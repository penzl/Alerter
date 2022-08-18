from AlerterV1_helpers import *
from AlerterV1_constants import *
import time
from datetime import date, timedelta

def run(test=False):
    if test:  # TESTMODE
        BOT = BotStarter(TELEPOT_BOT_TEST, CHAT_ID_TEST,
                         use_local_config_or_pythonanywhere, PA_USERNAME, PA_API_TOKEN, "TEST",LOC_STRING)
        BOT.start_telegram_bot()
        while True:
            BOT.loop_this()
            print("waiting 5 min...")
            time.sleep(2)
    else:
        BOT = BotStarter(TELEPOT_BOT, CHAT_ID,
                         use_local_config_or_pythonanywhere, PA_USERNAME, PA_API_TOKEN, "USD",LOC_STRING)
        BOT.start_telegram_bot()
        #This part ends the script if the day changes. Its restarted everyday on pythonanywhere
        Tomorrow_Date = date.today() + timedelta(days=1)
        while date.today() < Tomorrow_Date:
            print("Still same day... Continuing")
        #
        #while True:
            try:
                BOT.loop_this()
            except:
                print("retrying...")
            print("waiting 5 min...")
            time.sleep(60 * 5)


if __name__ == '__main__':
    run(test=True)
    #run()
