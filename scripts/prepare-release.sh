#!/bin/bash

set -e

RELEASE_VERSION=$1
RELEASE_NOTES_PATH="docs/release-${RELEASE_VERSION}.md"

if [[ $(git rev-parse --abbrev-ref HEAD) != develop ]]
then
    echo "Must be on the develop branch"
    exit 1
fi

git pull
git checkout -b "release/${RELEASE_VERSION}"
set -i "s/VERSION=.*/${RELEASE_VERSION}/g" Config
cp docs/template.md ${RELEASE_NOTES_PATH}
set -i "s/{{release_version}}/${RELEASE_VERSION}/g" ${RELEASE_NOTES_PATH}
set -i "s/{{release_date}}/$(date +\"%Y/%m/%d\")/g" ${RELEASE_NOTES_PATH}
git add ${RELEASE_NOTES_PATH}
