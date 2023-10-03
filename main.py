#!/usr/bin/env python3
import logging
import os
from datetime import timedelta, datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import requests
import json
from qth_locator import square_to_location
from haversine import haversine
import countries

js8_group = -1001550712749

cc = countries.CountryChecker('br.shp')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    #requests.get('https://pskreporter.info/cgi-bin/pskquery5.pl?encap=0&callback=doNothing&statistics=0&noactive=1&nolocator=1&flowStartSeconds=-3600&mode=JS8&modify=all&callsign=ZZZZZ')
    with open('sample_pskreporter') as f:
        data = f.read()
    
    data = json.loads(data.removeprefix('doNothing(').removesuffix(');\n'))

    spots = []

    for report in data['receptionReport']:
        rx_lat, rx_lon = square_to_location(report['receiverLocator'][:8])

        country = cc.getCountry(countries.Point(rx_lat, rx_lon))
        if country is None or country.iso != 'BR':
            continue

        tx_lat, tx_lon = square_to_location(report['senderLocator'][:8])
        dist = round(haversine((rx_lat, rx_lon), (tx_lat, tx_lon)))

        flowStart = datetime.fromtimestamp(report['flowStartSeconds'])
        minutesAgo = round((datetime.now() - flowStart).total_seconds()/60)

        spots.append(f"• {report['senderCallsign']} → {report['receiverCallsign']} @ {report['frequency']} Hz, {dist} km, {report['sNR']} dB, há {minutesAgo} min")

    if spots != []:
        await context.bot.send_message(js8_group, '\n'.join(spots))


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
