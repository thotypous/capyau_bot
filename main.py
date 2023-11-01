#!/usr/bin/env python3
import logging
import os
from datetime import date, timedelta, datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import requests
import json
from qth_locator import square_to_location
from haversine import haversine
import countries

js8_group = -1001392437961

cc = countries.CountryChecker('br.shp')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


lastQueryDuration = None
lastSequenceNumber = None

async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    global lastQueryDuration, lastSequenceNumber

    url = 'https://pskreporter.info/cgi-bin/pskquery5.pl?encap=0&callback=doNothing&statistics=0&noactive=1&nolocator=1&flowStartSeconds=-600&mode=JS8&modify=all&callsign=ZZZZZ'
    if lastSequenceNumber != None:
        url += f'&lastseqno={lastSequenceNumber}'
    if lastQueryDuration != None:
        url += f'&lastDuration={lastQueryDuration}'

    t1 = datetime.now()
    r = requests.get(url)
    r.raise_for_status()
    t2 = datetime.now()

    lastQueryDuration = round(1000*(t1-t2).total_seconds())

    data = json.loads(r.text.removeprefix('doNothing(').removesuffix(');\n'))

    lastSequenceNumber = data['lastSequenceNumber']

    spots = []

    for report in data['receptionReport']:
        try:
            frequency = report['frequency']

            if 26960000 <= frequency <= 27860000:
                continue
            if report['senderCallsign'].startswith('3CW'):
                continue

            rx_lat, rx_lon = square_to_location(report['receiverLocator'][:8])
            tx_lat, tx_lon = square_to_location(report['senderLocator'][:8])

            country = cc.getCountry(countries.Point(tx_lat, tx_lon))
            if country is None or country.iso != 'BR':
                continue

            dist = round(haversine((rx_lat, rx_lon), (tx_lat, tx_lon)))

            flowStart = datetime.fromtimestamp(report['flowStartSeconds'])
            minutesAgo = round((datetime.now() - flowStart).total_seconds()/60)

            spots.append(f"• {report['senderCallsign']} → {report['receiverCallsign']} @ {frequency} Hz, {dist} km, {report['sNR']} dB, há {minutesAgo} min")
        except:
            logger.exception('processing report: %r', report)

    if spots != []:
        await context.bot.send_message(js8_group, '\n'.join(spots), disable_notification=True)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        f"{update.effective_chat.id}"
    )


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(os.getenv("TOKEN")).build()

    application.add_handler(CommandHandler("id", get_id))

    application.job_queue.run_once(alarm, timedelta(seconds=1))
    application.job_queue.run_repeating(alarm, timedelta(minutes=5))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
