"""Expected owner of the ETL S3 buckets, passed on every S3 call as ExpectedBucketOwner."""
import os
import re


def expected_bucket_owner():
    owner = os.environ.get("ETL_S3_BUCKET_OWNER", "")
    if not re.fullmatch(r"\d{12}", owner):
        raise RuntimeError("ETL_S3_BUCKET_OWNER must be set to the 12-digit AWS account id that owns the ETL buckets")
    return owner
