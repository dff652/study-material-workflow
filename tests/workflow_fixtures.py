"""Anonymous synthetic batches used to verify integration contracts."""
import copy
from pathlib import Path
import sys
from PIL import Image, ImageDraw
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/study-material-workflow/scripts'
sys.path.insert(0,str(SCRIPTS))
from workflow_common import read_json,write_json,canonical,digest
from collect_sources import collect_sources
from adapt_catalog import adapt_catalog


def fixture(root):
    root=Path(root);source=root/'sources';source.mkdir(parents=True)
    for number,text in [(1,'1. Calculate 1/2 + 1/6.'),(2,'2. Triangle: base 6, height 4.')]:
        image=Image.new('RGB',(640,320),'white');draw=ImageDraw.Draw(image);draw.text((30,30),text,fill='black');image.save(source/f'page{number}.png')
    selection={'batch_id':'anonymous-heldout-v1','files':[{'path':f'page{n}.png','book':'J1','token':f'{n:06d}','page_order':n} for n in [1,2]],'expected_counts':{'sources':2,'parent_questions':2,'entries':2}}
    rows=[{'book':'J1','num':str(n),'group':1,'photo':f'{n:06d}','feature':'anonymous problem summary','method':'draft method','tag':'pending','tip':'preserve unknowns','aux':''} for n in [1,2]]
    profile=read_json(SCRIPTS.parent/'references/calculation-profile.json')
    sources=collect_sources(source,selection);catalog=adapt_catalog(rows,sources,profile)
    packet=copy.deepcopy(read_json(SCRIPTS.parent/'assets/example-packet.json'))
    packet['batch_id']=selection['batch_id'];packet['sources_sha256']=digest(canonical(sources));packet['catalog_sha256']=digest(canonical(catalog))
    for document in packet['documents']:document['source'].update(source_id=packet['batch_id'],sha256=packet['catalog_sha256'])
    for name,value in [('selection',selection),('raw',rows),('profile',profile),('sources',sources),('catalog',catalog),('packet',packet)]:write_json(root/(name+'.json'),value)
    return {'root':root,'source_root':source,'sources':sources,'catalog':catalog,'packet':packet,'profile':profile}


def review(packet,recipe):
    from packet import packet_digest
    return {'packet_sha256':packet_digest(packet),'recipe_sha256':recipe,
            **{key:{'status':'pass','reviewer':'synthetic-test-reviewer','notes':'Synthetic fixture gate; not a real learner assessment.'} for key in ['content','math','independent','pdf_visual']},
            'word_client':{'status':'not_tested','reviewer':None,'notes':'No Word client is invoked by these integration tests.'}}
