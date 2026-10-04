"""Compare recorded outputs with frozen truth; no model invocation or guessed bill."""
from workflow_common import WorkflowArgumentParser
import argparse
from decimal import Decimal,InvalidOperation
from workflow_common import read_json,write_json,canonical,digest,fail,cli_result


def compare(truth,predictions,usage=None):
    for dataset in [truth,predictions]:
        if not isinstance(dataset,list) or len(dataset)>10000:fail('invalid_benchmark','Expected bounded record arrays')
        if any(not isinstance(row,dict) or set(row)!={'id','task','fields'} or not isinstance(row['id'],str) or
               not isinstance(row['task'],str) or not isinstance(row['fields'],dict) for row in dataset):
            fail('invalid_benchmark','Records need id, task and fields')
        if len({(row['task'],row['id']) for row in dataset})!=len(dataset):fail('duplicate_record','Task/id must be unique')
    actual={(row['task'],row['id']):row['fields'] for row in predictions};metrics={};mismatches=[]
    expected_keys=set()
    for row in truth:
        key=(row['task'],row['id']);expected_keys.add(key)
        task=metrics.setdefault(row['task'],{'records':0,'missing_records':0,'fields':0,'matched_fields':0,'unknowns_preserved':0,'unknowns_invented':0})
        task['records']+=1;observed=actual.get(key)
        if observed is None:task['missing_records']+=1
        for field,value in row['fields'].items():
            task['fields']+=1
            matched=observed is not None and field in observed and canonical(observed[field])==canonical(value)
            if matched:task['matched_fields']+=1
            else:mismatches.append({'id':row['id'],'task':row['task'],'field':field,'reason':'missing_or_different'})
            if value is None or value=='unknown':
                if matched:task['unknowns_preserved']+=1
                elif observed is not None and field in observed and observed[field] is not None and observed[field]!='unknown':task['unknowns_invented']+=1
        if observed is not None:
            for field in set(observed)-set(row['fields']):mismatches.append({'id':row['id'],'task':row['task'],'field':field,'reason':'unexpected_field'})
    result={'schema_version':'swf.benchmark.v1','truth_sha256':digest(canonical(truth)),'predictions_sha256':digest(canonical(predictions)),
            'metrics':metrics,'mismatches':mismatches,'extra_records':[{'task':task,'id':id_} for task,id_ in sorted(set(actual)-expected_keys)],
            'real_model':'not_tested','actual_cost_usd':None,'usage':None}
    if usage is not None:
        required={'provider','model','request_ids','scope_sha256','input_tokens','output_tokens','actual_cost_usd','evidence_kind'}
        if not isinstance(usage,dict) or set(usage)!=required:fail('invalid_usage','Usage needs explicit evidence, scope and cost')
        if any(type(usage[k]) is not str or not usage[k].strip() for k in ['provider','model','scope_sha256','evidence_kind']):fail('invalid_usage','Provider, model, scope and evidence kind must be explicit text')
        if any(type(usage[k]) is not int or usage[k]<0 for k in ['input_tokens','output_tokens']):fail('invalid_usage','Token values must be nonnegative integers')
        if not isinstance(usage['request_ids'],list) or any(not isinstance(v,str) or not v for v in usage['request_ids']):fail('invalid_usage','Request IDs must be explicit')
        if usage['actual_cost_usd'] is not None:
            try:cost=Decimal(str(usage['actual_cost_usd']))
            except InvalidOperation:fail('invalid_usage','Invalid observed cost')
            if not cost.is_finite() or cost<0:fail('invalid_usage','Observed cost must be finite and nonnegative')
        if (usage['evidence_kind']=='real_provider_record' and usage['provider'] and usage['model'] and usage['request_ids'] and
            isinstance(usage['scope_sha256'],str) and len(usage['scope_sha256'])==64 and all(c in '0123456789abcdef' for c in usage['scope_sha256'])):
            result['real_model']='record_supplied_not_independently_verified'
        result['usage']=usage;result['actual_cost_usd']=usage['actual_cost_usd']
    return result


def main():
    parser=WorkflowArgumentParser(description=__doc__)
    for name in ['truth','predictions','output']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--usage');args=parser.parse_args()
    report=compare(read_json(args.truth),read_json(args.predictions),read_json(args.usage) if args.usage else None)
    write_json(args.output,report);return {'output':args.output,'real_model':report['real_model'],'mismatches':len(report['mismatches'])}


if __name__=='__main__':raise SystemExit(cli_result(main))
