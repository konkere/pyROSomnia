#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from sys import exit
from argparse import ArgumentParser
from urllib.request import Request, urlopen
from related_utils import lists_subtraction, ips_from_data, ips_from_asn, collapse_ips, print_output
from related_utils import generate_connector, generate_telegram_bot, markdownv2_converter, asns_and_urls


def args_parser():
    parser = ArgumentParser(description='RouterOS list updater.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str,
                        help='Host (in ssh_config or IP/URL for API).', required=True)
    parser.add_argument('-a', '--login', type=str, help='API username for login.', required=False)
    parser.add_argument('-p', '--password', type=str, help='API password for login.', required=False)
    parser.add_argument('-u', '--url', type=str,
                        help='URLs or/and ASNs (comma separated) to IP list.', required=True)
    parser.add_argument('-i', '--list', type=str, help='Name of address list.', required=True)
    parser.add_argument('-l', '--label', type=str, help='Comment as label in list.', required=True)
    parser.add_argument('-b', '--bottoken', type=str, help='Telegram Bot token.', required=False)
    parser.add_argument('-c', '--chatid', type=str, help='Telegram chat id.', required=False)
    arguments = parser.parse_args().__dict__
    return arguments


class ListUpdater:

    def __init__(self, args):
        self.report = ''
        self.ip_list_add = []
        self.ip_list_fresh = []
        self.ip_list_remove = []
        self.ip_list_current = []
        self.label = args['label']
        self.list_name = args['list']
        self.ip_list_url = args['url']
        self.asn_pattern = r'[Aa][Ss][1-9]\d{0,9}'
        self.connect = generate_connector(args)
        self.emoji = {
            'device':   '\U0001F4F6',       # 📶
            'list':     '\U0001F4CB',       # 📋
            'tag':      '\U0001F4CE',       # 📎
        }

    def run(self):
        self.generate_lists()
        if self.ip_list_add or self.ip_list_remove:
            self.generate_report()
            self.update_ip_on_device()

    def generate_lists(self):
        self.generate_fresh_ip_list()
        self.generate_current_ip_list()
        self.ip_list_add = lists_subtraction(self.ip_list_fresh, self.ip_list_current)
        self.ip_list_remove = lists_subtraction(self.ip_list_current, self.ip_list_fresh)

    def generate_fresh_ip_list(self):
        asns, urls = asns_and_urls(self.ip_list_url)
        ip_list_all = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        if asns:
            for asn in asns:
                ip_list_all += ips_from_asn(asn, collapse=False)
        if urls:
            for url in urls:
                data_list = urlopen(Request(url, headers=headers))
                content = data_list.read().decode(data_list.headers.get_content_charset('UTF-8'))
                ip_list = ips_from_data(content, collapse=False)
                ip_list_all += ip_list
        if ip_list_all:
            self.ip_list_fresh = collapse_ips(ip_list_all)
        else:
            exit('Source list is empty.')

    def generate_current_ip_list(self):
        pass

    def update_ip_on_device(self):
        pass

    def get_identity(self):
        pass

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


class ListUpdaterSSH(ListUpdater):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self.connect.enable()
        super().run()
        self.connect.disconnect()

    def generate_current_ip_list(self):
        command = f'/ip firewall address-list print without-paging where comment={self.label}'
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


class ListUpdaterAPI(ListUpdater):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def generate_current_ip_list(self):
        address_list = self.connect.get_resource('/ip/firewall/address-list').get(
            comment=self.label,
            list=self.list_name,
        )
        self.ip_list_current = [addr['address'] for addr in address_list]

    def update_ip_on_device(self):
        address_list = self.connect.get_resource('/ip/firewall/address-list')
        for ip_addr in self.ip_list_remove:
            addr_id = address_list.get(comment=self.label, list=self.list_name, address=ip_addr)[0]['id']
            address_list.remove(numbers=addr_id)
        for ip_addr in self.ip_list_add:
            address_list.add(list=self.list_name, comment=self.label, address=ip_addr)

    def get_identity(self):
        identity = self.connect.get_resource('/').call('system/identity/print')
        identity_name = identity[0]['name']
        return identity_name


def main():
    args_in = args_parser()
    telegram_bot = generate_telegram_bot(args_in['bottoken'], args_in['chatid'])
    if args_in['sshconf']:
        list_upd = ListUpdaterSSH(args_in)
    elif args_in['login'] and args_in['password']:
        list_upd = ListUpdaterAPI(args_in)
    else:
        exit('SSH or API?')
    list_upd.run()
    if list_upd.report and telegram_bot and telegram_bot.alive():
        telegram_bot.send_text_message(list_upd.report)


if __name__ == '__main__':
    main()
