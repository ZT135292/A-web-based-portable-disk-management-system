# 移动硬盘管理系统 / Portable Disk Management System

**[中文](#中文说明) | [English](#english)**

基于 Flask + SQLite 的内网硬盘管理 Web 应用，适合超算中心、实验室等需要集中管理多块移动硬盘的场景。

> A self-hosted web app for managing portable/external disks in HPC labs. Built with Flask + SQLite, supports Chinese / English UI.

---

## 截图 / Screenshots

<!-- 把截图放到 screenshots/ 文件夹后，取消下面几行的注释 -->
![登录](screenshots/login.png)
![仪表板](screenshots/dashboard.png)
![硬盘列表](screenshots/disks.png)
![硬盘详情](screenshots/disk_detail.png)
![申请](screenshots/requests.png)
![日志](screenshots/log.png)

---

## 中文说明

### 功能列表

- **硬盘管理**：编号、类型（HDD/SSD/NVMe）、总容量/已用/剩余、状态、物理位置
- **管理人系统**：每块硬盘指定管理人，记录开始管理日期
- **申请流程**：用户发起申请 → 管理员审批 → 自动交接管理权
- **数据记录**：每块硬盘可添加多条数据（描述、路径、大小、备份状态）
- **仪表板**：总览统计、全局存储使用率、待审批提醒
- **搜索筛选**：按编号/状态/类型/管理人筛选
- **导出 CSV**：一键导出所有硬盘或审计日志
- **管理员功能**：添加/编辑/删除硬盘、用户角色管理、操作审计日志
- **历史记录**：管理员变更历史、完整操作日志
- **多语言**：支持中文 / English 切换（页面右上角）

---

## 安装方法

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | **3.8 或更高版本** |
| pip | 随 Python 附带，无需单独安装 |
| 操作系统 | Windows 7+ / Linux / macOS |
| 网络端口 | 默认使用 **5000**（可修改） |

> 检查 Python 版本：在命令行运行 `python --version`

---

### Windows 安装

#### 第一步：确认 Python 已安装

打开「命令提示符」（Win+R 输入 `cmd`），运行：

```bat
python --version
```

如果提示"不是内部或外部命令"，请前往 [python.org](https://www.python.org/downloads/) 下载安装，**安装时勾选"Add Python to PATH"**。

#### 第二步：安装依赖包

在命令提示符中进入项目文件夹：

```bat
cd /d J:\disk_manager
pip install -r requirements.txt
```

> 如果 pip 下载缓慢，可切换国内镜像：
> ```bat
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

#### 第三步：配置 SECRET_KEY

系统启动时**必须**提供 `SECRET_KEY` 环境变量，否则拒绝启动。

先生成一个随机密钥：

```bat
python -c "import secrets; print(secrets.token_hex(32))"
```

在项目目录下新建 `.env` 文件，将生成的密钥填入（此文件已被 `.gitignore` 忽略，不会上传到 Git）：

```
SECRET_KEY=粘贴你生成的随机密钥
```

#### 第四步：启动服务

**推荐方式（无黑窗口）：** 双击 `start_server.vbs`，它会自动读取 `.env` 并在后台静默启动。

**命令行方式：**

```bat
set SECRET_KEY=粘贴你生成的随机密钥
python app.py
```

看到类似以下输出即表示启动成功：

```
[初始化] 创建默认管理员账户: admin / admin123
 * Running on http://0.0.0.0:5000
```

#### 第五步：访问系统

打开浏览器，访问：

- 本机访问：`http://localhost:5000`
- 局域网其他电脑访问：`http://<本机IP>:5000`

> 查看本机 IP：在命令提示符运行 `ipconfig`，找到"IPv4 地址"

#### 第六步：首次登录

| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

> **重要**：首次登录后请立即在右上角「修改密码」中更换默认密码！

---

### Windows 开机自启（可选）

项目提供了两种开机自启方式：

#### 方式一：使用已有的 VBS 脚本（推荐，无黑窗口）

项目根目录已包含 `start_server.vbs`，双击即可在后台静默启动服务（不弹出命令窗口）。

将其设为开机自启：按 `Win+R` 输入 `shell:startup` 打开启动文件夹，将 `start_server.vbs` 的**快捷方式**复制进去即可。

#### 方式二：使用 BAT 脚本

新建 `start.bat`，写入以下内容：

```bat
@echo off
cd /d J:\disk_manager
start /min python app.py
```

同样复制快捷方式到 `shell:startup` 启动文件夹。

#### 方式三：Windows 任务计划程序（最稳定）

1. 按 `Win+S` 搜索「任务计划程序」并打开
2. 右侧点击「创建任务」
3. 「常规」选项卡：名称填 `disk_manager`，勾选「不管用户是否登录都要运行」
4. 「触发器」→ 新建 → 开始任务选「启动时」
5. 「操作」→ 新建：
   - 程序：`python`
   - 参数：`app.py`
   - 起始于：`J:\disk_manager`
6. 点击确定并输入管理员密码保存

---

### Linux 服务器安装

#### 第一步：安装依赖

```bash
cd /path/to/disk_manager
pip install -r requirements.txt
```

#### 第二步：配置 SECRET_KEY

生成随机密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

在项目目录下新建 `.env` 文件：

```bash
echo "SECRET_KEY=粘贴你生成的随机密钥" > .env
chmod 600 .env   # 限制只有当前用户可读
```

#### 第三步：启动方式

**临时运行（测试用）：**

```bash
export SECRET_KEY=粘贴你生成的随机密钥
python app.py
```

**后台持续运行（推荐）：**

```bash
export SECRET_KEY=粘贴你生成的随机密钥
nohup python app.py > disk_manager.log 2>&1 &
echo $! > disk_manager.pid
```

停止服务：

```bash
kill $(cat disk_manager.pid)
```

**使用 gunicorn（生产环境推荐）：**

```bash
pip install gunicorn
SECRET_KEY=你的密钥 gunicorn -w 2 -b 0.0.0.0:5000 --access-logfile access.log app:app
```

#### 第四步：systemd 开机自启

创建服务文件 `/etc/systemd/system/disk_manager.service`：

```ini
[Unit]
Description=移动硬盘管理系统
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/disk_manager
EnvironmentFile=/path/to/disk_manager/.env
ExecStart=/usr/bin/python3 app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> 将 `/path/to/disk_manager` 替换为项目实际路径，`User` 改为实际运行用户。`EnvironmentFile` 会自动从 `.env` 读取 `SECRET_KEY`。

启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable disk_manager
sudo systemctl start disk_manager

# 查看运行状态
sudo systemctl status disk_manager
```

---

### 配置说明

#### 修改端口

编辑 `app.py` 最后一行，将 `5000` 改为所需端口：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

#### 配置 SECRET_KEY（必须设置，否则无法启动）

`SECRET_KEY` 用于保护登录会话，必须通过 `.env` 文件或环境变量提供，**不要写入源码或上传到 Git**。

生成一个安全的随机密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

在项目目录创建 `.env` 文件（已被 `.gitignore` 忽略）：

```
SECRET_KEY=粘贴你生成的随机密钥
```

启动时系统会自动从 `.env` 读取（通过 `start_server.vbs` 或手动 `set`/`export`）。

#### 数据库位置

数据库文件为 `instance/disk_manager.db`（SQLite），首次运行自动创建，**请定期备份此文件**。

---

### 常见问题

**Q：pip install 报错"找不到命令"？**
> 尝试 `python -m pip install -r requirements.txt`

**Q：启动后浏览器无法访问？**
> 检查 Windows 防火墙是否放行了 5000 端口：控制面板 → Windows Defender 防火墙 → 高级设置 → 入站规则 → 新建规则 → 端口 → TCP 5000。

**Q：局域网其他电脑访问不了？**
> 确认服务监听的是 `0.0.0.0`（而非 `127.0.0.1`），并确认防火墙已开放端口。

**Q：忘记管理员密码怎么办？**
> 删除 `instance/disk_manager.db` 文件后重启服务，系统会重新初始化并创建默认账户 `admin / admin123`（**注意：此操作会清空所有数据**）。

---

## English

### Features

- **Disk management**: ID, type (HDD/SSD/NVMe), capacity, usage, status, physical location
- **Manager system**: Each disk has an assigned manager with start date tracking
- **Request workflow**: User submits request → Admin approves → Manager auto-reassigned
- **Data records**: Add multiple data entries per disk (description, path, size, backup status)
- **Dashboard**: Overview stats, global storage usage, pending approval alerts
- **Search & filter**: Filter by ID / status / type / manager
- **CSV export**: Export disk list or audit logs
- **Admin panel**: Add/edit/delete disks, user role management, full audit log
- **History**: Complete manager change history and operation log
- **Bilingual UI**: Switch between Chinese and English (top-right corner)

### Quick Start

**Requirements:** Python 3.8+

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate a secret key
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Create .env file with the generated key
echo "SECRET_KEY=paste_your_key_here" > .env

# 4. Start the server
python app.py
```

Access at `http://localhost:5000` (local) or `http://<server-ip>:5000` (LAN).

Default admin credentials: **admin / admin123** — change immediately after first login.

**Run in background (Linux):**

```bash
nohup python app.py > disk_manager.log 2>&1 &
```

**Windows silent start (no console window):** double-click `start_server.vbs` (reads `.env` automatically).

---

## 技术栈 / Tech Stack

| | |
|---|---|
| 后端 / Backend | Python 3.8+ / Flask 3.x |
| 数据库 / Database | SQLite（自动创建） |
| 前端 / Frontend | Bootstrap 5.3 + Bootstrap Icons |
| 认证 / Auth | Flask Session + Werkzeug password hashing |

## 目录结构 / Project Structure

```
disk_manager/
├── app.py                  # 主应用 / Main application
├── i18n.py                 # 多语言翻译 / Translations (zh/en)
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── disks.html
│   ├── disk_detail.html
│   ├── my_requests.html
│   ├── change_password.html
│   └── admin/
│       ├── requests.html
│       ├── add_disk.html
│       ├── edit_disk.html
│       ├── users.html
│       └── audit.html
└── static/
    ├── css/style.css
    └── js/main.js
```

## License

[Mozilla Public License 2.0](LICENSE)
