#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from urllib import request
from netmiko import ConnectHandler
from argparse import ArgumentParser
from related_utils import generate_device, lists_subtraction, ips_from_data
from related_utils import generate_telegram_bot, markdownv2_converter, print_output


def args_parser():
    parser = ArgumentParser(description='RouterOS list updater.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str, help='Host (in ssh_config).', required=True)
    parser.add_argument('-u', '--url', type=str, help='URL to IP list.', required=True)
    parser.add_argument('-i', '--list', type=str, help='Name of address list.', required=True)
    parser.add_argument('-l', '--label', type=str, help='Comment as label in list.', required=True)
    parser.add_argument('-b', '--bottoken', type=str, help='Telegram Bot token.', required=False)
    parser.add_argument('-c', '--chatid', type=str, help='Telegram chat id.', required=False)
    arguments = parser.parse_args().__dict__
    return arguments


class ListUpdater:

    def __init__(self, host, ip_list_url, list_name, label, ssh_config_file='~/.ssh/config'):
        self.ip_list_fresh = []
        self.ip_list_current = []
        self.ip_list_add = []
        self.ip_list_remove = []
        self.ip_list_url = ip_list_url
        self.list_name = list_name
        self.label = label
        self.connect = ConnectHandler(**generate_device(ssh_config_file, host))
        self.report = ''
        self.emoji = {
            'device':   '\U0001F4F6',       # 📶
            'list':     '\U0001F4CB',       # 📋
            'tag':      '\U0001F4CE',       # 📎
        }

    def run(self):
        self.connect.enable()
        self.generate_lists()
        if self.ip_list_add or self.ip_list_remove:
            self.generate_report()
            self.update_ip_on_device()
        self.connect.disconnect()

    def generate_lists(self):
        self.generate_fresh_ip_list()
        self.generate_current_ip_list()
        self.ip_list_add = lists_subtraction(self.ip_list_fresh, self.ip_list_current)
        self.ip_list_remove = lists_subtraction(self.ip_list_current, self.ip_list_fresh)

    def generate_fresh_ip_list(self):
        data_list = request.urlopen(self.ip_list_url)
        content = data_list.read().decode(data_list.headers.get_content_charset('UTF-8'))
        if content:
            self.ip_list_fresh = ips_from_data(content)
        else:
            exit(0)

    def generate_current_ip_list(self):
        command = f'/ip firewall address-list print where comment={self.label}'
        output = print_output(self.connect, command)
        if output:
            self.ip_list_current = ips_from_data(output)

    def update_ip_on_device(self):
        for ip_addr in self.ip_list_remove:
            entry = f'/ip firewall address-list find address={ip_addr}'
            self.connect.send_command(f'/ip firewall address-list remove [{entry}]')
        for ip_addr in self.ip_list_add:
            entry = f'list={self.list_name} comment={self.label} address={ip_addr}'
            self.connect.send_command(f'/ip firewall address-list add {entry}')

    def get_identity(self):
        command = '/system identity print'
        identity = print_output(self.connect, command)
        identity_name = re.match(r'^name: (.*)$', identity).group(1)
        return identity_name

    def generate_report(self):
        identity = markdownv2_converter(self.get_identity())
        list_name = markdownv2_converter(self.list_name)
        label = markdownv2_converter(self.label)
        self.report = f'Отчёт об изменении на {self.emoji["device"]}*{identity}*'
        self.report += f' списка {self.emoji["list"]}__{list_name}__ с меткой {self.emoji["tag"]}\#{label}\n\n'
        if self.ip_list_add:
            self.report += f'Добавлено:\n```'
            for ip_elem in self.ip_list_add:
                self.report += f'\n{ip_elem}'
            self.report += f'```\n'
        if self.ip_list_remove:
            self.report += f'Удалено:\n```'
            for ip_elem in self.ip_list_remove:
                self.report += f'\n{ip_elem}'
            self.report += f'```\n'


def main(args):
    telegram_bot = generate_telegram_bot(args_in['bottoken'], args_in['chatid'])
    list_upd = ListUpdater(
        ssh_config_file=args['sshconf'],
        host=args['host'],
        ip_list_url=args['url'],
        list_name=args['list'],
        label=args['label'],
    )
    list_upd.run()
    if list_upd.report and telegram_bot and telegram_bot.alive():
        telegram_bot.send_text_message(list_upd.report)


if __name__ == '__main__':
    args_in = args_parser()
    main(args_in)
