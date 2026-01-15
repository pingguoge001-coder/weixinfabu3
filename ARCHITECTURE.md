# 项目架构文档

## 整体架构

```
wechat-fabu/
├── gui/                    # UI层
│   ├── main_window.py      # 主窗口 (1030行)
│   ├── queue_tab.py        # 队列标签页
│   ├── schedule_tab.py     # 定时任务标签页
│   ├── stats_tab.py        # 统计报表标签页
│   ├── settings_tab.py     # 设置标签页
│   └── services/           # GUI业务逻辑服务层 ✨ NEW
│       ├── __init__.py
│       ├── task_executor.py         # 任务执行器 (224行)
│       ├── scheduler_controller.py  # 调度器控制器 (260行)
│       └── import_handler.py        # 导入处理器 (141行)
│
├── core/                   # 核心业务逻辑
│   ├── moment/             # 朋友圈发布模块 ✨ 已重构
│   │   ├── __init__.py
│   │   ├── locator.py          # 元素定位器
│   │   ├── window_handler.py   # 窗口处理器
│   │   ├── image_handler.py    # 图片处理器
│   │   ├── text_handler.py     # 文案处理器
│   │   ├── publish_handler.py  # 发布处理器
│   │   └── sender.py           # 主发送器
│   │
│   ├── moment_sender.py    # 向后兼容层
│   ├── wechat_controller.py # 微信控制器
│   ├── group_sender.py     # 群发送器
│   └── clipboard_manager.py # 剪贴板管理器
│
├── scheduler/              # 调度系统
│   ├── task_scheduler.py   # 任务调度器
│   ├── queue_manager.py    # 队列管理器
│   └── idempotency_manager.py # 幂等性管理器
│
├── models/                 # 数据模型
│   ├── task.py            # 任务模型
│   ├── content.py         # 内容模型
│   ├── enums.py           # 枚举定义
│   └── stats.py           # 统计模型
│
├── data/                   # 数据访问层
│   ├── database.py        # 数据库操作
│   └── excel_parser.py    # Excel解析器
│
└── services/               # 全局服务
    ├── config_manager.py   # 配置管理器
    └── voice_notifier.py   # 语音通知器
```

## 层次架构

### 1. UI层 (gui/)
**职责**: 用户界面展示和用户交互

```
MainWindow (主窗口)
    ├── 管理标签页
    ├── 系统托盘
    ├── 状态栏
    └── 菜单栏

使用服务:
    ├── TaskExecutor (任务执行)
    ├── SchedulerController (调度控制)
    └── ImportHandler (数据导入)
```

### 2. GUI服务层 (gui/services/) ✨ NEW
**职责**: UI相关的业务逻辑，连接UI层和核心业务层

#### TaskExecutor (任务执行器)
```
职责:
- 异步执行任务
- 管理任务执行流程
- 通过信号与UI通信

依赖:
- core.moment_sender.MomentSender
- core.group_sender.GroupSender
- models.task.Task
- models.content.Content

信号:
- task_started
- task_completed
- task_failed
```

#### SchedulerController (调度器控制器)
```
职责:
- 管理调度器生命周期
- 监控调度器状态
- 管理任务队列

依赖:
- scheduler.task_scheduler.TaskScheduler
- scheduler.queue_manager.QueueManager
- scheduler.idempotency_manager.IdempotencyManager

信号:
- status_changed
- scheduler_started
- scheduler_paused
- scheduler_stopped
```

#### ImportHandler (导入处理器)
```
职责:
- 解析Excel文件
- 管理导入数据
- 保存任务到数据库

依赖:
- data.excel_parser
- data.database.Database
- models.task.Task
- models.content.Content

信号:
- import_started
- import_completed
- import_failed
```

### 3. 核心业务层 (core/)
**职责**: 核心业务逻辑实现

#### 朋友圈发布模块 (core/moment/) ✨ 已重构
```
MomentSender (主发送器)
    使用:
    ├── WindowHandler (窗口管理)
    ├── ImageHandler (图片处理)
    ├── TextHandler (文案处理)
    ├── PublishHandler (发布操作)
    └── ElementLocator (元素定位)
```

#### 微信控制器 (core/wechat_controller.py)
```
职责:
- 微信窗口查找和管理
- 版本检测
- 基础UI操作
```

#### 群发送器 (core/group_sender.py)
```
职责:
- 群聊消息发送
- 批量发送管理
- 小程序转发
```

### 4. 调度系统 (scheduler/)
**职责**: 任务调度和队列管理

```
TaskScheduler (任务调度器)
    ├── 定时任务调度
    ├── APScheduler集成
    └── 任务执行触发

QueueManager (队列管理器)
    ├── 渠道队列管理
    ├── 任务队列操作
    └── 队列状态监控

IdempotencyManager (幂等性管理器)
    ├── 防止重复执行
    └── 执行记录管理
```

### 5. 数据层 (models/ + data/)
**职责**: 数据模型和数据访问

```
Models (数据模型)
    ├── Task (任务)
    ├── Content (内容)
    ├── Stats (统计)
    └── Enums (枚举)

Data Access (数据访问)
    ├── Database (SQLite操作)
    └── ExcelParser (Excel解析)
```

