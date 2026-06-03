"""Multi-source retrievers for academic papers."""
from .openalex   import OpenAlexSource
from .pubmed     import PubMedSource
from .semantic   import SemanticScholarSource

__all__ = ['OpenAlexSource', 'PubMedSource', 'SemanticScholarSource']
