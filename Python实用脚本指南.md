当然可以。**Python 最适合做的事情之一，就是把那些“重复、机械、容易出错、需要处理大量文件/数据”的工作自动化。**

如果你是开发人员，我甚至建议把 Python 理解成：

> **“个人自动化操作系统”——凡是你手动做过 3～5 次的事情，都值得考虑能不能写成一个 Python 脚本。**

而且 Python 脚本不一定非得是几十 MB 的大型项目。很多非常实用的工具，可能只有 **30～200 行代码**。

下面我按照实际工作场景，给你系统地盘点一遍。

---

# 一、先建立一个 Python 脚本的全景地图

Python 可以做的实用脚本，大致可以分成：

```text
Python 自动化
│
├── 1. 文件系统自动化
│   ├── 批量重命名
│   ├── 文件分类
│   ├── 文件搜索
│   ├── 重复文件检测
│   ├── 文件备份
│   └── 文件同步
│
├── 2. 办公自动化
│   ├── Excel
│   ├── Word
│   ├── PDF
│   ├── PPT
│   ├── CSV
│   └── 报表生成
│
├── 3. Web 自动化
│   ├── HTTP 请求
│   ├── API 调用
│   ├── 网页抓取
│   ├── 页面监控
│   ├── 数据采集
│   └── 自动化测试
│
├── 4. 开发者工具
│   ├── Git 工具
│   ├── 日志分析
│   ├── 代码统计
│   ├── 项目初始化
│   ├── 构建脚本
│   └── CLI 工具
│
├── 5. 数据处理
│   ├── CSV
│   ├── JSON
│   ├── Excel
│   ├── 数据清洗
│   ├── 数据转换
│   └── 数据分析
│
├── 6. 系统运维
│   ├── CPU / 内存监控
│   ├── 磁盘监控
│   ├── 服务监控
│   ├── 日志监控
│   ├── 自动备份
│   └── 健康检查
│
├── 7. 图片 / 视频
│   ├── 批量压缩
│   ├── 格式转换
│   ├── 加水印
│   ├── 缩略图
│   ├── OCR
│   └── 视频处理
│
├── 8. 网络工具
│   ├── IP 查询
│   ├── DNS
│   ├── Ping
│   ├── 端口检测
│   ├── HTTP 检测
│   └── 网络测速
│
├── 9. AI 工具
│   ├── 批量调用 API
│   ├── 文本处理
│   ├── PDF → Markdown
│   ├── OCR
│   ├── embedding
│   └── 本地 AI 自动化
│
└── 10. 个人效率工具
    ├── Todo
    ├── 笔记
    ├── 时间统计
    ├── 密码生成
    ├── 文件整理
    └── 自动提醒
```

实际上还远不止这些。

---

# 二、文件处理：Python 最值得掌握的领域之一

这是我最推荐你学习的。

因为文件系统是**自动化需求最密集的地方之一**。

---

## 1. 批量重命名

例如：

```text
IMG_001.jpg
IMG_002.jpg
IMG_003.jpg
IMG_004.jpg
```

变成：

```text
vacation_001.jpg
vacation_002.jpg
vacation_003.jpg
vacation_004.jpg
```

甚至可以根据日期：

```text
2026-09-01_001.jpg
2026-09-01_002.jpg
2026-09-03_003.jpg
```

Python：

```python
from pathlib import Path

folder = Path("./photos")

for index, file in enumerate(folder.iterdir(), 1):
    if file.is_file():
        new_name = f"photo_{index:03d}{file.suffix}"
        file.rename(folder / new_name)
```

这类脚本非常简单，但是实际使用频率很高。

---

# 三、自动整理下载文件夹

这是一个非常经典的个人自动化脚本。

假设：

```text
Downloads/
├── a.pdf
├── b.pdf
├── photo.jpg
├── image.png
├── demo.mp4
├── test.zip
├── app.exe
```

运行脚本后：

```text
Downloads/
├── Documents/
│   ├── a.pdf
│   └── b.pdf
│
├── Images/
│   ├── photo.jpg
│   └── image.png
│
├── Videos/
│   └── demo.mp4
│
├── Archives/
│   └── test.zip
│
└── Programs/
    └── app.exe
```

核心逻辑：

```python
from pathlib import Path
import shutil

folder = Path.home() / "Downloads"

categories = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov"],
    "Documents": [".pdf", ".docx", ".txt", ".xlsx"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Programs": [".exe", ".msi"],
}

for file in folder.iterdir():

    if not file.is_file():
        continue

    for category, extensions in categories.items():

        if file.suffix.lower() in extensions:

            target = folder / category
            target.mkdir(exist_ok=True)

            shutil.move(str(file), target / file.name)

            break
```

