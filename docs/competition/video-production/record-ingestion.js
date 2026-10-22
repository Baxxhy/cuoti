page.setDefaultTimeout(15000);
const results=[];
results.push(await capture('02-login-settings','登录与个性化设置',async()=>{
 await tap('我的');await tap('退出登录');await type(page.getByLabel('邮箱',{exact:true}),email);await type(page.getByLabel('密码',{exact:true}),password);await tap('登录');await page.waitForURL('**/pages/index/index*');await tap('我的');await tap('学习设置');await page.getByLabel('当前学科',{exact:true}).selectOption('数学');await tap('巩固一类题');await tap('10 分钟');await tap('保存设置');await w(2000);
}));
console.log('02',results.at(-1).status);
results.push(await capture('03-photo-upload','选图录入与框选',async()=>{
 await tap('返回');await tap('录入');const chooser=page.waitForEvent('filechooser');await tap('拍照或选择图片');await(await chooser).setFiles('docs/competition/video-production/assets/math-original.png');await w(2000);await tap('框选题目');await page.waitForURL('**/pages/crop/crop*');await tap('选择整张图片');await w(2200);global.photoId=new URL(page.url().replace('/#/','/')).searchParams.get('id');
}));
console.log('03',results.at(-1).status);
results.push(await capture('04-photo-ocr','识别题目与原始步骤',async()=>{
 await tap('开始识别');await page.waitForURL('**/pages/ocr/ocr*',{timeout:180000});await page.locator('.confirm-actions').waitFor({timeout:180000});await w(2000);await scroll(560);await scroll(420);
}));
console.log('04',results.at(-1).status);
results.push(await capture('05-photo-confirm','核对题目与真实错因分析',async()=>{
 await tap('修改内容');await w(1200);await scroll(-300);await w(1800);await tap('预览修改');await tap('确认并分析');await page.waitForURL('**/pages/diagnosis/diagnosis*',{timeout:180000});await page.locator('.tutor-btn').first().waitFor({timeout:180000});await w(2400);await scroll(340);
}));
return results.map(c=>({id:c.id,status:c.status,error:c.error}));
