#!/bin/bash

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

# Default the -j factor to the number of CPUs
_jobs=`grep -c processor /proc/cpuinfo`

# Default board list
BOARDS=""
BOARDS="$BOARDS ivydale"
BOARDS="$BOARDS full_x86"
BOARDS="$BOARDS mrst_ref"
BOARDS="$BOARDS mrst_edv"
BOARDS="$BOARDS crossroads"

while getopts nhj:c: opt
do
    case "${opt}" in
    c)
        BOARDS="${OPTARG}"
        ;;
    j)
        if [ ${OPTARG} -gt 0 ]; then
            _jobs=${OPTARG}
        else
            _jobs=`grep -c processor /proc/cpuinfo`
        fi
        ;;
    n )
        dont_clean=1
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
  lunch $i-eng
  mv $i.log $i.log-1
  echo Building $i ....

  # make sure that PVR is clean
  z=`repo forall hardware/intel/PRIVATE/pvr -c git clean -d -f -x | wc -l`
  echo "Cleaned: $z files from the hardware/intel/PRIVATE/pvr directory"

  case "$i" in
  full_x86 )
    target=installer_vdi
    time make -j$_jobs $target showcommands > $i.log 2>&1

    # Build again (no target) to pick up some objects needed by the NDK build.
    time make -j$_jobs showcommands >> $i.log 2>&1
    ;;

  * )
    target=$i
    time make -j$_jobs $target showcommands >> $i.log 2>&1
    ;;
  esac

  echo

done
