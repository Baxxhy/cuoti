"""Original Cangjie fingerprint golden and renewable receipt links."""
from sczx_api.practice_alignment import digest
from sczx_api.practice import refresh,request_text
from sczx_api.practice_context import equivalent
from sczx_api.security import valid_media
from urllib.parse import urlsplit,parse_qs


def test_original_cangjie_fingerprint_golden():
    value={'题目':'x="\\\n中文😀','options':[{'text':'选项甲','key':'A'}],'student_work_revisions':['a','b'],'empty':None}
    assert digest(value)=='74c903ec10726de023bff49559f627c703eee2e5dc3d57d8973d16c70c3dac9a'
    assert request_text({'mistake_id':' id '},'mistake_id',100,True)==' id '
    assert equivalent({'b':[1,'1'],'a':None},{'a':None,'b':[1,'1']})
    assert not equivalent(True,1)
    assert not equivalent([{'answer':1}],[{'answer':1.0}])


def test_receipt_renews_signed_solution_images_without_mutating_saved_receipt(monkeypatch):
    secret='practice-test-secret-with-at-least-32-characters'
    monkeypatch.setenv('SCZX_AUTH_SECRET',secret)
    question={'id':'image-question','question_text':'求解','options':[],'answer':'2','solution':'<ImageHere>','image_paths':['uploads/diagram.png']}
    receipt={'correct':True,'solution_image_urls':['/expired']}
    result=refresh(question,receipt)
    url=urlsplit(result['solution_image_urls'][0]);query=parse_qs(url.query)
    assert url.path=='/api/v1/practice/questions/image-question/images/0'
    assert valid_media(url.path,query['expires'][0],query['signature'][0],secret)
    assert result['correct'] is True and receipt['solution_image_urls']==['/expired']
