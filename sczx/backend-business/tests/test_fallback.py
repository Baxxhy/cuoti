import unittest
from sczx_business.model_provider import ModelProvider,ModelError
from sczx_business.retrieval import retrieve

class RerankFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_or_failed_ranking_keeps_all_candidates(self):
        docs=[{'id':str(i),'title':'等式性质','content':'两边同时变化'} for i in range(4)]
        spec={'query':'等式性质','documents':docs,'rerank':True,'limit':3}
        expected=retrieve({'query':spec['query'],'limit':3},docs)['items']
        provider=ModelProvider()
        try:
            for mode in ['timeout','rate_limit','duplicate','unknown','missing','unsorted']:
                async def injected(cap,data,**kwargs):
                    if mode in ['timeout','rate_limit']:raise ModelError(mode,retryable=True)
                    ids=[x['id'] for x in data['candidates']]
                    if mode=='duplicate':ids[-1]=ids[0]
                    if mode=='unknown':ids[-1]='unknown'
                    if mode=='missing':ids=ids[:-1]
                    scores=[.9-i*.1 for i in range(len(ids))]
                    if mode=='unsorted':scores.reverse()
                    return {'ranking':[{'id':i,'score':s} for i,s in zip(ids,scores)]},'controlled','controlled'
                provider.call=injected
                with self.subTest(mode=mode):
                    actual=await provider._call({},'retrieval',spec,None)
                    self.assertFalse(actual['rerankApplied']);self.assertTrue(actual['warning']);self.assertEqual(actual['items'],expected)
        finally:await provider.close()
