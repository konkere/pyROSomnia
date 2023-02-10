#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from time import sleep
from threading import Thread
from datetime import datetime
from argparse import ArgumentParser
from os import path, mkdir, environ
from netmiko import ConnectHandler, file_transfer
from mikrotik_utils import generate_device, allowed_filename, print_output, remove_old_files


def args_parser():
    parser = ArgumentParser(description='RouterOS backuper.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str, help='Single Host (in ssh_config).', required=False)
    parser.add_argument('-l', '--hostlist', type=str, help='Path to file with list of Hosts.', required=False)
    parser.add_argument('-p', '--path', type=str, help='Path to backups.', required=True)
    parser.add_argument('-t', '--lifetime', type=int, help='Files (backup) lifetime (in days).', required=False)
    arguments = parser.parse_args().__dict__
    return arguments


def hosts_to_devices(hosts):
    devices = []
    ssh_config_file = args_in['sshconf'] if args_in['sshconf'] else path.join(environ.get('HOME'), '.ssh/config')
    for hostname in hosts:
        hostname = hostname.strip()
        if hostname:
            host_device = Backuper(
                ssh_config_file=ssh_config_file,
                host=hostname,
                path_to_backups=args_in['path'],
                lifetime=args_in['lifetime']
            )
            devices.append(host_device)
    return devices


class Backuper(Thread):

    def __init__(self, host, path_to_backups, ssh_config_file, lifetime, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_to_backups = path_to_backups
        self.mikrotik_router = generate_device(ssh_config_file, host)
        self.connect = ConnectHandler(**self.mikrotik_router)
        self.lifetime = lifetime
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
        if self.lifetime:
            remove_old_files(path_to_backup, self.lifetime)

    def generate_identity(self):
        command = '/system identity print'
        identity = print_output(self.connect, command, self.delay)
        identity_name = re.match(r'^name: (.*)$', identity).group(1)
        allowed_identity_name = allowed_filename(identity_name)
        return allowed_identity_name

    def make_dirs(self, path_to_backup):
        try:
            mkdir(path_to_backup)
        except FileExistsError:
            pass
        command = f'/file print detail where name={self.subdir}'
        backup_dir = print_output(self.connect, command, self.delay)
        if not backup_dir:
            # Crutch for create directory
            self.connect.send_command(f'/ip smb shares add directory={self.subdir} name=crutch_for_dir')
            self.connect.send_command('/ip smb shares remove [/ip smb shares find where name=crutch_for_dir]')

    def create_backup(self, backup_name):
        file_path_name = f'{self.subdir}/{backup_name}'
        self.connect.send_command(f'/export file={file_path_name}')
        self.connect.send_command(f'/system backup save dont-encrypt=yes name={file_path_name}')
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


def main():
    if args_in['hostlist']:
        with open(args_in['hostlist']) as file:
            hosts_list = file.readlines()
    elif args_in['host']:
        hosts_list = [args_in['host']]
    else:
        exit(0)
    devices_backup = hosts_to_devices(hosts_list)
    for device in devices_backup:
        device.start()
    for device in devices_backup:
        device.join()


if __name__ == '__main__':
    args_in = args_parser()
    main()
