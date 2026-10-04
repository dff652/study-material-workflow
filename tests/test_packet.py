import copy
import sys
import unittest
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/study-material-workflow/scripts'
sys.path.insert(0,str(SCRIPTS))
from workflow_common import WorkflowError,canonical,digest
from packet import validate_packet,validate_review,packet_digest
from exact_math import calculate


def example():
    import json
    return json.loads((SCRIPTS.parent/'assets/example-packet.json').read_text())


class PacketTests(unittest.TestCase):
    def test_five_purposes_and_unknown_evidence(self):
        packet=example();self.assertEqual(len(validate_packet(packet)),5)
        packet['documents'].pop();packet['omitted_purposes']=['parent_answers'];self.assertEqual(len(validate_packet(packet)),4)

    def test_hint_role_rejected(self):
        packet=example();packet['documents'][3]['pages'][0][1]['role']='answer'
        with self.assertRaises(WorkflowError) as caught:validate_packet(packet)
        self.assertEqual(caught.exception.code,'independent_hint')

    def test_false_accepted_state_rejected(self):
        packet=example();packet['documents'][0]['source'].update(state='accepted',revision_id='revision-1')
        with self.assertRaises(WorkflowError):validate_packet(packet)

    def test_missing_purpose_rejected(self):
        packet=example();packet['documents'].pop()
        with self.assertRaises(WorkflowError):validate_packet(packet)

    def test_mutated_inputs_invalidate(self):
        packet=example();sources={'batch_id':packet['batch_id']}
        with self.assertRaises(WorkflowError):validate_packet(packet,sources)

    def test_review_recipe_and_person(self):
        packet=example();review={'packet_sha256':packet_digest(packet),'recipe_sha256':'a'*64}
        for name in ['content','math','independent','pdf_visual','word_client']:
            review[name]={'status':'pass','reviewer':'test-reviewer','notes':'synthetic test'}
        validate_review(review,packet,recipe_sha256='a'*64,require_verified=True)
        with self.assertRaises(WorkflowError):validate_review(review,packet,recipe_sha256='b'*64,require_verified=True)
        review['math']['reviewer']=''
        with self.assertRaises(WorkflowError):validate_review(review,packet)

    def test_changed_packet_invalidates_review(self):
        packet=example();review={'packet_sha256':packet_digest(packet)}
        packet['documents'][0]['pages'][0][1]['content']='Changed input'
        with self.assertRaises(WorkflowError):validate_review(review,packet)

    def test_exact_rational_and_attack(self):
        self.assertEqual(str(calculate('1/2+1/6')),'2/3')
        for expression in ['1/0','__import__("os").system("echo x")','2**100000','True+1','0.5']:
            with self.subTest(expression=expression),self.assertRaises(WorkflowError):calculate(expression)

    def test_nonunit_integer_and_fraction_identity(self):
        from fractions import Fraction
        for a in [1,2,5]:
            for d in [1,2,3]:
                for m in range(1,7):
                    x=a+(m-1)*d
                    total=sum((a+k*d)*(a+(k+1)*d) for k in range(m))
                    self.assertEqual(total,Fraction(x*(x+d)*(x+2*d)-(a-d)*a*(a+d),3*d))
                self.assertEqual(Fraction(1,a*(a+d)*(a+2*d)),(Fraction(1,a*(a+d))-Fraction(1,(a+d)*(a+2*d)))/(2*d))


if __name__=='__main__':unittest.main()
