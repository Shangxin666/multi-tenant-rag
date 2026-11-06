# real-tech-v1 审核修订候选差异

30 题全部 unverified / human_reviewed=false；不覆盖原始候选，不运行模型或数据库。
29 题仅具备后续人工验收资格；VUE026 因冻结语料缺历史证据继续暂不计分。当前可信评测题数仍为 0。

## 规则

支持至少一个明确必要事实点可标相关；背景、标题和同词命中不升级。
同一事实的证据互为替代，一个 Chunk 可以覆盖多组，多事实点不要求多个文档。
保留原 Recall/MRR/nDCG 代码；没有实现或执行新指标。未来 Evidence Group Coverage 可按必要组中任一支持 Chunk 命中计算。

## 变更统计

- 新增题目—Chunk 关联：39。
- 移除题目—Chunk 关联：0。
- 必要事实组：56；明确待扩展缺证组：1（VUE026/G1）。
- VUE004、VUE012、VUE014、VUE020 调整精确表述；VUE026 使用历史区别草案并暂缓。
- VUE008 分开记录 126 行和 174 行的重复原句，按真实位置映射。
- VUE011～VUE015 重组必要事实点，保留原 category 但不强制多文档。
- 负样本分类：VUE021～023 语料范围不足；VUE024 用户上下文不足；VUE025 测量依据不足。

## 逐题差异

| 题目 | 新增关联 | 移除关联 | 必要组 | 处理 |
| --- | ---: | ---: | ---: | --- |
| VUE001 | 1 | 0 | 2 | blocked_pending_human_review |
| VUE002 | 0 | 0 | 2 | blocked_pending_human_review |
| VUE003 | 0 | 0 | 1 | blocked_pending_human_review |
| VUE004 | 1 | 0 | 3 | blocked_pending_human_review |
| VUE005 | 1 | 0 | 2 | blocked_pending_human_review |
| VUE006 | 1 | 0 | 2 | blocked_pending_human_review |
| VUE007 | 2 | 0 | 2 | blocked_pending_human_review |
| VUE008 | 0 | 0 | 1 | blocked_pending_human_review |
| VUE009 | 0 | 0 | 2 | blocked_pending_human_review |
| VUE010 | 1 | 0 | 2 | blocked_pending_human_review |
| VUE011 | 5 | 0 | 2 | blocked_pending_human_review |
| VUE012 | 3 | 0 | 3 | blocked_pending_human_review |
| VUE013 | 3 | 0 | 2 | blocked_pending_human_review |
| VUE014 | 3 | 0 | 3 | blocked_pending_human_review |
| VUE015 | 2 | 0 | 2 | blocked_pending_human_review |
| VUE016 | 0 | 0 | 3 | blocked_pending_human_review |
| VUE017 | 3 | 0 | 3 | blocked_pending_human_review |
| VUE018 | 2 | 0 | 2 | blocked_pending_human_review |
| VUE019 | 3 | 0 | 2 | blocked_pending_human_review |
| VUE020 | 4 | 0 | 3 | blocked_pending_human_review |
| VUE021 | 0 | 0 | 0 | blocked_pending_human_review |
| VUE022 | 0 | 0 | 0 | blocked_pending_human_review |
| VUE023 | 0 | 0 | 0 | blocked_pending_human_review |
| VUE024 | 0 | 0 | 0 | blocked_pending_human_review |
| VUE025 | 0 | 0 | 0 | blocked_pending_human_review |
| VUE026 | 2 | 0 | 3 | deferred_missing_corpus_evidence |
| VUE027 | 0 | 0 | 2 | blocked_pending_human_review |
| VUE028 | 0 | 0 | 3 | blocked_pending_human_review |
| VUE029 | 0 | 0 | 1 | blocked_pending_human_review |
| VUE030 | 2 | 0 | 3 | blocked_pending_human_review |

## VUE001

我改完 count 就去读页面上的数字，拿到的还是旧值。Vue 里应该等哪个时机，代码怎么写？

**候选答案：** DOM 更新不是同步的；修改状态后 await nextTick()，再读取更新后的 DOM。

**Rubric：** 说明 DOM 更新被缓冲；给出修改状态后 await nextTick() 的顺序

- G1：响应式状态修改后的 DOM 更新是缓冲、异步执行的；状态 mapped_unverified
  - 支持 Chunk：a61ced98-5f68-5f24-9fa9-0f0239cb5331

- G2：修改状态后可等待 nextTick 再访问 DOM；状态 mapped_unverified
  - 支持 Chunk：720f300d-f184-5069-9ad2-3aafb122b8cc, a61ced98-5f68-5f24-9fa9-0f0239cb5331

- 新增 `720f300d-f184-5069-9ad2-3aafb122b8cc`（src/guide/essentials/reactivity-fundamentals.md #9）
  - 支持：G2 修改状态后可等待 nextTick 再访问 DOM

## VUE002

模板里反复用同一个计算结果，用 computed 和直接调用方法有什么实际区别？

**候选答案：** 计算属性基于响应式依赖缓存，只在依赖变化时重新计算；方法在重渲染时会再次执行。

