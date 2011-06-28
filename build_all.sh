#!/bin/bash

# Use the correct java...
# Uncomment this if you have a macro for setting the 1.6 java environment
# source ~/.bashrc
# aosp

# This script builds all variations/images cleanly.


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
BOARDS="$BOARDS mfld_pr2"

# ARM builds (keep us honest)
BOARDS="$BOARDS full"

# SDK builds (both arm and x86)
BOARDS="$BOARDS sdk_x86"
BOARDS="$BOARDS sdk"

# List of projects that need scrubbing before each build
DIRTY_LIST="hardware/intel/PRIVATE/pvr hardware/ti/wlan hardware/intel/linux-2.6"

BUILD_TYPE=eng

usage() {
    echo >&1 "Usage: $0 [-c <board_list> ] [ -j <jobs> ] [ -h ] [ -n ] [ -N ]"
    echo >&1 "       -c <board_list>:   defaults to $BOARDS"
    echo >&1 "       -j <jobs>:         defaults to $_jobs"
    echo >&1 "       -t:                Build type. Defaults to ${BUILD_TYPE}"
    echo >&1 "       -h:                this help message"
    echo >&1 "       -n:                Don't clean up the out/ directory first"
    echo >&1 "       -N:                Don't clean up the (selected) source projects"
    echo >&1 "                          (be careful with this)"
    echo >&1 "List of source projects to clean:"
    echo >&1 "  $DIRTY_LIST"
    echo >&1
    exit 1
}


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

while getopts t:snNhj:c: opt
do
    case "${opt}" in
    t)
        BUILD_TYPE=${OPTARG}
        ;;
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
    N )
        dont_clean_dirty=1
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

  if [ -d .repo -a -z "$dont_clean_dirty" ]; then
    for _dirty in $DIRTY_LIST
    do
      z=`repo forall $_dirty -c git clean -d -f -x | wc -l`
      echo "Cleaned: $z files from the $_dirty directory"
    done
  fi

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

  mrst_ref | mrst_edv | mfld_pr1 | mfld_pr2 | mfld_cdk | crossroads | ivydale )
    target="$i"
    lunch=$target
    ;;

  * )
    echo >&2 "Target unknown. Guessing with target=\"droid $i\", lunch=\"$target\""
    target="droid $i"
    lunch=$target
    ;;
  esac

  lunch $lunch-$BUILD_TYPE
  time make -j$_jobs $target $SHOW > $i.log 2>&1
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo -e >&2 "Error: $rc returned from build\n\n"
    echo -e >>$i.log "\nError: $rc returned from build"
  fi


  case "$i" in
  sdk | sdk_x86 )
    TODAY=`date '+%Y%m%d'`
    SDK=sdk-release-$TODAY
    mkdir -p $SDK
    bash -c -x "cp out/host/linux-x86/sdk/android-sdk_eng.${LOGNAME}_linux-x86.zip $SDK/$i.zip" >> $i.log 2>&1
    ;;

  full | full_x86)
    # We also build libm.a - required for making an NDK
    mmm bionic/libm >> $i.log 2>&1
    ;;
  esac
done
