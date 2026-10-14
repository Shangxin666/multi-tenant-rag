# Multi-tenant authentication backend — M4

Python venv + pip、FastAPI、SQLAlchemy 2.x Async、asyncpg、Alembic、
PostgreSQL 17 + pgvector。M2 实现 Tenant/User 注册、JWT 登录与 Tenant admin 查询。
不包含 RLS、Refresh Token 或 RAG。M4 新增本地文档 ingestion。

## 本地环境（PowerShell）

需要 Python 3.11+、Docker Desktop（Linux containers）。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

已有 .env 时不要覆盖。设置非空 POSTGRES_PASSWORD 和随机 JWT_SECRET。
JWT_SECRET 至少 32 字节，应使用安全随机值；没有默认 Secret。
.env 和 .venv 被 Git 忽略，.env.example 可以提交。
生产环境从环境变量注入，环境变量优先于当前目录 .env。

配置：
- DB_HOST=127.0.0.1、DB_PORT=5433；Compose 映射固定 5433 → 5432。
- POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD：开发库配置。
- JWT_SECRET：HS256 签名密钥；不要记录或提交。
- JWT_ALGORITHM：只能是 HS256。
- ACCESS_TOKEN_EXPIRE_MINUTES：默认 30，范围 1–1440。
- TEST_DATABASE_NAME：显式指定独立测试库，例如 rag_test，必须以 _test 结尾。
- DB_ECHO 默认 false；SQLAlchemy 隐藏 SQL 参数，应用不记录请求 Body 或 Authorization。

## 启动与迁移

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/docs，或验证健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
docker compose ps
```

/health 返回 200 和 {"status":"ok"}，不访问数据库。
数据库使用命名卷和 pg_isready。初始化完成后的账号密码不会因修改 .env 自动更新。
不要为了修复密码配置而删除数据卷。

0001 只启用 vector，保持历史内容不变；0002 创建 tenants/users。
迁移由明确的命令执行，应用不自动迁移，不调用 create_all。
0002 的 downgrade 会删除这两个业务表；只在可丢弃环境执行。
0001 的 downgrade 保留共享 vector 扩展。

## API

| API | 请求 | 成功响应 |
| --- | --- | --- |
| POST /auth/register | JSON: tenant_name, tenant_slug, email, password | 201: tenant + user |
| POST /auth/login | JSON: email, password | 200: access_token + token_type |
| GET /auth/me | Authorization: Bearer token | 200: UserPublic |
| GET /users | Bearer；admin；limit 默认 50、最大 100，offset 默认 0 | 200: UserPublic 数组 |

通过 /docs 执行 register → login，然后把 access_token 填入 Authorize 的 Bearer 输入框，
调用 me 和 users。登录只提供 JSON，不实现 OAuth2 表单接口。

TenantPublic: id、name、slug、created_at。
UserPublic: id、tenant_id、email、role、is_active、created_at。
这些公开 Schema 不含 password 或 password_hash。
所有输入 Schema 拒绝额外字段；注册无法指定 role、tenant_id 或 is_active。

注册密码长度 12–128，使用 SecretStr；不 trim 密码。
email 在注册和登录入口统一 strip + lower，全局唯一。
Tenant slug strip + lower，长度 1–63，仅允许字母数字及中间连字符。
Tenant name 长度 1–100。输入错误 422，email/slug 冲突统一 409。
登录错误、账号不存在或 inactive 统一 401，不返回具体原因。
未认证、无效/过期 Token 401 并附带 WWW-Authenticate: Bearer；非 admin 403。

## 模型、事务与认证

Tenant: UUID id、name、唯一 slug、带时区 created_at。
User: UUID id、tenant_id 外键、全局唯一 email、Argon2 password_hash、
admin/member role CHECK、is_active、带时区 created_at。
tenant_id 有索引；外键 ON DELETE RESTRICT。email 没有 lower/trim CHECK。
所有其他写入入口未来也必须遵守 email 规范化约定。

注册在 hash 完成后开始单一 Session 事务：Tenant add/flush → User add/flush →
事务退出 commit。User 写入失败会回滚已 flush 的 Tenant；提交后才返回 201。
get_db 提供独立 Session 并关闭，不自动提交。沿用模块级 Engine/sessionmaker，
应用关闭时 dispose，不共享并发请求的 Session。

pwdlib 使用 Argon2id，hash 和 verify 在线程池执行。账号不存在时验证 dummy hash，
减少明显时序差异；不保证完全消除侧信道。
JWT 仅含 sub（User UUID）和 exp，使用固定 HS256 验签并要求两个 claim 都存在。
get_current_user 每请求按 sub 查数据库并检查 active；require_admin 使用数据库最新 role。
Token 不含 role/tenant_id。角色修改或停用在后续请求生效。

/users 只查询 current_user.tenant_id，客户端参数不能切换 Tenant。
M2 没有成员创建或角色管理 API，测试通过 fixture 构造成员。

## 独立测试数据库

M2 集成测试不再使用开发库。保持 APP_ENV=local，在 .env 显式设置
TEST_DATABASE_NAME=rag_test（必须不同于 POSTGRES_DB，且连接目标为本机）。

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe scripts/prepare_test_database.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m integration
.\.venv\Scripts\python.exe -m pytest -o "addopts="
```