这种东西甚至可以设置成：

```text
Windows 启动
    ↓
Python 自动运行
    ↓
扫描 Downloads
    ↓
自动分类
```

---

# 四、重复文件检测

非常实用。

比如硬盘里面：

```text
photo1.jpg
photo1_copy.jpg
IMG_1234.jpg
backup/photo1.jpg
old/photo1.jpg
```

你可能不知道哪些文件实际上是同一个。

可以计算：

```text
MD5
SHA256
```

例如：

```python
import hashlib

def file_hash(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)

    return h.hexdigest()
```

然后：

```text
hash A → 3 个文件
hash B → 1 个文件
hash C → 5 个文件
```

就可以发现：

> **文件内容完全相同，但文件名不同。**

这对于清理硬盘非常有用。

---

# 五、自动备份

比如：

```text
project/
```

每天自动备份：

```text
backup/
├── 2026-09-05/
├── 2026-09-06/
└── 2026-09-07/
```

甚至可以实现：

```text
源目录
   ↓
检测变化
   ↓
只复制新增/修改文件
   ↓
生成备份日志
```

进一步：

```text
Python
+
zip
+
定时任务
```

就能做一个简单的：

> **个人自动备份系统**

---

# 六、文件搜索工具

你可以自己做一个：

```bash
python search.py "invoice"
```

然后：

```text
搜索结果：

D:\Documents\invoice-2025.xlsx
D:\Backup\invoice-2025.xlsx
D:\Finance\invoice.pdf
```

还可以支持：

```bash
python search.py "invoice" --ext pdf
```

或者：

```bash
python search.py "invoice" --size ">10MB"
```

甚至：

```bash
python search.py "invoice" --modified "7days"
```

这已经开始有点像真正的 CLI 工具了。

---

# 七、自动清理临时文件

例如：

```text
*.tmp
*.log
*.cache
Thumbs.db
.DS_Store
```

扫描：

```text
发现 1842 个临时文件

预计释放：
3.7 GB
```

然后：

```text
是否删除？ [y/N]
```

这类工具很适合 Python。

---

# 八、Excel 自动化

这又是 Python 的一个超级强项。

比如公司每天都有：

```text
attendance.xlsx
```

里面：

```text
员工
日期
上班时间
下班时间
工作时长
加班时长
```

你可以自动：

```text
读取 Excel
   ↓
计算工时
   ↓
统计迟到
   ↓
统计早退
   ↓
统计加班
   ↓
生成报表
   ↓
保存 Excel
```

常用：

```python
openpyxl
pandas
```

---

# 九、自动生成考勤报表

这个其实特别适合你目前关注的**考勤 / 工时管理项目**。

比如原始数据：

```text
张三  08:59  18:03
李四  09:17  18:20
王五  08:51  17:45
```

Python 自动计算：

```text
张三
迟到：否
工时：9h04m

李四
迟到：是
迟到：17min
工时：9h03m

王五
迟到：否
早退：15min
工时：8h54m
```

然后生成：

```text
月度考勤报表.xlsx
```

甚至：

```text
员工维度
部门维度
月份维度
异常维度
```

---

# 十、自动生成 PDF 报表

比如：

```text
销售数据
    ↓
Python
    ↓
统计
    ↓
图表
    ↓
PDF
```

最终：

```text
2026 年 9 月销售分析报告.pdf
```

里面自动包含：

```text
销售额
订单数
客户数
同比
环比
Top 10 商品
Top 10 客户
柱状图
折线图
饼图
```

这类事情如果手工做，非常烦。

Python 做起来就变成：

```bash
python report.py
```

---

# 十一、CSV / JSON 批量转换

例如：

```text
users.csv
```

转换成：

```text
users.json
```

或者：

```text
JSON
 ↓
CSV
 ↓
Excel
 ↓
数据库
```

非常适合 Python。

---

# 十二、数据清洗脚本

这是实际开发中非常有价值的一类。

比如：

```text
原始数据
```

里面存在：

```text
" Zhang San "
"zhang san"
"张三"
"张 三"
```

你可以统一：

```text
张三
```

还有：

```text
手机号格式
日期格式
金额格式
空值
重复数据
非法数据
异常数据
```

Python + pandas 做这类事情非常舒服。

---

# 十三、批量图片压缩

比如：

```text
photos/
├── 001.jpg 8MB
├── 002.jpg 12MB
├── 003.jpg 6MB
```

运行：

```bash
python compress.py photos/
```

变成：

```text
compressed/
├── 001.jpg 800KB
├── 002.jpg 1.2MB
├── 003.jpg 700KB
```