**Rubric：** 说明缓存依据是响应式依赖；区分方法重渲染时再次执行

- G1：计算属性按响应式依赖缓存，依赖更新才重新计算；状态 mapped_unverified
  - 支持 Chunk：311e4473-3182-5dcf-82cd-9e855bf2c846

- G2：模板方法在重渲染时重新执行；状态 mapped_unverified
  - 支持 Chunk：311e4473-3182-5dcf-82cd-9e855bf2c846

## VUE003

孙组件 emit 了 save，爷爷组件直接写 @save 为什么收不到？组件事件不是也会冒泡吗？

**候选答案：** Vue 组件事件没有 DOM 事件的冒泡机制，只能直接监听子组件；跨层通信需显式转发或使用合适的跨层通信机制。

**Rubric：** 明确组件事件不冒泡；说明直接子组件监听范围

- G1：组件事件不冒泡，只能直接监听子组件事件；状态 mapped_unverified
  - 支持 Chunk：8ac182f3-5001-5e2e-be32-96cff001c95c

## VUE004

在普通 setup() 中，我把 onMounted 注册放进接口 Promise.then 回调或 setTimeout 回调里，这样为什么不行？它与 script setup 中顶层 await 后调用组合式 API 的情况有什么区别？

**候选答案：** 普通 setup 的异步回调不会保留当前组件实例，应在初始化的同步调用链中注册生命周期钩子。注册可以位于同步起源于 setup 的外部函数。script setup 的顶层 await 是编译器会恢复当前实例的特殊上下文，不能据此认为任意 Promise 或定时器回调都可注册钩子。

**Rubric：** 限定普通 setup 的 Promise/定时器异步回调场景；说明同步注册及同步外部调用链；明确 script setup 顶层 await 的编译器恢复实例例外，不泛化为任意异步回调

- G1：普通 setup 的异步回调中不能依赖当前实例注册生命周期钩子，应同步注册；状态 mapped_unverified
  - 支持 Chunk：70ea2dc7-cd64-584f-a91f-a91c4cc6e9ff, 9d63a26c-c553-5fdf-a1f8-88f7bc432c7e

- G2：允许在同步起源于 setup 的外部函数内注册；状态 mapped_unverified
  - 支持 Chunk：70ea2dc7-cd64-584f-a91f-a91c4cc6e9ff

- G3：script setup 顶层 await 由编译器恢复实例，是特殊上下文，不能泛化为任意异步回调；状态 mapped_unverified
  - 支持 Chunk：0c637b1f-991e-5d17-9162-91456a434925

- 新增 `0c637b1f-991e-5d17-9162-91456a434925`（src/guide/reusability/composables.md #14）
  - 支持：G3 script setup 顶层 await 由编译器恢复实例，是特殊上下文，不能泛化为任意异步回调

## VUE005

组件现在有 header 和 main 两个根节点，父组件传的 class 不知道落哪儿，还报了警告，要怎么处理？

**候选答案：** 多根节点组件不会自动透传 attributes，需要显式选择目标元素绑定 $attrs，否则可能产生运行时警告。

**Rubric：** 多根节点没有自动透传；显式将 $attrs 绑定到目标元素

- G1：多根节点不会自动透传 attributes，未显式绑定会警告；状态 mapped_unverified
  - 支持 Chunk：50476fce-cc56-5fb7-85b8-c4b220f7cc0c

- G2：可选择目标根节点显式绑定 $attrs；状态 mapped_unverified
  - 支持 Chunk：2e64ec45-953b-5fd1-a559-13f1a4e04f71, 50476fce-cc56-5fb7-85b8-c4b220f7cc0c

- 新增 `2e64ec45-953b-5fd1-a559-13f1a4e04f71`（src/guide/components/attrs.md #4）
  - 支持：G2 可选择目标根节点显式绑定 $attrs

## VUE006

watch(obj.count, ...) 一直没按预期触发，我只想盯着 count，不想监控整个对象，该怎么改？

**候选答案：** 直接传 obj.count 得到的是普通值；应使用 watch(() => obj.count, callback) 提供 getter 数据源。

**Rubric：** 指出传入的是普通 number；提供 getter 形式

- G1：直接传入对象的数字属性得到普通值，不能直接作为响应式源；状态 mapped_unverified
  - 支持 Chunk：a69b781c-faf2-5e17-9bff-942dd6d58e1e

- G2：应传入返回该属性的 getter；状态 mapped_unverified
  - 支持 Chunk：6df6403f-8dea-58e9-bd6a-514c4cdf368e, a69b781c-faf2-5e17-9bff-942dd6d58e1e

- 新增 `6df6403f-8dea-58e9-bd6a-514c4cdf368e`（src/api/reactivity-core.md #10）
  - 支持：G2 应传入返回该属性的 getter

## VUE007

reactive 数组里放了 ref，取出来怎么还是个对象？我以为 Vue 都会帮忙拆开。

**候选答案：** ref 作为响应式数组或 Map 等原生集合的元素访问时不会自动解包，需要读取 .value。

**Rubric：** 数组与集合元素不自动解包；说明 .value