prepare_test_database.py 只创建指定测试库；已有库保留，账号需要 CREATEDB 权限。
集成测试 fixture 首先在该库执行 Alembic upgrade head，再用独立请求 Session 运行测试。
每个用例前后显式 TRUNCATE chunks、documents、knowledge_bases、users、tenants；仅允许明确指定、不同于开发库、
后缀为 _test 的本机数据库，并在清理前核对 current_database()。
不要把有价值的数据放入测试库。当前串行运行，不支持多个测试进程共用同一库。

默认 pytest 只运行单元测试；-m integration 显式运行数据库测试；
-o "addopts=" 运行全部测试。数据库不可用会报错，不静默跳过。
测试覆盖注册 hash、唯一冲突、事务整体回滚、登录、JWT 无效/过期、
数据库最新权限、member 403、跨 Tenant 隔离、响应字段及迁移约束。
单元测试中的配置和密码随机生成，不读取真实 Secret。

## 安全边界 / TODO

- tenant_id filter 只是应用层隔离，不是最终数据库级安全方案。
  PostgreSQL RLS 将在后续 Milestone 单独实现和测试。
- 当前没有 Refresh Token、Token blacklist、密码重置、邮箱验证或第三方 OAuth。
- 没有速率限制和注册防滥用，不能据此认为已经满足公开生产部署要求。
- JWT 是签名而非加密，生产必须 HTTPS；保护客户端 Token 存储。
- 更完整的 FastAPI 422 校验错误 input 脱敏属于后续 Security Hardening。
  SecretStr 不保证原始无效输入在默认校验错误响应中被隐藏。
- 数据库直接写入不强制 email 小写；未来写入口必须统一规范化。
- 生产数据库应用账号与迁移账号应分权，后续完善密钥轮换与审计。
- pip 使用依赖兼容范围，无锁文件；不同时间解析的依赖版本可能不同。


## M3：KnowledgeBase / Document / Chunk

新增三张表全部保留非空 tenant_id。KnowledgeBase name strip 首尾空白、长度 1–100，
保留大小写；同一 Tenant 内唯一，不同 Tenant 可同名。description 可空，API 最大 5000 字符。

| API | 权限 | 响应 |
| --- | --- | --- |
| POST /knowledge-bases | admin | 201；同 Tenant 重名 409 |
| GET /knowledge-bases | admin/member | 当前 Tenant 数组；limit 默认 50、范围 1–100，offset >= 0 |
| GET /knowledge-bases/{id} | admin/member | 当前 Tenant 详情；不可见或不存在均 404 |

Create 仅接受 name、description，拒绝 tenant_id/id/created_at/updated_at。
Public 仅输出 id、tenant_id、name、description、created_at、updated_at。
列表固定按 created_at、id 升序；详情在同一 SQL 中按 id + 当前 tenant_id 过滤。
客户端 query/body 不能改变授权 Tenant。

认证查询已经通过 autobegin 开启 Session 事务。创建使用 add → flush → 构造响应 →
commit → 返回；任何普通异常 rollback，已知名称唯一冲突返回 409。
不会再次 begin，不使用 nested transaction。

