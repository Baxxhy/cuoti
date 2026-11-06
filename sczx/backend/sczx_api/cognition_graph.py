from .accounts import current_user
from .database import Database
from .insights import days_parameter,canonical_mistake,method_label,learner_text,graph_topic,percent
from .questions import display_key
from .recognition import short_title
from .rows import row_json


async def cognition_graph(request):
    days=days_parameter(request,90,3650);subject=request.query_params.get('subject','')
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            all_updates=db.query("SELECT * FROM cognitive_updates WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) AND entity_type<>'note_evidence' ORDER BY created_at,id",[user['id'],-days]).rows
            all_mappings=db.query('SELECT * FROM user_question_knowledge_links WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY created_at,id',[user['id'],-days]).rows
            referenced={r['question_id'] for r in all_updates+all_mappings if r.get('question_id')};questions={};seen=set()
            for row in db.query("SELECT * FROM questions WHERE user_id=? AND status<>'archived' ORDER BY updated_at DESC,id DESC",[user['id']]).rows:
                item_id=row['id']
                if item_id not in referenced:continue
                key=display_key(row['question_text'],item_id)
                if key in seen:continue
                seen.add(key)
                if not subject or row['subject']==subject:questions[item_id]=row_json('questions',row)
            updates=[row_json('cognitive_updates',r) for r in all_updates if not r.get('question_id') or r['question_id'] in questions]
            mappings=[row_json('user_question_knowledge_links',r) for r in all_mappings if not subject or r['question_id'] in questions]
            mapped_questions={r['question_id'] for r in mappings};cards={};labels={};topics={}
            for row in db.query('SELECT * FROM knowledge_points ORDER BY id').rows:
                card=row_json('knowledge_points',row)
                if subject and card['subject']!=subject:continue
                cards[card['id']]=card
                for label in [card['name'],card['code']]:labels[(card['subject'],label)]=card
            for update in updates:
                item_id=update.get('question_id') or '';key=update.get('entity_key') or ''
                if item_id and update['entity_type']=='mastery' and key and item_id not in topics:topics[item_id]=key
            for mapping in mappings:
                card=cards.get(mapping['knowledge_point_id'])
                if card and (mapping['role']=='primary' or mapping['question_id'] not in topics):topics[mapping['question_id']]=card['name']
            nodes={};edges=[];mistakes_by_code={}
            def node(item_id,name,kind,score,**extra):
                value={'id':item_id,'name':name,'category':kind,'value':score,**extra};nodes[item_id]=value;return value
            def connect(source,target,relation):
                if source in nodes and target in nodes:edges.append({'source':source,'target':target,'relation':relation})
            for row in db.query('SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at,id',[user['id']]).rows:
                item=row_json('mastery_states',row);row_subject=item['subject'];point=item['knowledge_point']
                if subject and row_subject!=subject:continue
                card=labels.get((row_subject,point))
                if subject and card is None:continue
                key=card['code'] if card else point
                node('knowledge:'+row_subject+':'+key,point,'knowledge',percent(item['mastery_score']),subject=row_subject,detail=learner_text(item.get('update_reason') or ''),confidence=item['confidence'])
            for row in db.query('SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id',[user['id']]).rows:
                item=row_json('misconception_states',row);row_subject=item['subject']
                if subject and row_subject!=subject:continue
                label=canonical_mistake(item['label']);item_id='misconception:'+row_subject+':'+label;mistakes_by_code[(row_subject,item['code'])]=item_id
                if item_id in nodes:continue
                node(item_id,label,'misconception',percent(item['probability']),subject=row_subject,status=item['status'],detail=f"已参考 {item['evidence_count']} 次学习记录；有效方法："+method_label(item.get('successful_strategy') or ''))
                strategies=set()
                for field in ['successful_strategy','failed_strategy']:
                    strategy=item.get(field) or ''
                    if not strategy or strategy in strategies:continue
                    strategies.add(strategy);strategy_id='strategy:'+strategy
                    node(strategy_id,method_label(strategy),'strategy',35,detail='学习过程中使用过的方法')
                    connect(item_id,strategy_id,'有效策略' if strategy==item.get('successful_strategy') else '待改进策略')
            for item_id,question in questions.items():
                topic=topics.get(item_id,graph_topic(question));title='相关错题' if topic in ['错题学习','其他题型'] else topic+'相关错题';text=question['question_text']
                node('question:'+item_id,title,'question',28,subject=question['subject'],detail=text if '$' in text or '\\' in text else short_title(text,120),question_id=item_id)
            for mapping in mappings:
                question_node='question:'+mapping['question_id'];card=cards.get(mapping['knowledge_point_id'])
                if question_node not in nodes or card is None:continue
                item_id='knowledge:'+card['subject']+':'+card['code']
                if item_id not in nodes:node(item_id,card['name'],'knowledge',45,subject=card['subject'],detail='由你的错题映射到共享知识点；依据：'+(mapping.get('evidence_text') or ''),confidence=mapping['confidence'])
                connect(question_node,item_id,'涉及知识点' if mapping['role']=='primary' else '需要先修')
            for update in updates:
                item_id=update.get('question_id') or '';question=questions.get(item_id)
                if question is None:continue
                row_subject=question['subject'];key=update['entity_key'];question_node='question:'+item_id
                if update['entity_type']=='mastery':
                    for target,value in nodes.items():
                        if value['category']=='knowledge' and value.get('subject')==row_subject and value['name']==key:connect(question_node,target,'提供掌握证据');break
                elif update['entity_type']=='misconception':
                    target=mistakes_by_code.get((row_subject,key))
                    if target:connect(question_node,target,'暴露错因')
            for row in db.query('SELECT * FROM knowledge_relations ORDER BY id').rows:
                source,target=cards.get(row['source_id']),cards.get(row['target_id'])
                if source and target:connect('knowledge:'+source['subject']+':'+source['code'],'knowledge:'+target['subject']+':'+target['code'],row['relation_type'])
            visible=[]
            for kind,limit in [('knowledge',8),('question',4),('misconception',2),('strategy',2)]:
                visible.extend(sorted((n for n in nodes.values() if n['category']==kind),key=lambda n:(-n['value'],n['name']))[:limit])
            ids={n['id'] for n in visible}
            return {'nodes':visible,'links':[e for e in edges if e['source'] in ids and e['target'] in ids],'categories':['knowledge','misconception','question','strategy'],'filters':{'subject':subject if 'subject' in request.query_params else None,'days':days},'evidence_count':len(updates),'personal_mapping_count':len(mappings),'mapped_question_count':len(mapped_questions)}