- G1：响应式数组及 Map 中的 ref 元素不会自动解包；状态 mapped_unverified
  - 支持 Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf, 2fec68ae-f214-59b6-95e5-37d905d03449, a53426c4-b3fd-5e34-bbd0-6a6c5c21450c

- G2：访问这些 ref 元素需要 .value；状态 mapped_unverified
  - 支持 Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf, 2fec68ae-f214-59b6-95e5-37d905d03449

- 新增 `2fec68ae-f214-59b6-95e5-37d905d03449`（src/api/reactivity-core.md #3）
  - 支持：G1 响应式数组及 Map 中的 ref 元素不会自动解包；G2 访问这些 ref 元素需要 .value

- 新增 `a53426c4-b3fd-5e34-bbd0-6a6c5c21450c`（src/api/reactivity-core.md #2）
  - 支持：G1 响应式数组及 Map 中的 ref 元素不会自动解包

## VUE008

页面外层和内层都 provide 了同名配置，最里面的组件 inject 到底会用哪一份？

**候选答案：** 沿祖先链解析时使用距离注入组件最近的同名提供者的值。

**Rubric：** 最近祖先提供者优先

- G1：多个祖先提供同名依赖时采用最近祖先的值；状态 mapped_unverified
  - 支持 Chunk：6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 9e7b4f5a-68a8-5d51-ad27-6ce534c99190, f7de642c-8c51-5935-b29d-e813ff85d667

## VUE009

父组件已经拿到子组件 ref 了，为什么调用不到 script setup 里写的那个方法？

**候选答案：** script setup 组件默认私有；子组件需要用 defineExpose 显式暴露方法，且应在 await 之前调用。

**Rubric：** 默认私有；defineExpose；await 前调用

- G1：script setup 组件默认私有，须用 defineExpose 显式暴露；状态 mapped_unverified
  - 支持 Chunk：a4c45296-6467-56cf-abc4-1ab6df219fe9

- G2：defineExpose 必须在 await 前调用；状态 mapped_unverified
  - 支持 Chunk：39306021-aad3-5ab4-b8ef-2089274e1c23

## VUE010

我把 useXXX 返回的状态解构出来用，页面就不更新了。组合式函数应该返回什么结构才不容易踩这个坑？

**候选答案：** 推荐返回包含多个 ref 的普通非响应式对象；解构后 ref 仍保持响应性。直接解构返回的 reactive 对象可能丢失属性的响应性连接。

**Rubric：** 普通对象包含多个 ref；解释 reactive 对象解构的风险

- G1：推荐返回普通非响应式对象，其中包含多个 ref，解构仍保留响应性；状态 mapped_unverified
  - 支持 Chunk：78622d60-8947-503b-afda-dd4ff065daf0

- G2：解构返回的 reactive 对象可能断开属性的响应式连接，而 ref 保留连接；状态 mapped_unverified
  - 支持 Chunk：78622d60-8947-503b-afda-dd4ff065daf0, 912be6b3-bf0c-52fa-b084-b32a071bda9b

- 新增 `912be6b3-bf0c-52fa-b084-b32a071bda9b`（src/guide/reusability/composables.md #13）
  - 支持：G2 解构返回的 reactive 对象可能断开属性的响应式连接，而 ref 保留连接

## VUE011

搜索条件变化后要刷新接口数据，结果再拿来算一段展示文字。这两步都塞进 computed 合适吗，应该怎样分工？

**候选答案：** computed getter 应保持无副作用，用于计算派生展示值；请求等副作用应放在 watch 或 watchEffect 等侦听逻辑中。

**Rubric：** 请求与派生计算分开；computed getter 不做请求；侦听状态变化执行副作用

- G1：computed getter 只计算派生值，不执行请求、DOM 修改等副作用；状态 mapped_unverified
  - 支持 Chunk：978727b4-5fcd-52c9-9986-cade596174c5

- G2：响应式状态改变驱动的请求可放在 watch 或 watchEffect 中；状态 mapped_unverified
  - 支持 Chunk：62e663f6-fd0c-559c-83e0-7c188ac39bb9, 8e4f1aff-7937-55a2-8a64-90738891a3c4, 978727b4-5fcd-52c9-9986-cade596174c5, b7b4b10e-3228-5438-9b74-94acea8e14c9, db2b988d-215d-57ec-bede-2f464494b832, e6a99cf2-692a-571b-bba4-cc7b833242b0, eb733fbd-8a4c-595e-bebe-6f8c374b6aca

- 新增 `62e663f6-fd0c-559c-83e0-7c188ac39bb9`（src/guide/reusability/composables.md #6）
  - 支持：G2 响应式状态改变驱动的请求可放在 watch 或 watchEffect 中

- 新增 `b7b4b10e-3228-5438-9b74-94acea8e14c9`（src/guide/essentials/watchers.md #7）
  - 支持：G2 响应式状态改变驱动的请求可放在 watch 或 watchEffect 中

- 新增 `db2b988d-215d-57ec-bede-2f464494b832`（src/guide/essentials/watchers.md #2）
  - 支持：G2 响应式状态改变驱动的请求可放在 watch 或 watchEffect 中

