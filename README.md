# 自动合并规则列表项目

本项目旨在自动从多个来源下载规则列表，并为每个源文件生成独立的格式化规则文件，适用于 Clash 等代理工具。

## 功能

* 从 `sources/` 目录下的多个文本文件中读取规则列表的 URL。
* 为每个源文件独立下载和处理 URL 指向的规则内容。
* 兼容纯文本列表和 YAML `payload:` 格式；规范化规则格式（去掉逗号后的空格）并去重，去除注释行（以 `#`, `!`, `/`, `;`, `[` 开头的行）。
* 为每个源文件生成对应的规则列表文件到 `output/` 目录（例如 `sources/telegram.txt` 生成 `output/telegram.list`）。
* `sources/ASN/` 下的源会额外去掉 `//` 注释并补上 `,no-resolve`，输出到 `output/ASN/`。
* 某个规则源下载失败时会跳过该源、继续合并其余源，并在运行日志末尾和 GitHub Actions 页面（警告注解）列出失败的 URL；若某个源文件的所有规则源都失败，则保留旧的输出文件。
* 规则内容无变化时不改写输出文件（不会产生仅更新时间戳的提交）。
* 使用 GitHub Actions 自动化此过程，每天 UTC 5:00 定时运行，或在 `sources/`、`Rules/`、脚本、工作流有变更推送到 `main` 分支时触发。

## 文件结构

```plaintext
.
├── .github/
│   └── workflows/
│       └── merge_rules.yml  # GitHub Actions 工作流程定义
├── sources/               # 规则源（每行一个 URL 或一条规则），文件名决定输出文件名
│   ├── ai.txt / games.txt / telegram.txt / twitter.txt / wechat.txt / youtube.txt
│   ├── others.txt         # 预留，当前为空（为空时不生成输出）
│   └── ASN/
│       └── asn_cn.txt     # 中国 ASN 规则源
├── output/                # 自动生成，请勿手动修改
│   ├── ai.list / games.list / telegram.list / twitter.list / wechat.list / youtube.list
│   └── ASN/
│       └── asn_cn.list
├── Rules/                 # 手工维护的规则，部分被 sources/ 引用
├── .gitignore             # 指定 Git 忽略的文件
├── merge_rules.py         # 执行合并和分类逻辑的 Python 脚本
├── requirements.txt       # Python 依赖库列表 (requests)
└── README.md              # 项目说明文件
```

## 使用方法

1. **克隆仓库**:
   ```bash
   git clone https://github.com/Jacky-Bruse/Rules.git
   cd Rules
   ```

2. **添加/修改规则源**:
   * 导航到 `sources/` 目录。
   * 打开现有的 `.txt` 文件或创建新的 `.txt` 文件（文件名将决定输出的规则文件名）。
   * 在文件中添加或删除规则列表的 URL，确保每个有效的 URL 独占一行。
   * 以 `#` 开头的行将被视为注释，会被忽略。

3. **提交更改**:
   ```bash
   git add sources/
   git commit -m "更新规则源列表"
   git push origin main
   ```

4. **自动化处理**:
   * 当你将更改推送到 `main` 分支后，GitHub Actions 会自动触发执行脚本。
   * 或者，Actions 也会按照预定计划（每天 UTC 5:00）自动运行。
   * 如果脚本成功生成了新的规则文件，Actions 会自动将更新后的文件提交回仓库。

5. **手动运行**:
   * 你也可以在 GitHub 仓库页面的 "Actions" 标签页找到 "Merge Rule Lists" 工作流，并手动触发它。

## 获取生成的规则列表

所有生成的规则列表位于仓库的 `output/` 目录中，每个源文件都有对应的 `.list` 文件。

你可以通过以下 URL 格式直接访问最新版本的规则文件（以 telegram.list 为例）:

```
https://raw.githubusercontent.com/Jacky-Bruse/Rules/main/output/telegram.list
```

## 规则文件格式

生成的规则文件符合标准的 Clash 规则格式，包含以下内容：

```
# NAME: telegram
# AUTHOR: Jacky-Bruse
# REPO: https://github.com/Jacky-Bruse/Rules
# UPDATED: 2023-04-23 12:34:56
# DOMAIN: 10
# DOMAIN-SUFFIX: 20
# IP-CIDR: 30
# TOTAL: 60

DOMAIN,telegram.org
DOMAIN,api.telegram.org
DOMAIN-SUFFIX,t.me
DOMAIN-SUFFIX,tdesktop.com
IP-CIDR,91.108.4.0/24
IP-CIDR,91.108.8.0/24
```

## 本地测试

如果你想在本地运行脚本进行测试：

1. 确保你的系统安装了 Python 3 (建议 3.7+)。
2. 创建并激活虚拟环境:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```
3. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```
4. 运行脚本:
   ```bash
   python merge_rules.py
   ```
5. 检查 `output/` 目录下生成的规则文件。

## 注意事项

* 添加到源文件中的 URL 应该是可公开访问的，并且指向纯文本格式的规则列表。
* 脚本不会改写规则类型，规则按源中的原样（规范化空格后）输出，因此源规则应带有类型前缀（如 `DOMAIN-SUFFIX,example.com`）。
* 头部的分类统计按前缀计数（DOMAIN, DOMAIN-SUFFIX, DOMAIN-KEYWORD, IP-CIDR, IP-CIDR6, USER-AGENT, IP-ASN, PROCESS-NAME），其余类型（如 AND、URL-REGEX）计入 OTHER。
* 每个源文件生成的规则列表是相互独立的，方便用户选择性地使用所需的规则集。 