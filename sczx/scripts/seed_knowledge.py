"""Load the bundled public knowledge cards into the configured sczx database."""
from pathlib import Path
import sys
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from sczx_api.knowledge_seed import seed_public_knowledge

if __name__=='__main__':
    load_dotenv(ROOT/'.env')
    counts=seed_public_knowledge()
    print(f"公开知识卡导入完成：{counts['cards']}张卡片，{counts['relations']}条关系。")
