import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple

import oss2
from oss2.models import CnameInfo


def _get_input(name: str, required: bool = False, default: Optional[str] = None) -> str:
    env_name = f"INPUT_{name.replace('-', '_').upper()}"
    value = os.getenv(env_name, default)
    if required and (value is None or str(value).strip() == ""):
        raise ValueError(f"Missing required input: {name}")
    return "" if value is None else value


def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _build_endpoint_from_region(region: str) -> str:
    region_value = region.strip()
    if not region_value:
        raise ValueError("region cannot be empty")
    return f"https://oss-{region_value}.aliyuncs.com"


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _resolve_cert_material(
    certificate: str, private_key: str, certificate_path: str, private_key_path: str
) -> Tuple[str, str]:
    cert = certificate.strip() if certificate else ""
    key = private_key.strip() if private_key else ""

    if not cert and certificate_path:
        cert = _read_text_file(certificate_path).strip()
    if not key and private_key_path:
        key = _read_text_file(private_key_path).strip()

    if not cert or not key:
        raise ValueError(
            "Certificate/private key not provided. Use content inputs or path inputs."
        )

    return cert, key


def _set_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"Output {name}={value}")


class OSSUpdater:
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket_name: str,
        region: str,
    ):
        auth = oss2.AuthV4(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(
            auth, endpoint, bucket_name=bucket_name, region=region
        )

    def _get_matched_cname(self, target_cname: str) -> Optional[CnameInfo]:
        list_result = self.bucket.list_bucket_cname()
        for c in list_result.cname:
            if c.domain == target_cname:
                return c
        return None

    @staticmethod
    def _is_cert_valid(cname_info: CnameInfo) -> bool:
        if not cname_info.certificate or not cname_info.certificate.valid_end_date:
            return False
        exp_date_obj = datetime.strptime(
            cname_info.certificate.valid_end_date,
            "%b %d %H:%M:%S %Y GMT",
        ).replace(tzinfo=timezone.utc)
        return exp_date_obj > datetime.now(timezone.utc)

    def update(
        self, target_cname: str, certificate: str, private_key: str, force: bool
    ) -> CnameInfo:
        cname_info = self._get_matched_cname(target_cname)
        if not cname_info:
            raise RuntimeError(f"Target cname not found in bucket: {target_cname}")

        create_with_previous = False
        if cname_info.certificate and self._is_cert_valid(cname_info):
            create_with_previous = True

        if create_with_previous:
            cert = oss2.models.CertInfo(
                previous_cert_id=cname_info.certificate.cert_id,
                certificate=certificate,
                private_key=private_key,
                force=force,
            )
            print(
                f"Certificate is valid, rotate with previous_cert_id={cname_info.certificate.cert_id}"
            )
        else:
            cert = oss2.models.CertInfo(
                certificate=certificate,
                private_key=private_key,
                force=force,
            )
            print("Certificate expired or not bound, create new certificate binding")

        request = oss2.models.PutBucketCnameRequest(cname_info.domain, cert)
        self.bucket.put_bucket_cname(request)

        refreshed = self._get_matched_cname(target_cname)
        if not refreshed:
            raise RuntimeError(
                "Certificate update completed but failed to fetch refreshed cname info"
            )
        return refreshed


def main() -> int:
    try:
        access_key_id = _get_input("access-key-id", required=True)
        access_key_secret = _get_input("access-key-secret", required=True)
        region = _get_input("region", required=True)
        bucket_name = _get_input("bucket-name", required=True)
        target_cname = _get_input("target-cname", required=True)
        endpoint = _build_endpoint_from_region(region)

        certificate = _get_input("certificate")
        private_key = _get_input("private-key")
        certificate_path = _get_input("certificate-path")
        private_key_path = _get_input("private-key-path")
        force = _is_true(_get_input("force", default="true"))

        certificate, private_key = _resolve_cert_material(
            certificate,
            private_key,
            certificate_path,
            private_key_path,
        )

        updater = OSSUpdater(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket_name=bucket_name,
            region=region,
        )

        result = updater.update(
            target_cname=target_cname,
            certificate=certificate,
            private_key=private_key,
            force=force,
        )

        cert_id = ""
        valid_end_date = ""
        if result.certificate:
            cert_id = result.certificate.cert_id or ""
            valid_end_date = result.certificate.valid_end_date or ""

        _set_output("updated", "true")
        _set_output("domain", result.domain)
        _set_output("cert-id", cert_id)
        _set_output("cert-valid-end-date", valid_end_date)

        print("OSS cname certificate updated successfully")
        return 0
    except Exception:
        _set_output("updated", "false")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
