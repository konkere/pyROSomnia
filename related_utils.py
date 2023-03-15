#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import ipaddress
from telebot import TeleBot
from time import sleep, time
from paramiko import SSHConfig


def generate_device(ssh_config_file, host):
    disabled_algorithms = {'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']}
    mkt_ssh_conf = SSHConfig()
    mkt_ssh_conf.parse(open(ssh_config_file))
    hostname = mkt_ssh_conf.lookup(host)['hostname']
    key = mkt_ssh_conf.lookup(host)['identityfile'][0]
    user = mkt_ssh_conf.lookup(host)['user']
    port = mkt_ssh_conf.lookup(host)['port']
    mikrotik_router = {
        'device_type': 'mikrotik_routeros',
        'host': hostname,
        'port': port,
        'username': user,
        'use_keys': True,
        'key_file': key,
        'disabled_algorithms': disabled_algorithms,
    }
    return mikrotik_router


def lists_subtraction(list_minuend, list_subtrahend):
    list_difference = [element for element in list_minuend if element not in list_subtrahend]
    return list_difference


def ip_pattern():
    ip_b = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    mask = r'(\/([1-9][0-9]|[0-9]))?'
    dot = r'\.'
    re_pattern = (ip_b + dot) * 3 + ip_b + mask
    return re_pattern


def ips_from_data(data):
    ips = []
    pattern = ip_pattern()
    re_data = re.finditer(pattern, data)
    for elem in re_data:
        addr_or_net = elem.group(0)
        addr_or_net_valid = validate_ip(addr_or_net)
        if addr_or_net_valid:
            ips.append(addr_or_net)
    return ips


def validate_ip(ip):
    valid = True
    try:
        addr_or_net = ipaddress.ip_network(ip)
    except ValueError:
        valid = False
    else:
        if not addr_or_net.is_global:
            valid = False
    return valid


def allowed_filename(filename):
    allowed_pattern = re.compile('[^A-z0-9!@#$%^&-]')
    allowed_name = re.sub(allowed_pattern, '_', filename)
    return allowed_name


def print_output(device, command, delay=1, timeout=60):
    output = device.send_command(command)
    sleep(delay)
    if not output:
        output = device.send_command(command, expect_string=r'[\$#]', read_timeout=float(timeout))
        sleep(delay)
    return output


def remove_old_files(path_to_dir, lifetime_days):
    secs_in_day = 60 * 60 * 24
    lifetime = lifetime_days * secs_in_day
    filenames = os.listdir(path_to_dir)
    timestamp_now = time()
    for file_name in filenames:
        file_path = os.path.join(path_to_dir, file_name)
        file_mtime = os.stat(file_path).st_mtime
        diff_time = timestamp_now - file_mtime
        if diff_time > lifetime:
            os.remove(file_path)


def size_converter(size_bytes, decimal_places=2, divide=False):
    x_bytes = {
        'GB': 1073741824,
        'MB': 1048576,
        'KB': 1024,
        'B': 0,
    }
    x_bytes_sorted = sorted(x_bytes.items(), key=lambda x: x[1], reverse=True)
    for (name, size_1) in x_bytes_sorted:
        if size_bytes >= size_1:
            size_round = round(size_bytes/size_1 if size_1 > 0 else size_bytes, decimal_places)
            size_converted = f'{size_round}' + ' ' * divide + f'{name}'
            return size_converted


def generate_telegram_bot(bot_token, chat_id):
    bot = None
    if bot_token and chat_id:
        bot = TlgrmBot(bot_token, chat_id)
    return bot


def markdownv2_converter(text):
    symbols_for_replace = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for symbol in symbols_for_replace:
        text = text.replace(symbol, '\\' + symbol)
    return text


class TlgrmBot:

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = TeleBot(self.bot_token)

    def send_text_message(self, text, disable_web_page_preview=True, parse_mode='MarkdownV2'):
        message = self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return message.message_id

    def alive(self):
        try:
            self.bot.get_me()
        except Exception:
            return False
        else:
            return True
