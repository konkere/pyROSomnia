#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from time import sleep
from os import path, mkdir
from datetime import datetime
from argparse import ArgumentParser
from netmiko import ConnectHandler, file_transfer
from mikrotik_utils import generate_device, allowed_filename


def args_parser():
    parser = ArgumentParser(description='RouterOS backuper.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str, help='Single Host (in ssh_config).', required=False)
    parser.add_argument('-l', '--hostlist', type=str, help='Path to file with list of Hosts.', required=False)
    parser.add_argument('-p', '--path', type=str, help='Path to backups.', required=True)
    arguments = parser.parse_args().__dict__
    return arguments


def hosts_to_devices(hosts):
    devices = []
    for hostname in hosts:
        hostname = hostname.strip()
        if hostname:
            devices.append(Backuper(
                ssh_config_file=args['sshconf'],
                host=hostname,
                path_to_backups=args['path'],
            ))
    return devices


class Backuper:

    def __init__(self, host, path_to_backups, ssh_config_file='~/.ssh/config'):
        self.path_to_backups = path_to_backups
        self.mikrotik_router = generate_device(ssh_config_file, host)
        self.connect = ConnectHandler(**self.mikrotik_router)
        self.subdir = 'backup'
        self.delay = 1

    def run(self):
        self.connect.enable()
        identity = self.generate_identity()
        path_to_backup = path.join(self.path_to_backups, identity)
        backup_name = f'{identity}_{datetime.now().strftime("%Y.%m.%d_%H.%M.%S.%f")}'
        self.make_dirs(path_to_backup)
        self.create_backup(backup_name)
        for backup_type in ['rsc', 'backup']:
            self.download_backup(backup_type, backup_name, path_to_backup)
            self.remove_backup_from_device(backup_type, backup_name)
        self.connect.disconnect()

    def generate_identity(self):
        identity = self.connect.send_command('/system identity print')
        identity_name = re.match(r'^name: (.*)$', identity).group(1)
        allowed_identity_name = allowed_filename(identity_name)
        return allowed_identity_name

    def make_dirs(self, path_to_backup):
        try:
            mkdir(path_to_backup)
        except FileExistsError:
            pass
        backup_dir = self.connect.send_command(f'/file print detail where name={self.subdir}')
        if not backup_dir:
            # Crutch for create directory
            self.connect.send_command(f'/ip smb shares add directory={self.subdir} name=crutch_for_dir')
            self.connect.send_command('/ip smb shares remove [/ip smb shares find where name=crutch_for_dir]')

    def create_backup(self, backup_name):
        self.connect.send_command(f'/export file="{self.subdir}/{backup_name}"')
        self.connect.send_command(f'/system backup save dont-encrypt=yes name={self.subdir}/{backup_name}')
        # Wait for files creation
        sleep(self.delay)

    def download_backup(self, backup_type, backup_name, path_to_backup):
        src_file = f'{backup_name}.{backup_type}'
        dst_file = f'{path_to_backup}/{backup_name}.{backup_type}'
        direction = 'get'
        try:
            transfer_dict = file_transfer(
                self.connect,
                source_file=src_file,
                dest_file=dst_file,
                file_system=self.subdir,
                direction=direction,
                overwrite_file=True,
            )
        # Bug in scp_handler.py → https://github.com/ktbyers/netmiko/issues/2818 (fixed only in develop branch)
        except ValueError:
            pass
        # Wait for file download
        sleep(self.delay)

    def remove_backup_from_device(self, backup_type, backup_name):
        self.connect.send_command(f'/file remove {self.subdir}/{backup_name}.{backup_type}')


if __name__ == '__main__':
    args = args_parser()
    if args['hostlist']:
        with open(args['hostlist']) as file:
            hosts_list = file.readlines()
    elif args['host']:
        hosts_list = [args['host']]
    else:
        exit(0)
    devices_backup = hosts_to_devices(hosts_list)
    for device in devices_backup:
        device.run()
