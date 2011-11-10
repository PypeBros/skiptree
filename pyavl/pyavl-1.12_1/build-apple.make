# -*-make-*-
# targets: build install clean topclean
# contains Mac OS X specific directives

MAKEFILE        = build-apple.make
PYTHON_HOME    := /System/Library/Frameworks/Python.framework/Versions/2.5
PYTH           := python2.5
PYTHON_INCL     = $(PYTHON_HOME)/include/$(PYTH)
PYTHON_EXTDIR   = /Library/Python/$(PYTH)/site-packages

BUILD_DIR       = build
OBJ_DIR         = $(BUILD_DIR)/obj.osx-applebuild
LIB_DIR         = $(BUILD_DIR)/lib.osx-applebuild

# options taken from output of setup.py
CFLAGS          = -fno-strict-aliasing -Wno-long-double -no-cpp-precomp \
                    -mno-fused-madd -fno-common \
                    -Wall -Wstrict-prototypes \
                    -O3
OTHER_CFLAGS    = -Wno-parentheses -Wno-uninitialized
DEFS            = -DHAVE_AVL_VERIFY -DAVL_FOR_PYTHON

LINK_FLAGS      = -Wl,-F. -framework Python

include build-osx-common.make
