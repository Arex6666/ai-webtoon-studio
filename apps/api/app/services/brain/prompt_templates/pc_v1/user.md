# User Prompt Template (pc_v1)

此文件为用户输入模板的占位符。
实际内容由 PromptComposer 动态生成，包含：

1. 剧本文本 (script_text)
2. 风格配置 (style_profile)
3. 资产上下文摘要 (assets_context)
4. 生成约束 (constraints)

---

## 动态生成示例

```
# 剧本文本
[剧本内容]

# 风格要求
风格：default，标签：korean_webtoon，色调：warm

# 可用资产
## 角色资产
- 周昀
- 林知夏

## 场景资产
- 旧书店

# 生成约束
- 分镜数量: 4 ~ 20
- 总时长: 30 ~ 120 秒
- 单镜头时长: 1.5 ~ 8 秒

# 任务
请根据上述剧本和约束，生成 StoryboardDraftV2 JSON。
```
