#!/usr/bin/env python

import sys
import hashlib
import os
import subprocess

print "#!/bin/bash"
print "adb shell mount -o remount,rw /"
print "adb shell mkdir /mnt/bootloader"
print "adb shell mount -t vfat /dev/block/sda1 /mnt/bootloader"

print "set -e"

def get_hash_and_size(filename):
    h = hashlib.sha1(open(filename).read()).hexdigest()
    s = os.stat(filename).st_size
    return (h, s)

def from_outdir(filename):
    out = os.environ['OUT']
    return os.path.join(out, filename)

def get_build_date():
    bd = subprocess.check_output("cat $OUT/system/build.prop | grep ro.build.date.utc | cut -d= -f2", shell=True)
    return bd

for f in ["efi/gummiboot.efi", "efi/shim.efi"]:
    h, s = get_hash_and_size(from_outdir(f))
    print "adb shell applypatch -c /mnt/bootloader/%s %s" % (os.path.basename(f), h)

for f,n in [("recovery.img","sda4"), ("boot.img","sda3"), ("droidboot.img","sda11")]:
    h, s = get_hash_and_size(from_outdir(f))
    print "adb shell applypatch -c EMMC:/dev/block/%s:%s:%s" % (n,s,h)

print "BD_ACTUAL=`adb shell getprop ro.build.date.utc | awk 'END{print}' | tr -d [:space:]`"
print "BD_ACTUAL=`echo -n $BD_ACTUAL`"
print "BD_EXPECTED=%s" % (get_build_date(),)
print 'if [ "$BD_ACTUAL" != "$BD_EXPECTED" ]; then'
print '    echo Incorrect build stamp, expected $BD_ACTUAL found $BD_EXPECTED'
print '    exit 1'
print 'fi'
print "echo All tests completed SUCCESS!"