可以控制：

```text
最大宽度
最大高度
JPEG quality
WebP
AVIF
```

---

# 十四、图片格式批量转换

例如：

```text
JPG
PNG
WEBP
```

批量：

```bash
python convert.py --input jpg --output webp
```

得到：

```text
1000.jpg
    ↓
1000.webp
```

Web 开发人员尤其适合做这个。

---

# 十五、自动生成缩略图

比如：

```text
products/
```

里面有：

```text
product001.jpg
product002.jpg
...
```

自动生成：

```text
thumbnails/
├── product001.webp
├── product002.webp
└── ...
```

这在：

* 电商
* CMS
* 图片管理
* 后台管理系统

里面都非常实用。

---

# 十六、自动加水印

例如：

```text
原图
 ↓
Python
 ↓
右下角 Logo
 ↓
输出
```

还可以：

```text
版权信息
时间
用户名
二维码
```

动态生成。

---

# 十七、截图自动处理

例如：

```text
screenshots/
```

自动：

```text
裁剪
缩放
压缩
加边框
加标题
转换 WebP
```

对于开发者做：

```text
技术文章
README
博客
产品文档
```

很方便。

---

# 十八、OCR：图片 → 文字

这是非常值得玩的一类。

例如：

```text
截图
 ↓
OCR
 ↓
文本
```

可以批量处理：

```text
100 张截图
 ↓
100 个文本文件
```

进一步：

```text
截图
 ↓
OCR
 ↓
Markdown
```

甚至：

```text
PDF
 ↓
OCR
 ↓
Markdown
 ↓
知识库
```

---

# 十九、PDF 自动化

Python 可以处理很多 PDF 工作。

例如：

### 合并

```text
a.pdf
b.pdf
c.pdf
```

→

```text
all.pdf
```

### 拆分

```text
document.pdf
```

→

```text
page-001.pdf
page-002.pdf
page-003.pdf
```

### 提取文字

```text
PDF
 ↓
TXT
```

### PDF 加密

### PDF 解密

### PDF 加水印

### PDF 转图片

### 图片转 PDF

这些都非常适合脚本化。

---

# 二十、网页数据采集

Python 的另一个传统强项。

比如：

```text
网页
 ↓
HTTP
 ↓
HTML
 ↓
解析
 ↓
结构化数据
```

典型组合：

```text
requests
BeautifulSoup
lxml
Playwright
Selenium
```

例如：

```python
import requests
from bs4 import BeautifulSoup

url = "https://example.com"

html = requests.get(url).text

soup = BeautifulSoup(html, "html.parser")

for item in soup.select(".item"):
    print(item.get_text(strip=True))
```

---

# 二十一、API 批量调用

这个对开发人员尤其重要。

例如：

```text
10000 个用户
 ↓
调用 API
 ↓
获取数据
 ↓
保存 JSON
```

或者：

```text
10000 个 URL
 ↓
HTTP 请求
 ↓
检测状态码
 ↓
生成报告
```

可以做：

```text
API 测试
数据同步
批量更新
批量导入
批量删除
数据迁移
```

---

# 二十二、API 健康检查

例如你有：

```text
/api/users
/api/orders
/api/products
/api/attendance
```

Python 每隔 1 分钟检查：

```text
GET /api/users       200 ✓
GET /api/orders      200 ✓
GET /api/products    500 ✗
GET /api/attendance  200 ✓
```

最终：

```text
服务健康度：75%
```

甚至：

```text
失败
 ↓
记录日志
 ↓
发送通知
```

---

# 二十三、网站监控

比如监控：

```text
https://example.com
```

自动检查：

```text
DNS
HTTP
HTTPS
Response Time
Status Code
Certificate
```

输出：

```text
example.com

HTTP: 200
响应时间：182ms
SSL：正常
```

---

# 二十四、网页内容变化监控

这个很有意思。

比如：

```text
网页 A
```

每小时：

```text
抓取
 ↓
计算 Hash
 ↓
与上一次比较
```

发现：

```text
页面发生变化！
```

然后：

```text
发送 Email
Telegram
Discord
Webhook
```

这就是一个很实用的：

> **Website Change Monitor**

---

# 二十五、网站批量 URL 检查

例如：

```text
urls.txt
```

里面：

```text
https://example.com
https://example.com/about
https://example.com/contact
https://example.com/products
```

Python：

```text
URL                  Status
--------------------------------
/                    200
/about               200
/contact             404
/products            500
```

对于 SEO、前端、后端开发都很实用。

---

# 二十六、网站死链检测

甚至可以做：

