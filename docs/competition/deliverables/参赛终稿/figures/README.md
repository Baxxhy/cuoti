# 图源与用途

所有技术图为原生可编辑SVG，同时提供3000×1800 PNG供Word嵌入。SVG保留独立文字、形状与连线；未追描或覆盖旧生成图标记。真实截图在screenshots内，字节与原始运行归档一致。

| 文件 | 内容 |
|---|---|
|00-background|学生错题学习背景|
|01|四项技术总览|
|03|系统分层与服务方向|
|04|错因定位与正反案例|
|05|有效事件与掌握更新|
|06|当前行动与后续选题|
|07|检索和生成的不同检查路径|
|08|单协调器与学生交互|
|09|数据关联与来源版本|
|10|异步计算与事务提交|

生成源为仓库docs/competition/work_final_20261023/draw_figures.py。图中文字使用宋体和DejaVu Serif；编辑SVG时应安装相应字体，或在编辑器中替换后复核字符宽度。所有文字纯黑，填充为低饱和蓝绿橙紫。

## 按图意区分视觉形式

背景采用学习材料示意，架构采用设备、服务器、数据库和文件的语义图标，错因采用批注对照，掌握采用同刻度数值条，数据采用实体表和版本时间线。规划和补题保留决策图，工作流保留泳道，异步过程保留时序图。

新增构图源：docs/competition/work_final_20261023/varied_figures.py，由draw_figures.py调用。图标均为本项目绘制的简单SVG几何图形，无外部图标文件依赖。

表达参考：[C4图形记法](https://c4model.com/diagrams/notation)、[C4部署图与图标建议](https://c4model.com/diagrams/deployment)、[Material Icons官方指南](https://google.github.io/material-design-icons/)。参考组件辨识、图例和线性表达，不复制参考项目架构。
