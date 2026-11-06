from starlette.concurrency import run_in_threadpool
from .algorithm import compute
from .database import Database


async def system_api(kind):
    if kind=='health':
        with Database.from_environment() as db:db.query('SELECT COUNT(*) AS total FROM users')
    state=await run_in_threadpool(compute,{'operation':'system_state','probe_provider':kind=='probe'})
    if kind in ['probe','providers']:return state['provider']
    if kind=='voice':return state['voice']
    provider=state.get('provider') or {}
    return {'status':'healthy','database':'mysql','ai':provider['last_status'],'image_recognition':type(provider.get('vision_entries')) is int and provider['vision_entries']>0}
