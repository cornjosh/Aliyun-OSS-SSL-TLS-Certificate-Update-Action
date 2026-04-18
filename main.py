import argparse
from datetime import datetime, timezone

import oss2


def normalize_endpoint(region_or_endpoint: str) -> str:
    value = (region_or_endpoint or "").strip()
    if not value:
        raise ValueError("region is required")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if "." in value:
        return f"https://{value}"
    if value.startswith("oss-"):
        return f"https://{value}.aliyuncs.com"
    return f"https://oss-{value}.aliyuncs.com"


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def cert_not_expired(cert_info) -> bool:
    if not cert_info or not cert_info.valid_end_date:
        return False
    exp = datetime.strptime(cert_info.valid_end_date, "%b %d %H:%M:%S %Y GMT").replace(
        tzinfo=timezone.utc
    )
    return exp > datetime.now(timezone.utc)


def find_cname(bucket: oss2.Bucket, domain: str):
    result = bucket.list_bucket_cname()
    for c in result.cname:
        if c.domain == domain:
            return c
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Update OSS CNAME certificate")
    parser.add_argument("--access-key-id", required=True)
    parser.add_argument("--access-key-secret", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--certificate-path", required=True)
    parser.add_argument("--private-key-path", required=True)
    args = parser.parse_args()

    endpoint = normalize_endpoint(args.region)
    cert_content = read_file(args.certificate_path)
    key_content = read_file(args.private_key_path)

    auth = oss2.AuthV4(args.access_key_id, args.access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name=args.bucket, region=args.region)

    cname_info = find_cname(bucket, args.domain)
    if not cname_info:
        print(f"CNAME domain not found on bucket: {args.domain}")
        return 1

    if cname_info.certificate and cert_not_expired(cname_info.certificate):
        cert = oss2.models.CertInfo(
            previous_cert_id=cname_info.certificate.cert_id,
            certificate=cert_content,
            private_key=key_content,
            force=True,
        )
        print(f"Updating certificate for domain {args.domain} with previous cert id")
    else:
        cert = oss2.models.CertInfo(
            certificate=cert_content, private_key=key_content, force=True
        )
        print(f"Creating/rebinding certificate for domain {args.domain}")

    req = oss2.models.PutBucketCnameRequest(args.domain, cert)
    bucket.put_bucket_cname(req)
    print("OSS CNAME certificate update completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
