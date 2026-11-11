# un-design - 用布局减少界面的重复解释

Markdown + YAML

<directory>
agents/ - Codex 技能展示元数据，无执行逻辑。
</directory>

<config>
README.md - GitHub 项目入口，说明安装和使用。
SKILL.md - 技能入口，定义文案取舍和界面验证。
agents/openai.yaml - 展示名称和简短用途。
</config>

职责边界：精简 UI，不改变产品功能和内容事实。
决策规则只写入 SKILL.md，元数据只描述用途。
修改规则后，核对入口描述和展示文案。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
