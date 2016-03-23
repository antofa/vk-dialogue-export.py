# -*- coding: utf-8 -*-

import codecs
import ConfigParser
import datetime
import json
import sys
import urllib2
from urllib import urlencode

import vk_auth


def _api(method, params, token):
    params.append(("access_token", token))
    url = "https://api.vk.com/method/%s?%s" % (method, urlencode(params))
    return json.loads(urllib2.urlopen(url).read())["response"]

# read config values

Config = ConfigParser.ConfigParser()
Config.read("config.ini")

login = Config.get("auth", "username")
password = Config.get("auth", "password")
token = Config.get("auth", "token")
messages_id = Config.get("messages", "chat_id")
messages_type = Config.get("messages", "chat_type")
app_id = Config.get("application", "app_id")

# some chat preparation

if messages_type == "interlocutor":
    is_chat = False
elif messages_type == "chat":
    is_chat = True
else:
    sys.exit("Messages type must be either interlocutor or chat.")

if not token:
# auth to get token

    try:
        token, user_id = vk_auth.auth(login, password, app_id, 'messages')
    except RuntimeError:
        sys.exit("Incorrect login/password. Please check it.")

    sys.stdout.write('Authorized vk (token = %s)\n' % token)

# get some information about chat

selector = "chat_id" if is_chat else "uid"
messages = _api("messages.getHistory", [(selector, messages_id)], token)

out = codecs.open(
    'vk_exported_dialogue_%s%s.txt' % ('ui' if not is_chat else 'c', messages_id),
    "w+", "utf-8"
)

if not is_chat:
    human_uids = [messages[1]["uid"]]
else:
    chat_info = _api("messages.getChat", [('chat_id', messages_id)], token)
    # fixme: receives not all human_ids in some chats
    human_uids = chat_info['users']

# Export details from uids
human_details = _api(
    "users.get",
    [("uids", ','.join(str(v) for v in human_uids))],
    token
)

human_details_index = {}
for human_detail in human_details:
    human_details_index[human_detail["uid"]] = human_detail

def write_message(who, to_write):
    if who not in human_details_index.keys():
        human_details_index[who] = {'first_name': 'UNKNOWN', 'last_name': 'UNKNOWN'}

    out.write(u'[{date}] {full_name}:\n {message} \n\n\n'.format(**{
            'date': datetime.datetime.fromtimestamp(
                int(to_write["date"])).strftime('%Y-%m-%d %H:%M:%S'),

            'full_name': '%s %s' % (
                human_details_index[who]["first_name"], human_details_index[who]["last_name"]),

            'message': to_write["body"].replace('<br>', '\n')
        }
    ))


mess = 0
max_part = 200  # Due to vk.api

cnt = messages[0]
sys.stdout.write("Count of messages: %s\n" % cnt)

while mess != cnt:
    # Try to retrieve info anyway

    while True:
        try:
            message_part = _api(
                "messages.getHistory",
                [(selector, messages_id), ("offset", mess), ("count", max_part), ("rev", 1)],
                token
            )
        except Exception as e:
            sys.stderr.write('Got error %s, continue...\n' % e)
            continue
        break

    try:
        for i in range(1, 201):
            write_message(message_part[i]["uid"], message_part[i])
    except IndexError:
        break

    result = mess + max_part
    if result > cnt:
        result = (mess - cnt) + mess
    mess = result
    sys.stdout.write("Exported %s messages of %s\n" % (mess, cnt))

out.close()
sys.stdout.write('Export done!\n')