### 6. 全局服务 (services/)
**职责**: 全局共享服务

```
Services
    ├── ConfigManager (配置管理)
    └── VoiceNotifier (语音通知)
```

## 数据流

### 任务导入流程
```
用户选择文件夹
    ↓
QueueTab.import_folder()
    ↓
MainWindow._on_import_file()
    ↓
ImportHandler.import_folder()
    ↓
ExcelParser.parse_folder()
    ↓
ImportHandler.save_tasks_to_db()
    ↓
Database.create_task()
    ↓
SchedulerController.add_task()
    ↓
QueueManager.add_task()
    ↓
UI更新
```

### 任务执行流程 (手动执行)
```
用户点击执行
    ↓
QueueTab.task_execute_requested
    ↓
MainWindow._on_execute_task()
    ↓
TaskExecutor.execute_task_async()
    ↓
TaskExecutor.execute_moment_task() 或 execute_group_task()
    ↓
MomentSender.send_moment() 或 GroupSender.send_to_groups()
    ↓
TaskExecutor.task_completed (信号)
    ↓
MainWindow._on_task_completed()
    ↓
UI更新 + 语音通知
```

### 任务执行流程 (自动调度)
```
用户启动发布
    ↓
MainWindow._on_start_publishing()
    ↓
SchedulerController.start()
    ↓
TaskScheduler.start_scheduler()
    ↓
APScheduler 触发任务
    ↓
MainWindow._execute_scheduled_task()
    ↓
TaskExecutor.execute_moment_task() 或 execute_group_task()
    ↓
SchedulerController.mark_task_success/failed()
    ↓
MainWindow.scheduled_task_finished_signal
    ↓
MainWindow._on_scheduled_task_finished()
    ↓
UI更新 + 托盘通知 + 语音通知
```

## 通信机制

### 信号槽连接
```python
# GUI服务层 → 主窗口
TaskExecutor.task_completed → MainWindow._on_task_completed
SchedulerController.status_changed → MainWindow._on_scheduler_status_changed
ImportHandler.import_completed → MainWindow._on_import_completed

# 子标签页 → 主窗口
QueueTab.task_execute_requested → MainWindow._on_execute_task
QueueTab.start_publishing_requested → MainWindow._on_start_publishing
QueueTab.import_requested → MainWindow._on_import_file
```

### 依赖注入
```python
# 主窗口初始化服务
self._task_executor = TaskExecutor(self)
self._task_executor.set_group_names_provider(self._get_channel_group_names)
self._task_executor.set_extra_message_provider(self._get_channel_extra_message)

# 服务通过provider获取UI数据，避免直接依赖
```

## 设计模式

### 1. 分层架构 (Layered Architecture)
- UI层 → 服务层 → 业务层 → 数据层
- 每层只依赖下层，不依赖上层

### 2. 服务定位器 (Service Locator)
```python
from services.config_manager import get_config_manager
from core.wechat_controller import get_wechat_controller
```

### 3. 观察者模式 (Observer)
- Qt信号槽机制实现
- 服务层通过信号通知UI层

### 4. 策略模式 (Strategy)
```python
# TaskExecutor根据渠道类型选择执行策略
if task.channel == Channel.moment:
    result = self.execute_moment_task(task, content)
else:
    result = self.execute_group_task(task, content)
```

### 5. 工厂模式 (Factory)
```python
# core/moment/__init__.py
def create_moment_sender():
    return MomentSender()
```

### 6. 提供器模式 (Provider)
```python
# UI数据通过provider函数传递给服务层
self._task_executor.set_group_names_provider(self._get_channel_group_names)
```

## 重构成果

### 代码统计
```
gui/main_window.py:      1167 → 1030 行 (-137行, -11.7%)

新增服务文件:
├── task_executor.py:         224 行
├── scheduler_controller.py:  260 行
└── import_handler.py:        141 行
总计:                         625 行 (含文档)
```

### 优势
1. **职责分离**: UI层与业务逻辑分离
2. **可测试性**: 服务类可独立测试
3. **可维护性**: 代码结构清晰，易于定位和修改
4. **可扩展性**: 新增功能只需添加新服务类
5. **向后兼容**: 保持所有原有接口不变

### 测试验证
```bash
# 语法检查
✅ python -m py_compile gui/main_window.py
✅ python -m py_compile gui/services/*.py

# 导入测试
✅ from gui.services import TaskExecutor, SchedulerController, ImportHandler
```

## 未来优化建议

### 短期 (1-2周)
1. 为服务类添加单元测试
2. 完善错误处理和日志记录
3. 添加API文档和使用示例

### 中期 (1-2个月)
1. 重构其他大文件 (queue_tab.py, stats_tab.py)
2. 优化性能瓶颈
3. 实现插件化架构

### 长期 (3-6个月)
1. 引入依赖注入框架
2. 实现微服务架构
3. 支持分布式部署

## 总结

通过本次重构，成功建立了清晰的分层架构，将业务逻辑从UI层分离到独立的服务层。主窗口代码从1167行减少到1030行，同时创建了3个专门的服务类来处理任务执行、调度控制和数据导入。重构后的代码结构更清晰、职责更明确、更易于测试和维护，为项目的长期发展奠定了坚实的基础。