```text
首页
 ↓
抓取所有链接
 ↓
递归爬取
 ↓
检查 HTTP Status
```

最终：

```text
发现 17 个死链

404:
 /old-page
 /test
 /abc

500:
 /api/products
```

这已经是一个小型工具了。

---

# 二十七、Git 自动化

如果你经常开发，可以写：

```bash
python git-helper.py
```

自动：

```text
git status
git add .
git commit
git push
```

或者更聪明：

```text
分析 git diff
 ↓
生成 commit message
 ↓
询问确认
 ↓
git commit
```

---

# 二十八、Git 项目统计

例如：

```bash
python stats.py
```

输出：

```text
Project Statistics

Files:       382
JavaScript:  217
CSS:          43
HTML:         31
Python:       12

Lines:
Code:      128,432
Comments:   12,321
Blank:       8,223
```

还能统计：

```text
Top contributors
最近提交
提交频率
代码增长
```

---

# 二十九、代码搜索工具

例如：

```bash
python grep.py "TODO"
```

得到：

```text
src/components/A.vue:32
src/components/B.vue:78
src/utils/request.js:102
```

进一步：

```bash
python grep.py "console.log"
```

就能扫描整个项目。

当然，成熟工具已经很多，但**自己实现一遍非常适合学习 Python + 文件系统 + CLI**。

---

# 三十、项目初始化器

这个非常适合开发人员。

例如：

```bash
python create_project.py my-app
```

自动：

```text
my-app/
├── src/
├── tests/
├── docs/
├── README.md
├── .gitignore
├── package.json
└── ...
```

这实际上就是：

> 自己做一个 mini `create-vue` / `create-next-app`

---

# 三十一、批量创建项目目录

例如：

```text
company/
```

自动生成：

```text
company/
├── frontend/
├── backend/
├── database/
├── docs/
├── scripts/
├── tests/
└── deployment/
```

这类脚本几十行就能完成。

---

# 三十二、依赖分析

可以扫描：

```text
package.json
requirements.txt
pyproject.toml
```

生成：

```text
项目依赖树
```

比如：

```text
vue
├── @vue/runtime-dom
├── @vue/compiler-dom
└── ...

fastify
├── ...
```

甚至检查：

```text
过期依赖
重复依赖
未使用依赖
```

---

# 三十三、日志分析

这是 Python 特别适合的场景。

假设：

```text
app.log
```

里面：

```text
2026-09-07 INFO ...
2026-09-07 ERROR ...
2026-09-07 WARN ...
```

Python 可以分析：

```text
INFO   10231
WARN    1822
ERROR    381
```

再分析：

```text
最常见 Error Top 20
```

例如：

```text
Connection timeout      182
Database error          93
Unauthorized            42
Not found               31
```

---

# 三十四、服务器日志分析

进一步可以做：

```text
Nginx access.log
```

分析：

```text
访问量
IP
URL
状态码
响应时间
User-Agent
```

最终：

```text
Top URL

/api/users      12032
/api/orders      9231
/api/products   8122
```

---

# 三十五、CPU / 内存 / 磁盘监控

Python + `psutil` 可以做一个简单系统监控器：

```text
CPU       31%
Memory    62%
Disk      71%
Network   18MB/s
```

然后：

```text
CPU > 90%
```

触发：

```text
报警
```

---

# 三十六、进程监控

例如：

```text
node
python
nginx
mysql
redis
```

发现：

```text
node 进程消失
```

自动：

```text
重启
```

这已经进入轻量运维工具的范畴。

---

# 三十七、端口检测

例如：

```bash
python portscan.py localhost
```

输出：

```text
22    OPEN
80    OPEN
3000  OPEN
3306  OPEN
5432  CLOSED
```

开发环境特别方便。

---

# 三十八、Ping / 网络诊断

做一个：

```bash
python network.py google.com
```

输出：

```text
DNS:       23ms
TCP:       31ms
TLS:       42ms
HTTP:      88ms
```

进一步做成：

```text
Network Diagnostic Tool
```

---

# 三十九、DNS 查询工具

例如：

```bash
python dns.py example.com
```

输出：

```text
A:
1.2.3.4

AAAA:
....

MX:
....

TXT:
....

NS:
....
```

实际上就是自己做一个小型 DNS CLI。

---

# 四十、批量 Ping

例如：

```text
servers.txt
```

里面：

```text
192.168.1.1
192.168.1.2
192.168.1.3
192.168.1.100
```

输出：

```text
192.168.1.1    OK    2ms
192.168.1.2    OK    5ms
192.168.1.3    FAIL
192.168.1.100  OK    3ms
```

---

