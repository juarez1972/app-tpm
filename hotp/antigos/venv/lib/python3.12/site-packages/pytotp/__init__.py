# coding: utf-8

__author__ = "cevin"

import random
import time
import math
import struct
import hmac
import platform

if platform.python_version() < '3':
    raise Exception("low python version");

class c2fa:

    keyRegenration = 30

    otpLength = 6

    __lut = {
        "A" : 0,   "B" : 1,
        "C" : 2,   "D" : 3,
        "E" : 4,   "F" : 5,
        "G" : 6,   "H" : 7,
        "I" : 8,   "J" : 9,
        "K" : 10,  "L" : 11,
        "M" : 12,  "N" : 13,
        "O" : 14,  "P" : 15,
        "Q" : 16,  "R" : 17,
        "S" : 18,  "T" : 19,
        "U" : 20,  "V" : 21,
        "W" : 22,  "X" : 23,
        "Y" : 24,  "Z" : 25,
        "2" : 26,  "3" : 27,
        "4" : 28,  "5" : 29,
        "6" : 30,  "7" : 31
    }
    @staticmethod
    def generate_secret_key(length=16):        
        b32 = "234567QWERTYUIOPASDFGHJKLZXCVBNM";
        string = "";

        loop = 0
        while loop<length:
            string = string+b32[random.randint(0,31)]
            loop+=1

        return string

    @staticmethod
    def get_timestamp():
        return math.floor(time.time()/__class__.keyRegenration)


    @staticmethod
    def b32_decode(string):
        b32 = str(string).upper();

        #import re
        #if not re.search('/^[ABCDEFGHIJKLMNOPQRSTUVWXYZ234567]+$/', b32):
        #    raise Exception('Invalid characters in the base32 string.');

        l = len(b32);
        n = 0;
        j = 0;
        i = 0;
        binary = "";

        while i<l:

            n = n << 5;
            n = n + __class__.__lut[b32[i]];
            j = j + 5;

            if (j >= 8):
                j = j - 8;
                binary = "%s%s" % (binary, chr((n & (0xFF << j)) >> j) );

            i+=1

        return binary;

    @staticmethod
    def oath_hotp(key, counter):
        if len(key) < 8:
            raise Exception('Secret key is too short. Must be at least 16 base 32 characters');

        bin_counter = struct.pack('L', 0) + struct.pack('L', counter);
        hash = hmac.new(key.encode(encoding='utf-8'),bin_counter,'SHA1').hexdigest();

        return str(__class__.oath_truncate(hash)).rjust(__class__.otpLength,'0');

    @staticmethod
    def oath_truncate(hash):    
        offset = ord(hash[19]) & 0xf;

        return (
            ((ord(hash[offset+0]) & 0x7f) << 24 ) |
            ((ord(hash[offset+1]) & 0xff) << 16 ) |
            ((ord(hash[offset+2]) & 0xff) << 8 ) |
            (ord(hash[offset+3]) & 0xff)
        ) % pow(10, __class__.otpLength);

    @staticmethod
    def verify_key(b32seed, key, window = 10):

        timeStamp = __class__.get_timestamp();

        binarySeed = __class__.b32_decode(b32seed);
        ts = timeStamp-window

        while ts<=timeStamp:
            if __class__.oath_hotp(binarySeed,ts) == key:
                return True;
            ts+=1

        return False;


class pytotp(c2fa):
    pass