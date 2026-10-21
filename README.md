# Multi-tenant RAG backend — M6

Python venv + pip、FastAPI、SQLAlchemy 2.x Async、asyncpg、Alembic、
PostgreSQL 17 + pgvector。M2 实现 Tenant/User 注册、JWT 登录与 Tenant admin 查询。
M4 实现本地文档 ingestion，M5 实现 Basic RAG，M6 增加 PostgreSQL RLS。
不包含 Refresh Token 或 M7 检索增强。

## 本地环境（PowerShell）

需要 Python 3.11+、Docker Desktop（Linux containers）。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

已有 .env 时不要覆盖。设置非空 POSTGRES_PASSWORD、APP_DB_PASSWORD、MIGRATION_DB_PASSWORD 和随机 JWT_SECRET。
三个数据库密码应分别生成，应用连接身份固定为 rag_app，迁移为 rag_migrator。
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
.\.venv\Scripts\python.exe -m scripts.prepare_database_roles
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
集成测试 fixture 首先准备专用角色并在该库执行 Alembic upgrade head，再用真实 rag_app 请求 Session 运行测试。
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
  M6 在此基础上增加 PostgreSQL RLS，具体身份与事务边界见下文。
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
应用层 tenant filter 保留，Composite FK 保证一致性；M6 另提供 RLS 防线。
不实现 BM25、融合、rerank、HNSW/IVFFlat、SSE、会话、Agent、Redis 或任务队列。

## M6：PostgreSQL Row-Level Security

### 必须遵守的执行顺序

先停止旧应用，避免它继续使用管理员凭据访问数据库。保留原数据卷和 M1～M5 migration。
在本地 `.env` 中分别配置管理员 POSTGRES_*、APP_DB_PASSWORD 和 MIGRATION_DB_PASSWORD。
现有 `.env` 不要用示例覆盖；Secret 不进 Git、不进入命令行参数。

```powershell
docker compose up -d --wait db
# 管理员身份：创建/校正三个固定角色，调整明确列出的项目表所有权。
.\.venv\Scripts\python.exe -m scripts.prepare_database_roles
# rag_migrator：创建 Policy、认证函数、ACL，并 ENABLE/FORCE RLS。
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
# rag_app：启动时校验角色、RLS 标志、对象所有权、认证函数和危险权限。
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

角色初始化可以重复运行，保留数据，不禁用已有 RLS，不做全库 REASSIGN OWNED。
只调整 alembic_version、tenants、users、knowledge_bases、documents、chunks 的所有权。
在全新数据库中，管理员先启用 vector，随后历史 0001 的 IF NOT EXISTS 保持幂等。
角色是 PostgreSQL 集群级对象，数据库级 grant/所有权是每个库独立配置；本地开发库与测试库
共用同一套固定角色凭据。不要在共享集群上把本脚本当作任意项目角色管理器使用。
若 rag_app 或 rag_auth_lookup 已加入其他角色，脚本拒绝继续，须管理员先审计现有授权。

测试库准备顺序：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_test_database.py
.\.venv\Scripts\python.exe -m scripts.prepare_database_roles --test
.\.venv\Scripts\python.exe -m pytest -o "addopts="
```

集成 fixture 会幂等准备测试角色并升级测试库；只在显式本地 *_test 库清理指定表。
API 通过 rag_app 执行；管理员连接仅用于准备、观察、迁移兼容测试及清理。
不要与真实验收脚本同时运行这些测试。

### 角色与凭据

| 身份 | 权限及用途 |
| --- | --- |
| POSTGRES_USER | Docker 初始化/本地管理员，负责 provision、测试准备和清理，不用于 FastAPI |
| rag_migrator | LOGIN、NOSUPERUSER、NOBYPASSRLS、NOINHERIT；拥有项目表和认证 schema，负责 Alembic |
| rag_app | LOGIN、NOSUPERUSER、NOBYPASSRLS、NOINHERIT；非表所有者、没有任何角色成员关系 |
| rag_auth_lookup | NOLOGIN、NOSUPERUSER、NOBYPASSRLS、NOINHERIT；非表所有者，仅认证函数需要的 users 列读取 |

