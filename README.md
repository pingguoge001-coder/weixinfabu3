# 微信自动发布助手

PC 端微信自动发布工具，支持朋友圈发布、群发消息、小程序转发、定时任务等功能。

## 功能特性

- **朋友圈发布** - 支持图文/纯文字自动发布
- **群发消息** - 代理群、客户群批量发送
- **小程序转发** - 小程序商品自动转发到群
- **自定义频道** - 支持配置多个自定义发布频道
- **定时任务** - 支持间隔发送、固定时间点发送
- **语音播报** - 发布完成后语音提醒
- **邮件通知** - 发布结果邮件推送
- **数据统计** - 发布数据可视化报表
- **风控检测** - 熔断重试、异常告警
- **激活码系统** - 软件授权管理

## 环境要求

- Python 3.8+
- Windows 10/11
- 微信 PC 版 v3.9.x
- 屏幕分辨率 >= 1920x1080

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

### 主要依赖

| 依赖 | 用途 |
|------|------|
| PySide6 | GUI 界面 |
| uiautomation | UI 自动化 |
| pywinauto | 窗口控制 |
| PyAutoGUI | 鼠标键盘操作 |
| pyperclip | 剪贴板操作 |
| pywin32 | Windows API |
| openpyxl | Excel 解析 |
| Pillow | 图片处理 |
| opencv-python | 图像识别 |
| APScheduler | 定时调度 |
| pyttsx3 | 语音播报 |
| watchdog | 文件监控 |
| cryptography | 密码加密 |

## 快速开始

### 1. 激活软件

首次使用需要激活码。在 `config.yaml` 中配置激活凭证：

```yaml
activation:
  app_key: 你的app_key
  app_secret: 你的app_secret
```

凭证可在管理后台获取：https://pingguoge.zeabur.app/admin

### 2. 配置发布参数

编辑 `config.yaml`：

```yaml
paths:
  shared_folder: ./data/shared    # 发布内容目录
  cache_dir: ./data/cache         # 缓存目录
  logs_dir: ./data/logs           # 日志目录

schedule:
  channels:
    moment:                       # 朋友圈
      enabled: true
      mode: interval
      interval_value: 3
      interval_unit: minutes
    agent_group:                  # 代理群
      enabled: true
      interval_value: 1
      interval_unit: minutes
    customer_group:               # 客户群
      enabled: true
      interval_value: 1
      interval_unit: minutes
```

### 3. 准备发布内容

在 `data/shared` 目录放置 Excel 文件，格式：

| 列 | 说明 |
|----|------|
| 文本 | 发布文案 |
| 图片 | 图片文件名 (多张用逗号分隔) |

### 4. 启动程序

```bash
python run.py
```

## 配置说明

### 定时设置

```yaml
schedule:
  default_interval: 180        # 默认间隔 (秒)
  daily_limit: 50              # 每日限额
  random_delay_min: 0          # 随机延迟范围
  random_delay_max: 60
  active_hours:
    start: 08:00               # 运行时段
    end: 22:00
  work_days: [1,2,3,4,5,6,7]   # 工作日 (1=周一)
```

### 自定义频道

```yaml
custom_channels:
  custom_1:
    name: 自定义频道名
    enabled: true
    global_group_names:
      - 群名1
      - 群名2
    daily_start_time: 08:00
    daily_end_time: 22:00
```

### 邮件通知

```yaml
email:
  enabled: true
  smtp:
    host: smtp.qq.com
    port: 465
    use_ssl: true
  sender:
    address: your-email@qq.com
    password: ENC(加密密码)
  notify_on:
    failure: true              # 失败时通知
    daily_summary: true        # 每日汇总
    circuit_break: true        # 熔断告警
```

### 语音播报

```yaml
voice:
  moment_complete_enabled: true
  moment_complete_text: 又发了一条朋友圈，还剩{remaining}条
  agent_group_complete_enabled: true
  customer_group_complete_enabled: true
```

### 熔断保护

```yaml
circuit_breaker:
  enabled: true
  failure_threshold: 3         # 连续失败3次触发熔断
  recovery_timeout: 300        # 5分钟后恢复
  half_open_attempts: 1        # 半开状态尝试次数
```

### 小程序配置

```yaml
miniprogram:
  restore_window:
    x: 1493
    y: 236
  buttons:
    more:
      absolute_x: 2150
      absolute_y: 323
    forward:
      absolute_x: 2177
      absolute_y: 1110
```

### 图片处理

```yaml
image_processing:
  auto_compress: true
  compress_quality: 85
  max_size:
    width: 2048
    height: 2048
  max_file_size_mb: 10
  supported_formats: [.jpg, .jpeg, .png, .gif, .bmp, .webp]
```

## 项目结构

```
wechat-fabu/
├── gui/                       # 界面层
│   ├── main_window.py         # 主窗口
│   ├── queue_tab.py           # 发布队列
│   ├── schedule_tab.py        # 定时设置
│   ├── stats_tab.py           # 数据统计
│   ├── settings_tab.py        # 系统设置
│   ├── activation_dialog.py   # 激活对话框
│   ├── preview_dialog.py      # 预览对话框
│   ├── log_panel.py           # 日志面板
│   └── styles.py              # 界面样式
├── core/                      # 核心执行层
│   ├── moment_sender.py       # 朋友圈发布
│   ├── group_sender.py        # 群发消息
│   ├── base_sender.py         # 发送器基类
│   ├── wechat_controller.py   # 微信控制
│   ├── element_locator.py     # 元素定位
│   ├── risk_detector.py       # 风控检测
│   ├── popup_detector.py      # 弹窗检测
│   ├── display_manager.py     # 显示管理
│   ├── clipboard_manager.py   # 剪贴板管理
│   ├── env_checker.py         # 环境检查
│   ├── shutdown_controller.py # 关机控制
│   └── exceptions.py          # 异常定义
├── scheduler/                 # 调度层
│   ├── queue_manager.py       # 任务队列
│   ├── task_scheduler.py      # 定时调度
│   ├── circuit_breaker.py     # 熔断器
│   ├── retry_handler.py       # 重试处理
│   ├── rate_limiter.py        # 速率限制
│   └── idempotency_manager.py # 幂等性管理
├── services/                  # 服务层
│   ├── config_manager.py      # 配置管理
│   ├── activation_service.py  # 激活服务
│   ├── email_notifier.py      # 邮件通知
│   ├── voice_notifier.py      # 语音播报
│   ├── notification_manager.py# 通知管理
│   ├── stats_service.py       # 统计服务
│   └── time_service.py        # 时间服务
├── data/                      # 数据层
│   ├── database.py            # SQLite 数据库
│   ├── excel_parser.py        # Excel 解析
│   ├── image_loader.py        # 图片加载
│   ├── image_validator.py     # 图片验证
│   └── path_mapper.py         # 路径映射
├── models/                    # 数据模型
│   ├── task.py                # 任务模型
│   ├── content.py             # 内容模型
│   ├── stats.py               # 统计模型
│   └── enums.py               # 枚举定义
├── tests/                     # 测试目录
├── config.yaml                # 配置文件
├── selectors.yaml             # 元素选择器配置
└── run.py                     # 程序入口
```

## 使用注意

1. 确保微信 PC 端已登录
2. 不要遮挡微信窗口
3. 建议使用固定屏幕分辨率 (1920x1080)
4. 首次使用建议小量测试
5. 运行期间请勿手动操作微信

## 许可证

MIT License
