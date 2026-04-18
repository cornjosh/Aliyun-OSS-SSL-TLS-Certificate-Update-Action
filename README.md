# OSS CNAME Certificate Update

使用阿里云官方 Python SDK（`oss2`）更新 OSS Bucket 绑定 CNAME 域名的证书。

## 特性

- 使用 `PutBucketCname` 更新 CNAME 证书
- 自动检查当前证书是否过期
- 未过期证书走 `previous_cert_id` 轮替
- 输入 `region` 时自动规范化 endpoint（支持 region/oss-xxx/完整 endpoint）

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `access_key_id` | 是 | 阿里云 Access Key ID |
| `access_key_secret` | 是 | 阿里云 Access Key Secret |
| `bucket` | 是 | OSS Bucket 名称 |
| `region` | 是 | OSS 区域或 endpoint 片段（如 `cn-hangzhou` / `oss-cn-hangzhou` / `oss-cn-hangzhou.aliyuncs.com`） |
| `domain` | 是 | 已绑定到 OSS 的 CNAME 域名 |
| `certificate_path` | 是 | 证书 fullchain 文件路径 |
| `private_key_path` | 是 | 私钥文件路径 |

## 使用示例

```yaml
name: Update OSS CNAME Certificate

on:
  workflow_dispatch:

jobs:
  update-cert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Update OSS CNAME certificate
        uses: your-org/aliyun-oss-ssl-tls-certificate-update-action@v1
        with:
          access_key_id: ${{ secrets.ALIYUN_ACCESS_KEY_ID }}
          access_key_secret: ${{ secrets.ALIYUN_ACCESS_KEY_SECRET }}
          bucket: ${{ vars.OSS_BUCKET }}
          region: ${{ vars.OSS_REGION }}
          domain: ${{ secrets.DOMAIN }}
          certificate_path: certs/fullchain.pem
          private_key_path: certs/privkey.pem
```

## acme.sh 签发并上传 OSS（完整示例）

```yaml
name: Issue with acme.sh and Upload to OSS

on:
  workflow_dispatch:
  schedule:
    - cron: "13 3 * * *"

jobs:
  issue-and-upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install acme.sh
        run: |
          curl https://get.acme.sh | sh -s email=devnull@example.com
          ~/.acme.sh/acme.sh --version

      - name: Issue certificate via AliDNS
        env:
          Ali_Key: ${{ secrets.ALI_DNS_KEY }}
          Ali_Secret: ${{ secrets.ALI_DNS_SECRET }}
        run: |
          ~/.acme.sh/acme.sh --register-account -m devnull@example.com
          ~/.acme.sh/acme.sh --set-default-ca --server letsencrypt
          ~/.acme.sh/acme.sh --issue --dns dns_ali -d "${{ secrets.DOMAIN }}" --keylength ec-256

      - name: Export certificate files
        run: |
          mkdir -p certs
          ~/.acme.sh/acme.sh --install-cert -d "${{ secrets.DOMAIN }}" --ecc \
            --key-file certs/privkey.pem \
            --fullchain-file certs/fullchain.pem

      - name: Upload certificate to OSS CNAME
        uses: your-org/aliyun-oss-ssl-tls-certificate-update-action@v1
        with:
          access_key_id: ${{ secrets.ALIYUN_ACCESS_KEY_ID }}
          access_key_secret: ${{ secrets.ALIYUN_ACCESS_KEY_SECRET }}
          bucket: ${{ vars.OSS_BUCKET }}
          region: ${{ vars.OSS_REGION }}
          domain: ${{ secrets.DOMAIN }}
          certificate_path: certs/fullchain.pem
          private_key_path: certs/privkey.pem
```
