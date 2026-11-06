# Vue 3 中文真实语料候选集审核

**全部 30 题均为 unverified，不得进入可信最终评测。**

固定 Commit：`418f5ae6e15c7a90beae017e44d58dac3d93ad95`。
15 份原始 Markdown，215 个 Chunk；单个查询知识库包含全部 215 个候选 Chunk。

| 源文件 | Chunk 数 |
| --- | ---: |
| src/guide/essentials/reactivity-fundamentals.md | 16 |
| src/guide/essentials/computed.md | 10 |
| src/guide/essentials/watchers.md | 15 |
| src/guide/essentials/lifecycle.md | 3 |
| src/guide/essentials/template-refs.md | 8 |
| src/guide/essentials/component-basics.md | 24 |
| src/guide/components/props.md | 20 |
| src/guide/components/events.md | 7 |
| src/guide/components/v-model.md | 21 |
| src/guide/components/attrs.md | 5 |
| src/guide/components/slots.md | 23 |
| src/guide/components/provide-inject.md | 11 |
| src/guide/reusability/composables.md | 17 |
| src/guide/extras/reactivity-in-depth.md | 21 |
| src/api/reactivity-core.md | 14 |

## VUE001 · exact · unverified

我改完 count 就去读页面上的数字，拿到的还是旧值。Vue 里应该等哪个时机，代码怎么写？

**候选标准答案：** DOM 更新不是同步的；修改状态后 await nextTick()，再读取更新后的 DOM。

**评价点：** 说明 DOM 更新被缓冲；给出修改状态后 await nextTick() 的顺序

- 来源：[src/guide/essentials/reactivity-fundamentals.md:336](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L336-L338)
- 章节：响应式基础 / 声明方法 \* / DOM 更新时机
- Chunk：a61ced98-5f68-5f24-9fa9-0f0239cb5331

```text
当你修改了响应式状态时，DOM 会被自动更新。但是需要注意的是，DOM 更新不是同步的。Vue 会在“next tick”更新周期中缓冲所有状态的修改，以确保不管你进行了多少次状态修改，每个组件都只会被更新一次。

要等待 DOM 更新完成后再执行额外的代码，可以使用 [nextTick()](/api/general#nexttick) 全局 API：
```


## VUE002 · exact · unverified

模板里反复用同一个计算结果，用 computed 和直接调用方法有什么实际区别？

**候选标准答案：** 计算属性基于响应式依赖缓存，只在依赖变化时重新计算；方法在重渲染时会再次执行。

**评价点：** 说明缓存依据是响应式依赖；区分方法重渲染时再次执行