- 新增 `e6a99cf2-692a-571b-bba4-cc7b833242b0`（src/guide/essentials/watchers.md #8）
  - 支持：G2 响应式状态改变驱动的请求可放在 watch 或 watchEffect 中

- 新增 `eb733fbd-8a4c-595e-bebe-6f8c374b6aca`（src/guide/essentials/watchers.md #9）
  - 支持：G2 响应式状态改变驱动的请求可放在 watch 或 watchEffect 中

## VUE012

父组件把一个普通的可变 user 对象作为 prop 传给编辑器。子组件直接执行 props.user.name = '新名字'，和执行 props.user = 新对象有什么区别？推荐怎样把姓名修改交给父组件处理？

**候选答案：** prop 绑定是只读的，子组件不能重新赋值 props.user。但父组件传入普通可变对象时，子组件通常可以修改其嵌套属性；这是共享对象引用带来的修改，也会影响父组件持有的对象。通常应避免这种隐式修改，由子组件发出变更事件，父组件监听后更新自己的状态；紧密耦合场景需明确约定。

**Rubric：** 区分重新赋值 prop 绑定与修改嵌套属性；解释共享对象引用带来的父级状态影响；不把 props 描述成对任意嵌套内容都强制深只读；给出子组件通知、父组件更新的推荐数据流

- G1：prop 的顶层绑定不能由子组件重新赋值；状态 mapped_unverified
  - 支持 Chunk：1e51ef13-4dab-5e04-a08e-7b5624fb54b3, cb0c49b4-fe85-52e6-8e8b-e126933a0c77

- G2：普通可变对象或数组的嵌套内容可因共享引用被修改，影响父级状态；状态 mapped_unverified
  - 支持 Chunk：cb0c49b4-fe85-52e6-8e8b-e126933a0c77

- G3：通常由子组件发事件通知父组件更新，避免隐式嵌套修改；状态 mapped_unverified
  - 支持 Chunk：7ad21482-7a99-5298-b491-e4c038d091ed, 8ac182f3-5001-5e2e-be32-96cff001c95c, 8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 90bda472-1d76-59a5-9be1-f3b3765b6d0b, af17e069-2291-5e66-ab9e-3e461f361655, cb0c49b4-fe85-52e6-8e8b-e126933a0c77

- 新增 `1e51ef13-4dab-5e04-a08e-7b5624fb54b3`（src/guide/components/props.md #8）
  - 支持：G1 prop 的顶层绑定不能由子组件重新赋值

- 新增 `8ac182f3-5001-5e2e-be32-96cff001c95c`（src/guide/components/events.md #1）
  - 支持：G3 通常由子组件发事件通知父组件更新，避免隐式嵌套修改

- 新增 `90bda472-1d76-59a5-9be1-f3b3765b6d0b`（src/guide/components/events.md #2）
  - 支持：G3 通常由子组件发事件通知父组件更新，避免隐式嵌套修改

## VUE013

封装按钮时把 click 写进 emits，父组件的 @click 还是不是透传到原生按钮？为什么声明事件会影响这个行为？

**候选答案：** 声明过的事件监听器会被组件消费，不再作为普通透传监听器；click 声明为组件事件后，父级监听的是组件 emit 的 click，而非自动监听原生 click。

**Rubric：** 声明过的监听器被消费；区分组件 click 与原生 click

- G1：已声明的 props 和 emits 监听器不属于透传 attributes；状态 mapped_unverified
  - 支持 Chunk：14715e3f-b60c-5d9b-91d8-18b640139142, 24112c6d-aa7e-5f69-9bdc-2127f4042050, 3b0f0264-6b3a-5091-9c44-ba77aa88f80b, 560d6037-50db-51fc-a466-5bb2b407b0e5, e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a

- G2：click 在 emits 中声明后，监听组件发出的 click，不再自动响应原生 click；状态 mapped_unverified
  - 支持 Chunk：3b0f0264-6b3a-5091-9c44-ba77aa88f80b

- 新增 `24112c6d-aa7e-5f69-9bdc-2127f4042050`（src/guide/components/attrs.md #0）
  - 支持：G1 已声明的 props 和 emits 监听器不属于透传 attributes

- 新增 `560d6037-50db-51fc-a466-5bb2b407b0e5`（src/guide/components/attrs.md #2）
  - 支持：G1 已声明的 props 和 emits 监听器不属于透传 attributes

- 新增 `e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a`（src/guide/essentials/component-basics.md #14）
  - 支持：G1 已声明的 props 和 emits 监听器不属于透传 attributes

## VUE014

我想在 useFocus 中，等组件挂载后通过模板 ref 聚焦 input，并手动给 window 注册一个事件监听器。模板 ref 初始为空应该怎样处理？组件卸载时，手动注册的监听器应该在哪里移除？

**候选答案：** 模板引用需要等挂载后访问，尚未挂载或元素被移除时可能为空，使用前应检查。模板引用的可用性由 Vue 渲染生命周期管理；它与手动注册的事件监听器不是同一资源。手动注册的 window 监听器应在 onUnmounted 中用相应的 removeEventListener 清理，不能认为 ref 变空就意味着监听器已移除。