rag_migrator 可显式 SET ROLE 到 rag_auth_lookup 管理函数，但不自动继承该角色的读取 Policy。
rag_app 不能 SET ROLE、创建对象、修改 Policy 或 TRUNCATE。
实际表权限：tenants/users/knowledge_bases 为 SELECT+INSERT；documents 增加 UPDATE；chunks 增加 UPDATE+DELETE。
每张表都有四类 tenant Policy，但 Policy 本身不授予表权限，也不增加任何 HTTP API。

生产应用只注入 APP_DB_PASSWORD、数据库地址/库名及其他运行配置；不注入
POSTGRES_PASSWORD 或 MIGRATION_DB_PASSWORD，也不要挂载含管理凭据的开发 .env。
管理员密码缺失不会影响正常 runtime Settings；访问 administrator URL 时才强制要求它。
缺少应用/迁移密码分别报错，绝不回退使用管理员连接。

### Policy 与默认拒绝

0006 对五张业务表执行 ENABLE 和 FORCE ROW LEVEL SECURITY。
tenants 使用 id，其余使用 tenant_id，与事务局部 app.tenant_id UUID 比较。
SELECT/DELETE 使用 USING；INSERT 使用 WITH CHECK；UPDATE 同时检查旧行和新行。
上下文不存在或为空时不返回租户数据，INSERT 被拒绝；UPDATE/DELETE 无可见目标影响零行。
非法 UUID 报错，不能退化为放行。无相关表权限的操作直接被 ACL 拒绝。
每张表的四个策略为 `<table>_tenant_select/insert/update/delete`，仅授予 rag_app。
users 另有 users_auth_lookup SELECT Policy，仅适用于 rag_auth_lookup。
所有应用层 tenant filter 和 Composite FK 原样保留。

### 认证函数与 password_hash 风险

认证之前尚不知道 tenant，不能直接使用普通受限 users 查询。
app_private.login_credentials(email) 至多返回一行 user_id/password_hash/is_active，
app_private.user_tenant(user_id) 只返回 tenant UUID，不返回密码或角色。
两个函数均为 SECURITY DEFINER，所有者 rag_auth_lookup，固定 search_path=pg_catalog,pg_temp，
全限定引用 public.users；没有动态 SQL。PUBLIC EXECUTE 被撤销，仅 rag_app 可调用。
认证角色只有 id/tenant_id/email/password_hash/is_active 的列级 SELECT，并依靠
users_auth_lookup Policy 读取；不是表所有者，也没有 BYPASSRLS。不能写 users 或访问其他业务表。

登录按规范化 email 查询凭据，复制标量后结束事务，再在线程池校验 Argon2。
password_hash 只在服务端短暂用于验证，不进入 JWT、公开 Schema 或日志。
但持有 rag_app SQL 凭据或获得任意 SQL 执行能力的人，仍可能按已知 email 调用凭据函数，
取得 hash 并离线猜测密码；这是明确的认证信任边界，不宣称函数完全消除 hash 暴露风险。
不授予列举所有账号的认证函数；继续使用 Argon2、通用登录失败响应和 Secret 隔离。

JWT 仍只有 sub/exp。先校验 JWT，再按 sub 获取 tenant UUID，rollback 结束认证只读事务，
绑定 tenant 后重新按 user_id+tenant_id 查询最新 User、active 和 role。普通用户列表始终受 RLS。
注册在服务端预生成新的 tenant UUID，hash 后绑定该 UUID，再同一事务插入 Tenant+首个 admin；
客户端不能指定已有 tenant。用户创建失败仍整体 rollback。

### Session、事务与连接池

应用沿用一个 AsyncEngine 和请求级 AsyncSession；运行 Session 使用 TenantSession。
已认证 UUID 存在 Session.info，after_begin 通过该事件提供的 Connection 执行参数化
set_config('app.tenant_id', tenant, true)。无 tenant 时显式设置空值。
数据库值仅当前事务有效，commit/rollback 后恢复；下一个事务自动重新设置。
只读认证事务结束前不允许绑定，已绑定的同一请求 Session 不允许切换到另一个 tenant。
请求关闭时清理 Session.info；Session 不跨请求复用，共享的是连接池。
事件只注册在 TenantSession，不影响管理员 Session，不靠全局变量或永久 SET。