# 四十一、数据库自动化

Python 可以连接：

```text
SQLite
MySQL
PostgreSQL
Redis
MongoDB
```

做：

```text
批量导入
批量导出
数据库迁移
数据清洗
备份
统计
```

例如：

```text
SQLite
 ↓
查询
 ↓
CSV
```

或者：

```text
CSV
 ↓
Python
 ↓
SQLite
```

这对于你经常做的：

> Vue + Supabase / SQLite + Fastify

这一类项目尤其有价值。

---

# 四十二、数据库备份脚本

例如：

```bash
python backup.py
```

自动：

```text
数据库
 ↓
dump
 ↓
压缩
 ↓
2026-09-07.zip
```

甚至：

```text
保留最近 7 天
删除更旧备份
```

---

# 四十三、数据库数据迁移

例如：

```text
旧数据库
   ↓
Python
   ↓
字段转换
   ↓
新数据库
```

特别适合：

```text
SQLite → PostgreSQL
MySQL → PostgreSQL
JSON → SQLite
CSV → MySQL
```

---

# 四十四、JSON 数据生成器

开发的时候经常需要：

```text
100
1000
10000
100000
```

条测试数据。

Python 可以：

```bash
python generate.py users 10000
```

生成：

```json
[
  {
    "name": "User001",
    "age": 21,
    "email": "user001@example.com"
  }
]
```

这对前端开发非常有用。

---

# 四十五、Mock 数据生成

比如你的考勤系统需要：

```text
10,000 员工
12 个月考勤
每天签到
上下班
加班
请假
```

Python 可以一次生成几十万条：

```text
employees.json
attendance.json
departments.json
leave.json
overtime.json
```

然后直接灌进：

```text
SQLite / PostgreSQL / Supabase
```

做压力测试。

---

# 四十六、AI 自动化脚本

这是现在非常值得关注的一块。

Python 可以批量：

```text
读取文件
 ↓
调用 AI API
 ↓
处理结果
 ↓
保存文件
```

例如：

```text
1000 个 Markdown
 ↓
AI 总结
 ↓
生成 summary
```

或者：

```text
1000 个商品
 ↓
AI
 ↓
生成商品描述
```

或者：

```text
会议记录
 ↓
AI
 ↓
提取：
任务
负责人
截止日期
```

---

# 四十七、批量翻译

例如：

```text
docs/
├── a.md
├── b.md
├── c.md
```

Python：

```text
中文
 ↓
AI API
 ↓
英文
 ↓
保存
```

生成：

```text
docs-en/
├── a.md
├── b.md
└── c.md
```

---

# 四十八、Markdown 自动化

例如：

```text
Markdown
 ↓
Python
 ↓
HTML
```

或者：

```text
Markdown
 ↓
目录生成
 ↓
文章索引
 ↓
README
```

甚至自动生成：

```text
侧边栏
文章目录
标签
分类
RSS
```

这类脚本对于博客、文档站非常有价值。

---

# 四十九、自动生成 README

扫描项目：

```text
项目
 ↓
Python
 ↓
分析目录
 ↓
分析 package.json
 ↓
分析 API
 ↓
生成 README.md
```

例如：

```text
# My Project

## Features

- User management
- Authentication
- Attendance
- Reports

## Tech Stack

- Vue 3
- Fastify
- SQLite
```

---

# 五十、自动生成 API 文档

如果项目结构规范，可以：

```text
源码
 ↓
Python
 ↓
扫描路由
 ↓
生成 API Markdown
```

例如：

```text
GET /users
POST /users
GET /users/:id
DELETE /users/:id
```

---

# 五十一、定时任务

Python 可以配合：

```text
Windows Task Scheduler
Linux cron
systemd
```

实现：

```text
每天 02:00
 ↓
自动备份
```

或者：

```text
每天 09:00
 ↓
抓取数据
```

或者：

```text
每小时
 ↓
检测网站
```

---

# 五十二、邮件自动化

例如：

```text
Excel
 ↓
Python
 ↓
生成报表
 ↓
Email
```

自动发送：

```text
每日销售报告
每日考勤报告
服务器健康报告
异常日志报告
```

---

# 五十三、桌面 GUI 小工具

如果不想做 CLI，也可以用：

```text
Tkinter
PySide / PyQt
```

做：

```text
文件批量重命名器
图片压缩器
PDF 工具
JSON 格式化器
编码转换器
日志分析器
```

例如：

```text
┌─────────────────────────────┐
│       Image Compressor      │
├─────────────────────────────┤
│ Input:  [选择文件夹]         │
│                             │
│ Quality: ████████░░ 80%     │
│                             │
│ Output: [选择目录]           │
│                             │
│        [开始压缩]            │
└─────────────────────────────┘
```

