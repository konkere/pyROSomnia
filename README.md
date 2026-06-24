![pyROSomnia](/.github/img/pyROSomnia.svg)

A set of Python scripts for maintaining RouterOS (MikroTik) devices: automatic configuration backups and firewall address-list updates from external sources. Both scripts can send reports to Telegram.

## Components

- **`mikrotik_backup.py`** — pulls a configuration export (`.rsc`) and a system backup (`.backup`) from devices, stores them locally in per-device folders, and prunes outdated copies. Works over SSH/SCP.
- **`mikrotik_addrlist_upd.py`** — syncs a firewall address-list on the device with an IP list from external sources (URLs and/or ASNs). Works over SSH or the RouterOS API.

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Connecting to devices

### SSH (backups and address-lists)

Hosts are defined in `~/.ssh/config` (or in a file passed via `-s`). See `examples/ssh_config-dist`:

```
Host Mikrotik_1
    HostName 192.168.0.1
    Port 22
    User sshbackup
    IdentitiesOnly yes
    IdentityFile ~/.ssh/authorized_keys/mikrotik_1_rsa
```

The public key must be imported on the device for the matching user
(`/user ssh-keys import`). For backups, the account only needs rights to read,
export, and manage files.

### RouterOS API (address-lists only)

An alternative to SSH for `mikrotik_addrlist_upd.py`: connect via the API with a
login and password (`-a` / `-p`). The `api` service must be enabled on the device
(`/ip service`).

## Backing up configuration

```bash
python mikrotik_backup.py -s ~/.ssh/config -n Mikrotik_1,Mikrotik_2 -p /path/to/backups/ -t 90
```

For each device a subfolder named after its identity is created, containing
`<identity>_<date_time>.rsc` and `.backup`. Temporary files on the device are
removed after they are downloaded.

| Argument | Purpose | Required |
|----------|---------|----------|
| `-s`, `--sshconf` | Path to ssh_config (defaults to `~/.ssh/config`) | no |
| `-n`, `--hosts` | A host or comma-separated hosts (names from ssh_config) | no* |
| `-f`, `--hostfile` | Path to a file with a list of hosts (one per line) | no* |
| `-p`, `--path` | Directory to store backups in | yes |
| `-t`, `--lifetime` | Retention in days (older copies are deleted) | no |
| `-b`, `--bottoken` | Telegram bot token | no |
| `-c`, `--chatid` | Telegram chat ID | no |

\* Provide either `-n` or `-f`. The host-file format is shown in `examples/mikrotiks_for_backup.lst-dist`.

## Updating an address-list

Over SSH:

```bash
python mikrotik_addrlist_upd.py -s ~/.ssh/config -n Mikrotik_1 \
    -u https://example.com/ips-v4 -i blocklist -l ExampleIPs
```

Over the API:

```bash
python mikrotik_addrlist_upd.py -n 192.168.0.1 -a login -p password \
    -u https://example.com/ips-v4,AS12345 -i blocklist -l ExampleIPs
```

`-u` may mix URLs and ASNs separated by commas: IPs/subnets are extracted from URLs,
and announced prefixes are pulled for ASNs. The script compares the fresh list with
what is already on the device (matched by the `-l` label) and applies only the
difference — adding new addresses and removing ones that disappeared.

| Argument | Purpose | Required |
|----------|---------|----------|
| `-s`, `--sshconf` | Path to ssh_config (SSH mode) | no |
| `-n`, `--host` | Host from ssh_config (SSH) or device IP/address (API) | yes |
| `-a`, `--login` | API login | no** |
| `-p`, `--password` | API password | no** |
| `-u`, `--url` | URLs and/or ASNs with IP lists, comma-separated | yes |
| `-i`, `--list` | Address-list name on the device | yes |
| `-l`, `--label` | Label (comment) used to track the list | yes |
| `-b`, `--bottoken` | Telegram bot token | no |
| `-c`, `--chatid` | Telegram chat ID | no |

\** The mode is chosen automatically: `-s` selects SSH, `-a` + `-p` selects the API.

## Telegram reports

If `-b` and `-c` are provided, a report is sent on completion: for backups — which
files were saved and their sizes per device; for address-lists — what was added and
removed. Without these arguments the scripts run silently.

## Bulk runs

Iterating over several devices and several lists is easy to automate with a wrapper —
a ready example is in `examples/mikrotiks_bulk_upd.sh`. Both scripts are suitable for
running from cron.

## License

MIT — see [LICENSE](LICENSE).