M4/M5 的 claim、快照、发布、错误状态写回、提交结果确认都在各自短事务自动获得上下文。
文件读写、解析、embedding、LLM 期间仍无数据库事务。没有新增长事务、嵌套事务或 UoW。

### 回滚与系统维护

0006 downgrade 先撤销 rag_app 对五张表的权限，再删除认证函数与 Policy、取消 FORCE/ENABLE。
不删除业务数据、角色或密码。迁移完成后新版应用启动检查会拒绝启动，避免无 RLS 继续服务。
回滚须停应用并配合兼容版本及管理员审计后的权限方案；不自动回退到超级用户。
表所有者在 FORCE 下的普通读取仍默认拒绝；需要跨租户的数据修复/备份使用独立、显式管理员操作。
不新增 HTTP 系统管理员接口，也不把后台管理员身份放进 get_db。

### 测试与安全边界

集成测试直接用运行角色执行不带 WHERE 的 SQL，包括向量排序/JOIN，验证数据库独立隔离。
覆盖非法 INSERT、改 tenant、跨父资源外键、无上下文写入、真实 Policy/函数 ACL、表 owner FORCE、
禁止 SET ROLE/TRUNCATE/DDL、同一物理连接 A/B/无上下文复用、commit/rollback 重启、并发 HTTP、
以及 0006 downgrade/re-upgrade 后的数据保留与权限恢复。M1～M5 原测试仍全部保留。
启动检查不能替代数据库 Policy 审计；alembic check 也不会完整检查 Policy/ACL，另有 pg_policies 断言。

自定义 GUC 是可信服务端传递的上下文，不是密码或签名。共享 SQL 角色可以设置它，
因此 RLS 防御遗漏过滤、正常请求串租户和错误写入，不能防御任意 SQL 注入或应用进程完全失陷。
FORCE 不限制超级用户/BYPASSRLS，表所有者仍能修改 DDL；必须隔离管理凭据。
UNIQUE/FK 检查可能暴露存在性线索，API 保持通用冲突响应，不泄漏原始数据库错误。
RLS 不替代 admin/member RBAC，不保护本地原文件，也不改变 M5 的 Prompt/外发安全边界。
M6 不引入新检索算法、Agent、Redis、worker 或 M7 功能。


## M7：Hybrid Search + Rerank

现有 query API 和 Answer/Sources 字段不变。流程为 query embedding → Dense + Sparse →
RRF → 本地 BGE Reranker → 完整 Context block → 原有 LLM。自动测试不调用真实模型或 LLM。

### 检索和状态

两路都复用 tenant/KB/text ready/index ready/model/non-null embedding 过滤，
由 rag_app + TenantSession 执行，M6 FORCE RLS 不变。
Sparse 不提前检索尚未 embedding 的文本。Dense 仍是 exact cosine search，无 HNSW/IVFFlat。
Sparse 用 PostgreSQL FTS 的 ts_rank，**不是 BM25**。

0007 增加 chunks.search_vector STORED GENERATED TSVECTOR 和 GIN 索引。
文档及问题统一调用 app_private.search_tokens：基本汉字范围 U+4E00～U+9FFF 连续片段
切为双字词项，独立单字保留；ASCII 英文/数字及内部 ._- 组成完整标识符，小写化。
最长 128 字符的 ASCII 标识符保留，超长标识符跳过；不做前缀、词干或模糊匹配。
E1001 不等于 E10010，ZX-200 不等于 ZX-200S。其他文字系统尚未覆盖。
词项编码为带类型前缀的 Unicode 码点十六进制序列，以 z 分隔，再交给固定 simple 配置。
这是无语义词典的字符级 baseline，不宣称中文分词质量。

search_question 对去重词项做 OR，最多 64 个，ASCII 词项优先，其余按出现顺序；
不执行用户输入中的 tsquery 操作符。Sparse 按 ts_rank DESC、Chunk.id ASC 排序。
自然语言问题中的常见双字组合可能产生噪声，精确词项存在不保证最终排序一定正确。

