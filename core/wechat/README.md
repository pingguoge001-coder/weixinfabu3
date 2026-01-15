# 微信控制模块 (core/wechat)

原 `core/wechat_controller.py` 已拆分为多个功能模块，提高代码可维护性。

## 模块结构

```
core/wechat/
├── __init__.py           # 模块导出和单例管理
├── controller.py         # 主控制器（整合所有子模块）
├── window_manager.py     # 窗口管理（查找、激活、移动、调整大小）
├── version_detector.py   # 版本检测（3.x 或 4.0+）
├── login_checker.py      # 登录状态检查
├── navigation.py         # 导航操作（小程序、转发）
└── README.md            # 本文件
```

## 模块职责

### 1. `controller.py` - 主控制器
整合所有子模块，提供统一的微信控制接口。

**功能**:
- 窗口查找和管理
- 登录状态检测
- 版本检测
- 进程管理
- 小程序和转发操作

**示例**:
```python
from core.wechat import get_wechat_controller

controller = get_wechat_controller()
window = controller.find_wechat_window()
status = controller.check_login_status()
```

### 2. `window_manager.py` - 窗口管理器
负责所有窗口相关操作。

**功能**:
- 查找窗口（通过类名、标题）
- 激活/最小化窗口
- 移动/调整窗口大小
- 显示器管理
- 截图

**示例**:
```python
from core.wechat.window_manager import WindowManager

wm = WindowManager()
window = wm.find_window_by_class(["mmui::MainWindow"], timeout=10)
wm.activate_window(window)
wm.move_window(window, x=100, y=100, width=800, height=600)
```

### 3. `version_detector.py` - 版本检测器
检测微信版本（3.x 或 4.0+）。

**功能**:
- 从窗口检测版本
- 从进程检测版本
- 检查微信进程是否运行
- 提供版本相关的窗口类名

**示例**:
```python
from core.wechat.version_detector import VersionDetector

detector = VersionDetector()
version = detector.detect_version_from_process()
is_running = detector.is_wechat_running()
```

### 4. `login_checker.py` - 登录检查器
检测和等待微信登录。

**功能**:
- 检测登录状态（NOT_RUNNING, NOT_LOGGED_IN, LOGGED_IN, LOCKED）
- 等待登录
- 启动微信

**示例**:
```python
from core.wechat.login_checker import LoginChecker, WeChatStatus

checker = LoginChecker(version_detector, window_manager)
status = checker.check_login_status()

if status == WeChatStatus.NOT_LOGGED_IN:
    print("请登录微信")
    checker.wait_for_login(timeout=300)
```

### 5. `navigation.py` - 导航操作器
处理小程序和转发相关操作。

**功能**:
- 查找小程序窗口
- 恢复小程序窗口位置
- 点击小程序按钮
- 刷新小程序
- 转发对话框操作
- 产品转发

**示例**:
```python
from core.wechat.navigation import NavigationOperator

nav = NavigationOperator()
nav.refresh_miniprogram()
nav.open_product_forward("F00619", "测试群")
```

## 向后兼容

原有的 `core/wechat_controller.py` 已更新为兼容层，所有导入仍然有效：

```python
# 原有导入方式仍然有效
from core.wechat_controller import get_wechat_controller, WeChatController, WeChatStatus

# 推荐使用新的导入方式
from core.wechat import get_wechat_controller, WeChatController, WeChatStatus
```

## 数据类型

### `Rect` (NamedTuple)
窗口矩形区域。

**属性**:
- `left: int` - 左边界
- `top: int` - 上边界
- `right: int` - 右边界
- `bottom: int` - 下边界
- `width: int` - 宽度（属性）
- `height: int` - 高度（属性）
- `center: Tuple[int, int]` - 中心点（属性）

### `MonitorInfo` (dataclass)
显示器信息。

**属性**:
- `handle: int` - 显示器句柄
- `is_primary: bool` - 是否为主显示器
- `rect: Rect` - 显示器矩形区域
- `work_rect: Rect` - 工作区域（排除任务栏）

### `WeChatStatus` (Enum)
微信状态枚举。

**值**:
- `NOT_RUNNING` - 微信未运行
- `NOT_LOGGED_IN` - 未登录
- `LOGGED_IN` - 已登录
- `LOCKED` - 锁定状态
- `UNKNOWN` - 未知状态

## 设计原则

1. **单一职责**: 每个模块负责一个明确的功能领域
2. **依赖注入**: 子模块之间通过构造函数注入依赖
3. **单例模式**: 通过 `get_wechat_controller()` 获取单例实例
4. **向后兼容**: 保留原有导入方式，不破坏现有代码

## 测试

运行主控制器测试：

```bash
cd C:\Users\95629\Downloads\programming\wechat-fabu\wechat-fabu
python core/wechat_controller.py
```

测试内容：
- 检查微信状态
- 启动微信（如果未运行）
- 查找主窗口
- 获取窗口位置和大小
- 激活窗口
- 获取显示器信息
- 截图

## 迁移指南

如果你正在编写新代码，推荐使用新的导入方式：

**旧代码**:
```python
from core.wechat_controller import get_wechat_controller

controller = get_wechat_controller()
```

**新代码（推荐）**:
```python
from core.wechat import get_wechat_controller

controller = get_wechat_controller()
```

如果需要直接使用子模块：

```python
from core.wechat import WindowManager, VersionDetector, LoginChecker, NavigationOperator

# 创建实例
wm = WindowManager()
vd = VersionDetector()
lc = LoginChecker(vd, wm)
nav = NavigationOperator()
```

## 未来优化

1. **添加类型提示**: 为所有方法添加完整的类型提示
2. **单元测试**: 为每个模块添加单元测试
3. **错误处理**: 使用 `core/exceptions.py` 中的自定义异常
4. **日志优化**: 统一日志格式和级别
5. **配置管理**: 进一步解耦配置依赖

## 相关文件

- `core/exceptions.py` - 自定义异常类
- `core/utils/element_helper.py` - UI 元素操作辅助工具
- `services/config_manager.py` - 配置管理服务