一个 Python 文件就可以做出来。

---

# 五十四、CLI 工具

对于开发人员，我尤其推荐这一类。

例如：

```bash
mytool init
mytool scan
mytool clean
mytool backup
mytool report
```

甚至：

```bash
mytool project create my-app
mytool project stats
mytool project clean
```

这其实就是：

> **把 Python 从“脚本”升级成真正的开发工具。**

可以使用：

```text
argparse
click
typer
rich
```

---

# 五十五、漂亮的终端工具

例如用 Rich：

```text
╭────────────────────────────╮
│ System Monitor             │
├────────────────────────────┤
│ CPU       32%              │
│ Memory    61%              │
│ Disk      72%              │
│ Network   18 MB/s          │
╰────────────────────────────╯
```

还可以：

```text
进度条
表格
日志
颜色
Spinner
```

这已经非常接近成熟 CLI 工具了。

---

# 五十六、代码自动格式化 / 检查

例如：

```bash
python codecheck.py
```

自动：

```text
扫描 *.py
扫描 *.js
扫描 *.vue
扫描 *.css
```

然后：

```text
发现：

23 个 TODO
12 个 console.log
4 个 debugger
3 个超长文件
7 个超长函数
```

甚至生成：

```text
code-quality.html
```

---

# 五十七、前端项目专用脚本

对于你这种前端开发者，我觉得这一类非常值得玩。

比如：

```bash
python frontend.py analyze
```

分析：

```text
Vue 文件数量
JS 文件数量
CSS 文件数量
组件数量
页面数量
API 数量
图片数量
Bundle 大小
```

甚至：

```text
发现 37 个未使用图片
发现 12 个 console.log
发现 8 个超大组件
发现 5 个重复组件
```

---

# 五十八、自动检测 Vue 项目

甚至可以针对：

```text
Vue 3
```

分析：

```text
.vue 文件
<script setup>
props
emits
computed
watch
ref
reactive
```

生成：

```text
Component Dependency Graph
```

这就是一个非常有意思的开发工具。

---

# 五十九、自动生成前端 Mock 数据

例如：

```bash
python mock.py users 1000
```

自动生成：

```text
users.json
```

或者直接启动：

```bash
python mock-server.py
```

然后：

```text
GET /api/users
GET /api/orders
GET /api/products
```

成为一个小型 Mock Server。

---

# 六十、文件上传测试工具

这对于你之前关注的**大文件上传**也特别有价值。

可以写：

```bash
python upload-test.py bigfile.zip
```

测试：

```text
上传速度
分片大小
并发数
失败重试
断点续传
总耗时
```

输出：

```text
File: 2.4GB

Chunk: 10MB
Concurrency: 6

Uploaded: 100%
Speed: 82 MB/s
Time: 31.2s

Failed chunks: 2
Retry: 2
```

这已经是非常专业的开发辅助工具了。

---

# 六十一、WebSocket 测试客户端

你之前研究过 WebSocket，这个也特别适合 Python。

例如：

```bash
python ws-client.py ws://localhost:3000
```

自动：

```text
连接
 ↓
发送消息
 ↓
接收消息
 ↓
统计延迟
 ↓
压力测试
```

甚至：

```text
1000 clients
 ↓
WebSocket Server
```

用于压测。

---

# 六十二、HTTP 压测工具

例如自己做一个简易版：

```bash
python benchmark.py http://localhost:3000/api/users
```

输出：

```text
Requests: 10000

Concurrency: 100

Average: 82ms
P50:      63ms
P95:     182ms
P99:     321ms

Success: 99.8%
Error:    0.2%
```

这对于后端开发非常有价值。

---

# 六十三、自动化测试辅助工具

Python 可以控制：

```text
浏览器
 ↓
Playwright
 ↓
打开页面
 ↓
点击
 ↓
填写表单
 ↓
截图
 ↓
验证结果
```

比如：

```text
登录
 ↓
进入后台
 ↓
创建员工
 ↓
创建考勤记录
 ↓
查看统计
 ↓
截图
```

这就是：

> **E2E 自动化测试**

---

# 六十四、浏览器自动化

Python + Playwright 可以：

```text
打开浏览器
登录网站
点击按钮
填写表单
上传文件
下载文件
截图
读取 DOM
```

可以用于：

* 自动化测试
* 内部系统自动操作
* 数据采集
* 回归测试

当然，涉及第三方网站时要遵守其服务条款和访问规则。

---

# 六十五、视频批处理

Python 可以调用 FFmpeg 做：

