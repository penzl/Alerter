from AlerterV1_helpers import *
from AlerterV1_constants_fresh import *
import time


def run(test=False):
    if test:  # TESTMODE
        BOT = BotStarter(TELEPOT_BOT_TEST, CHAT_ID_TEST,
                         use_local_config_or_pythonanywhere, PA_USERNAME, PA_API_TOKEN, "TEST")
        BOT.start_telegram_bot()
        while True:
            BOT.loop_this()
            print("waiting 5 min...")
            time.sleep(2)
    else:
        BOT = BotStarter(TELEPOT_BOT, CHAT_ID,
                         use_local_config_or_pythonanywhere, PA_USERNAME, PA_API_TOKEN, "USD")
        BOT.start_telegram_bot()
        while True:
            try:
                BOT.loop_this()
            except:
                print("retrying...")
            print("waiting 5 min...")
            time.sleep(60 * 5)


if __name__ == '__main__':
    #    run(test=True)
    run()
