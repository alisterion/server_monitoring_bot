import logging
import os
import platform
import time
from multiprocessing import Process

import telegram
from telegram.ext import Updater
from telegram.ext import CommandHandler
import psutil
from psutil._common import bytes2human

import settings

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class TelegramBotService:
    updater = None
    bot = None

    def __init__(self, token=settings.TELEGRAM_TOKEN):
        self.updater = Updater(token=token, use_context=True)
        self.bot = telegram.Bot(token=token)
        logging.log(logging.INFO, f'INIT bot {self.bot.username}')

    def cmd_start(self, update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

    def cmd_get_stats(self, update, context):
        logging.log(logging.INFO, f'Receive cmd get_stats')
        context.bot.send_message(chat_id=update.effective_chat.id, text=get_info(), parse_mode=telegram.ParseMode.HTML)

    def init_cmd(self):
        logging.log(logging.INFO, 'init_cmd')
        method_list = [func for func in dir(self) if callable(getattr(self, func)) and func.startswith('cmd_')]
        for method in method_list:
            cmd = method.split('_', 1)[1]
            logging.log(logging.INFO, f'init {method} for {cmd}')
            start_handler = CommandHandler(cmd, getattr(self, method))
            self.updater.dispatcher.add_handler(start_handler)

    def send_message(self, chat_id, message):
        self.bot.send_message(chat_id=chat_id, text=message, parse_mode=telegram.ParseMode.HTML)

    def run(self):
        logging.log(logging.INFO, 'Run bot')
        self.init_cmd()
        self.updater.start_polling()


service = TelegramBotService()


def get_info():
    mem = psutil.virtual_memory()
    memory_in_mb = mem.available / 1024 / 1024
    total_in_mb = mem.total / 1024 / 1024
    cpu_usage = f"<b>CPU Load</b>: {psutil.cpu_percent()}"

    if platform.system() == 'Linux':
        cpu_usage += f"\n<b>Load avg</b>: {psutil.getloadavg()}"

    template = "%-17s %8s %8s %8s %5s%%"
    disks_usage = f'{template % ("<b>Device", "Total", "Used", "Free", "Use </b>")}\n'

    for part in psutil.disk_partitions(all=False):
        if os.name == 'nt':
            if 'cdrom' in part.opts or part.fstype == '':
                continue
        usage = psutil.disk_usage(part.mountpoint)
        disks_usage += f'{template % (part.device, bytes2human(usage.total), bytes2human(usage.used), bytes2human(usage.free), int(usage.percent))}\n'

    return f"{cpu_usage}\n" \
           f"{disks_usage}\n" \
           f"<b>Total memory</b>: {total_in_mb}\n" \
           f"<b>Available memory</b>: {memory_in_mb}\n" \
           f""


def check_system() -> str:
    mem = psutil.virtual_memory()
    available_memory_in_mb = mem.available / 1024 / 1024
    cpu_usage = psutil.cpu_percent()
    disk_usage = psutil.disk_usage('/').percent

    alert_msg = ""

    logging.log(logging.INFO, f'CPU: {cpu_usage} MEMEORY: {available_memory_in_mb:.2f} DISK_USAGE: {disk_usage}')

    if available_memory_in_mb < settings.FREE_MEMORY_ALERT:
        alert_msg += f"<b>Warning! Low free memory {available_memory_in_mb:.2f}</b>\n"

    if cpu_usage > settings.CPU_MAX_LOADING_ALERT:
        alert_msg += f"<b>Warning! High CPU loading {cpu_usage}</b>\n"

    if disk_usage < settings.DISK_MIN_USAGE_ALERT:
        alert_msg += f"<b>Warning! Low disk space {disk_usage}%</b>\n"

    return alert_msg


def service_updater_process():
    service.run()


if __name__ == "__main__":
    updater_process = Process(name='updater_process', target=service_updater_process)
    updater_process.start()

    while True:
        time.sleep(settings.SERVER_POLLING_TTL)

        alert = check_system()
        if alert:
            service.send_message(settings.MAIN_CHAT_ID, alert)
