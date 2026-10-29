"""Hand-worked check of the two metrics (run: pytest test_metrics.py -v).

Worked by hand first. Question with gold sections {A::s1, B::s2}.
Ranking returned (best first):
  1 C::x   2 C::y   3 A::s1 (chunk 0)   4 A::s1 (chunk 1)   5 D::z   6 B::s2
rank_of_first_gold = 3        (first chunk whose (doc, section) is gold)
recall_at_5 over SECTIONS: top 5 hold A::s1 twice but it counts once, B::s2 is
  at rank 6, so 1 of 2 gold sections = 0.5   (a per-chunk count would say 2/2)
A ranking with no gold chunk at all: rank None, recall 0.0 (not rank 'infinity').
"""
from dataclasses import dataclass

from metrics import rank_of_first_gold, recall_at_k


@dataclass
class C:
    doc_id: str
    section: str
    chunk_id: str = ""


@dataclass
class Q:
    gold_sections: tuple


Q1 = Q(("A::s1", "B::s2"))
RANKED = [C("C", "x"), C("C", "y"), C("A", "s1"), C("A", "s1"), C("D", "z"),
          C("B", "s2")]


def test_rank_is_three():
    assert rank_of_first_gold(RANKED, Q1) == 3


def test_recall_counts_sections_not_chunks():
    assert recall_at_k(RANKED, Q1, k=5) == 0.5
    assert recall_at_k(RANKED, Q1, k=6) == 1.0


def test_no_gold_anywhere_is_none_not_a_number():
    assert rank_of_first_gold([C("C", "x")], Q1) is None
    assert recall_at_k([C("C", "x")], Q1, k=5) == 0.0
