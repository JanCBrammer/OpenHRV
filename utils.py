import re


def valid_mac(mac):

    regex = "[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
    valid = re.match(regex, mac.lower())

    return valid
