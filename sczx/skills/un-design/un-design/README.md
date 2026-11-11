# un-design

> Avoid unnecessary secondary labels and descriptions. Let the layout do the explaining.

一个精简 UI 界面的 Skill。
用分组、间距、层级和对齐表达关系，删掉重复解释的辅助标签与说明。
保留名称、选项差异、限制和操作后果。

## 安装

安装到 Codex 的个人技能目录：

```sh
git clone https://github.com/hiyeshu/un-design.git ~/.codex/skills/un-design
```

目录已经存在时，先检查现有文件，避免覆盖本地修改。

## 使用

```text
$un-design 精简当前页面，让布局表达信息关系，删除多余的标签和说明。
```

可以提供界面截图，也可以在项目中直接检查源码。
审查任务输出具体建议；实现任务交付局部改动。

## 工作原则

- 重复标题或按钮的说明：删除。
- 归属、顺序和主次不清楚：先修布局。
- 条目共用的上下文：合并到标题、表头或分组。
- 名称、单位、限制、费用和操作后果：保留。

完整规则见 [SKILL.md](SKILL.md)。
