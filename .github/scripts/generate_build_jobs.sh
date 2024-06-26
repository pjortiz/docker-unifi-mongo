#!/bin/bash
set -e

if [ -z ${UPDATED_BUILD_INFO_FILES+x} ]; then
	echo "UPDATED_BUILD_INFO_FILES is unset"
	exit 1
fi

strategy="$( 
	for build_info_file in ${UPDATED_BUILD_INFO_FILES[@]}; do
		if ! [ -f "$build_info_file" ]; then
			echo "$build_info_file does not exist!" >&2
			exit 1
		fi
		cat $build_info_file | jq -c
	done | jq -cs '{ "fail-fast": false, matrix: { include: . } }'
)"

if [ -t 1 ]; then
	jq <<<"$strategy"
else
	cat <<<"$strategy"
fi