**Rubric：** 挂载后访问引用，并处理空值；区分模板引用与手动注册的监听器；注册与移除使用对应的事件、目标和回调；不把元素消失与组件卸载混为同一时机

- G1：模板引用在挂载后才可访问，初次渲染或元素移除时可能为空；状态 mapped_unverified
  - 支持 Chunk：bd25d6f5-da4c-58c1-8947-f810071a1b1b, bf02ccc6-915f-583e-9f67-fcbf7f74af46

- G2：DOM 相关副作用可安排在 onMounted 等挂载后阶段；状态 mapped_unverified
  - 支持 Chunk：312f7e93-4108-55d5-b002-f76890c5bb39, 912be6b3-bf0c-52fa-b084-b32a071bda9b, 9727377d-866a-536a-87cf-8b81720723dc

- G3：手动添加的事件监听器需要在组件卸载时配对移除，ref 变空不等于监听器已清理；状态 mapped_unverified
  - 支持 Chunk：312f7e93-4108-55d5-b002-f76890c5bb39, 912be6b3-bf0c-52fa-b084-b32a071bda9b, 9727377d-866a-536a-87cf-8b81720723dc

- 新增 `312f7e93-4108-55d5-b002-f76890c5bb39`（src/guide/reusability/composables.md #3）
  - 支持：G2 DOM 相关副作用可安排在 onMounted 等挂载后阶段；G3 手动添加的事件监听器需要在组件卸载时配对移除，ref 变空不等于监听器已清理

- 新增 `9727377d-866a-536a-87cf-8b81720723dc`（src/guide/reusability/composables.md #1）
  - 支持：G2 DOM 相关副作用可安排在 onMounted 等挂载后阶段；G3 手动添加的事件监听器需要在组件卸载时配对移除，ref 变空不等于监听器已清理

- 新增 `bd25d6f5-da4c-58c1-8947-f810071a1b1b`（src/guide/essentials/template-refs.md #2）
  - 支持：G1 模板引用在挂载后才可访问，初次渲染或元素移除时可能为空

## VUE015

把 reactive 对象里的一个数字解构到局部变量，和从组合式函数拿到一个 ref 再解构，为什么更新效果不一样？

**候选答案：** 解构 reactive 对象的原始类型属性会脱离源对象的代理访问，局部绑定不再响应；从普通对象解构得到的 ref 保留自身的响应式容器身份。

**Rubric：** 解释代理 get/set 与局部绑定；区分 ref 容器和原始值

- G1：原始类型属性被解构为局部变量后不再触发源代理访问，因而断开连接；状态 mapped_unverified
  - 支持 Chunk：4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, a2425d5f-5163-58d8-8d74-37d38abc304f

- G2：从普通对象解构得到的 ref 保留自身响应性；状态 mapped_unverified
  - 支持 Chunk：78622d60-8947-503b-afda-dd4ff065daf0, 912be6b3-bf0c-52fa-b084-b32a071bda9b

- 新增 `4dbf7985-2e57-5fd4-be7d-efe56d8b62ed`（src/guide/essentials/reactivity-fundamentals.md #12）
  - 支持：G1 原始类型属性被解构为局部变量后不再触发源代理访问，因而断开连接

- 新增 `912be6b3-bf0c-52fa-b084-b32a071bda9b`（src/guide/reusability/composables.md #13）
  - 支持：G2 从普通对象解构得到的 ref 保留自身响应性

## VUE016

watch 和 watchEffect 是不是只差一个不用写监听源？如果回调里有 await，依赖追踪有什么容易漏掉的地方？

**候选答案：** watch 只追踪显式数据源；watchEffect 自动追踪同步执行中访问的响应式依赖，异步回调第一个 await 之后才访问的属性不会被其追踪。

**Rubric：** 显式源与自动追踪区别；第一个 await 前的同步依赖限制

- G1：watch 仅追踪显式数据源，不追踪回调内的其它访问；状态 mapped_unverified
  - 支持 Chunk：eb733fbd-8a4c-595e-bebe-6f8c374b6aca

- G2：watchEffect 自动追踪同步执行中访问的响应式依赖；状态 mapped_unverified
  - 支持 Chunk：eb733fbd-8a4c-595e-bebe-6f8c374b6aca

- G3：异步 watchEffect 仅追踪第一个 await 前访问的依赖；状态 mapped_unverified
  - 支持 Chunk：e6a99cf2-692a-571b-bba4-cc7b833242b0

## VUE017

同一个 ref 放进 reactive 对象属性时不用 .value，放进数组或 Map 就要写，这两种情况到底怎么区分？

**候选答案：** 深层 reactive 对象的属性会自动解包 ref，但响应式数组或原生集合的元素访问不会自动解包，后者需 .value。

**Rubric：** 深层对象属性自动解包；数组及 Map 元素不解包

- G1：深层 reactive 对象属性中的 ref 自动解包；状态 mapped_unverified
  - 支持 Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf, 4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, 81f8da2e-7ef3-530a-8195-12de98776e89, a53426c4-b3fd-5e34-bbd0-6a6c5c21450c