- 来源：[src/guide/essentials/computed.md:173](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/computed.md#L173-L173)
- 章节：计算属性 / 计算属性缓存 vs 方法
- Chunk：311e4473-3182-5dcf-82cd-9e855bf2c846

```text
若我们将同样的函数定义为一个方法而不是计算属性，两种方式在结果上确实是完全相同的，然而，不同之处在于**计算属性值会基于其响应式依赖被缓存**。一个计算属性仅会在其响应式依赖更新时才重新计算。这意味着只要 `author.books` 不改变，无论多少次访问 `publishedBooksMessage` 都会立即返回先前的计算结果，而不用重复执行 getter 函数。
```

- 来源：[src/guide/essentials/computed.md:197](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/computed.md#L197-L197)
- 章节：计算属性 / 计算属性缓存 vs 方法
- Chunk：311e4473-3182-5dcf-82cd-9e855bf2c846

```text
相比之下，方法调用**总是**会在重渲染发生时再次执行函数。
```


## VUE003 · exact · unverified

孙组件 emit 了 save，爷爷组件直接写 @save 为什么收不到？组件事件不是也会冒泡吗？

**候选标准答案：** Vue 组件事件没有 DOM 事件的冒泡机制，只能直接监听子组件；跨层通信需显式转发或使用合适的跨层通信机制。

**评价点：** 明确组件事件不冒泡；说明直接子组件监听范围

- 来源：[src/guide/components/events.md:65](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/events.md#L65-L65)
- 章节：组件事件 / 触发与监听事件
- Chunk：8ac182f3-5001-5e2e-be32-96cff001c95c

```text
和原生 DOM 事件不一样，组件触发的事件**没有冒泡机制**。你只能监听直接子组件触发的事件。平级组件或是跨越多层嵌套的组件间通信，应使用一个外部的事件总线，或是使用一个[全局状态管理方案](/guide/scaling-up/state-management)。
```


## VUE004 · exact · unverified

我想等接口返回之后再注册 onMounted，这样写可以吗？生命周期钩子什么时候必须注册？

**候选标准答案：** 生命周期钩子需要在组件初始化时同步注册，不应等异步接口返回后再注册；可以在同步起源于 setup 的外部函数中注册。

**评价点：** 同步注册；区分同步调用链与词法位置

- 来源：[src/guide/essentials/lifecycle.md:44](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/lifecycle.md#L44-L44)
- 章节：生命周期钩子 / 注册周期钩子
- Chunk：9d63a26c-c553-5fdf-a1f8-88f7bc432c7e

```text
当调用 `onMounted` 时，Vue 会自动将回调函数注册到当前正被初始化的组件实例上。这意味着这些钩子应当在组件初始化时被**同步**注册。例如，请不要这样做：
```

- 来源：[src/guide/essentials/lifecycle.md:55](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/lifecycle.md#L55-L55)
- 章节：生命周期钩子 / 注册周期钩子
- Chunk：70ea2dc7-cd64-584f-a91f-a91c4cc6e9ff

```text
注意这并不意味着对 `onMounted` 的调用必须放在 `setup()` 或 `<script setup>` 内的词法上下文中。`onMounted()` 也可以在一个外部函数中调用，只要调用栈是同步的，且最终起源自 `setup()` 就可以。
```


## VUE005 · exact · unverified

组件现在有 header 和 main 两个根节点，父组件传的 class 不知道落哪儿，还报了警告，要怎么处理？

**候选标准答案：** 多根节点组件不会自动透传 attributes，需要显式选择目标元素绑定 $attrs，否则可能产生运行时警告。

**评价点：** 多根节点没有自动透传；显式将 $attrs 绑定到目标元素

- 来源：[src/guide/components/attrs.md:129](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/attrs.md#L129-L137)
- 章节：透传 Attributes / 多根节点的 Attributes 继承
- Chunk：50476fce-cc56-5fb7-85b8-c4b220f7cc0c

```text
## 多根节点的 Attributes 继承 {#attribute-inheritance-on-multiple-root-nodes}

和单根节点组件有所不同，有着多个根节点的组件没有自动 attribute 透传行为。如果 `$attrs` 没有被显式绑定，将会抛出一个运行时警告。

```vue-html
<CustomLayout id="custom-layout" @click="changeValue" />
```

如果 `<CustomLayout>` 有下面这样的多根节点模板，由于 Vue 不知道要将 attribute 透传到哪里，所以会抛出一个警告。
```


## VUE006 · paraphrase · unverified

watch(obj.count, ...) 一直没按预期触发，我只想盯着 count，不想监控整个对象，该怎么改？

**候选标准答案：** 直接传 obj.count 得到的是普通值；应使用 watch(() => obj.count, callback) 提供 getter 数据源。

**评价点：** 指出传入的是普通 number；提供 getter 形式

- 来源：[src/guide/essentials/watchers.md:137](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L137-L155)
- 章节：侦听器 / 基本示例 / 侦听数据源类型
- Chunk：a69b781c-faf2-5e17-9bff-942dd6d58e1e

```text
注意，你不能直接侦听响应式对象的属性值，例如：

```js
const obj = reactive({ count: 0 })

// 错误，因为 watch() 得到的参数是一个 number
watch(obj.count, (count) => {
  console.log(`Count is: ${count}`)
})
```

这里需要用一个返回该属性的 getter 函数：

```js
// 提供一个 getter 函数
watch(
  () => obj.count,
  (count) => {
    console.log(`Count is: ${count}`)
```


## VUE007 · paraphrase · unverified

reactive 数组里放了 ref，取出来怎么还是个对象？我以为 Vue 都会帮忙拆开。

**候选标准答案：** ref 作为响应式数组或 Map 等原生集合的元素访问时不会自动解包，需要读取 .value。

**评价点：** 数组与集合元素不自动解包；说明 .value

- 来源：[src/guide/essentials/reactivity-fundamentals.md:497](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L497-L508)
- 章节：响应式基础 / 额外的 ref 解包细节 \*\* / 数组和集合的注意事项 \*\*
- Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf

```text
### 数组和集合的注意事项 \*\* {#caveat-in-arrays-and-collections}

与 reactive 对象不同的是，当 ref 作为响应式数组或原生集合类型 (如 `Map`) 中的元素被访问时，它**不会**被解包：

```js
const books = reactive([ref('Vue 3 Guide')])
// 这里需要 .value
console.log(books[0].value)

const map = reactive(new Map([['count', ref(0)]]))
// 这里需要 .value
console.log(map.get('count').value)
```


## VUE008 · paraphrase · unverified

页面外层和内层都 provide 了同名配置，最里面的组件 inject 到底会用哪一份？

**候选标准答案：** 沿祖先链解析时使用距离注入组件最近的同名提供者的值。

**评价点：** 最近祖先提供者优先

- 来源：[src/guide/components/provide-inject.md:126](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/provide-inject.md#L126-L126)
- 章节：依赖注入 / Inject (注入)
- Chunk：9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 6c6a0da9-16b7-505e-a86f-e4c448a3a84f, f7de642c-8c51-5935-b29d-e813ff85d667

```text
如果有多个父组件提供了相同键的数据，注入将解析为组件链上最近的父组件所注入的值。
```


## VUE009 · paraphrase · unverified

父组件已经拿到子组件 ref 了，为什么调用不到 script setup 里写的那个方法？

**候选标准答案：** script setup 组件默认私有；子组件需要用 defineExpose 显式暴露方法，且应在 await 之前调用。

**评价点：** 默认私有；defineExpose；await 前调用

- 来源：[src/guide/essentials/template-refs.md:191](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L191-L191)
- 章节：模板引用 / 组件上的 ref
- Chunk：a4c45296-6467-56cf-abc4-1ab6df219fe9

```text
有一个例外的情况，使用了 `<script setup>` 的组件是**默认私有**的：一个父组件无法访问到一个使用了 `<script setup>` 的子组件中的任何东西，除非子组件在其中通过 `defineExpose` 宏显式暴露：
```

- 来源：[src/guide/essentials/template-refs.md:210](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L210-L210)
- 章节：模板引用 / 组件上的 ref
- Chunk：39306021-aad3-5ab4-b8ef-2089274e1c23

```text
请注意，defineExpose 必须在任何 await 操作之前调用。否则，在 await 操作后暴露的属性和方法将无法访问。
```


## VUE010 · paraphrase · unverified

我把 useXXX 返回的状态解构出来用，页面就不更新了。组合式函数应该返回什么结构才不容易踩这个坑？

**候选标准答案：** 推荐返回包含多个 ref 的普通非响应式对象；解构后 ref 仍保持响应性。直接解构返回的 reactive 对象可能丢失属性的响应性连接。

**评价点：** 普通对象包含多个 ref；解释 reactive 对象解构的风险

- 来源：[src/guide/reusability/composables.md:266](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/reusability/composables.md#L266-L275)
- 章节：组合式函数 / 约定和最佳实践 / 返回值
- Chunk：78622d60-8947-503b-afda-dd4ff065daf0

```text
### 返回值 {#return-values}

你可能已经注意到了，我们一直在组合式函数中使用 `ref()` 而不是 `reactive()`。我们推荐的约定是组合式函数始终返回一个包含多个 ref 的普通的非响应式对象，这样该对象在组件中被解构为 ref 之后仍可以保持响应性：

```js
// x 和 y 是两个 ref
const { x, y } = useMouse()
```

从组合式函数返回一个响应式对象会导致在对象解构过程中丢失与组合式函数内状态的响应性连接。与之相反，ref 则可以维持这一响应性连接。
```


## VUE011 · multi_evidence · unverified

搜索条件变化后要刷新接口数据，结果再拿来算一段展示文字。这两步都塞进 computed 合适吗，应该怎样分工？

**候选标准答案：** computed getter 应保持无副作用，用于计算派生展示值；请求等副作用应放在 watch 或 watchEffect 等侦听逻辑中。

**评价点：** 请求与派生计算分开；computed getter 不做请求；侦听状态变化执行副作用

- 来源：[src/guide/essentials/computed.md:379](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/computed.md#L379-L379)
- 章节：计算属性 / 最佳实践 / Getter 不应有副作用
- Chunk：978727b4-5fcd-52c9-9986-cade596174c5

```text
计算属性的 getter 应只做计算而没有任何其他的副作用，这一点非常重要，请务必牢记。举例来说，**不要改变其他状态、在 getter 中做异步请求或者更改 DOM**！一个计算属性的声明中描述的是如何根据其他值派生一个值。因此 getter 的职责应该仅为计算和返回该值。在之后的指引中我们会讨论如何使用[侦听器](./watchers)根据其他响应式状态的变更来创建副作用。
```

- 来源：[src/guide/essentials/watchers.md:5](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L5-L5)
- 章节：侦听器 / 基本示例
- Chunk：8e4f1aff-7937-55a2-8a64-90738891a3c4

```text
计算属性允许我们声明性地计算衍生值。然而在有些情况下，我们需要在状态变化时执行一些“副作用”：例如更改 DOM，或是根据异步操作的结果去修改另一处的状态。
```


## VUE012 · multi_evidence · unverified

编辑器子组件收到一个对象 prop，想修改里面的姓名并通知父组件保存。技术上能直接改吗，推荐的数据流怎么设计？

**候选标准答案：** 对象 prop 的嵌套值技术上可以修改，但通常不推荐；子组件抛出变更事件，由父组件监听并更新自己的状态，保持数据流清晰。

**评价点：** 区分不能改 prop 绑定与可以改嵌套对象；通常由子组件 emit 通知父组件更新

- 来源：[src/guide/components/props.md:455](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/props.md#L455-L459)
- 章节：Props / 单向数据流 / 更改对象 / 数组类型的 props
- Chunk：cb0c49b4-fe85-52e6-8e8b-e126933a0c77

```text
### 更改对象 / 数组类型的 props {#mutating-object-array-props}

当对象或数组作为 props 被传入时，虽然子组件无法更改 props 绑定，但仍然**可以**更改对象或数组内部的值。这是因为 JavaScript 的对象和数组是按引用传递，对 Vue 来说，阻止这种更改需要付出的代价异常昂贵。

这种更改的主要缺陷是它允许了子组件以某种不明显的方式影响父组件的状态，可能会使数据流在将来变得更难以理解。在最佳实践中，你应该尽可能避免这样的更改，除非父子组件在设计上本来就需要紧密耦合。在大多数场景下，子组件应该[抛出一个事件](/guide/components/events)来通知父组件做出改变。
```

- 来源：[src/guide/essentials/component-basics.md:363](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/component-basics.md#L363-L363)
- 章节：组件基础 / 监听事件
- Chunk：af17e069-2291-5e66-ab9e-3e461f361655

```text
这个按钮目前还没有做任何事情，我们想要点击这个按钮来告诉父组件它应该放大所有博客文章的文字。要解决这个问题，组件实例提供了一个自定义事件系统。父组件可以通过 `v-on` 或 `@` 来选择性地监听子组件上抛的事件，就像监听原生 DOM 事件那样：
```

- 来源：[src/guide/essentials/component-basics.md:384](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/component-basics.md#L384-L384)
- 章节：组件基础 / 监听事件
- Chunk：8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 7ad21482-7a99-5298-b491-e4c038d091ed

```text
因为有了 `@enlarge-text="postFontSize += 0.1"` 的监听，父组件会接收这一事件，从而更新 `postFontSize` 的值。
```


## VUE013 · multi_evidence · unverified

封装按钮时把 click 写进 emits，父组件的 @click 还是不是透传到原生按钮？为什么声明事件会影响这个行为？

**候选标准答案：** 声明过的事件监听器会被组件消费，不再作为普通透传监听器；click 声明为组件事件后，父级监听的是组件 emit 的 click，而非自动监听原生 click。

**评价点：** 声明过的监听器被消费；区分组件 click 与原生 click

- 来源：[src/guide/components/attrs.md:72](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/attrs.md#L72-L72)
- 章节：透传 Attributes / Attributes 继承 / 深层组件继承
- Chunk：14715e3f-b60c-5d9b-91d8-18b640139142

```text
1. 透传的 attribute 不会包含 `<MyButton>` 上声明过的 props 或是针对 `emits` 声明事件的 `v-on` 侦听函数，换句话说，声明过的 props 和侦听函数被 `<MyButton>`“消费”了。
```

- 来源：[src/guide/components/events.md:225](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/events.md#L225-L225)
- 章节：组件事件 / 声明触发的事件
- Chunk：3b0f0264-6b3a-5091-9c44-ba77aa88f80b

```text
如果一个原生事件的名字 (例如 `click`) 被定义在 `emits` 选项中，则监听器只会监听组件触发的 `click` 事件而不会再响应原生的 `click` 事件。
```


## VUE014 · multi_evidence · unverified

想把输入框自动聚焦逻辑抽成 useFocus，应该什么时候读取模板 ref，卸载时带上的事件监听器又该在哪清理？

**候选标准答案：** 模板引用在挂载后才可访问，初次渲染或元素被卸载时可能为空；DOM 副作用放在 onMounted 等挂载后阶段，事件监听器在 onUnmounted 清理。

**评价点：** 挂载后访问模板 ref；处理 null；卸载时清理事件监听器

- 来源：[src/guide/essentials/template-refs.md:96](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L96-L96)
- 章节：模板引用 / 访问模板引用
- Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46

```text
注意，你只可以**在组件挂载后**才能访问模板引用。如果你想在模板中的表达式上访问 <span class="options-api">`$refs.input`</span><span class="composition-api">`input`</span>，在初次渲染时会是 <span class="options-api">`undefined`</span><span class="composition-api">`null`</span>。这是因为在初次渲染前这个元素还不存在呢！
```

- 来源：[src/guide/reusability/composables.md:293](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/reusability/composables.md#L293-L295)
- 章节：组合式函数 / 约定和最佳实践 / 副作用
- Chunk：912be6b3-bf0c-52fa-b084-b32a071bda9b

```text
- 如果你的应用用到了[服务端渲染](/guide/scaling-up/ssr) (SSR)，请确保在组件挂载后才调用的生命周期钩子中执行 DOM 相关的副作用，例如：`onMounted()`。这些钩子仅会在浏览器中被调用，因此可以确保能访问到 DOM。

- 确保在 `onUnmounted()` 时清理副作用。举例来说，如果一个组合式函数设置了一个事件监听器，它就应该在 `onUnmounted()` 中被移除 (就像我们在 `useMouse()` 示例中看到的一样)。当然也可以像之前的 `useEventListener()` 示例那样，使用一个组合式函数来自动帮你做这些事。
```


## VUE015 · multi_evidence · unverified

把 reactive 对象里的一个数字解构到局部变量，和从组合式函数拿到一个 ref 再解构，为什么更新效果不一样？

**候选标准答案：** 解构 reactive 对象的原始类型属性会脱离源对象的代理访问，局部绑定不再响应；从普通对象解构得到的 ref 保留自身的响应式容器身份。

**评价点：** 解释代理 get/set 与局部绑定；区分 ref 容器和原始值

- 来源：[src/guide/extras/reactivity-in-depth.md:107](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/extras/reactivity-in-depth.md#L107-L107)
- 章节：深入响应式系统 / Vue 中的响应性是如何工作的
- Chunk：a2425d5f-5163-58d8-8d74-37d38abc304f

```text
- 当你将一个响应式对象的属性赋值或解构到一个本地变量时，访问或赋值该变量是非响应式的，因为它将不再触发源对象上的 get / set 代理。注意这种“断开”只影响变量绑定——如果变量指向一个对象之类的非原始值，那么对该对象的修改仍然是响应式的。
```

- 来源：[src/guide/reusability/composables.md:268](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/reusability/composables.md#L268-L275)
- 章节：组合式函数 / 约定和最佳实践 / 返回值
- Chunk：78622d60-8947-503b-afda-dd4ff065daf0

```text
你可能已经注意到了，我们一直在组合式函数中使用 `ref()` 而不是 `reactive()`。我们推荐的约定是组合式函数始终返回一个包含多个 ref 的普通的非响应式对象，这样该对象在组件中被解构为 ref 之后仍可以保持响应性：

```js
// x 和 y 是两个 ref
const { x, y } = useMouse()
```

从组合式函数返回一个响应式对象会导致在对象解构过程中丢失与组合式函数内状态的响应性连接。与之相反，ref 则可以维持这一响应性连接。
```


## VUE016 · similar_concepts · unverified

watch 和 watchEffect 是不是只差一个不用写监听源？如果回调里有 await，依赖追踪有什么容易漏掉的地方？

**候选标准答案：** watch 只追踪显式数据源；watchEffect 自动追踪同步执行中访问的响应式依赖，异步回调第一个 await 之后才访问的属性不会被其追踪。

**评价点：** 显式源与自动追踪区别；第一个 await 前的同步依赖限制

- 来源：[src/guide/essentials/watchers.md:356](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L356-L356)
- 章节：侦听器 / `watchEffect()` \*\*
- Chunk：e6a99cf2-692a-571b-bba4-cc7b833242b0

```text
`watchEffect` 仅会在其**同步**执行期间，才追踪依赖。在使用异步回调时，只有在第一个 `await` 正常工作前访问到的属性才会被追踪。
```

- 来源：[src/guide/essentials/watchers.md:363](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L363-L365)
- 章节：侦听器 / `watchEffect()` \*\* / `watch` vs. `watchEffect`
- Chunk：eb733fbd-8a4c-595e-bebe-6f8c374b6aca

```text
- `watch` 只追踪明确侦听的数据源。它不会追踪任何在回调中访问到的东西。另外，仅在数据源确实改变时才会触发回调。`watch` 会避免在发生副作用时追踪依赖，因此，我们能更加精确地控制回调函数的触发时机。

- `watchEffect`，则会在副作用发生期间追踪依赖。它会在同步执行过程中，自动追踪所有能访问到的响应式属性。这更方便，而且代码往往更简洁，但有时其响应性依赖关系会不那么明确。
```


## VUE017 · similar_concepts · unverified

同一个 ref 放进 reactive 对象属性时不用 .value，放进数组或 Map 就要写，这两种情况到底怎么区分？

**候选标准答案：** 深层 reactive 对象的属性会自动解包 ref，但响应式数组或原生集合的元素访问不会自动解包，后者需 .value。

**评价点：** 深层对象属性自动解包；数组及 Map 元素不解包

- 来源：[src/guide/essentials/reactivity-fundamentals.md:470](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L470-L470)
- 章节：响应式基础 / 额外的 ref 解包细节 \*\* / 作为 reactive 对象的属性 \*\*
- Chunk：4dbf7985-2e57-5fd4-be7d-efe56d8b62ed

```text
一个 ref 会在作为响应式对象的属性被访问或修改时自动解包。换句话说，它的行为就像一个普通的属性：
```

- 来源：[src/guide/essentials/reactivity-fundamentals.md:495](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L495-L499)
- 章节：响应式基础 / 额外的 ref 解包细节 \*\* / 作为 reactive 对象的属性 \*\*
- Chunk：0acddac2-51f2-57d9-aa94-d7c60909bccf

```text
只有当嵌套在一个深层响应式对象内时，才会发生 ref 解包。当其作为[浅层响应式对象](/api/reactivity-advanced#shallowreactive)的属性被访问时不会解包。

### 数组和集合的注意事项 \*\* {#caveat-in-arrays-and-collections}

与 reactive 对象不同的是，当 ref 作为响应式数组或原生集合类型 (如 `Map`) 中的元素被访问时，它**不会**被解包：
```


## VUE018 · similar_concepts · unverified

插槽写在父组件里，为什么不能直接读子组件的局部变量？作用域插槽是怎么把这部分数据交给我的？

**候选标准答案：** 插槽表达式遵循定义位置的作用域，不能直接访问子组件状态；子组件通过 slot 出口传递属性，父组件通过 v-slot 接收插槽 props。

**评价点：** 定义作用域；slot props 与 v-slot

- 来源：[src/guide/components/slots.md:101](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/slots.md#L101-L103)
- 章节：插槽 Slots / 渲染作用域
- Chunk：94c5c015-934e-56ce-bf8f-b2e48d2f1227

```text
插槽内容**无法访问**子组件的数据。Vue 模板中的表达式只能访问其定义时所处的作用域，这和 JavaScript 的词法作用域规则是一致的。换言之：

> 父组件模板中的表达式只能访问父组件的作用域；子组件模板中的表达式只能访问子组件的作用域。
```

- 来源：[src/guide/components/slots.md:349](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/slots.md#L349-L353)
- 章节：插槽 Slots / 作用域插槽
- Chunk：675b751e-f782-5245-a31c-7c8747b4bc51

```text
在上面的[渲染作用域](#render-scope)中我们讨论到，插槽的内容无法访问到子组件的状态。

然而在某些场景下插槽的内容可能想要同时使用父组件域内和子组件域内的数据。要做到这一点，我们需要一种方法来让子组件在渲染时将一部分数据提供给插槽。

事实上，我们确实可以这样做——可以像向组件传递 props 一样，向一个插槽的出口上传递 attributes。父级模板通过 `v-slot` 接收插槽 props，而子级模板在渲染时将 props 传递给插槽出口：
```


## VUE019 · similar_concepts · unverified

把对象交给 reactive 后，返回值和原对象用 === 比较为什么不相等？修改时应该一直用哪一个？

**候选标准答案：** reactive 返回的是原对象的 Proxy，不与原对象严格相等；应该统一使用代理对象，以便访问和修改被响应式系统追踪。

**评价点：** Proxy 与原对象不同身份；使用代理对象

- 来源：[src/guide/essentials/reactivity-fundamentals.md:399](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L399-L399)
- 章节：响应式基础 / `reactive()` \*\* / Reactive Proxy vs. Original \*\*
- Chunk：1c6906ee-9f65-5463-8a09-0c1e1f83e9d9

```text
值得注意的是，`reactive()` 返回的是一个原始对象的 [Proxy](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy)，它和原始对象是不相等的：
```

- 来源：[src/guide/essentials/reactivity-fundamentals.md:409](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/reactivity-fundamentals.md#L409-L409)
- 章节：响应式基础 / `reactive()` \*\* / Reactive Proxy vs. Original \*\*
- Chunk：1c6906ee-9f65-5463-8a09-0c1e1f83e9d9

```text
只有代理对象是响应式的，更改原始对象不会触发更新。因此，使用 Vue 的响应式系统的最佳实践是**仅使用你声明对象的代理版本**。
```


## VUE020 · similar_concepts · unverified

组件 v-model 看起来像双向绑定，它和手写 prop 加事件有什么关系？不使用宏时应该接收和触发什么名字？

**候选标准答案：** 默认组件 v-model 对应 modelValue prop 和 update:modelValue 事件；子组件读取 prop，通过事件通知父组件更新，宏只是简化该协议。

**评价点：** modelValue；update:modelValue；解释 prop + 事件协议

- 来源：[src/guide/components/v-model.md:55](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/v-model.md#L55-L62)
- 章节：组件 v-model / 基本用法 / 底层机制
- Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d

```text
### 底层机制 {#under-the-hood}

`defineModel` 是一个便利宏。编译器将其展开为以下内容：

- 一个名为 `modelValue` 的 prop，本地 ref 的值与其同步；
- 一个名为 `update:modelValue` 的事件，当本地 ref 的值发生变更时触发。

在 3.4 版本之前，你一般会按照如下的方式来实现上述相同的子组件：
```

- 来源：[src/guide/components/v-model.md:78](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/v-model.md#L78-L87)
- 章节：组件 v-model / 基本用法 / 底层机制
- Chunk：bf9cd212-476d-5496-8800-b97f88ca327c

```text
然后，父组件中的 `v-model="foo"` 将被编译为：

```vue-html [Parent.vue]
<Child
  :modelValue="foo"
  @update:modelValue="$event => (foo = $event)"
/>
```

如你所见，这显得冗长得多。然而，这样写有助于理解其底层机制。
```


## VUE021 · unanswerable · unverified

项目用 Vue Router 4，登录过期时 beforeEach 怎么配置才能登录后回到原来的地址？请给完整配置。

**候选标准答案：** 这批冻结文档没有 Vue Router 导航守卫配置证据，不能据此提供已核实的完整实现；需要补充 Vue Router 官方资料。

**评价点：** 说明当前资料范围不足；不编造路由配置

无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。

## VUE022 · unanswerable · unverified

Pinia store 想跨标签页同步，还要让持久化缓存两小时后失效，具体插件配置怎么写？

**候选标准答案：** 这批文档没有该 Pinia 插件、跨标签页同步和 TTL 配置的足够证据，需要插件名称、版本及其文档。

**评价点：** 不把 Vue 核心响应式知识当插件配置证据；请求插件与版本信息

无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。

## VUE023 · unanswerable · unverified

Vite 开发服务器把 /socket 代理到后端 WebSocket，vite.config.ts 里代理规则应该怎么写？

**候选标准答案：** 所选 Vue 文档没有 Vite WebSocket 代理配置证据，应查阅相应版本的 Vite 文档，不能将组件通信机制当作服务代理配置。

**评价点：** 区分 Vue 组件与 Vite 服务器配置；指出资料缺失

无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。

## VUE024 · unanswerable · unverified

我的 UserProfile.vue 第 87 行报 Cannot read properties of undefined，你直接告诉我那一行该怎么改，代码暂时不能提供。

**候选标准答案：** 缺少项目代码、堆栈和触发条件，无法从通用官方文档确定具体修改；应先请求最小复现或相关代码。

**评价点：** 不猜测私有代码；请求最小复现与堆栈

无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。

## VUE025 · unanswerable · unverified

一万个带校验的输入框全部改成 ref 后，在我的电脑上每次更新能保证低于 16ms 吗？给我确定的耗时数值。

**候选标准答案：** 这些文档不包含指定硬件和应用负载的测量结果，不能保证 16ms 或给出确定耗时；需要实际基准测量。

**评价点：** 拒绝无实测依据的数值保证；区分响应式机制与性能测量

无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。

## VUE026 · version_boundary · unverified

项目还在 Vue 3.3，组件双向绑定能直接照文档用 defineModel 吗？如果不按 3.4 的推荐写法，旧协议是什么？

**候选标准答案：** 该快照从 Vue 3.4 开始推荐 defineModel；对 Vue 3.3 不应直接套用这项推荐，应按 modelValue prop 与 update:modelValue 事件实现相同协议。

**评价点：** 识别 3.4 推荐边界，不推断实验 API 绝对不存在；给出旧协议

- 来源：[src/guide/components/v-model.md:13](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/v-model.md#L13-L13)
- 章节：组件 v-model / 基本用法
- Chunk：0f8e1a48-a80a-5e02-8265-590e6dee4d02

```text
从 Vue 3.4 开始，推荐的实现方式是使用 [`defineModel()`](/api/sfc-script-setup#definemodel) 宏：
```

- 来源：[src/guide/components/v-model.md:59](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/v-model.md#L59-L60)
- 章节：组件 v-model / 基本用法 / 底层机制
- Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d, bf9cd212-476d-5496-8800-b97f88ca327c

```text
- 一个名为 `modelValue` 的 prop，本地 ref 的值与其同步；
- 一个名为 `update:modelValue` 的事件，当本地 ref 的值发生变更时触发。
```

- 来源：[src/guide/components/v-model.md:62](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/v-model.md#L62-L62)
- 章节：组件 v-model / 基本用法 / 底层机制
- Chunk：1bbe5952-a953-5a71-8973-d627be6ae29d, bf9cd212-476d-5496-8800-b97f88ca327c

```text
在 3.4 版本之前，你一般会按照如下的方式来实现上述相同的子组件：
```


## VUE027 · version_boundary · unverified

升级到 Vue 3.5 后，从 defineProps 解构出来的变量为什么又能跟着更新了？在 3.4 项目里也能这样理解吗？

**候选标准答案：** 在同一 script setup 中，3.5+ 编译器会把对解构 props 变量的访问转换为 props 属性访问；3.4 及以下的同类解构变量是不会随 prop 更新的常量，不能混用解释。

**评价点：** 3.5 编译器转换；3.4 及以下区别；同一 script setup 上下文

- 来源：[src/guide/components/props.md:122](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/components/props.md#L122-L138)
- 章节：Props / 响应式 Props 解构 <sup class="vt-badge" data-text="3.5+" /> \*\*
- Chunk：3769516e-964b-55cd-ad0e-2035bcfdef73

```text
## 响应式 Props 解构 <sup class="vt-badge" data-text="3.5+" /> \*\* {#reactive-props-destructure}

Vue 的响应系统基于属性访问跟踪状态的使用情况。例如，在计算属性或侦听器中访问 `props.foo` 时，`foo` 属性将被跟踪为依赖项。

因此，在以下代码的情况下：

```js
const { foo } = defineProps(['foo'])

watchEffect(() => {
  // 在 3.5 之前只运行一次
  // 在 3.5+ 中在 "foo" prop 变化时重新执行
  console.log(foo)
})
```

在 3.4 及以下版本，`foo` 是一个实际的常量，永远不会改变。在 3.5 及以上版本，当在同一个 `<script setup>` 代码块中访问由 `defineProps` 解构的变量时，Vue 编译器会自动在前面添加 `props.`。因此，上面的代码等同于以下代码：
```


## VUE028 · version_boundary · unverified

Vue 3.4 项目复制 useTemplateRef 示例后用不了，这个 API 从哪个版本开始有，旧项目应该怎样拿模板引用？

**候选标准答案：** useTemplateRef 是 3.5+ API；之前需要声明一个与模板 ref attribute 匹配的 ref，并在挂载后访问。

**评价点：** 3.5+ 边界；同名 ref 旧写法；挂载后访问

- 来源：[src/guide/essentials/template-refs.md:15](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L15-L15)
- 章节：模板引用 / 访问模板引用
- Chunk：da91b8dd-87b7-56c9-b189-d662360d8d3d

```text
要在组合式 API 中获取引用，我们可以使用辅助函数 [`useTemplateRef()`](/api/composition-api-helpers#usetemplateref) <sup class="vt-badge" data-text="3.5+" />：
```

- 来源：[src/guide/essentials/template-refs.md:37](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L37-L48)
- 章节：模板引用 / 访问模板引用
- Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46

```text
<summary>3.5 前的用法</summary>

在 3.5 之前的版本尚未引入 `useTemplateRef()`，我们需要声明一个与模板里 ref attribute 匹配的引用：

```vue
<script setup>
import { ref, onMounted } from 'vue'

// 声明一个 ref 来存放该元素的引用
// 必须和模板里的 ref 同名
const input = ref(null)
```

- 来源：[src/guide/essentials/template-refs.md:96](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/template-refs.md#L96-L96)
- 章节：模板引用 / 访问模板引用
- Chunk：bf02ccc6-915f-583e-9f67-fcbf7f74af46

```text
注意，你只可以**在组件挂载后**才能访问模板引用。如果你想在模板中的表达式上访问 <span class="options-api">`$refs.input`</span><span class="composition-api">`input`</span>，在初次渲染时会是 <span class="options-api">`undefined`</span><span class="composition-api">`null`</span>。这是因为在初次渲染前这个元素还不存在呢！
```


## VUE029 · version_boundary · unverified

想让 watch 只往对象里检查两层，deep: 2 能直接用在 Vue 3.4 吗？数字形式的 deep 有版本要求吗？

**候选标准答案：** 文档将数字形式的 deep 标为 Vue 3.5+，表示最大遍历深度；不能将这项语义直接用于 3.4。

**评价点：** 3.5+ 数字 deep；最大遍历深度；不对 3.4 作同样保证

- 来源：[src/guide/essentials/watchers.md:227](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L227-L227)
- 章节：侦听器 / 深层侦听器
- Chunk：e2800ff6-c50c-5f52-99b7-831b1347f720

```text
在 Vue 3.5+ 中，`deep` 选项还可以是一个数字，表示最大遍历深度——即 Vue 应该遍历对象嵌套属性的级数。
```

- 来源：[src/api/reactivity-core.md:426](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/api/reactivity-core.md#L426-L426)
- 章节：响应式 API：核心 / watch()
- Chunk：6df6403f-8dea-58e9-bd6a-514c4cdf368e

```text
  - **`deep`**：如果源是对象，强制深度遍历，以便在深层级变更时触发回调。在 3.5+ 中，此参数还可以是指示最大遍历深度的数字。参考[深层侦听器](/guide/essentials/watchers#deep-watchers)。
```


## VUE030 · version_boundary · unverified

Vue 3.5 里我先 await 再调用 onWatcherCleanup 取消旧请求，为什么不对？它和回调参数给的 onCleanup 限制一样吗？

**候选标准答案：** onWatcherCleanup 仅在 3.5+ 支持，必须在 watch/watchEffect 的同步执行阶段调用，不能放在 await 后；回调参数 onCleanup 与侦听器实例绑定，不受该同步限制。

**评价点：** 3.5+；同步阶段注册；与 onCleanup 区分

- 来源：[src/guide/essentials/watchers.md:449](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L449-L449)
- 章节：侦听器 / 副作用清理
- Chunk：93ee0ba2-4f0f-5338-b6c6-b02f9b42f907

```text
请注意，`onWatcherCleanup` 仅在 Vue 3.5+ 中支持，并且必须在 `watchEffect` 效果函数或 `watch` 回调函数的同步执行期间调用：你不能在异步函数的 `await` 语句之后调用它。
```

- 来源：[src/guide/essentials/watchers.md:489](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/guide/essentials/watchers.md#L489-L489)
- 章节：侦听器 / 副作用清理
- Chunk：cb8f0eda-ad24-5450-936d-a2eef1905f3b

```text
通过函数参数传递的 `onCleanup` 与侦听器实例相绑定，因此不受 `onWatcherCleanup` 的同步限制。
```

- 来源：[src/api/reactivity-core.md:557](https://github.com/vuejs-translations/docs-zh-cn/blob/418f5ae6e15c7a90beae017e44d58dac3d93ad95/src/api/reactivity-core.md#L557-L559)
- 章节：响应式 API：核心 / onWatcherCleanup() <sup class="vt-badge" data-text="3.5+" />
- Chunk：5acc91a0-5fd7-5021-86c0-a9d2e4ee124e

```text
## onWatcherCleanup() <sup class="vt-badge" data-text="3.5+" /> {#onwatchercleanup}

注册一个清理函数，在当前侦听器即将重新运行时执行。只能在 `watchEffect` 作用函数或 `watch` 回调函数的同步执行期间调用 (即不能在异步函数的 `await` 语句之后调用)。
```

