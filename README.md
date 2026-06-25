# 超算硬盘管理系统

基于 Flask + SQLite 的内网硬盘管理 Web 应用。

## 多语言 / i18n

系统支持 **中文** 与 **English** 切换：

- 登录页右上角，或登录后导航栏中的语言按钮
- 语言偏好保存在浏览器 Session 中
- 切换地址：`/set_language/zh` 或 `/set_language/en`

## 功能列表

- **硬盘管理**：序号、类型(HDD/SSD/NVMe)、总容量/已用/剩余、状态、物理位置(服务器/机架/槽位)、挂载点
- **管理人系统**：每块硬盘有管理人，显示开始管理日期
- **申请流程**：用户发起申请 → 管理员审批 → 自动更换管理人
- **数据记录**：每块硬盘可记录多条数据（描述、路径、大小、重要性、备份状态）
- **仪表板**：总览统计、存储使用率、待审批提醒
- **搜索筛选**：按序号/状态/类型筛选
- **导出 CSV**：一键导出所有硬盘信息
- **管理员功能**：添加/编辑/删除硬盘、用户角色管理、操作审计日志
- **历史记录**：管理员变更历史、操作日志

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python app.py
```

默认监听 `0.0.0.0:5000`，内网所有机器均可访问。

### 3. 默认管理员账户

| 用户名  | 密码      |
|---------|-----------|
| admin   | admin123  |

**首次使用请立即修改密码（在数据库中直接修改 hash，或添加修改密码页面）。**

### 4. 内网部署（Linux 超算）

```bash
# 安装依赖
pip install --user flask flask-sqlalchemy

# 后台运行
nohup python app.py > disk_manager.log 2>&1 &

# 或使用 screen
screen -S disk_manager
python app.py
# Ctrl+A, D 分离 screen
```

访问地址：`http://<超算IP>:5000`

### 5. 修改端口

编辑 `app.py` 最后一行：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

将 `5000` 改为任意端口号。

## 技术栈

- **后端**：Python 3.8+ / Flask 3.x
- **数据库**：SQLite（自动创建 `disk_manager.db`）
- **前端**：Bootstrap 5.3 + Bootstrap Icons（CDN）
- **认证**：Flask Session + Werkzeug 密码哈希

## 目录结构

```
disk_manager/
├── app.py                  # 主应用（路由、模型、所有逻辑）
├── requirements.txt
├── disk_manager.db         # 自动生成的数据库文件
├── templates/
│   ├── base.html           # 基础模板（导航栏）
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html      # 仪表板
│   ├── disks.html          # 硬盘列表
│   ├── disk_detail.html    # 硬盘详情
│   ├── my_requests.html    # 我的申请
│   └── admin/
│       ├── requests.html   # 申请审批
│       ├── add_disk.html
│       ├── edit_disk.html
│       ├── users.html
│       └── audit.html
└── static/
    ├── css/style.css
    └── js/main.js
```
