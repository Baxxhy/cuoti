from .manual_questions import display_options,answer_text
from .accounts import secret
from .security import media_url


def image_layout(question):
    count=len(question.get('image_paths',[]));stem=question.get('question_text','').count('<ImageHere>')
    option_counts=[o.get('text','').count('<ImageHere>') for o in display_options(question)]
    answer=answer_text(question.get('answer')).count('<ImageHere>');solution=question.get('solution','').count('<ImageHere>')
    total=stem+sum(option_counts)+answer+solution;visual=(question.get('source_metadata') or {}).get('has_visual') is True
    result={'review':total!=count and (total>0 or visual),'stem':[],'options':[],'answer':[],'solution':[]};index=0
    for key,amounts in [('stem',[count if total==0 and not visual else stem]),('options',option_counts),('answer',[answer]),('solution',[solution])]:
        for amount in amounts:
            indices=[i for i in range(index,index+amount) if i<count];index+=amount
            if key=='options':result[key].append(indices)
            else:result[key]=indices
    return result


def image_urls(question,indices):
    return [media_url(f"/api/v1/practice/questions/{question['id']}/images/{index}",secret()) for index in indices]


def question_images(question):
    layout=image_layout(question);images=[] if layout['review'] else image_urls(question,layout['stem']);previews=list(images);options=display_options(question)
    for index,option in enumerate(options):
        urls=[] if layout['review'] else image_urls(question,layout['options'][index])
        if urls:option['image_urls']=urls
        previews.extend(urls)
    return {'image_urls':images,'preview_image_urls':previews,'options':options,'image_layout_review':layout['review']}


def solution_images(question):
    layout=image_layout(question)
    return {'answer_image_urls':image_urls(question,layout['answer']),'solution_image_urls':image_urls(question,layout['solution'])}


def bank_question(value):
    result={k:value.get(k) for k in ['id','subject','grade','grade_band','title','question_text','question_type','options','difficulty','knowledge_points','source_name']}
    if (value.get('source_metadata') or {}).get('passage_id'):
        paragraphs=value['question_text'].split('\n\n')
        if len(paragraphs)>1:result['preview_text']='阅读理解：'+paragraphs[-1]
    result.update(question_images(value));return result
