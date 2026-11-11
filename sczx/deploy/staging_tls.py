#!/usr/bin/env python3
"""Loopback-only TLS test proxy. Production uses the reviewed nginx template."""
import argparse,http.client,ssl
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
class Proxy(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def forward(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>25*1024*1024:self.send_error(413);return
        body=self.rfile.read(length) if length else None
        headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','transfer-encoding','x-forwarded-for','x-forwarded-proto')}
        headers.update({'X-Forwarded-Proto':'https','X-Forwarded-For':'127.0.0.1','Connection':'close'})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.backend_port,timeout=180)
        try:
            conn.request(self.command,self.path,body,headers);response=conn.getresponse();self.send_response(response.status)
            for k,v in response.getheaders():
                if k.lower() not in ('connection','transfer-encoding'):self.send_header(k,v)
            if self.path.startswith('/sw.js'):self.send_header('Cache-Control','no-cache')
            self.end_headers()
            while chunk:=response.read1(65536):self.wfile.write(chunk);self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):pass
        except OSError:
            try:self.send_error(502,'Staging backend unavailable')
            except OSError:pass
        finally:conn.close()
    do_GET=do_POST=do_PUT=do_DELETE=do_PATCH=do_OPTIONS=forward
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backend-port',type=int,required=True);p.add_argument('--port',type=int,default=9443);p.add_argument('--cert',required=True);p.add_argument('--key',required=True);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Proxy);server.backend_port=a.backend_port;ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(a.cert,a.key);server.socket=ctx.wrap_socket(server.socket,server_side=True);server.serve_forever()
