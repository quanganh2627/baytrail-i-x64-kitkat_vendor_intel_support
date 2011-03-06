#!/bin/bash

# Use the correct java...
# Uncomment this if you have a macro for setting the 1.6 java environment
# source ~/.bashrc
# aosp

# This script builds all variations/images cleanly.

z="none"

usage() {
    echo >&1 "Usage: $0 [-c <board_list> ] [ -j <jobs> ] [ -h ] [ -n ]"
    echo >&1 "       -c <board_list>:   defaults to $BOARDS"
    echo >&1 "       -j <jobs>:         defaults to $_jobs"
    echo >&1 "       -h:                this help message"
    echo >&1 "       -n:                Don't clean up the out/ directory first"
    exit 1
}

# Default the -j factor to a bit less than the number of CPUs
_jobs=`grep -c processor /proc/cpuinfo`
_jobs=$(($_jobs * 8 / 10))

# The full build list that this script knows how to build...
BOARDS=""

# x86 builds also available in AOSP/master and in honeycomb
BOARDS="$BOARDS full_x86"		# QEMU/emulator bootable disk
BOARDS="$BOARDS vbox"			# installer_vdi for virtualbox
BOARDS="$BOARDS android_disk"		# Bootable disk for virtualbox

# MRST targets (not supported in this tree)
# BOARDS="$BOARDS mrst_ref"
# BOARDS="$BOARDS ivydale"
# BOARDS="$BOARDS mrst_edv"
# BOARDS="$BOARDS crossroads"

# MFLD targets
BOARDS="$BOARDS mfld_cdk"
BOARDS="$BOARDS mfld_pr1"

# ARM builds (keep us honest)
BOARDS="$BOARDS full"

# SDK builds (both arm and x86)
BOARDS="$BOARDS sdk_x86"
BOARDS="$BOARDS sdk"


# Verify java version.
java_version=`javac -version 2>&1 | head -1`
case "$java_version" in
*1.6* )
    ;;
* )
    echo >&1 "Java 1.6 must be used, version $java_version found."
    exit 1
    ;;
esac

while getopts snhj:c: opt
do
    case "${opt}" in
    c)
        BOARDS="${OPTARG}"
        ;;
    j)
        if [ ${OPTARG} -gt 0 ]; then
            _jobs=${OPTARG}
        fi
        ;;
    n )
        dont_clean=1
        ;;
    s )
	SHOW="showcommands"
        ;;
    ? | h)
        usage
        ;;
    * )
        echo >&1 "Unhandled option ${opt}"
        usage
        ;;
    esac
done
shift $(($OPTIND-1))

if [ $# -ne 0 ]; then
    usage
fi

if [ ! -f build/envsetup.sh ]; then
    echo >&2 "Execute $0 from the top of your tree"
    exit 1
fi

# Start clean
if [ -z "$dont_clean" ]; then
    rm -rf out
fi

echo "Building with j-factor of $_jobs"
echo "Building for boards: $BOARDS"
echo

source build/envsetup.sh
for i in $BOARDS; do
  mv $i.log $i.log-1
  echo Building $i ....

  # make sure that PVR is clean
  z=`repo forall hardware/intel/PRIVATE/pvr -c git clean -d -f -x | wc -l`
  echo "Cleaned: $z files from the hardware/intel/PRIVATE/pvr directory"

  case "$i" in
  sdk )
    target=sdk
    lunch=sdk
    ;;

  sdk_x86 )
    target=sdk
    lunch=sdk_x86
    ;;

  full )
    target="droid"
    lunch=full
    ;;

  vbox | vbox_x86 )
    target="installer_vdi"
    lunch=vbox_x86
    ;;

  android_disk | android_disk_x86 )
    target="android_disk_vdi"
    lunch=vbox_x86
    ;;

  full_x86 )
    target="droid"
    lunch=full_x86
    ;;

  mrst_ref | mrst_edv | mfld_pr1 | mfld_cdk | crossroads | ivydale )
    target="$i"
    lunch=$target
    ;;

  * )
    echo >&2 "Target unknown. Guessing with target=\"droid $i\", lunch=\"$target\""
    target="droid $i"
    lunch=$target
    ;;
  esac

  lunch $lunch-eng
  time make -j$_jobs $target $SHOW > $i.log 2>&1
done