RRF 分数为各路 1/(RRF_K + rank) 之和，rank 从 1 开始，按 Chunk UUID 去重。
同路重复只贡献首次排名；分数并列按 UUID 排序。不混加 cosine distance 和 ts_rank。
重排同分按融合顺序保留。Response.distance 始终是该候选真实 cosine distance，
包括 Sparse-only 候选；响应顺序按重排结果，所以 distance 不保证递增。

### 配置与运行

.env.example 增加以下初始参数，尚未针对业务数据调优：

| 配置 | 默认值 |
| --- | --- |
| DENSE_CANDIDATE_K / SPARSE_CANDIDATE_K | 各 30，范围 10～100 |
| RRF_K | 60，范围 1～1000 |
| RERANK_CANDIDATE_K | 30，范围 10～100 |
| RERANKER_MODEL | BAAI/bge-reranker-base |
| RERANKER_DEVICE | cpu |
| RERANKER_BATCH_SIZE | 8 |
| RERANKER_MAX_LENGTH | 512 tokens，问题与正文合计 |

复用 sentence-transformers CrossEncoder，不新增 Python 依赖。
模型每进程 lazy cache，锁串行化加载和推理，线程池执行；多 worker 各自持有模型。
输出为原始 logits，不是概率或置信度；校验一维、数量匹配、数值类型、finite。
空 KB 不调用任何模型；空候选不调用 Reranker。模型失败返回安全 503，不静默降级。
两路 SQL 在同一 Session 顺序执行，随后结束事务，再进行 Rerank 和 LLM；
模型推理和外部调用期间不持有数据库事务。

### 迁移、权限和部署

先停止应用，在维护窗口执行 python -m alembic upgrade head，再执行 alembic check。
0001～0006 不变。生成列会计算历史 Chunk，不重做 embedding；新写入或 content 更新自动维护。
0007 downgrade 删除 GIN、生成列和三个 search_* 函数，保留文本、向量和 M6 Policy。

三个函数均为 IMMUTABLE、SECURITY INVOKER，固定 search_path，没有业务表查询、
动态 SQL 或外部数据；测试检查实际使用的 catalog 函数 overload 也为 immutable。
不使用依赖 session 默认配置的单参数 to_tsvector，也不使用 array_to_string 的通用类型转换。
rag_app 拥有 schema USAGE 和所需函数 EXECUTE，无 schema CREATE；PUBLIC 和
rag_auth_lookup 不获 search_* EXECUTE。原有认证函数和权限保持不变。

增加 stored generated column 可能重写表并持锁；普通 GIN 构建阻塞写入，增加磁盘/WAL。
当前采用事务式维护窗口迁移，不声称在线无锁。大表须另做分阶段部署；
CONCURRENTLY 不可放进普通 migration transaction，也不能解决生成列重写。
RLS 可能影响 GIN 执行计划，不给任何函数虚假标注 LEAKPROOF 来追求索引命中。
GUC 仍是可信应用上下文，不防御任意 SQL 注入或完全失陷的应用进程。

