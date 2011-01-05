#
# file: vendor/intel/x86_only_Android.mk
# Only compile this directory tree for IA buildsd.
#
# This makefile is copied to several places in the tree
# by a copyfile directive in the manifest.

ifeq ($(TARGET_ARCH),x86)
include $(all-subdir-makefiles)
endif
