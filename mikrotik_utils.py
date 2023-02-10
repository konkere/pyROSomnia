#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
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


def generate_ip_pattern():
    ip_b = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    mask = r'(\/(([1-3][0-9]|[1-9])[^0-9]))?'
    dot = r'\.'
    re_pattern = (ip_b + dot) * 3 + ip_b + mask
    return re_pattern


def allowed_filename(filename):
    allowed_pattern = re.compile('[^A-z0-9!@#$%^&-]')
    allowed_name = re.sub(allowed_pattern, '_', filename)
    return allowed_name


def print_output(device, command, delay=1, timeout=60):
    output = None
    for iteration in range(timeout):
        output = device.send_command(command, read_timeout=float(timeout))
        if output:
            return output
        else:
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
