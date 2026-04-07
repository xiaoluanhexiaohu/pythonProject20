# 校园体育天气联动系统（pythonProject20）

本项目是一个基于 Django 的校园体育活动管理系统，支持：

- 校区、场地、活动维护
- 天气中心、预警中心
- 基于天气的智能建议
- 活动自动排程与通知

---

## 新增：实时天气 API（双版本）

已新增两个对中国地区可用性较好的实时天气接口版本，都会基于**已维护的校区地址**拉取天气，并自动联动：

1. 生成/刷新天气记录（`WeatherRecord`）
2. 生成预警（`WeatherAlert`）
3. 若有预警，写入系统通知（`Notification`）
4. 生成智能建议（`Suggestion`）

### API 列表

- **V1（和风天气 QWeather）**  
  `GET /api/v1/weather/refresh/<campus_id>/`
- **V2（高德开放平台 AMap）**  
  `GET /api/v2/weather/refresh/<campus_id>/`

返回示例：

```json
{
  "ok": true,
  "version": "v1",
  "provider": "qweather",
  "data": {
    "campus": "主校区",
    "provider": "qweather",
    "records": 1,
    "alerts": 0,
    "suggestions": 8
  }
}
```

---

## 快速启动

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

---

## API 申请与接入教程

> 下面给出两套接口申请与配置步骤，你可以先接入任意一个，另一个作为备用版本。

### 版本一：和风天气（QWeather）

#### 1）申请 Key

1. 打开：https://dev.qweather.com/
2. 注册并登录开发者账号
3. 创建项目，选择 Web 服务
4. 获取 API Key

#### 2）在项目中配置

编辑 `campus_sports_weather_system/settings.py`：

```python
QWEATHER_BASE_URL = "https://devapi.qweather.com"
QWEATHER_API_KEY = "你的QWeatherKey"
```

#### 3）调用方式

```bash
curl "http://127.0.0.1:8000/api/v1/weather/refresh/1/"
```

#### 4）调用链路说明

- 系统使用校区 `location`（地址）先调用 QWeather 地理查询接口拿到 `location id`
- 再调用实时天气接口获取实时天气
- 自动写入天气记录、预警中心、智能建议、系统通知

---

### 版本二：高德开放平台（AMap）

#### 1）申请 Key

1. 打开：https://lbs.amap.com/
2. 注册并登录
3. 进入应用管理创建应用
4. 添加 Web 服务 Key

#### 2）在项目中配置

编辑 `campus_sports_weather_system/settings.py`：

```python
AMAP_BASE_URL = "https://restapi.amap.com"
AMAP_API_KEY = "你的AMapKey"
```

#### 3）调用方式

```bash
curl "http://127.0.0.1:8000/api/v2/weather/refresh/1/"
```

#### 4）调用链路说明

- 系统使用校区 `location`（地址）先调用高德地理编码拿到 `adcode`
- 再调用高德实时天气接口获取天气
- 自动写入天气记录、预警中心、智能建议、系统通知

---

## 一次跑成功建议（务必按顺序）

1. 先执行 `python manage.py seed_demo`，保证有校区数据。  
2. 在校区管理里把 `location` 地址填完整（如“上海市闵行区东川路800号”）。  
3. 至少配置一个可用 API Key（QWeather 或 AMap）。  
4. 用浏览器或 curl 调用对应版本接口。  
5. 到以下页面核验结果：
   - 天气中心 `/weather/`
   - 预警中心 `/alerts/`
   - 智能建议 `/suggestions/`
   - 系统通知 `/notifications/`

---

## 兼容说明

- 原有 `weather/refresh/` 页面功能仍保留（默认 Open-Meteo）。
- 新增 API 版本是对外接口能力增强，不影响原有页面流程。
