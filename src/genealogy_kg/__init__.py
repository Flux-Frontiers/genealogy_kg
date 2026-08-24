"""genealogy_kg -- KGModule for genealogical knowledge graphs built from GEDCOM files.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from genealogy_kg.extractor import GedcomExtractor
from genealogy_kg.module import GenealogyKG

__all__ = ["GenealogyKG", "GedcomExtractor"]
__version__ = "0.1.0"
