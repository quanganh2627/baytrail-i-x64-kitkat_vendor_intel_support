#
# file: vendor/intel/ds_switch_Android.mk
# Select which "flavor" to build.
#
# This makefile is copied to several places in the tree
# by a copyfile directive in the manifest.

LOCAL_PATH := $(my-dir)

ALL_MAKEFILES  := $(call first-makefiles-under,$(LOCAL_PATH))
DSDS_MAKEFILES := $(foreach v,$(ALL_MAKEFILES),$(if $(findstring -dsds,$(v)),$(v),))
STD_MAKEFILES := $(filter-out $(DSDS_MAKEFILES), $(ALL_MAKEFILES))
STD_FOR_FLAVORS := $(foreach dir, $(DSDS_MAKEFILES), $(subst -dsds,,$(dir)))
ALL_BUT_FLAVORS := $(filter-out $(DSDS_MAKEFILES) $(STD_FOR_FLAVORS), $(ALL_MAKEFILES))

ifeq (dsds,$(USE_FLAVOR))
include $(DSDS_MAKEFILES) $(ALL_BUT_FLAVORS)
else
include $(STD_MAKEFILES)
endif