- G2：响应式数组或 Map 的 ref 元素不会自动解包；状态 mapped_unverified
  - 支持 Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf, 2fec68ae-f214-59b6-95e5-37d905d03449, a53426c4-b3fd-5e34-bbd0-6a6c5c21450c

- G3：响应式数组或 Map 中的 ref 元素使用 .value 读取；状态 mapped_unverified
  - 支持 Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf, 2fec68ae-f214-59b6-95e5-37d905d03449

- 新增 `2fec68ae-f214-59b6-95e5-37d905d03449`（src/api/reactivity-core.md #3）
  - 支持：G2 响应式数组或 Map 的 ref 元素不会自动解包；G3 响应式数组或 Map 中的 ref 元素使用 .value 读取

- 新增 `81f8da2e-7ef3-530a-8195-12de98776e89`（src/api/reactivity-core.md #4）
  - 支持：G1 深层 reactive 对象属性中的 ref 自动解包

- 新增 `a53426c4-b3fd-5e34-bbd0-6a6c5c21450c`（src/api/reactivity-core.md #2）
  - 支持：G1 深层 reactive 对象属性中的 ref 自动解包；G2 响应式数组或 Map 的 ref 元素不会自动解包

## VUE018

插槽写在父组件里，为什么不能直接读子组件的局部变量？作用域插槽是怎么把这部分数据交给我的？

**候选答案：** 插槽表达式遵循定义位置的作用域，不能直接访问子组件状态；子组件通过 slot 出口传递属性，父组件通过 v-slot 接收插槽 props。

**Rubric：** 定义作用域；slot props 与 v-slot

- G1：插槽表达式使用定义它的父级作用域，不能直接读子组件状态；状态 mapped_unverified
  - 支持 Chunk：94c5c015-934e-56ce-bf8f-b2e48d2f1227

- G2：子组件向 slot 传递属性，父组件通过 v-slot 接收插槽 props；状态 mapped_unverified
  - 支持 Chunk：444f4b72-184b-5ad3-a962-27ad89bec941, 675b751e-f782-5245-a31c-7c8747b4bc51, 6c17ff85-749b-5089-aba8-32381c08392c

- 新增 `444f4b72-184b-5ad3-a962-27ad89bec941`（src/guide/components/slots.md #15）
  - 支持：G2 子组件向 slot 传递属性，父组件通过 v-slot 接收插槽 props

- 新增 `6c17ff85-749b-5089-aba8-32381c08392c`（src/guide/components/slots.md #14）
  - 支持：G2 子组件向 slot 传递属性，父组件通过 v-slot 接收插槽 props

## VUE019

把对象交给 reactive 后，返回值和原对象用 === 比较为什么不相等？修改时应该一直用哪一个？

**候选答案：** reactive 返回的是原对象的 Proxy，不与原对象严格相等；应该统一使用代理对象，以便访问和修改被响应式系统追踪。

**Rubric：** Proxy 与原对象不同身份；使用代理对象

- G1：reactive 产生代理对象，代理与原对象不是同一身份；状态 mapped_unverified
  - 支持 Chunk：1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 2fec68ae-f214-59b6-95e5-37d905d03449, 4f39a83a-2200-5b6d-ac29-cbf29f3495f7, a2425d5f-5163-58d8-8d74-37d38abc304f

- G2：应统一通过代理访问和修改，以被响应式系统追踪；状态 mapped_unverified
  - 支持 Chunk：1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 2fec68ae-f214-59b6-95e5-37d905d03449, 4f39a83a-2200-5b6d-ac29-cbf29f3495f7

- 新增 `2fec68ae-f214-59b6-95e5-37d905d03449`（src/api/reactivity-core.md #3）
  - 支持：G1 reactive 产生代理对象，代理与原对象不是同一身份；G2 应统一通过代理访问和修改，以被响应式系统追踪

- 新增 `4f39a83a-2200-5b6d-ac29-cbf29f3495f7`（src/guide/essentials/reactivity-fundamentals.md #2）
  - 支持：G1 reactive 产生代理对象，代理与原对象不是同一身份；G2 应统一通过代理访问和修改，以被响应式系统追踪

- 新增 `a2425d5f-5163-58d8-8d74-37d38abc304f`（src/guide/extras/reactivity-in-depth.md #3）
  - 支持：G1 reactive 产生代理对象，代理与原对象不是同一身份

## VUE020

在自定义组件上使用不带参数的 v-model="value" 时，不用 defineModel 应该怎样实现？子组件接收哪个 prop、触发哪个事件？这和 v-model:title 有什么区别？

**候选答案：** 默认无参数的组件 v-model 对应 modelValue prop 和 update:modelValue 事件。子组件读取 prop，在需要更新时通过该事件把新值交给父组件。具名的 v-model:title 则对应 title 和 update:title，不能混用默认名称。

**Rubric：** 明确讨论的是组件上的默认无参数 v-model；正确给出 modelValue/update:modelValue；说明父级值通过事件更新；区分 title/update:title；不混入原生 input 的展开协议

