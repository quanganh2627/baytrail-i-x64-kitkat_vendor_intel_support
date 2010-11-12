#!/bin/bash

# This script builds all variations/images cleanly.

z="none"

# If BUILD_NUM_CPUS is not already defined in your environment,
# define it as the double of HOST_NUM_CPUS. This is used to
# run make commands in parallel, as in 'make -j$BUILD_NUM_CPUS'
#
if [ -z "$BUILD_NUM_CPUS" ] ; then
    HOST_NUM_CPUS=`cat /proc/cpuinfo | grep processor | wc -l`
    BUILD_NUM_CPUS=`expr $HOST_NUM_CPUS \* 2`
fi

# Build for the VirtualBox Emulator
BOARDS=""
BOARDS="$BOARDS ivydale"
BOARDS="$BOARDS full_x86"
BOARDS="$BOARDS mrst_ref"
BOARDS="$BOARDS mrst_edv"
BOARDS="$BOARDS crossroads"

# Start clean
rm -rf out

source build/envsetup.sh
for i in $BOARDS; do
  lunch $i-eng
  mv $i.log $i.log-1
  echo Building $i ....

  # make sure that PVR is clean
  z=`repo forall hardware/intel/PRIVATE/pvr -c git clean -d -f -x | wc -l`
  echo Cleaned: $z

  case "$i" in
  full_x86 )
    target=installer_vdi
    ;;
  * )
    target=$i
    ;;
  esac

  time make -j$BUILD_NUM_CPUS $target showcommands > $i.log 2>&1
  echo

done