```text
视频压缩
视频格式转换
提取音频
截取片段
合并视频
批量生成缩略图
提取关键帧
```

例如：

```text
100 个 MP4
 ↓
统一转换
 ↓
H.264
1080p
```

Python 负责：

```text
任务调度
文件遍历
参数生成
错误处理
```

FFmpeg 负责：

```text
真正的视频编码
```

这是非常典型的：

> Python 做 orchestration，专业工具做底层工作。

---

# 六十六、音频自动化

例如：

```text
mp3
wav
m4a
```

批量：

```text
转换
剪切
合并
提取
音量标准化
```

进一步：

```text
音频
 ↓
Whisper
 ↓
文字
 ↓
Markdown
```

就变成一个：

> **音频转文字工具**

---

# 六十七、个人知识库工具

这个我也非常推荐。

例如：

```bash
python note.py add "WebSocket 原理"
```

自动：

```text
notes/
├── websocket.md
├── vue-reactivity.md
├── cors.md
└── cookie.md
```

然后：

```bash
python note.py search websocket
```

输出：

```text
websocket.md
```

进一步：

```text
Markdown
+
全文搜索
+
SQLite
+
Embedding
+
AI
```

可以变成个人知识库。

---

# 六十八、桌面文件智能整理器

进一步甚至可以做：

```text
Downloads
Desktop
Documents
Pictures
```

Python 自动：

```text
识别扩展名
 ↓
识别文件名
 ↓
识别创建时间
 ↓
识别文件大小
 ↓
分类
```

例如：

```text
2026-09-07_invoice.pdf
```

自动：

```text
Documents/Finance/2026/
```

这已经开始像一个：

> **个人文件管理系统**

---

# 六十九、自动生成日报 / 周报

例如：

```text
Git commits
+
Issue
+
Todo
+
Calendar
```

Python 汇总：

```text
本周完成：

1. 考勤列表优化
2. 工时统计
3. API 性能优化
4. 修复 17 个 Bug

代码提交：
47 commits

新增：
12,382 lines

修改：
8,123 lines
```

自动生成：

```text
weekly-report.md
```

甚至自动发邮件。

---

# 七十、把多个工具串成一个“自动化流水线”

这才是 Python 真正厉害的地方。

例如：

```text
Excel
  ↓
Python
  ↓
数据清洗
  ↓
SQLite
  ↓
统计
  ↓
生成图表
  ↓
生成 PDF
  ↓
发送 Email
```

一条命令：

```bash
python report.py
```

全部完成。

---

# 七十一、Python 最值得掌握的“脚本能力栈”

如果你的目标是：

> **成为一个非常会自动化的开发者**

我建议按照这个顺序学习。

### 第一层：文件系统

```python
pathlib
os
shutil
glob
```

掌握：

```text
遍历
复制
移动
删除
重命名
搜索
```

---

### 第二层：数据

```python
json
csv
re
datetime
collections
```

掌握：

```text
JSON
CSV
正则
日期
数据结构
```

---

### 第三层：网络

```python
requests
httpx
urllib
```

掌握：

```text
HTTP
REST API
文件下载
上传
并发请求
```

---

### 第四层：办公

```text
openpyxl
pandas
python-docx
PyMuPDF
reportlab
```

掌握：

```text
Excel
Word
PDF
报表
```

---

### 第五层：系统

```text
subprocess
psutil
platform
shutil
```

掌握：

```text
进程
CPU
内存
磁盘
命令行
```

---

### 第六层：CLI

```text
argparse
Typer
Click
Rich
```

开始把：

```text
script.py
```

升级成：

```text
mytool
```

---

### 第七层：自动化

```text
Playwright
Selenium
schedule
APScheduler
```

掌握：

```text
浏览器自动化
定时任务
后台任务
```

---

### 第八层：数据分析

```text
NumPy
Pandas
Matplotlib
```

开始：

```text
处理数据
分析数据
可视化
```

---

### 第九层：AI

```text
LLM API
OCR
Whisper
Embedding
Vector DB
```

开始：

```text
传统自动化
        +
AI
        ↓
智能自动化
```

---

# 七十二、如果我是开发者，我会优先写这 20 个

如果不考虑“学习 Python”，而单纯考虑：

> **哪些东西写出来以后真的可能天天用？**

我会优先做：

