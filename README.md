# Aliyun OSS SSL/TLS Certificate Update Action

一个可发布到 GitHub Marketplace 的 Docker Action，用于通过阿里云官方 Python SDK 自动更新 OSS 自定义域名证书。

适合与 `acme.sh`、`certbot` 或其他证书签发流程配合，做到证书续期后自动同步到 OSS。

## 功能

- 基于官方 SDK `oss2` 调用 `PutBucketCname` 更新证书
- 自动判断当前绑定证书是否过期
- 未过期时使用 `previous_cert_id` 进行证书轮替
- 支持直接传入证书内容，或传入证书文件路径
- 输出更新状态和最终证书信息，便于后续 workflow 使用

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `access-key-id` | 是 | 阿里云 RAM 用户 AccessKey ID |
| `access-key-secret` | 是 | 阿里云 RAM 用户 AccessKey Secret |
| `region` | 是 | OSS 地域，例如 `cn-hangzhou`；Action 会自动拼接 endpoint |
| `bucket-name` | 是 | OSS Bucket 名称 |
| `target-cname` | 是 | 需要更新证书的自定义域名 |
| `certificate` | 否 | PEM 证书内容（与 `certificate-path` 二选一） |
| `private-key` | 否 | PEM 私钥内容（与 `private-key-path` 二选一） |
| `certificate-path` | 否 | 证书文件路径（与 `certificate` 二选一） |
| `private-key-path` | 否 | 私钥文件路径（与 `private-key` 二选一） |
| `force` | 否 | 是否强制更新，默认 `true` |

## 输出参数

| 参数 | 说明 |
| --- | --- |
| `updated` | 是否成功执行更新，`true/false` |
| `domain` | 更新的自定义域名 |
| `cert-id` | 更新后绑定证书 ID（若可获取） |
| `cert-valid-end-date` | 更新后证书到期时间（若可获取） |

## 使用示例

```yaml
name: Update OSS Certificate

on:
  workflow_dispatch:

jobs:
  update-cert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Update OSS cname certificate
        id: oss_cert
        uses: your-org/aliyun-oss-ssl-tls-certificate-update-action@v1
        with:
          access-key-id: ${{ secrets.ALIYUN_ACCESS_KEY_ID }}
          access-key-secret: ${{ secrets.ALIYUN_ACCESS_KEY_SECRET }}
          region: ${{ vars.OSS_REGION }}
          bucket-name: ${{ vars.OSS_BUCKET }}
          target-cname: ${{ secrets.DOMAIN }}
          certificate: ${{ secrets.FULLCHAIN_PEM }}
          private-key: ${{ secrets.PRIVATE_KEY_PEM }}

      - name: Print result
        run: |
          echo "updated=${{ steps.oss_cert.outputs.updated }}"
          echo "domain=${{ steps.oss_cert.outputs.domain }}"
          echo "cert-id=${{ steps.oss_cert.outputs.cert-id }}"
```

## acme.sh 签发并上传 OSS（完整示例）

下面示例演示：

1. 使用 `acme.sh` + 阿里云 DNS API 签发证书
2. 将产物写到工作目录
3. 通过本 Action 用路径方式上传 OSS

先在仓库配置：

- Secrets：
  - `ALIYUN_ACCESS_KEY_ID`
  - `ALIYUN_ACCESS_KEY_SECRET`
  - `DOMAIN`（例如 `static.example.com`）
  - `ALI_DNS_KEY`
  - `ALI_DNS_SECRET`
- Variables：
  - `OSS_REGION`（例如 `cn-hangzhou`）
  - `OSS_BUCKET`（你的 bucket 名称）

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

      - name: Upload certificate to OSS cname
        id: oss_cert
        uses: your-org/aliyun-oss-ssl-tls-certificate-update-action@v1
        with:
          access-key-id: ${{ secrets.ALIYUN_ACCESS_KEY_ID }}
          access-key-secret: ${{ secrets.ALIYUN_ACCESS_KEY_SECRET }}
          region: ${{ vars.OSS_REGION }}
          bucket-name: ${{ vars.OSS_BUCKET }}
          target-cname: ${{ secrets.DOMAIN }}
          certificate-path: certs/fullchain.pem
          private-key-path: certs/privkey.pem

      - name: Print action outputs
        run: |
          echo "updated=${{ steps.oss_cert.outputs.updated }}"
          echo "domain=${{ steps.oss_cert.outputs.domain }}"
          echo "cert-id=${{ steps.oss_cert.outputs.cert-id }}"
          echo "cert-valid-end-date=${{ steps.oss_cert.outputs.cert-valid-end-date }}"
```

## RAM 权限建议

建议创建最小权限 RAM 用户，至少包含：

- OSS 相关权限（读写 Bucket CNAME）
- SSL 证书服务相关权限（证书上传/管理）

可以先使用系统策略（如 `AliyunOSSFullAccess`、`AliyunYundunCertFullAccess`）验证流程，再逐步收敛为自定义最小权限策略。

## 发布到 Marketplace

1. 确保仓库公开，`action.yml` 位于仓库根目录
2. 打 Tag（例如 `v1.0.0`）并发布 Release
3. 在仓库 Settings 中启用 GitHub Actions
4. 到 GitHub Marketplace 完善说明、图标和分类

## 本地调试（可选）

```bash
docker build -t aliyun-oss-cert-action .
docker run --rm \
  -e INPUT_ACCESS-KEY-ID=xxx \
  -e INPUT_ACCESS-KEY-SECRET=yyy \
  -e INPUT_REGION=cn-hangzhou \
  -e INPUT_BUCKET-NAME=your-bucket \
  -e INPUT_TARGET-CNAME=static.example.com \
  -e INPUT_CERTIFICATE="$(cat fullchain.pem)" \
  -e INPUT_PRIVATE-KEY="$(cat privkey.pem)" \
  aliyun-oss-cert-action
```

注意：GitHub Action 实际运行时会自动注入 `INPUT_*` 环境变量，本地调试仅用于验证脚本逻辑。