### 验证与真实模型评估

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pytest -o "addopts="
.\.venv\Scripts\python.exe -m pip check
git diff --check
# 单独运行，不与 pytest 共用测试库同时执行。不调用任何 LLM。
.\.venv\Scripts\python.exe -m scripts.evaluate_m7
```

真实评估使用 scripts/m7_cases.json 的 24 条人工资料和 16 个问题，独立 *_test 库中创建
一个专用租户，finally 仅删除该租户的数据。不读取用户业务文档。
首次模型加载可能需要下载公开 Hugging Face 权重；之后可使用已准备好的本地缓存。
报告保存在被 Git 忽略的 .data/evaluations/m7.json，包括数据集 SHA、模型 revision、
逐题 Dense/Sparse/RRF/Rerank 排名、Recall@1/5/10、MRR@10、候选召回、阶段时间及进程内存。
无相关答案用例不混入 Recall 分母。Fake 测试只验证逻辑，不能作为模型质量证据。
冷启动包含模型加载及可能的下载；暖运行测 24 个短文本对，不能外推到长文生产负载。
内存是整个评估进程的 RSS/峰值，并非模型独占显存或内存。

### 边界

候选数大于本评估语料数，所以候选召回容易饱和；小数据集不是生产质量评估。
不设置召回相关性阈值，无答案问题仍可能检索到不相关候选，依赖原有生成约束，不能声称可靠拒答。
字符二元组噪声、模型 512 token 截断、CPU 延迟和线程池排队均需关注。
锁不提供硬超时、跨进程共享或推理沙箱。模型 revision 会记录，但生产默认尚未锁定权重版本。
M7 不加入 BM25、HNSW、Agent、SSE、会话、worker、Redis 或 M8 功能。


### 本次真实评估记录

2026-10-15，Windows 11、12 逻辑处理器、PyTorch 6 线程，固定 CPU 模型。
15 个有答案问题计入指标，另 1 个无答案问题单独记录；完整逐题数据见本地
`.data/evaluations/m7.json`（首次）和 `.data/evaluations/m7-cached.json`（离线缓存复测）。

| 方法 | Recall@1 | Recall@5 / @10 | MRR@10 |
| --- | --- | --- | --- |
| Dense | 0.9333 | 1.0000 / 1.0000 | 0.9667 |
| Sparse | 0.9333 | 0.9333 / 0.9333 | 0.9333 |
| RRF | 0.9333 | 1.0000 / 1.0000 | 0.9667 |
| Hybrid + Rerank | 1.0000 | 1.0000 / 1.0000 | 1.0000 |

E1001 在 Dense 中被 E10010 排到前面，Sparse/RRF/Rerank 修正；四个型号/错误码问题
最终均正确排第一。但 RRF 单独把“每周在家办公几天”的正确答案从第一降到第二，
Reranker 才恢复。无答案问题仍返回不相关候选，未进行 LLM 调用或声称能够可靠拒答。
候选召回在此小语料中为 1.0，不代表大规模检索效果。

首次 Reranker 加载并评分耗时 191.11 秒（包含下载），离线缓存进程首次耗时 8.95 秒。
24 个短文本对的暖运行三次为 0.318/0.329/0.316 秒；24 个各 1000 字符的合成文本对
耗时 **5.52 秒**（仍按 512 token 截断），CPU 长文本成本明显，不更换模型掩盖这一结果。
短文本 query 检索阶段不含 LLM/Context：Dense 平均 16.1 ms，Hybrid 平均 376.6 ms、
p95 429.0 ms。数值包含问题 embedding；不代表完整 HTTP 或高并发吞吐。
缓存复测进程峰值 RSS 2069.9 MiB（约 2.02 GiB，包含两个模型和框架）。
Reranker revision 为 2cfc18c9415c912f9d8155881c133215df768a70；
Embedding revision 为 7999e1d3359715c523056ef9478215996d62a620。

## M8：单知识库 Agent 与 SSE

保留普通 `POST /knowledge-bases/{id}/query`。新增
`POST /knowledge-bases/{id}/agent/stream`，Bearer 认证，Admin/Member 均可使用，
JSON 请求为 `{"question":"问题", "top_k":5}`，校验与普通 Query 相同。
浏览器应使用支持 Authorization 和 POST 的 fetch 流读取，不使用原生 EventSource。
本阶段没有持久化记忆、断点恢复、SSE 重连重放或多 Agent，也没有新增数据库迁移。

### 运行图、工具与预算

实际使用 LangGraph `START → llm → tools → llm`，模型结束调用工具后进入
`finalize → END`。工具顺序执行，复用 M7 的 Dense/Sparse/RRF/Rerank pipeline。
两个工具是 `search_knowledge_base(query, top_k)` 和 `get_document_info(document_id)`；
参数禁止额外字段，模型不能设置 tenant 或知识库。工具会重新校验用户 active 和当前 KB，
数据库操作使用原有应用角色、TenantSession 和事务局部 RLS 上下文。
文档查询必须同时匹配 document ID、tenant 和 KB；所有数据库事务在模型推理前结束。

State 中 messages 保存模型对话及完整工具证据；sources 只保留来源身份和公开摘要；
pending_tool_calls 只存当前轮待执行调用，执行后清空。重复 Chunk/Document 沿用 source ID，
后续工具结果只返回 already_provided，不重复完整证据。

| 限制 | 默认值 |
| --- | --- |
| AGENT_MAX_CONCURRENT | 每进程 2 个，满载立即 429，无等候队列 |
| AGENT_TIMEOUT_SECONDS | 120 秒，使用 monotonic deadline |
| AGENT_MODEL_TIMEOUT_SECONDS / AGENT_TOOL_TIMEOUT_SECONDS | 各 30 秒，且不超过总剩余时间 |
| 模型调用 / 工具尝试 | 最多 5 / 4 次，每轮最多 2 个工具 |
| LangGraph recursion_limit | 16 |
| 输出 token 预留预算 | 8192；单次 max_tokens 为 1024 或最后一轮 2048 |
| 工具证据 / 序列化模型输入 | 12000 / 24000 字符，后者不是精确 token 计数 |
| 来源 / 工具 JSON 参数 / SSE 队列 | 20 个 / 4096 bytes / 8 个事件 |
| SSE 分片 / 心跳 / 发送等待 | 512 字符 / 15 秒 / 5 秒 |

### SSE 协议

每个事件有 `id: <run_id>:<seq>`、`event: <类型>`，data 是 JSON envelope：
`v=1, run_id, seq, event, data`。Pydantic discriminated union 位于 agent/schemas.py。

| event | data |
| --- | --- |
| agent_start | knowledge_base_id |
| tool_start | 服务端 call_id、白名单 tool 名称 |
| tool_result | call_id、tool、status(ok/empty/error)、source_ids、error_code |
| answer_delta | text |
| error | 安全 code、固定 message、retryable |
| agent_end | status(completed/failed)、finish_reason、answer、sources、model_calls、tool_attempts |

过程事件实时发送；最终回答完整生成、校验引用后才分片发送，**不是逐 token streaming**。
客户端仅把 `agent_end.status=completed` 视为成功；断开或 failed 时不要提交临时回答。
来源包含 kind(chunk/document)、source_id、document_id、filename 及安全摘要和允许的引用元数据，
不包含完整证据、工具参数、系统 Prompt、向量、存储路径或凭证。
流开始前使用 HTTP 401/404/422/429/503；开始后错误使用 error + failed agent_end，
已断开的客户端无法保证收到结束事件。代理必须关闭响应缓冲。

### DeepSeek、取消与安全边界

固定 LangGraph 1.2.15；本次实际验证环境为 AsyncOpenAI 2.54.0、FastAPI 0.141.1、
Starlette 1.6.0。继续使用环境配置的 DeepSeek 模型，显式关闭 thinking，不读取 reasoning_content。
增量 tool_call 按 index 组装，验证结束原因、ID、参数长度和 JSON Schema 后才执行。
未知工具、非法参数和不可见文档返回安全工具错误供有限重试；上游失败、预算和超时终止运行。
显式关闭 LangSmith tracing，没有 checkpointer 或持久化消息。

客户端断开会取消上游 SDK 流、Graph、工具和数据库 await，并关闭 Session。
等待模型锁时每 50ms 检查取消/deadline。已经运行的原生 CPU 推理无法强制终止：
HTTP 请求可结束，但容量名额保留到实际计算结束；不伪装成已释放 CPU。
容量按进程计数，不能代替部署级限流，普通 RAG 路径也不受此 Agent 容量限制。
首次模型下载或冷加载可能超过工具 deadline，应在部署时准备权重缓存。

工具证据是不可信输入，不能升级为系统指令。知识库事实回答必须具有已提供的 Chunk 引用；
未知编号或缺少引用会失败。只有文档状态来源时输出服务端构造的状态摘要，不能据此回答正文事实。
没有证据的直接回答使用固定能力/缺少证据提示，不发布模型自由生成的事实。
**有效来源编号不等于事实真实**：混合来源、逐条事实蕴含与引用充分性仍不保证，深入评估留到 M9。
RLS 是第二道隔离防线，不防御应用进程完全失陷或任意 SQL 执行。

### 验证

自动化测试：`.venv\Scripts\python.exe -m pytest -o addopts=`，使用 Fake 模型、真实独立
PostgreSQL 和本地 Uvicorn 网络测试；不下载模型、不调用外部 LLM。
覆盖工具循环、参数/预算/引用、SSE 顺序、DeepSeek 等待取消、本地锁与原生计算取消、
队列背压、真实数据库 pg_sleep 中断、Admin/Member 和 tenant/KB 隔离。

人工真实验证：`.venv\Scripts\python.exe -m scripts.verify_m8`。
脚本仅向已配置的 https://api.deepseek.com 发送固定人工年假资料、问题及 Agent 协议包装，
在独立测试库创建并清理自己的租户，不能与回归测试同时运行。需本地模型权重和 API Key。
2026-10-15 真实验证：2 次模型调用、2 次检索、来源去重为 S1，回答明确为 12 天带薪年假。
首个 agent_start 约 0.368 秒，首次工具完成约 11.286 秒（含 Reranker 冷加载），
第二次工具约 0.087 秒，最终回答约 12.383 秒，总耗时约 12.384 秒。
这是单次人工用例，不是吞吐或延迟基准；安全结果保存在忽略文件 `.data/verification/m8.json`。
本次全量 M1～M8 回归为 **266 passed（114.60 秒）**，其中新增 M8 测试 30 项。
`alembic check`、`pip check`、`git diff --check` 通过，历史迁移保持不变。

## M9：精简评估与本地可观测性

新增版本化人工数据集（24 个 RAG 问题、12 个 Agent 任务），开发集与保留集分开统计。
保留普通 RAG/Agent API、检索算法、Prompt、RLS 和短事务设计；没有新数据库迁移。
基线恢复首先确认 Docker/PostgreSQL 不可达导致角色 fixture 失败，启动数据库后原 266 项测试通过，未跳过集成测试。

本地 Trace 默认关闭。设置 `TRACE_ENABLED=true` 后，安全 JSONL 写入
`TRACE_PATH`（默认 `.data/traces/runs.jsonl`），单文件约 2MB、最多两个轮转备份。
只记录固定操作名、阶段耗时、计数、安全错误码及 provider Token Usage；不捕获函数参数、
问题、Prompt、Context、JWT、身份ID、文件名或异常原文。启用失败/写出失败不改变业务响应。
Trace 有128个span上限，不引入在线监控、告警或数据库表。HTTP/SSE协议不变。

```powershell
# 全部自动测试：Fake模型 + 真实独立测试库；不调用外部模型
.venv\Scripts\python.exe -m pytest -o addopts=

