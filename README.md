# Bailian Knowledge Base Service

这是一个基于 FastAPI 的阿里云百炼知识库服务示例项目，当前提供以下能力：

- 创建知识库
- 上传本地文件到默认知识库
- 列出知识库中的文件
- 检索知识库内容

项目当前主要面向“文档搜索类知识库”场景。

## 1. 环境要求

- Python `>= 3.13`
- 使用 `uv` 管理依赖和运行服务

## 2. 安装依赖

如果你还没有安装依赖，可以在项目根目录执行：

```bash
uv sync
```

如果你使用的是 `pip`，也可以按 `pyproject.toml` 中的依赖自行安装。

## 3. 环境变量配置

在项目根目录创建 `.env` 文件，并至少配置以下内容：

```env
ALIBABA_CLOUD_ACCESS_KEY_ID=你的阿里云AK
ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的阿里云SK
WORKSPACE_ID=你的百炼工作空间ID
BAILIAN_REGION_ID=cn-beijing
IndexID=你的默认知识库ID
BAILIAN_CATEGORY_ID=default
```

### 必填项

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `WORKSPACE_ID`

### 常用可选项

- `BAILIAN_REGION_ID`
  默认值为 `cn-beijing`
- `IndexID`
  默认知识库 ID。上传文件、列出文件、检索内容时会优先使用它
- `BAILIAN_CATEGORY_ID`
  默认分类 ID。上传文件时如果未传，会优先使用它

### 兼容变量名

项目同时兼容以下写法：

- AK：`BAILIAN_ACCESS_KEY_ID` 或 `ALIBABA_CLOUD_ACCESS_KEY_ID`
- SK：`BAILIAN_ACCESS_KEY_SECRET` 或 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Workspace：`BAILIAN_WORKSPACE_ID` 或 `WORKSPACE_ID`
- 默认知识库 ID：`BAILIAN_INDEX_ID` 或 `INDEX_ID` 或 `IndexID`
- 默认分类 ID：`BAILIAN_CATEGORY_ID` 或 `CATEGORY_ID` 或 `CategoryID`

## 4. 启动服务

在项目根目录执行：

```bash
uv run uvicorn app.main:app --reload
```

启动成功后，默认访问地址：

- 服务首页：`http://127.0.0.1:8000/`
- Swagger 文档：`http://127.0.0.1:8000/docs`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

首页返回示例：

```json
{
  "message": "Bailian knowledge base service is running."
}
```

## 5. 接口说明

### 5.1 创建知识库

接口：

```http
POST /knowledge-bases
```

说明：

- 默认使用智能切块
- 默认 `chunk_size=1500`
- 默认 `overlap_size=200`
- 如果不传 `category_id`，服务会先自动创建一个空分类

请求示例：

```json
{
  "name": "电影",
  "description": "电影独白",
  "chunk_size": 1500,
  "overlap_size": 200,
  "enable_headers": false,
  "embedding_model_name": "text-embedding-v4",
  "rerank_model_name": "qwen3-rerank"
}
```

返回示例：

```json
{
  "index_id": "n2eud17xyd",
  "category_id": "default",
  "request_id": "xxx"
}
```

### 5.2 上传文件到默认知识库

接口：

```http
POST /knowledge-bases/documents
```

说明：

- 使用 `multipart/form-data`
- 默认上传到环境变量中的默认知识库 `IndexID`
- 默认分类优先取 `BAILIAN_CATEGORY_ID`，没有则回退到 `default`
- 默认使用智能切块
- 默认 `chunk_size=1500`
- 默认 `overlap_size=200`
- 默认 `wait_for_finish=false`，接口会先返回任务提交结果，不会一直等待解析完成

常用表单字段：

- `file`：上传文件，必填
- `category_id`：可选，默认 `default`
- `parser`：默认 `AUTO_SELECT`
- `chunk_size`：默认 `1500`
- `overlap_size`：默认 `200`
- `chunk_mode`：留空表示智能切块
- `wait_for_finish`：默认 `false`

返回示例：

```json
{
  "file_id": "file-xxx",
  "job_id": "job-xxx",
  "index_id": "n2eud17xyd",
  "category_id": "default",
  "status": "RUNNING"
}
```

### 5.3 列出知识库中的文件

接口：

```http
GET /knowledge-bases/documents/list
```

说明：

- 使用环境变量中的默认知识库 ID

返回内容包含：

- 文件 ID
- 文件名
- 索引状态
- 文件大小
- 修改时间

### 5.4 检索知识库内容

接口：

```http
POST /knowledge-bases/retrieve
```

请求示例：

```json
{
  "query": "这份文档主要讲了什么",
  "dense_similarity_top_k": 5,
  "sparse_similarity_top_k": 5,
  "rerank_top_n": 5,
  "enable_reranking": true,
  "enable_rewrite": false
}
```

返回内容包含：

- `nodes`：召回到的片段
- `request_id`：本次请求 ID

## 6. Swagger 测试建议

建议按下面顺序测试：

1. 先打开 `/docs`
2. 调用 `POST /knowledge-bases` 创建知识库
3. 把返回的 `index_id` 保存到 `.env` 中的 `IndexID`
4. 重启服务
5. 调用 `POST /knowledge-bases/documents` 上传文件
6. 调用 `GET /knowledge-bases/documents/list` 查看文件状态
7. 调用 `POST /knowledge-bases/retrieve` 做检索测试

## 7. 常见说明

### 智能切块怎么设置

如果你想使用智能切块：

- `chunk_mode` 留空
- 不要填写 `separator`

如果你填写了 `chunk_mode`，当前仅支持：

- `length`
- `page`
- `h1`
- `h2`
- `regex`

其中只有 `regex` 模式才会使用 `separator`。

### 为什么上传文件后一直转圈

如果 `wait_for_finish=true`，接口会等待百炼解析和建索引完成，耗时可能较长。  
如果只是想先把任务提交出去，建议使用默认值：

```text
wait_for_finish=false
```

### 为什么会报缺少环境变量

如果出现类似错误：

```text
Missing required environment variables
```

请先检查 `.env` 中是否正确配置了：

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `WORKSPACE_ID`

### 为什么上传文件时报 category_id 错误

如果返回：

```text
ApplyFileUploadLease failed: Cant find out category for your category_id parameter.
```

优先检查：

- `.env` 中是否设置了 `BAILIAN_CATEGORY_ID`
- 传入的 `category_id` 是否有效

如果你当前业务就是用默认分类，可以先尝试：

```env
BAILIAN_CATEGORY_ID=default
```

## 8. 项目结构

```text
app/
  main.py                 FastAPI 入口
  config.py               环境变量配置
  router/
    endpoint.py           路由层
  service/
    service.py            百炼知识库服务层
  test/
    generate_swagger.py   导出 OpenAPI 文件
    swagger.json          当前 Swagger 导出文件
```

## 9. 导出 Swagger 文件

如果需要重新生成本地 Swagger 文件，可以执行：

```bash
python -m app.test.generate_swagger
```

如果你的环境无法直接用这个命令导入模块，也可以在项目根目录下用等效脚本方式重新生成。
