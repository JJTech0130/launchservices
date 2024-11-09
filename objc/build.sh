#!/usr/bin/env bash
set -e

xcrun clang ./test.m -o test -framework Foundation -fobjc-arc -Wno-deprecated-declarations -F. -framework CoreServicesStore
./test