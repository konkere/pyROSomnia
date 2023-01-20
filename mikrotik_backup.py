#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from time import sleep
from os import path, mkdir
from datetime import datetime
from argparse import ArgumentParser
from mikrotik_utils import generate_device
from netmiko import ConnectHandler, file_transfer


def args_parser():
    parser = ArgumentParser(description='RouterOS backuper.')
    parser.add_argument('-s', '--sshconf', type=str, help='Path to ssh_config.', required=False)
    parser.add_argument('-n', '--host', type=str, help='Host (in ssh_config).', required=True)
    parser.add_argument('-p', '--path', type=str, help='Path to backups.', required=True)
    arguments = parser.parse_args().__dict__
    return arguments


class Backuper:

    def __init__(self, host, path_to_backups, ssh_config_file='~/.ssh/config'):
        self.path_to_backup = path.join(path_to_backups, host)
        self.backup_name = f'{host}_{datetime.now().strftime("%Y.%m.%d_%H.%M.%S.%f")}'
        self.mikrotik_router = generate_device(ssh_config_file, host)
        self.connect = ConnectHandler(**self.mikrotik_router)
        self.subdir = 'backup'
        self.delay = 1

    def run(self):
        self.connect.enable()
        self.make_dirs()
        self.create_backup()
        for backup_type in ['rsc', 'backup']:
            self.download_backup(backup_type)
            self.remove_backup_from_device(backup_type)
        self.connect.disconnect()

    def make_dirs(self):
        try:
            mkdir(self.path_to_backup)
        except FileExistsError:
            pass
        backup_dir = self.connect.send_command(f'/file print detail where name={self.subdir}')
        if not backup_dir:
            # Crutch for create directory
            self.connect.send_command(f'/ip smb shares add directory={self.subdir} name=crutch_for_dir')
            self.connect.send_command('/ip smb shares remove [/ip smb shares find where name=crutch_for_dir]')

    def create_backup(self):
        self.connect.send_command(f'/export file="{self.subdir}/{self.backup_name}"')
        self.connect.send_command(f'/system backup save dont-encrypt=yes name={self.subdir}/{self.backup_name}')

    def download_backup(self, backup_type):
        src_file = f'{self.backup_name}.{backup_type}'
        dst_file = f'{self.path_to_backup}/{self.backup_name}.{backup_type}'
        direction = 'get'
        # Wait for files creation
        sleep(self.delay)
        transfer_dict = file_transfer(
            self.connect,
            source_file=src_file,
            dest_file=dst_file,
            file_system=self.subdir,
            direction=direction,
            overwrite_file=True,
        )

    def remove_backup_from_device(self, backup_type):
        self.connect.send_command(f'/file remove {self.subdir}/{self.backup_name}.{backup_type}')


if __name__ == '__main__':
    args = args_parser()
    device_backup = Backuper(
        ssh_config_file=args['sshconf'],
        host=args['host'],
        path_to_backups=args['path'],
    )

    device_backup.run()
