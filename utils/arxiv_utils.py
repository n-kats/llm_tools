from functools import cached_property
import time
from typing import Dict, Sequence, TypeVar, Generic, Callable, Optional, List
from datetime import datetime
from pathlib import Path
import yaml
from pydantic import BaseModel
import arxiv

T = TypeVar("T")


class Category(BaseModel):
    category_id: str
    short_description: str
    description: str


class DictDB(Generic[T]):
    def __init__(self, key_fn: Callable[[T], str]):
        self.__key_to_item: Dict[str, T] = {}
        self.__key_fn = key_fn

    def update(self, items: Sequence[T]):
        for item in items:
            self.__key_to_item[self.__key_fn(item)] = item

    @property
    def key_to_item(self) -> Dict[str, T]:
        return self.__key_to_item


def _load_categories(path: Path):
    with open(path) as f_in:
        return [Category(**category) for category in yaml.safe_load(f_in)]


default_category_db = DictDB[Category](
    key_fn=lambda category: category.category_id)
DEFAULT_CATEGORY_FILE = Path(__file__).parent / "arxiv_categories.yml"
default_category_db.update(_load_categories(DEFAULT_CATEGORY_FILE))


class ArXivAbstractDB:
    pass


class ArxivAuthor(BaseModel):
    name: str

    @classmethod
    def from_arxiv(cls, author: arxiv.Result.Author):
        return cls(name=author.name)


class ArxivLink(BaseModel):
    content_type: Optional[str]
    title: Optional[str]
    href: str
    rel: Optional[str]

    @classmethod
    def from_arxiv(cls, link: arxiv.Result.Link):
        return cls(
            content_type=link.content_type,
            title=link.title,
            href=link.href,
            rel=link.rel,
        )


class ArxivSummary(BaseModel):
    authors: List[ArxivAuthor]
    categories: List[str]
    comment: Optional[str]
    doi: Optional[str]
    entry_id: str
    journal_ref: Optional[str]
    links: List[ArxivLink]
    primary_category: str
    published: datetime
    summary: str
    title: str
    updated: datetime

    @classmethod
    def from_arxiv(cls, result: arxiv.Result):
        return cls(
            authors=[ArxivAuthor.from_arxiv(author)
                     for author in result.authors],
            categories=result.categories,
            comment=result.comment,
            doi=result.doi,
            entry_id=result.entry_id,
            journal_ref=result.journal_ref,
            links=[ArxivLink.from_arxiv(link) for link in result.links],
            primary_category=result.primary_category,
            published=result.published,
            summary=result.summary,
            title=result.title,
            updated=result.updated,
        )

    @cached_property
    def short_id(self):
        return self.entry_id.split("/")[-1]


class ArxivRetriver:
    def __init__(self, max_count_per_request: int, interval_sec: float, stop_condition: Optional[Callable[[ArxivSummary], bool]] = None,):
        self.__max_count_per_request = max_count_per_request
        self.__interval_sec = interval_sec
        self.__stop_condition = stop_condition

    def iter_per_category(self, category: str):
        for result in arxiv.Client(
                page_size=self.__max_count_per_request,
                delay_seconds=self.__interval_sec).results(
                arxiv.Search(query=f"cat:{category}",
                             sort_by=arxiv.SortCriterion.LastUpdatedDate,
                             sort_order=arxiv.SortOrder.Descending)):
            result = ArxivSummary.from_arxiv(result)
            if self.__stop_condition is not None and self.__stop_condition(result):
                break
            yield result


class UpdateTimeStopCondition:
    def __init__(self, limit: datetime):
        self.__limit = limit

    def __call__(self, summary: ArxivSummary):
        return summary.updated <= self.__limit

    @classmethod
    def from_datefile(cls, path: Path):
        with open(path) as f_in:
            limit = datetime.fromisoformat(f_in.read().strip())
        return cls(limit)

    def save_datefile(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f_out:
            print(self.__limit.isoformat(), file=f_out)


def to_arxiv_id(url):
    id_ = [x for x in url.split("/") if x != ""][-1]
    if id_.endswith(".pdf"):
        id_ = id_[:-4]
    return id_

def from_arxiv_url(url: str) -> ArxivSummary:
    url = to_arxiv_id(url)
    search = arxiv.Search(id_list=[url])
    results = list(search.results())
    if not results:
        raise ValueError(f"arxiv id {url} is not found.")
    if len(results) > 1:
        raise ValueError(f"arxiv id {url} is not unique.")
    return ArxivSummary.from_arxiv(results[0])
