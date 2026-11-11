import {spawn} from 'node:child_process';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
export const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export class Browser {
  static async launch(options={}){
    const b=new Browser();b.profile=options.profile||await mkdtemp(join(tmpdir(),'sczx-browser-'));b.retainProfile=!!options.profile;b.pending=new Map();b.errors=[];b.next=0;
    b.process=spawn(process.env.CHROME_PATH||'chromium',['--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+b.profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
    try{
      const endpoint=await new Promise((resolve,reject)=>{let log='';const timeout=setTimeout(()=>reject(Error('Chrome startup timed out; set CHROME_PATH')),15000);b.process.once('error',e=>{clearTimeout(timeout);reject(e)});b.process.stderr.on('data',chunk=>{log+=chunk;const hit=log.match(/DevTools listening on (ws:\/\/\S+)/);if(hit){clearTimeout(timeout);resolve(hit[1])}})});
      b.socket=new WebSocket(endpoint);await new Promise((r,j)=>{b.socket.addEventListener('open',r,{once:true});b.socket.addEventListener('error',j,{once:true})});
      b.socket.addEventListener('message',event=>{const msg=JSON.parse(event.data);if(msg.id){const p=b.pending.get(msg.id);if(!p)return;b.pending.delete(msg.id);clearTimeout(p.timeout);msg.error?p.reject(Error(msg.error.message)):p.resolve(msg.result)}else if(msg.method==='Runtime.exceptionThrown')b.errors.push(msg.params.exceptionDetails.text)});
      const target=await b.send('Target.createTarget',{url:'about:blank'},false);b.session=(await b.send('Target.attachToTarget',{targetId:target.targetId,flatten:true},false)).sessionId;await b.send('Page.enable');await b.send('Runtime.enable');return b;
    }catch(e){await b.close();throw e}
  }
  send(method,params={},session=true){return new Promise((resolve,reject)=>{const id=++this.next;const timeout=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout: '+method))},25000);this.pending.set(id,{resolve,reject,timeout});this.socket.send(JSON.stringify({id,method,params,...(session&&this.session?{sessionId:this.session}:{})}))})}
  async eval(code,arg){const expression=typeof code==='function'?'('+code.toString()+')('+JSON.stringify(arg)+')':code;const r=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result?.value}
  async wait(code,ms=20000){const end=Date.now()+ms;while(Date.now()<end){if(await this.eval(code))return;await sleep(80)}throw Error('Browser wait timed out: '+code)}
  async goto(url){await this.send('Page.navigate',{url});await sleep(250);await this.wait('document.readyState === "complete"')}
  async viewport(width,height=1080){await this.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false})}
  async screenshot(path){const r=await this.send('Page.captureScreenshot',{format:'png'});await writeFile(path,Buffer.from(r.data,'base64'))}
  async close(){if(this.socket?.readyState===1){try{await this.send('Browser.close',{},false)}catch{}this.socket.close()}this.process?.kill('SIGKILL');for(const p of this.pending?.values()||[]){clearTimeout(p.timeout);p.reject(Error('Browser closed'))}if(this.profile&&!this.retainProfile)await rm(this.profile,{recursive:true,force:true,maxRetries:3,retryDelay:100})}
}
