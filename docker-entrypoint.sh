#!/bin/sh
set -e

# Das gemountete Volume gehört beim ersten Start root
if [ -d /data ]; then
    chown -R appuser:appuser /data
fi

exec setpriv --reuid=appuser --regid=appuser --init-groups --no-new-privs "$@"
