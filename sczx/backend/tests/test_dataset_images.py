import copy
from sczx_api.dataset_images import image_layout,question_images,solution_images


def test_stem_option_answer_solution_indices_and_original_snapshot(monkeypatch):
    monkeypatch.setenv('SCZX_AUTH_SECRET','isolated-image-layout-secret-000000000')
    source={'id':'image-question','question_text':'题干<ImageHere>','options':[{'label':'A','text':'选项<ImageHere>'},{'label':'B','text':'文字选项'}],'answer':'答案<ImageHere>','solution':'解析<ImageHere>','image_paths':['stem','option','answer','solution'],'source_metadata':{}}
    before=copy.deepcopy(source)
    layout=image_layout(source)
    assert layout=={'review':False,'stem':[0],'options':[[1],[]],'answer':[2],'solution':[3]}
    public=question_images(source)
    assert '/images/0?' in public['image_urls'][0]
    assert '/images/1?' in public['options'][0]['image_urls'][0]
    assert len(public['preview_image_urls'])==2
    revealed=solution_images(source)
    assert '/images/2?' in revealed['answer_image_urls'][0] and '/images/3?' in revealed['solution_image_urls'][0]
    assert source==before


def test_mismatched_visual_layout_hides_public_images(monkeypatch):
    monkeypatch.setenv('SCZX_AUTH_SECRET','isolated-image-layout-secret-000000000')
    source={'id':'mismatch','question_text':'题干<ImageHere>','options':[],'answer':'答案<ImageHere>','solution':'','image_paths':['only-one'],'source_metadata':{'has_visual':True}}
    assert image_layout(source)['review'] is True
    assert question_images(source)['image_urls']==[]
    assert question_images(source)['preview_image_urls']==[]
