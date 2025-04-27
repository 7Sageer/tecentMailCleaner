# IMAP邮件清理工具

什么？你也被邮箱轰炸了？赶快清理吧！

## 功能特点

- 连接到任何IMAP邮件服务器
- 列出并选择特定邮件文件夹
- 搜索并删除超过指定天数的旧邮件
- 支持dry-run模式，可预览将被删除的邮件
- 详细的日志输出

## 安装

```bash
# 克隆仓库
git clone https://github.com/7Sageer/tecentMailCleaner.git
cd tecentMailCleaner

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

```bash
python imap_mail_cleaner.py --server imap.example.com --username your_email@example.com --days 30 
--folder "收件箱" --dry-run
python imap_mail_cleaner.py --server imap.example.com --username user@example.com --time-range "2023-01-01 08:30" "2023-01-31 17:45" --dry-run
```

### 参数说明

- `--server`: IMAP服务器地址
- `--port`: 服务器端口（默认993）
- `--username`: 邮箱账户名
- `--password`: 密码（不推荐在命令行中使用，未提供时会安全提示输入）
- `--days`: 删除超过指定天数的邮件
- `--folder`: 要清理的文件夹（默认为"INBOX"）
- `--dry-run`: 不实际删除，仅显示将被删除的邮件
- `--no-ssl`: 不使用SSL连接

## 安全提示

- 首次使用时建议加上`--dry-run`参数，确认要删除的邮件无误后再实际操作
- 建议定期备份重要邮件
- 不建议在脚本或命令行中明文存储密码

## 许可证

MIT