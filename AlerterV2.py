import logging

from AlerterV2_helpers import *
from AlerterV2_constants import *
import time
from datetime import date, timedelta


def run(test=False):
    logging.basicConfig(
        # filename='file.log',
         level=logging.INFO,
        # level=logging.ERROR,
        #level=logging.DEBUG,
        format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')
    # logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')
    # #logging.basicConfig(level=logging.ERROR)
    # logging.basicConfig(level=logging.INFO)

    logging.info(" ++++++++++ Starting Bot... ++++++++++")

    if test:  # TESTMODE
        logging.info("Running test mode with faster repetitions...")
        BOT = BotStarter(TELEPOT_BOT_TEST, CHAT_ID_TEST, "TEST", LOC_STRING)
        BOT.start_telegram_bot()
        sleep_time = 10
        while True:
            logging.info("\t- Checking crypto and stocks and doing TA ...")
            BOT.loop_this()
            logging.info("\t\to Finished! Sleeping for %i seconds" % sleep_time)
            time.sleep(sleep_time)
    else:
        BOT = BotStarter(TELEPOT_BOT, CHAT_ID, "USD", LOC_STRING)
        BOT.start_telegram_bot()

        # This part below ends the script if the day changes.
        # It should be restarted everyday on pythonanywhere or anywhere else

        Tomorrow_Date = date.today() + timedelta(days=1)
        fail_count = 0
        sleep_time = 5  # in minutes
        while date.today() < Tomorrow_Date:
            if not BOT.loop_this():
                fail_count = fail_count + 1
                if fail_count > 10:
                    fail_count = 0
                    BOT.send_message("Bot failed 10x...")
            logging.info("\t\to Finished! Sleeping for %i minute(s)" % (sleep_time))
            time.sleep(60 * sleep_time)
        logging.critical("The day has ended -> ending python script...")


if __name__ == '__main__':
    run(test=False)
    # run()
