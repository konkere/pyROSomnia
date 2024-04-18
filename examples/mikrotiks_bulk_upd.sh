#!/bin/bash

URLS=(
        "https://example.com/ips-v4"
        "AS0000,AS00000,AS000000"
     )
LABELS=(
        "ExampleIPs"
        "ASNs"
       )
DEVICES=(
        "192.168.0.1"
        "192.168.1.1"
        )
COUNT_LABLES=${#LABELS[@]}
COUNT_DEVICES=${#DEVICES[@]}
BOT_TOKEN="000000000:AAAAAAaAA_0a0AA00aA0AAAA0aaAAaAaAa0"
CHAT_ID="-0000000000000"
API_LOGIN="login_for_upd_api"
API_PASS="PaSsFoRaPi"
LIST_NAME="list_name"

for (( LABLE=0; LABLE<$COUNT_LABLES; LABLE++ ))
    do
        for (( DEVICE=0; DEVICE<$COUNT_DEVICES; DEVICE++ ))
            do
                /PATH/TO/python3 /PATH/TO/mikrotik_addrlist_upd.py -n ${DEVICES[$DEVICE]} -u ${URLS[$LABLE]} -i $LIST_NAME -l ${LABELS[$LABLE]} -a $API_LOGIN -p $API_PASS -b $BOT_TOKEN -c $CHAT_ID
            done
    done
