"""Independent arithmetic and coordinate checks for the two diagnostic sets."""
from fractions import Fraction as F
import math
import unittest


def area(a,b,c):
    return abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2


def part(a,b,t):
    return tuple(x+t*(y-x) for x,y in zip(a,b))


class DiagnosticMathTests(unittest.TestCase):
    def test_eight_calculation_answers_by_direct_evaluation(self):
        values=[F(sum(10*k**3 for k in [2,5,8]),sum(12*k**3 for k in [2,5,8])),
                sum(k*(k+2) for k in range(4,17,2)),
                sum(F(1,k*(k+3)) for k in [4,7,10,13]),
                sum((-1)**(k+1)*F(2*k+1,k*(k+1)) for k in range(1,7)),
                4+3*(20-1),sum(F(1,sum(range(1,k+1))) for k in range(1,11)),
                sum(F(1,k*(k+1)*(k+2)) for k in range(3,9)),247**2-246*248]
        self.assertEqual(values,[F(5,6),952,F(1,16),F(6,7),61,F(20,11),F(13,360),1])

    def test_geometry_by_coordinates_and_lengths(self):
        A,B,C,D=(F(0),F(0)),(F(0),F(8)),(F(12),F(8)),(F(12),F(0))
        for P in [(F(3),F(5)),(F(10),F(2)),(F(1,3),F(4,7))]:self.assertEqual(area(A,B,P)+area(C,D,P),48)
        A,B,C=(F(0),F(10)),(F(12),F(0)),(F(0),F(0))
        self.assertEqual(area(A,part(A,B,F(2,5)),part(A,C,F(1,3))),8)
        A,B,C,D=(F(1),F(10)),(F(0),F(0)),(F(6),F(0)),(F(5),F(10));O=(F(3),F(6))
        self.assertEqual(area(B,O,C),18);self.assertEqual(area(A,B,C)+area(A,C,D),50)
        A,B,C=(F(0),F(8)),(F(0),F(0)),(F(15),F(0));D=part(B,C,F(2,5));O=part(A,D,F(2,3))
        self.assertEqual(area(A,B,O),16)
        A,B,C=(F(0),F(10)),(F(0),F(0)),(F(15),F(0))
        self.assertEqual(area(A,B,C)-area(A,part(A,B,F(2,5)),part(A,C,F(2,5))),63)
        leg=math.isqrt(13**2-5**2);self.assertEqual((leg,F(5*leg,2)),(12,30))
        side=math.isqrt(4*6+1);self.assertEqual(side**2,25);self.assertEqual(4*side,20)
        B,E,G=(F(0),F(0)),(F(4),F(0)),(F(3),F(2));self.assertEqual(area(B,E,G),4)


if __name__=='__main__':unittest.main()
