#!/bin/bash
# This script is used to flash modem firmware
# after invalidate_osip or reboot recovery.

function usage {
    echo "Usage: flash_modem.sh SMB_SUNRISE_MODEM...VERSION_MIPI_HSI.fls"
}

if [ $# -ne 1 ]
then
    echo "Invalid number of parameters."
    usage
    exit -1
fi


if [ -f $1 ]
then
    echo "Flashing modem: $1"
    fastboot flash /tmp/modem.fls $1
    fastboot oem system loadfw_modem.sh /tmp/modem.fls
else
    echo "The firmwware modem file '$1' doesn't exist."
    usage
    exit -2
fi