数据库约束：
- knowledge_bases.tenant_id → tenants.id，RESTRICT。
- UNIQUE(tenant_id, name)、UNIQUE(tenant_id, id)。
- documents.(tenant_id, knowledge_base_id) → knowledge_bases.(tenant_id, id)，RESTRICT。
- documents UNIQUE(tenant_id, id)，索引 (tenant_id, knowledge_base_id)。
- source_type 仅 pdf/markdown/html；status 仅 pending/processing/ready/failed，默认 pending。
- chunks.(tenant_id, document_id) → documents.(tenant_id, id)，CASCADE。
- chunks UNIQUE(document_id, chunk_index)，chunk_index >= 0，tenant_id 索引。
- 父表唯一索引以 tenant_id 开头，Chunk 唯一索引以 document_id 开头，不重复创建单列索引。

Chunk Python 属性 chunk_metadata 映射数据库 JSONB 列 metadata，None 存储为 SQL NULL。
没有 relationship、vector 列、Document/Chunk API 或删除 API。
0003 按 KnowledgeBase → Document → Chunk 创建，降级反向删除；0001/0002 不修改。

created_at/updated_at 使用带时区时间和数据库插入默认值。
updated_at 使用 SQLAlchemy onupdate；原始 SQL 更新必须显式设置，不是数据库触发器。
filename 仅为显示名称，不是可信存储路径；不要求文件名唯一。

测试清理范围扩展为 chunks、documents、knowledge_bases、users、tenants，
一次显式 TRUNCATE，不使用 TRUNCATE CASCADE。仍只清理已校验的独立测试库。
新增测试直接验证复合 FK、CHECK、UNIQUE、CASCADE/RESTRICT，也覆盖创建 commit 失败。

M4 接口边界：Document tenant_id 从可见 KnowledgeBase 注入，Chunk tenant_id 从 Document
注入；pending → processing → ready，失败为 failed。M3 不运行这些状态流转。
ready 应表示完整 ingestion 成功，不能只完成解析就提前发布。
未来再确定文件存储位置、重试幂等、Chunk 原子替换、Embedding 模型及维度。
error_message 只保存安全摘要，不保存 Secret、堆栈或文档全文。

复合 FK 保证父子归属一致，不能代替读取授权或 PostgreSQL RLS。
M3 不实现上传、解析、TextSplitter、Embedding、检索、RAG、Agent、Worker 或对象存储。


## M4：Document Ingestion

M4 在 HTTP 请求内完成 ingestion，不使用后台任务。只新增：
- POST /knowledge-bases/{knowledge_base_id}/documents：admin，单个 multipart 文件字段 file。
- GET /documents/{document_id}：admin/member，仅当前 Tenant。
- POST /documents/{document_id}/retry：admin，仅 failed。

上传成功创建资源返回 201 + DocumentPublic；解析失败时同样保留资源并返回 status=failed。
retry 返回 200 + DocumentPublic，必须检查 status，不把 HTTP 成功等同于 ready。
DocumentPublic 包含 id、tenant_id、knowledge_base_id、filename、source_type、status、
error_message、file_size_bytes、created_at、updated_at。
不暴露 storage_key、content_sha256 或真实路径。

仅允许 .pdf/.md/.markdown/.html/.htm，扩展名不区分大小写；MIME 不作为安全依据。
不支持扩展名 415，空文件 422，超限 413，权限不足 403，跨 Tenant 404。
额外 multipart 字段（包括 tenant_id）被拒绝。
Swagger /docs 可直接上传；也可以用 curl.exe -F "file=@sample.md" 并提供 Bearer header。
不要将真实 Token 写进脚本或提交 Git。

配置（.env.example 已列出）：
- DOCUMENT_STORAGE_ROOT=.data/documents，首次保存时创建，路径相对于启动工作目录。
- MAX_UPLOAD_BYTES=10485760（10 MiB）。
- MAX_UPLOAD_REQUEST_BYTES=11534336（11 MiB，包含 multipart 开销，应用级请求体上限）。
- CHUNK_SIZE=1000、CHUNK_OVERLAP=150，字符级，不是 token 级，尚未经检索质量评估。
- MAX_PDF_PAGES=200、MAX_PARSED_CHARS=2000000、MAX_DOCUMENT_CHUNKS=5000。

