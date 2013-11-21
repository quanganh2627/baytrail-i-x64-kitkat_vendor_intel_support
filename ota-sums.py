#!/usr/bin/env python

import sys
import hashlib
import os
import subprocess
import zipfile

print "#!/bin/bash"
print "adb shell mount -o remount,rw /"
print "adb shell mkdir /mnt/bootloader"
print "adb shell mount -t vfat /dev/block/sda1 /mnt/bootloader"

print "set -e"

tfp = zipfile.ZipFile(sys.argv[1], "r")

def get_hash_and_size(filename):
    fd = tfp.open(filename)
    data = fd.read()
    fd.close()
    h = hashlib.sha1(data).hexdigest()
    s = len(data)
    return (h, s)

def get_build_date():
    ret = None
    fd = tfp.open("SYSTEM/build.prop")
    for line in fd.readlines():
        st = line.split("=")
        if len(st) != 2:
            continue
        if st[0] == "ro.build.date.utc":
            ret = st[1]
            break
    return ret

# TODO just glob all .efi files
for f in ["RADIO/gummiboot.efi", "RADIO/shim.efi"]:
    h, s = get_hash_and_size(f)
    print "adb shell applypatch -c /mnt/bootloader/%s %s" % (os.path.basename(f), h)

# TODO read device node name from recovery.fstab
for f,n in [("BOOTABLE_IMAGES/recovery.img","sda4"), ("BOOTABLE_IMAGES/boot.img","sda3"), ("BOOTABLE_IMAGES/fastboot.img","sda11")]:
    h, s = get_hash_and_size(f)
    print "adb shell applypatch -c EMMC:/dev/block/%s:%s:%s" % (n,s,h)

print "BD_ACTUAL=`adb shell getprop ro.build.date.utc | awk 'END{print}' | tr -d [:space:]`"
print "BD_ACTUAL=`echo -n $BD_ACTUAL`"
print "BD_EXPECTED=%s" % (get_build_date(),)
print 'if [ "$BD_ACTUAL" != "$BD_EXPECTED" ]; then'
print '    echo Incorrect build stamp, expected $BD_ACTUAL found $BD_EXPECTED'
print '    exit 1'
print 'fi'
print "echo All tests completed SUCCESS!"
