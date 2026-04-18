# OSS CNAME Certificate Update

使用阿里云官方 Python SDK（`oss2`）更新 OSS Bucket 绑定 CNAME 域名的证书。

当前实现为 **Composite Action + Python 3.11**，入口脚本为仓库根目录 `main.py`。

## 特性

- 使用 `PutBucketCname` 更新 CNAME 证书
- 自动检查当前证书是否过期
- 未过期证书走 `previous_cert_id` 轮替
- 输入 `region` 时自动规范化 endpoint（支持 region/oss-xxx/完整 endpoint）

## 行为说明

- 如果 `domain` 不在目标 bucket 的 CNAME 列表中，Action 会失败退出（exit code 1）
- 如果当前证书未过期，会携带 `previous_cert_id` 进行轮替更新
- 如果当前证书过期或未绑定证书，会创建并重新绑定证书
- 当前版本**不提供 outputs**，请通过日志判断执行结果

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `access_key_id` | 是 | 阿里云 Access Key ID |
| `access_key_secret` | 是 | 阿里云 Access Key Secret |
| `bucket` | 是 | OSS Bucket 名称 |
| `region` | 是 | OSS 区域或 endpoint 片段（如 `cn-hangzhou` / `oss-cn-hangzhou` / `oss-cn-hangzhou.aliyuncs.com`）；建议优先传 `cn-hangzhou` 这类 region ID |
| `domain` | 是 | 已绑定到 OSS 的 CNAME 域名 |
| `certificate_path` | 是 | 证书 fullchain 文件路径 |
| `private_key_path` | 是 | 私钥文件路径 |

## 前置要求

- 目标 bucket 已绑定 `domain`（CNAME）
- 证书文件在当前 job 中可访问（如 `certs/fullchain.pem`、`certs/privkey.pem`）
- RAM 账号具备 OSS CNAME 与证书相关权限

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

建议仓库变量与密钥：

- `vars.OSS_BUCKET`
- `vars.OSS_REGION`
- `secrets.ALIYUN_ACCESS_KEY_ID`
- `secrets.ALIYUN_ACCESS_KEY_SECRET`
- `secrets.DOMAIN`

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