更新依赖和数据库后启动：
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 原文件与解析

存储 key 为服务端 tenant UUID / 随机 UUID，不含客户端 filename。
filename 只保留展示名称，处理 Windows/Unix 路径分隔符；真实路径必须位于 storage root。
文件以 64 KiB 分块复制到 .part 临时文件，同时统计大小和 SHA-256；
fsync、关闭后同目录原子 rename。异常清理临时文件，未保存完整文件不创建 Document。
.data/ 已被 Git 忽略，不作为静态目录提供。

0004 新增 nullable storage_key、file_size_bytes、content_sha256，兼容旧 Document。
三个字段必须同时为空或同时非空；size > 0；hash 为 64 位小写十六进制；
storage_key 唯一，hash 不唯一，不做自动去重。历史记录缺少原文件时 retry 返回 409。
0004 downgrade 删除字段和约束，不删除文件，文件与数据库的关联会丢失。

PDF 使用 pypdf 逐页提取，metadata.page 从 1 开始；加密 PDF 不支持。
Markdown 严格 UTF-8（允许 BOM），保留原 Markdown 内容。
HTML 使用 BeautifulSoup 和 html.parser，移除 script/style 等节点，提取正文，
可保留 title，不抓取网络资源。没有文本时进入 failed，不发布零 Chunk 的 ready。
解析和 RecursiveCharacterTextSplitter 整体在线程池执行，不传递数据库 Session。
langchain-text-splitters 带有 langchain-core/langsmith 等传递依赖，但本项目不启用
追踪或使用 Retriever/VectorStore/Agent，也不调用 LLM 或外部解析服务。

每个 Section 独立切块，PDF 不跨页合并。过滤空白后 Chunk index 从 0 连续编号；
metadata 复制解析上下文，不重复 tenant_id/document_id/status。
overlap 为递归切块的目标值，不保证每对 Chunk 都恰好重叠 150 字符。

### 状态与事务

认证与资源查询 → 保存 UUID 标量 → rollback 结束只读事务 → 文件保存 →
pending INSERT/commit → 条件更新 processing/commit → 无事务解析与切块 →
短事务 DELETE 旧 Chunk + INSERT 全部新 Chunk + ready/commit。

最终事务先锁定 ID + tenant_id 对应的 processing Document；
Chunk 可分批 INSERT，但不分批 commit。任何写入失败整体 rollback，
retry 原 Chunk 完整保留。新事务仅将仍为 processing 的 Document 改为 failed，
不覆盖已经提交成功的 ready。error_message 为固定安全摘要；
日志只保留错误类型及栈位置，不输出异常原始内容、请求体或 Authorization。

retry 使用 WHERE id + tenant_id + status=failed 的条件 UPDATE 取得处理权。
pending/processing/ready 返回 409；正常并发 retry 只有一个能取得处理权。
原文件每次处理前校验存在性、大小、SHA-256。成功替换全部旧 Chunk，失败保留旧 Chunk。
未来读取 Chunk 必须同时要求 Document ready；failed 留存的旧 Chunk 不是发布结果。

### 故障边界

文件系统与 PostgreSQL 没有共同事务。
pending INSERT 明确失败时尝试删除文件；提交结果不明确时先按生成的 Document ID 查询，
无法确认时保守保留文件，503 中带 Document ID 供后续查询。
可能留下未引用文件，不自动扫描或删除。状态写回失败也会返回 503，
不假装已经标记 failed。

请求取消、进程崩溃可能留下 pending/processing。没有 timeout takeover、lease、
attempt、scheduler 或 crash recovery worker，需要人工检查后续处理。
线程池不等于解析沙箱，不能强制终止解析；PDF 解压后的内存开销可能远超文件大小。
不支持 OCR、Office、杀毒、对象存储和文档下载 API。

M4 的 ready 仅代表原文件已解析并切块，不代表完成向量化。
该文本状态语义在 M5 中保持不变；M5 的独立 indexing 状态见下文。