- G1：默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件；状态 mapped_unverified
  - 支持 Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d, 454bd082-74ca-5e75-81f2-c53217654372, 507f1310-f227-5746-9b63-41dd014abf1c, bf9cd212-476d-5496-8800-b97f88ca327c, e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, f77c7aa6-62a8-5287-97ca-f2251684cf0c

- G2：子组件读取 prop，并通过事件把新值交给父组件更新；状态 mapped_unverified
  - 支持 Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d, 454bd082-74ca-5e75-81f2-c53217654372, 507f1310-f227-5746-9b63-41dd014abf1c, bf9cd212-476d-5496-8800-b97f88ca327c, e7a3fae7-1aef-535c-b29e-a3b5a619b3bd

- G3：具名 v-model:title 对应 title prop 和 update:title 事件；状态 mapped_unverified
  - 支持 Chunk：f77c7aa6-62a8-5287-97ca-f2251684cf0c

- 新增 `454bd082-74ca-5e75-81f2-c53217654372`（src/guide/components/v-model.md #5）
  - 支持：G1 默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件；G2 子组件读取 prop，并通过事件把新值交给父组件更新

- 新增 `507f1310-f227-5746-9b63-41dd014abf1c`（src/guide/components/v-model.md #4）
  - 支持：G1 默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件；G2 子组件读取 prop，并通过事件把新值交给父组件更新

- 新增 `e7a3fae7-1aef-535c-b29e-a3b5a619b3bd`（src/guide/components/v-model.md #3）
  - 支持：G1 默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件；G2 子组件读取 prop，并通过事件把新值交给父组件更新

- 新增 `f77c7aa6-62a8-5287-97ca-f2251684cf0c`（src/guide/components/v-model.md #7）
  - 支持：G1 默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件；G3 具名 v-model:title 对应 title prop 和 update:title 事件

## VUE021

项目用 Vue Router 4，登录过期时 beforeEach 怎么配置才能登录后回到原来的地址？请给完整配置。

**候选答案：** 这批冻结文档没有 Vue Router 导航守卫配置证据，不能据此提供已核实的完整实现；需要补充 Vue Router 官方资料。

**Rubric：** 说明当前资料范围不足；不编造路由配置

## VUE022

Pinia store 想跨标签页同步，还要让持久化缓存两小时后失效，具体插件配置怎么写？

**候选答案：** 这批文档没有该 Pinia 插件、跨标签页同步和 TTL 配置的足够证据，需要插件名称、版本及其文档。

**Rubric：** 不把 Vue 核心响应式知识当插件配置证据；请求插件与版本信息

## VUE023

Vite 开发服务器把 /socket 代理到后端 WebSocket，vite.config.ts 里代理规则应该怎么写？

**候选答案：** 所选 Vue 文档没有 Vite WebSocket 代理配置证据，应查阅相应版本的 Vite 文档，不能将组件通信机制当作服务代理配置。

**Rubric：** 区分 Vue 组件与 Vite 服务器配置；指出资料缺失

## VUE024

我的 UserProfile.vue 第 87 行报 Cannot read properties of undefined，你直接告诉我那一行该怎么改，代码暂时不能提供。

**候选答案：** 缺少项目代码、堆栈和触发条件，无法从通用官方文档确定具体修改；应先请求最小复现或相关代码。

**Rubric：** 不猜测私有代码；请求最小复现与堆栈

## VUE025

一万个带校验的输入框全部改成 ref 后，在我的电脑上每次更新能保证低于 16ms 吗？给我确定的耗时数值。

**候选答案：** 这些文档不包含指定硬件和应用负载的测量结果，不能保证 16ms 或给出确定耗时；需要实际基准测量。

**Rubric：** 拒绝无实测依据的数值保证；区分响应式机制与性能测量

## VUE026

同事说 defineModel 在 Vue 3.3 就能用，文档却从 3.4 开始推荐。这里的实验性支持和正式稳定有什么区别？如果 Vue 3.3 项目不启用实验特性，默认无参数的组件 v-model 应怎样实现？

**候选答案：** defineModel 在 Vue 3.3 中已作为需要显式启用的实验性功能提供，3.4 转为稳定功能并被文档推荐。不能说它到 3.4 才首次存在。不启用实验宏时，可用 modelValue prop 和 update:modelValue 事件实现默认组件 v-model。

**Rubric：** 不把 3.4 开始推荐解释成 3.3 完全不存在；区分 3.3 实验性且显式启用与 3.4 稳定；给出默认无参数协议；不编造未核对版本的构建配置

- G1：defineModel 在 3.3 中为需显式启用的实验特性，3.4 转为稳定；当前冻结语料缺此历史证据；状态 missing_corpus_evidence
  - 支持 Chunk：无；明确暂缓，不伪造证据

- G2：当前指南从 Vue 3.4 开始推荐 defineModel；状态 mapped_unverified
  - 支持 Chunk：0f8e1a48-a80a-5e02-8265-590e6dee4d02

- G3：不使用宏时，默认组件 v-model 使用 modelValue 和 update:modelValue；状态 mapped_unverified
  - 支持 Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d, 507f1310-f227-5746-9b63-41dd014abf1c, bf9cd212-476d-5496-8800-b97f88ca327c, e7a3fae7-1aef-535c-b29e-a3b5a619b3bd

