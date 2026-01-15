# 微信自动发布工具 - PyInstaller 打包指南

## 目标
- 打包方式：PyInstaller (--onedir 文件夹模式)
- 分发对象：其他用户
- 平台：Windows

---

## 代码改动（打包前需完成）

### 1. 数据库启动时清空文案数据
**文件**: `data/database.py`

**改动内容**: 添加 `clear_contents()` 方法，程序启动时调用

```python
def clear_contents(self) -> int:
    """清空文案内容表（保留任务和统计数据）"""
    with self.cursor() as cur:
        cur.execute("DELETE FROM contents")
        return cur.rowcount
```

**文件**: `run.py`

**改动内容**: 启动时调用清空方法

```python
# 在初始化数据库后添加
db = get_database()
cleared = db.clear_contents()
logger.info(f"已清空 {cleared} 条文案数据")
```

**数据保留策略**:
| 表名 | 启动时处理 | 说明 |
|------|-----------|------|
| contents | ✅ 清空 | 文案内容，每天重新导入 |
| tasks | ❌ 保留 | 任务状态，用于统计 |
| idempotent_keys | ❌ 保留 | 幂等键，防重复执行 |

---

## 打包前准备工作清单

### 1. 清理敏感数据 ✅ 必做
删除以下文件（打包时不能包含用户数据）：
- `data/wechat_publish.db` - 数据库
- `data/wechat_publish.db-shm` - SQLite临时文件
- `data/wechat_publish.db-wal` - SQLite日志
- `data/wechat_sender.db` - 次数据库
- `.secret.key` - 加密密钥（用户首次运行时自动生成）

### 2. 清理缓存文件 ✅ 必做
```
__pycache__/          - Python缓存（递归删除所有子目录）
.pytest_cache/        - pytest缓存
```

### 3. 创建 requirements.txt ✅ 必做
```
PySide6>=6.5.0
uiautomation>=2.0.0
pywinauto>=0.6.8
PyAutoGUI>=0.9.54
pyperclip>=1.8.2
openpyxl>=3.1.0
Pillow>=10.0.0
opencv-python>=4.8.0
APScheduler>=3.10.0
pyttsx3>=2.90
PyYAML>=6.0
cryptography>=41.0.0
watchdog>=3.0.0
pywin32>=306
```

### 4. 创建程序图标 ✅ 必做
创建 `icon.ico` 文件：
- 使用 Pillow 生成简单的程序图标
- 微信绿色主题（#07C160）
- 包含多尺寸：256x256, 128x128, 64x64, 32x32, 16x16

### 5. 创建干净的默认配置 ✅ 必做
备份当前 `config.yaml`，创建干净版本：
- 清空邮件密码（设为空字符串）
- 保留合理的默认值
- 确保路径使用相对路径

### 6. 创建 PyInstaller spec 文件 ✅ 必做
创建 `wechat-fabu.spec`，配置：
- 入口：`run.py`
- 数据文件：`config.yaml`, `selectors.yaml`
- 图标：`icon.ico`
- 隐藏导入：PySide6、uiautomation、pywin32相关模块
- 排除：测试文件、__pycache__、.git等

---

## 执行步骤

### Step 1: 清理文件
```cmd
:: 删除敏感数据
del /f ".secret.key"
del /f "data\wechat_publish.db"
del /f "data\wechat_publish.db-shm"
del /f "data\wechat_publish.db-wal"
del /f "data\wechat_sender.db"

:: 清理缓存（递归）
for /d /r . %d in (__pycache__) do @if exist "%d" rmdir /s /q "%d"
rmdir /s /q ".pytest_cache" 2>nul
```

### Step 2: 创建必要文件
- [ ] `requirements.txt` - 依赖列表
- [ ] `icon.ico` - 程序图标
- [ ] `wechat-fabu.spec` - PyInstaller配置
- [ ] 清理 `config.yaml` - 移除敏感数据

### Step 3: 安装打包工具
```cmd
pip install pyinstaller
```

### Step 4: 执行打包
```cmd
pyinstaller wechat-fabu.spec
```

### Step 5: 验证打包结果
- 运行 `dist/wechat-fabu/微信自动发布工具.exe`
- 检查是否正常启动
- 验证配置文件和数据目录是否正确创建

### Step 6: 分发
- 压缩 `dist/wechat-fabu/` 目录
- 提供给用户

---

## 需要创建的文件

| 文件 | 路径 | 说明 |
|------|------|------|
| requirements.txt | 项目根目录 | Python依赖列表 |
| icon.ico | 项目根目录 | 程序图标 |
| wechat-fabu.spec | 项目根目录 | PyInstaller配置 |

## 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| config.yaml | 清空敏感数据（邮件密码等） |

## 需要删除的文件

| 文件/目录 | 原因 |
|----------|------|
| .secret.key | 加密密钥，用户运行时自动生成 |
| data/*.db* | 数据库文件，含用户数据 |
| __pycache__/ | Python缓存 |
| .pytest_cache/ | 测试缓存 |

---

## 注意事项

1. **PySide6 体积大**：打包后约 150-200MB，这是正常的
2. **首次运行**：程序会自动创建 `.secret.key` 和数据库
3. **配置文件**：用户需要根据需要修改 `config.yaml`
4. **管理员权限**：uiautomation 可能需要管理员权限才能正常工作

---

## 打包后目录结构预览

```
dist/wechat-fabu/
├── 微信自动发布工具.exe    # 主程序
├── config.yaml              # 配置文件
├── selectors.yaml           # UI选择器配置
├── data/                    # 数据目录（空）
│   ├── cache/
│   ├── logs/
│   ├── receipts/
│   ├── screenshots/
│   └── shared/
├── _internal/               # PyInstaller内部文件
│   ├── PySide6/
│   └── ... (依赖库)
└── README.txt               # 使用说明（可选）
```
