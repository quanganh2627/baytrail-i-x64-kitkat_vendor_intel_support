#!/bin/bash
#
# This script will use the fastboot command to:
#  o  partition your SDCARD or NAND
#  o  format the file systems on the various partitions
#  o  flash the contents of the boot and system file systems

_error=0
_boot=sd
_cmd=`basename $0`


# Exit the script on failure of a command
function exit_on_failure {
    if [ "$_debug" ]; then
        set -x
    fi
    $@
    if [ $? -ne 0 ]; then
        exit $?
    fi
}

# Fastboot doesn't return a non-zero exit value when a command fails.
# We have to test stderr for the error.
function do_fastboot {
    if [ "$_debug" ]; then
        set -x
    fi
    _error=0
    _rv=`fastboot $@ 2>&1 | tee /dev/tty`

    case "$_rv" in
    *OKAY* )
        # Success
        ;;
    *FAILED* )
        _error=1
        ;;
    * )
        echo >&2 "$_cmd: Unknown response from fastboot"
        _error=1
        ;;
    esac

    return $_error
}

function usage {
    echo "Usage: $_cmd [-d nand|sd] [-c <dir>]"
    echo "       -d: select boot device. (default $_boot)"
    echo "       -c: find images in <dir>"
}

function main {
    while getopts c:xd: opt
    do
        case "${opt}" in
        c )
            if [ ! -d "${OPTARG}" ]; then
                _error=1
            fi
            cd ${OPTARG}
            ;;
        d )
            _boot=${OPTARG}
            ;;
        x )
            _debug=1
            set -x
            ;;
        * )
            _error=1
        esac
    done

    case "$_boot" in
    sd )
        _device=/dev/mmcblk0
        ;;
    nand )
        _device=/dev/nda
        ;;
    * )
        _error=1
        ;;
    esac

    if [ $_error -ne 0 ]; then
        usage
        exit 1;
    fi

    _boot_gz=boot.tar.gz
    _system_gz=system.tar.gz

    if [ ! -r "$_boot_gz" ]; then
        echo >&2 "$_cmd: Can not find $_boot_gz."
        _error=1
    fi
    if [ ! -r "$_system_gz" ]; then
        echo >&2 "$_cmd: Can not find $_system_gz."
        _error=1
    fi
    if [ "$_error" -ne 0 ]; then
        usage
        exit 1
    fi

    echo -n "Setting bootdev to $_boot. "
    exit_on_failure do_fastboot oem bootdev $_boot

    echo -n "Setting tarball_origin to root. "
    exit_on_failure do_fastboot oem tarball_origin root

    echo -n /sbin/PartitionDisk.sh $_device
    exit_on_failure do_fastboot oem system /sbin/PartitionDisk.sh $_device

    exit_on_failure do_fastboot erase recovery
    exit_on_failure do_fastboot erase cache
    exit_on_failure do_fastboot erase userdata
    exit_on_failure do_fastboot erase media
    exit_on_failure do_fastboot erase boot
    exit_on_failure do_fastboot erase system

    echo "Flashing boot image: $_boot_gz"
    exit_on_failure do_fastboot flash boot $_boot_gz
    echo "Flashing system image: $_system_gz"
    exit_on_failure do_fastboot flash system $_system_gz

    echo -n "Syncing storage devices"
    exit_on_failure do_fastboot oem system sync

    exit_on_failure do_fastboot continue
}

main $@