# 真实人工评估：有DeepSeek网络/Token成本，不与pytest并行
.venv\Scripts\python.exe -m scripts.evaluate_m9 --real

# 对已保存结果离线评分和重新生成报告
.venv\Scripts\python.exe -m scripts.evaluate_m9 --score docs/evaluation/m9-run.json --reviews docs/evaluation/m9-reviews.json
.venv\Scripts\python.exe -m scripts.evaluation.report docs/evaluation/m9-run.json --reviews docs/evaluation/m9-reviews.json --output docs/evaluation/m9-report.md

# LangSmith安全预览：默认不联网；--send才会使用显式环境Key上传白名单元数据
.venv\Scripts\python.exe -m scripts.export_m9_langsmith docs/evaluation/m9-run.json
```

真实运行使用原有独立 `_test` 数据库，创建自己的人工租户，仅清理本次数据。
评分只依据实际模型输入证据；记录哈希绑定复核结果，区分rule、human、model_assisted、unreviewed。
关键词规则不等于正确性，编号合法不等于引用支持，没有事实的拒答不自动获得Faithfulness满分。

本次真实36题评估共44次DeepSeek调用，全部usage可用，总25,666 Token。
RAG规则任务通过23/24，Agent9/12；11条模型辅助复核、0条人工复核、25条未复核。
保留了冻结标注错误R13、Agent漏检索/非法引用、RRF降序等案例，不以修Prompt或改答案追求高分。
LangSmith仅完成本地白名单与mock验证，未真实上传；不要宣称部署了LangSmith监控平台。

详细结果：`docs/evaluation/m9-report.md`、`m9-run.json`、`m9-reviews.json`、`m9-failure-cases.md`。
面试讲解：`docs/interview-prep/m9-evaluation-explanation.md`。
小样本、单次运行、规则误判及待人工复核范围必须连同数字一起介绍，不外推生产正确率或SLA。
最终M1～M9全量回归293项通过（新增27项，73.70秒）；依赖、迁移一致性及diff检查通过。