- 新增 `507f1310-f227-5746-9b63-41dd014abf1c`（src/guide/components/v-model.md #4）
  - 支持：G3 不使用宏时，默认组件 v-model 使用 modelValue 和 update:modelValue

- 新增 `e7a3fae7-1aef-535c-b29e-a3b5a619b3bd`（src/guide/components/v-model.md #3）
  - 支持：G3 不使用宏时，默认组件 v-model 使用 modelValue 和 update:modelValue

## VUE027

升级到 Vue 3.5 后，从 defineProps 解构出来的变量为什么又能跟着更新了？在 3.4 项目里也能这样理解吗？

**候选答案：** 在同一 script setup 中，3.5+ 编译器会把对解构 props 变量的访问转换为 props 属性访问；3.4 及以下的同类解构变量是不会随 prop 更新的常量，不能混用解释。

**Rubric：** 3.5 编译器转换；3.4 及以下区别；同一 script setup 上下文

- G1：默认编译配置下，3.4 及以下的此类解构变量不随 prop 更新；状态 mapped_unverified
  - 支持 Chunk：3769516e-964b-55cd-ad0e-2035bcfdef73

- G2：3.5+ 在同一 script setup 内将解构变量访问转换为 props 属性访问；状态 mapped_unverified
  - 支持 Chunk：3769516e-964b-55cd-ad0e-2035bcfdef73

## VUE028

Vue 3.4 项目复制 useTemplateRef 示例后用不了，这个 API 从哪个版本开始有，旧项目应该怎样拿模板引用？

**候选答案：** useTemplateRef 是 3.5+ API；之前需要声明一个与模板 ref attribute 匹配的 ref，并在挂载后访问。

**Rubric：** 3.5+ 边界；同名 ref 旧写法；挂载后访问

- G1：useTemplateRef 是 Vue 3.5+ API，旧版本尚未引入；状态 mapped_unverified
  - 支持 Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46, da91b8dd-87b7-56c9-b189-d662360d8d3d

- G2：旧写法声明与模板 ref attribute 匹配的 ref；状态 mapped_unverified
  - 支持 Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46

- G3：模板引用需在挂载后访问；状态 mapped_unverified
  - 支持 Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46

## VUE029

想让 watch 只往对象里检查两层，deep: 2 能直接用在 Vue 3.4 吗？数字形式的 deep 有版本要求吗？

**候选答案：** 文档将数字形式的 deep 标为 Vue 3.5+，表示最大遍历深度；不能将这项语义直接用于 3.4。

**Rubric：** 3.5+ 数字 deep；最大遍历深度；不对 3.4 作同样保证

- G1：数字 deep 表示最大遍历深度，属于 Vue 3.5+ 语义，不能直接保证 3.4 支持；状态 mapped_unverified
  - 支持 Chunk：6df6403f-8dea-58e9-bd6a-514c4cdf368e, e2800ff6-c50c-5f52-99b7-831b1347f720

## VUE030

Vue 3.5 里我先 await 再调用 onWatcherCleanup 取消旧请求，为什么不对？它和回调参数给的 onCleanup 限制一样吗？

**候选答案：** onWatcherCleanup 仅在 3.5+ 支持，必须在 watch/watchEffect 的同步执行阶段调用，不能放在 await 后；回调参数 onCleanup 与侦听器实例绑定，不受该同步限制。

**Rubric：** 3.5+；同步阶段注册；与 onCleanup 区分

- G1：onWatcherCleanup 属于 Vue 3.5+ 功能；状态 mapped_unverified
  - 支持 Chunk：21609aa6-5817-5c26-ac68-59aca2eff30f, 399b3a78-0f97-5021-ac15-5bb388f8260e, 5acc91a0-5fd7-5021-86c0-a9d2e4ee124e, 93ee0ba2-4f0f-5338-b6c6-b02f9b42f907

- G2：onWatcherCleanup 必须在同步执行期间注册，不能在 await 后调用；状态 mapped_unverified
  - 支持 Chunk：5acc91a0-5fd7-5021-86c0-a9d2e4ee124e, 93ee0ba2-4f0f-5338-b6c6-b02f9b42f907

- G3：回调参数 onCleanup 与侦听器绑定，不受上述同步调用限制；状态 mapped_unverified
  - 支持 Chunk：cb8f0eda-ad24-5450-936d-a2eef1905f3b

- 新增 `21609aa6-5817-5c26-ac68-59aca2eff30f`（src/api/reactivity-core.md #12）
  - 支持：G1 onWatcherCleanup 属于 Vue 3.5+ 功能

- 新增 `399b3a78-0f97-5021-ac15-5bb388f8260e`（src/api/reactivity-core.md #7）
  - 支持：G1 onWatcherCleanup 属于 Vue 3.5+ 功能

## 校验

结果：passed_with_declared_deferral
无效 Chunk、重复证据条目、位置错配、孤立组与非预期缺组均应为零。
同一事实在多个真实位置重复出现，属于替代证据；同一证据支持多组不属于重复条目。
结构通过不代表标注已获人工确认；没有自动将任何记录标记为 human_reviewed=true。
