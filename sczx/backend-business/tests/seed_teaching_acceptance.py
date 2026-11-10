"""Seed only a fresh sczx_test_* database for the documented browser acceptance."""
import argparse,json,secrets,subprocess,sys
from pathlib import Path
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account
from test_teaching_mysql import create_accounts,fixture

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    if not (engine.url.database or '').startswith('sczx_test_'):raise SystemExit('仅允许独立 sczx_test_* 数据库')
    subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True)
    with SessionLocal() as db:
        if db.scalar(select(Account.id).where(Account.id=='teaching-t1')):raise SystemExit('验收账号已存在，请使用新的隔离库')
    password=secrets.token_urlsafe(24);create_accounts(password);data=fixture('browser')
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'url':engine.url.render_as_string(hide_password=False),'password':password,**data},ensure_ascii=False));output.chmod(0o600)
    print('已准备2教师、3班、9名班内学生、跨班学生及晚加入学生；凭据仅写入指定私有文件。')
if __name__=='__main__':main()
