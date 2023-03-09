#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import re
from urllib import request
from netmiko import ConnectHandler
from argparse import ArgumentParser
from related_utils import generate_device, lists_subtraction, generate_ip_pattern


def args_parser():
    parser = ArgumentParser(description='RouterOS list updater.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str, help='Host (in ssh_config).', required=True)
    parser.add_argument('-u', '--url', type=str, help='URL to IP list.', required=True)
    parser.add_argument('-l', '--list', type=str, help='Name of address list.', required=True)
    parser.add_argument('-c', '--label', type=str, help='Comment as label of list.', required=True)
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
        self.ip_pattern = generate_ip_pattern()
        self.mikrotik_router = generate_device(ssh_config_file, host)

    def run(self):
        self.generate_lists()
        if self.ip_list_add or self.ip_list_remove:
            self.update_ip_on_device()

    def generate_lists(self):
        self.generate_fresh_ip_list()
        self.generate_current_ip_list()
        self.ip_list_add = lists_subtraction(self.ip_list_fresh, self.ip_list_current)
        self.ip_list_remove = lists_subtraction(self.ip_list_current, self.ip_list_fresh)

    def generate_fresh_ip_list(self):
        data_list = request.urlopen(self.ip_list_url)
        content = data_list.read().decode(data_list.headers.get_content_charset('UTF-8'))
        if not content:
            exit(0)
        re_output = re.finditer(self.ip_pattern, content)
        for line in re_output:
            ip_addr = line.group(0).replace('\n', '').replace('"', '')
            self.ip_list_fresh.append(ip_addr)

    def generate_current_ip_list(self):
        with ConnectHandler(**self.mikrotik_router) as device:
            output = device.send_command(f'/ip firewall address-list print where comment="{self.label}"')
        re_output = re.finditer(self.ip_pattern, output)
        for line in re_output:
            ip_addr = line.group(0).replace(' ', '')
            self.ip_list_current.append(ip_addr)

    def update_ip_on_device(self):
        with ConnectHandler(**self.mikrotik_router) as device:
            for ip_addr in self.ip_list_remove:
                entry = f'/ip firewall address-list find address={ip_addr}'
                device.send_command(f'/ip firewall address-list remove [{entry}]')
            for ip_addr in self.ip_list_add:
                entry = f'list={self.list_name} comment={self.label} address={ip_addr}'
                device.send_command(f'/ip firewall address-list add {entry}')


if __name__ == '__main__':
    args = args_parser()
    list_upd = ListUpdater(
        ssh_config_file=args['sshconf'],
        host=args['host'],
        ip_list_url=args['url'],
        list_name=args['list'],
        label=args['label'],
    )

    list_upd.run()
