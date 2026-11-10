# VisualizationSpec 与互动状态

2026-11-10，v1。仅使用固定 Vue 组件，无模型 HTML/脚本执行。

配置 Schema 在 backend-business/sczx_business/visualization.py；前端固定解释器为 lib/visualization.js 与 BalanceActivity.vue。配置字段：version=1、type=balance/equality_operations、initial.left/right、actions、step、minimum/maximum、learningGoal、completion=balanced_with_explanation。额外字段、未知动作、不合法边界、非有限数值拒绝。旧 type/base/step/max 按确定规则转换，保留已发布版本。

支持左右单侧加/减、两边共同加/减及重置。单侧变化显示真实不等关系和倾斜，双侧相同变化保持原有关系。任何动作不能越界；减至下界时按钮禁用。

配置与学习状态分开：StudentRecord.drafts.blocks[blockId] 保存 visualization.state、actions、explanation、weight/ completed。动作最多200步，可重置；服务器从初始值重放动作，拒绝伪造状态。完成要求至少一次动作、最终两边相等且有自己的解释。旧 weight 读取继续兼容，第一次新动作转换为共同增加历史；旧解释不覆盖。

当前只实现数量天平及共同加减，不扩展几何、函数绘图或任意模型教具。数学核验范围是确定的数量变化，不能据此证明学生理解等式性质。
