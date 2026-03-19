#!/bin/bash
set -e

# 1. Write credentials to the required file (if provided via Env Vars)
echo "${S3_ACCESS_KEY}:${S3_SECRET_KEY}" > /etc/passwd-s3fs
chmod 600 /etc/passwd-s3fs

# 2. Create the mount point
mkdir -p /eodata

# 3. Mount the CDSE bucket
# -f keeps s3fs in the foreground so the container doesn't exit immediately
# use _allow_other to let non-root users see the data
s3fs DIAS /eodata \
    -o passwd_file=/etc/passwd-s3fs \
    -o url=https://eodata.dataspace.copernicus.eu/ \
    -o use_path_request_style \
    -o allow_other \
    -f
