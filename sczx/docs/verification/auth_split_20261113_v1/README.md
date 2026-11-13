# GitHub模板分栏登录注册页

2026-11-13 / v1

参考：https://github.com/pure-admin/vue-pure-admin/blob/main/src/views/login/index.vue 。复用其左侧插画、右侧表单结构思路及原始illustration.svg，当前工程继续Vue3 + JavaScript + Element Plus，不引入模板的TypeScript、Motion、其他图标库或演示登录逻辑。

原插画：https://github.com/pure-admin/vue-pure-admin/blob/main/src/assets/login/illustration.svg 。保存在frontend/public/images/auth，附带上游MIT LICENSE和来源说明。下载日期2026-11-13，文件SHA256：04c4f3a7e8e2fcf4a30859f87771aee7b5875369c6af8a38b0cf16df2532f17f。

桌面左侧浅蓝大图，右侧白色表单，取消居中浮动卡片外观。切换时固定顶部位置，短窗口在表单区内滚动，窄于700px隐藏插画以保留表单。密码至少6位，重复账号字段错误等规则保留；前端5175。

验证：1440×1000、1920×1080、1024×768、768×600，登录与注册共8组布局；插画实际加载，输入/选择/按钮44px，无横向溢出或脚本异常。50项浏览器回归及构建、UI源码审计通过。

![登录](1440-login.png)

![注册](1440-register.png)