| #  | 工具                    | 实用程度  |
| -- | --------------------- | ----- |
| 1  | 📁 智能文件整理器            | ⭐⭐⭐⭐⭐ |
| 2  | 🔍 全盘文件搜索             | ⭐⭐⭐⭐⭐ |
| 3  | 🧹 重复文件清理             | ⭐⭐⭐⭐⭐ |
| 4  | 🖼️ 图片批量压缩            | ⭐⭐⭐⭐⭐ |
| 5  | 📄 PDF 工具箱            | ⭐⭐⭐⭐⭐ |
| 6  | 📊 Excel 自动报表         | ⭐⭐⭐⭐⭐ |
| 7  | 💾 自动备份               | ⭐⭐⭐⭐⭐ |
| 8  | 🌐 URL 批量检测           | ⭐⭐⭐⭐⭐ |
| 9  | 🔌 API 批量测试           | ⭐⭐⭐⭐⭐ |
| 10 | 📜 日志分析器              | ⭐⭐⭐⭐⭐ |
| 11 | 💻 系统监控器              | ⭐⭐⭐⭐  |
| 12 | 🌐 HTTP/WebSocket 测试器 | ⭐⭐⭐⭐  |
| 13 | 🧪 Mock 数据生成器         | ⭐⭐⭐⭐⭐ |
| 14 | 🚀 项目初始化器             | ⭐⭐⭐⭐⭐ |
| 15 | 📈 Git 项目统计器          | ⭐⭐⭐⭐  |
| 16 | 📝 Markdown 批处理器      | ⭐⭐⭐⭐  |
| 17 | 🤖 AI 批处理工具           | ⭐⭐⭐⭐⭐ |
| 18 | 🌐 Playwright 自动化     | ⭐⭐⭐⭐⭐ |
| 19 | 🎥 FFmpeg 批处理器        | ⭐⭐⭐⭐  |
| 20 | 🗄️ 数据库备份/迁移工具        | ⭐⭐⭐⭐⭐ |

---

# 七十三、而且这些东西可以逐渐“进化”

这是我觉得学习 Python 脚本最有意思的地方。

比如一开始：

```text
rename.py
```

只有：

```python
for file in files:
    rename(file)
```

后来：

```text
rename.py
```

支持：

```bash
rename --prefix photo
rename --suffix 2026
rename --pattern "*.jpg"
rename --dry-run
```

再后来：

```bash
mytool rename
```

然后：

```text
Rich UI
配置文件
日志
插件
并发
错误恢复
```

最后甚至可以：

```bash
pip install mytool
```

这时候它已经不再是：

> 一个 Python 脚本

而是：

> **一个真正的软件工具。**

---

# 七十四、对于开发者，Python 最重要的不是“写程序”

我反而建议你建立一个非常重要的思维：

```text
遇到重复工作
       ↓
先不要手动做
       ↓
能不能 Shell？
       ↓
复杂一点
       ↓
Python
       ↓
做成 CLI
       ↓
做成自动化工具
       ↓
定时运行
       ↓
日志 + 配置 + 错误恢复
       ↓
成为自己的基础设施
```

例如：

```text
今天手动整理 500 个文件
        ↓
浪费 30 分钟

明天又整理 500 个
        ↓
再浪费 30 分钟

写 Python
        ↓
30 分钟

以后：
python organize.py
        ↓
5 秒
```

这就是脚本最核心的价值。

---

# 七十五、如果进一步结合你做前端开发的方向

我其实非常建议你走一条：

**Python + 前端工程化工具**

路线。

例如最终可以自己构建一个：

```text
dev-tool
│
├── dev-tool init
│
├── dev-tool clean
│
├── dev-tool analyze
│
├── dev-tool mock
│
├── dev-tool api
│
├── dev-tool upload
│
├── dev-tool ws
│
├── dev-tool image
│
├── dev-tool pdf
│
├── dev-tool database
│
├── dev-tool backup
│
└── dev-tool report
```

里面：

```text
dev-tool image
    ↓
图片压缩 / WebP / 缩略图

dev-tool mock
    ↓
生成 10 万条 Mock 数据

dev-tool api
    ↓
批量 HTTP API 测试

dev-tool upload
    ↓
大文件上传测试

dev-tool ws
    ↓
WebSocket 测试

dev-tool analyze
    ↓
Vue 项目代码分析

dev-tool database
    ↓
SQLite / PostgreSQL 数据操作

dev-tool report
    ↓
生成项目统计报告
```

这会非常符合你作为**前端/全栈开发者**的实际工作。

甚至可以进一步做到：

```text
Vue 3
   +
Fastify
   +
SQLite
   +
Python CLI
   +
AI
```

形成一套自己的开发工具链。

**如果把 Python 学习从“学语法”转变成“不断给自己造工具”，学习效率会高很多。**每做一个小工具，你实际上都在同时练习 Python、操作系统、文件系统、HTTP、数据库、CLI、并发、自动化和工程化。
