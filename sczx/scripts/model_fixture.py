"""Local OpenAI-compatible fixture for explicitly enumerated browser tests only.

Unknown prompts fail closed. This is never part of the product startup command.
"""
import argparse
import base64
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,required=True);parser.add_argument('--events',type=Path,required=True);parser.add_argument('--figure-image',type=Path);args=parser.parse_args()
    figure_hash=hashlib.sha256(args.figure_image.read_bytes()).hexdigest() if args.figure_image else ''
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            self.send_response(200 if self.path=='/livez' else 404);self.end_headers()
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            text='\n'.join(str(m.get('content','')) for m in payload.get('messages',[]))
            compact=''.join(text.split())
            reviewed=re.search(r'学生作答：(.*?)\n请判断',text,re.S)
            allowed=(self.path=='/v1/chat/completions' and 'AnswerGradeOutput' in text and '3x+2=17' in compact and '标准答案：x=5' in compact and reviewed is not None and ''.join(reviewed[1].split())=='3x=15x=5')
            images=[part.get('image_url',{}).get('url','') for message in payload.get('messages',[]) if isinstance(message.get('content'),list) for part in message['content'] if part.get('type')=='image_url']
            matching=False
            if len(images)==1 and figure_hash:
                try:matching=hashlib.sha256(base64.b64decode(images[0].split(',',1)[1],validate=True)).hexdigest()==figure_hash
                except (ValueError,IndexError):pass
            figure=(self.path=='/v1/chat/completions' and matching and 'FigureHandwritingRecognition' in text and '在三角形ABC中，∠A=50°，∠B=60°，求∠C。' in text)
            if not (allowed or figure):
                self.send_response(503);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":"No controlled fixture for this prompt"}');return
            result={'correct':True,'score':100,'recognized_final_answer':'x=5','reason':'过程已核对：移项和求未知数的两步均与参考相符。','matched_key_steps':['3x=15','x=5'],'error_points':[],'confidence':.99}
            if figure:result={'final_answer':'80','steps':['∠C=80°'],'transcription':'∠C=80°','confidence':.9,'uncertain':False,'figure_observations':[{'relation':'angle_value','points':['A','C','B'],'value':'80','basis':'label','quote':'∠C=80°'}]}
            with args.events.open('a') as stream:stream.write(json.dumps({'fixture':'figure-transcription' if figure else 'review-process','accepted':True})+'\n')
            body=json.dumps({'choices':[{'message':{'content':json.dumps(result,ensure_ascii=False)}}]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()
