#!/bin/bash
set -e

if [ -z ${UPDATED_BUILD_INFO_FILES+x} ]; then
	echo "UPDATED_BUILD_INFO_FILES is unset"
	exit 1
fi

readarray -t files <<< "$UPDATED_BUILD_INFO_FILES"

count=${#files[@]}

strategy="$( 
	for build_info_file in ${UPDATED_BUILD_INFO_FILES[@]}; do
		echo "Proccesing '$build_info_file'..." >&2 # output on stderr for debuging aid
		if ! [ -f "$build_info_file" ]; then
			echo "$build_info_file does not exist!" >&2
			exit 1 # fast fail if file missing
		fi
		cat $build_info_file | jq -c
	done | jq -cs '{ "fail-fast": false, matrix: { include: . } }'
)"
 
echo "strategy count: $(echo "$strategy" | jq '.matrix.include | length')" >&2 # output on stderr for debuging aids
echo "expected count: $count" >&2 # output on stderr for debuging aid

if [[ "$(echo "$strategy" | jq '.matrix.include | length')" != "$count" ]]; then
	echo "Failed to generate jods" >&2
	exit 1
fi

echo "strategy: $strategy"  >&2 # output on stderr for debuging aid

if [ -t 1 ]; then
	jq <<<"$strategy"
else
	cat <<<"$strategy"
fi