### 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -o "addopts="
.\.venv\Scripts\python.exe -m alembic check
```

全部 M1～M3 测试保留。M4 storage 使用 pytest 临时目录，绝不使用开发 .data。
测试包括真正超过 10 MiB 的文件、无 Content-Length 的超限 multipart、PDF 页码、
独立 Session 观察已提交 pending/processing、分批 INSERT 失败和 commit 失败、
并发 retry、历史 Document 升级兼容及原文件完整性。
迁移兼容用例只在明确的独立测试库临时降级至 0003，随后恢复 head。

## M5：Basic RAG

M5 增加请求内 indexing 和非流式问答，不包含 M6/M7 功能。

### 配置和启动

仍使用 venv + pip。新增 sentence-transformers、pgvector、openai；
sentence-transformers 带入 PyTorch、Transformers、NumPy 等运行依赖。
安装和迁移沿用上文命令，之后填写本地 `.env` 中的 M5 配置：

| 配置 | 默认值 / 说明 |
| --- | --- |
| EMBEDDING_MODEL | BAAI/bge-small-zh-v1.5，M5 固定模型与 512 维 |
| EMBEDDING_DEVICE | cpu；GPU 部署须自行匹配 PyTorch/CUDA |
| EMBEDDING_BATCH_SIZE | 32 |
| DEEPSEEK_API_KEY | 本地 Secret；不提交、不打印 |
| LLM_BASE_URL | https://api.deepseek.com |
| LLM_MODEL | deepseek-flash，由配置传入请求 |
| LLM_TIMEOUT_SECONDS | 60 |
| LLM_MAX_TOKENS | 2048 |
| MAX_RAG_CONTEXT_CHARS | 12000，包含完整 source block 的标签和 metadata |

缺少 LLM key 不影响启动、上传或索引；有 Context 的问答返回安全 503。
生产模型每进程延迟加载并复用，加载/推理在线程池执行，以进程内锁串行化模型操作。
首次索引需要访问 Hugging Face 下载公开模型，之后使用本机缓存。
自动测试禁止真实模型加载和真实 LLM 客户端，使用 fake / mock transport。

### 数据和状态

0005 新增 `chunks.embedding VECTOR(512) NULL`，不创建近似向量索引。
Document 新增 `index_status`、`index_error_message`、`embedding_model`、`indexed_at`。
迁移先增加 nullable 状态列、回填所有历史行为 pending，再设置 NOT NULL 和 pending 默认值。
历史 embedding 保持 NULL；0001～0004 不修改。
CHECK 限定四种索引状态；processing/ready 要求文本 ready；只有 index ready 才允许
非空 model/indexed_at，且必须同时存在、error 为空。其他状态 model/indexed_at 为空。
跨表“全部 Chunk 都有向量”由短事务发布和测试保证，不使用跨表 CHECK 或触发器。
0005 downgrade 删除新字段和约束，会丢弃向量，但保留文本、Chunk 和原文件。

M4 发布新 Chunk 时，在同一个事务重置 index pending、清空索引元信息；新向量为 NULL。
`Document.status=ready` 始终只表示文本和切块已经发布。

### API

| API | 权限 | 响应 |
| --- | --- | --- |
| POST /documents/{id}/index | admin | 200 DocumentPublic；必须检查 index_status |
| GET /documents/{id} | admin/member | 包含独立索引状态和安全错误摘要 |
| POST /knowledge-bases/{id}/query | admin/member | answer + sources |

index 仅允许文本 ready 且索引 pending/failed。其他状态返回 409。
正常并发请求通过 tenant/id/status 条件 UPDATE RETURNING 取得唯一处理权。
编码失败或发布失败且成功记录状态：200 + index failed；状态不可可靠确认：503。
query JSON 仅接受 question 和 top_k；问题 strip 后 1～2000 字符，top_k 默认 5，范围 1～10。
不存在与跨 Tenant 资源均为 404；member index 为 403。

### 事务和检索

认证/范围查询结束只读事务 → claim processing/commit → 读取 Chunk 普通数据快照并结束事务 →
线程池生成向量 → 短事务锁 Document、重查 Chunk 的数量/ID/index/content →
分批更新向量（不分批 commit）→ index ready + model + indexed_at 一次提交。
任何更新或提交失败整体 rollback，新事务只把仍 processing 的记录标 failed，避免覆盖已提交 ready。
没有 Chunk 不能完成索引。模型输出必须数量一致、512 维、有限值且单位范数合理。

Passage 直接编码正文，Query 前缀为“为这个句子生成表示以用于检索相关文章：”。
两者都 normalize_embeddings=True。模型 encode 保持输入顺序，数据库按 chunk_index/id 取快照。
该模型输入上限为 512 tokens，现有 1000 字符 Chunk 不等于 512 tokens，长输入会被模型截断；
这是 baseline 的召回质量边界，M5 不改变 M4 切块或引入多向量/版本系统。

query 先检查是否有可检索 Chunk；没有则不加载 embedding、不调用 LLM，返回 200：
“当前知识库中没有足够的信息回答该问题”，sources=[]。
调用链明确为 embed_query → retrieve_chunks → build_context → generate_answer。
检索 SQL 对 Chunk 和 Document 同时过滤 tenant，限制 KB、文本 ready、index ready、
配置中的 embedding model 和非空向量，然后 cosine_distance ASC、Chunk.id ASC、LIMIT top_k。
不做全库检索后的 Python 租户过滤。distance 越小越近，不是 confidence。
Embedding 和外部 LLM 调用期间不持有数据库事务。

### Context、来源和外部服务

按排名加入完整 [S1]/[S2] source block，下一个 block 超过字符预算立即停止。
正文、展示文件名及允许的 page/title 作为 JSON 数据转义，Context 不进入 system message。
公开 sources 只包含实际加入 Context 的来源，snippet 最多 300 字符，不返回任意原始 metadata、
向量、storage key、hash 或本地路径。title 最多 300 字符。
固定 system message 要求只依据资料、忽略资料中的指令、信息不足说明、禁止虚构引用。
返回未知 S 编号视为 upstream invalid result，返回安全 502，不偷偷替换引用。
来源编号检查不能证明事实正确，Prompt Injection 没有被完全解决。

DeepSeek 使用 AsyncOpenAI、stream=False、显式 thinking.type=disabled，
只读取 message.content，不读取或返回 reasoning_content，不提供工具。
超时/连接失败/限流/上游不可用返回 503，其他无效响应返回 502。
不自动重试 provider 请求，不记录请求 Body、Authorization、完整 Prompt/Context 或 provider 原始异常。
发送给 DeepSeek 的内容包括用户问题和检索到的文档片段；部署方应确认文档允许外发。

### 验证命令

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
docker compose up -d --wait
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe scripts/prepare_test_database.py
.\.venv\Scripts\python.exe -m pytest -o "addopts="
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

真实验收脚本不是 pytest 测试，不使用 fake。它运行真实 Uvicorn HTTP，使用独立测试库和临时文件，
只清理本次创建租户的数据。请勿与回归测试同时运行。仅验证本地模型/数据库/权限：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_m5 --skip-llm
```

完整验收在 `.env` 配置有效 DeepSeek key 后运行 `python -m scripts.verify_m5`。
它会把脚本中的人工年假资料和问题发送到配置中的 LLM 服务，验证真实回答和 sources。
没有 key 或显式 skip 时会打印 NOT VERIFIED，不把本地模型或 fake 测试当作真实 LLM 验收。

### 已知边界

无崩溃接管、lease/heartbeat 或 durable worker；中断可能留下 index processing。
线程池不是进程隔离，无法强制取消模型推理，多 worker 各自占用一份模型内存。
模型权重未按 revision 锁定；模型升级与重建索引须后续单独设计，不能只改配置后混用向量。
Exact search 未做规模性能评估，不声明生产吞吐量；字符 Context 预算不是 token 精确预算。
无相似度阈值或质量评估体系，有召回结果不代表足以回答问题。
应用层 tenant filter 仍是访问隔离边界，Composite FK 只保证一致性，不是 RLS。
不实现 BM25、融合、rerank、HNSW/IVFFlat、SSE、会话、Agent、RLS、Redis 或任务队列。
