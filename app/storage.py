import json
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from app.config import PROMOTIONS_DIR, RUNS_DIR, TESTS_DIR
from app.models import PromotionCandidate, RunTrace, TestCase

T = TypeVar("T", bound=BaseModel)


def _save(obj: BaseModel, directory: Path, id_value: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{id_value}.json"
    path.write_text(obj.model_dump_json(indent=2))


def _load(directory: Path, id_value: str, model: Type[T]) -> Optional[T]:
    path = directory / f"{id_value}.json"
    if not path.exists():
        return None
    return model.model_validate_json(path.read_text())


def _list(directory: Path, model: Type[T]) -> list[T]:
    directory.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(directory.glob("*.json")):
        items.append(model.model_validate_json(path.read_text()))
    return items


# --- TestCase ---

def save_test(test: TestCase) -> None:
    _save(test, TESTS_DIR, test.test_id)


def load_test(test_id: str) -> Optional[TestCase]:
    return _load(TESTS_DIR, test_id, TestCase)


def list_tests() -> list[TestCase]:
    return sorted(_list(TESTS_DIR, TestCase), key=lambda t: t.created_at, reverse=True)


# --- RunTrace ---

def save_run(run: RunTrace) -> None:
    _save(run, RUNS_DIR, run.run_id)


def load_run(run_id: str) -> Optional[RunTrace]:
    return _load(RUNS_DIR, run_id, RunTrace)


def list_runs(test_id: Optional[str] = None) -> list[RunTrace]:
    runs = sorted(_list(RUNS_DIR, RunTrace), key=lambda r: r.started_at, reverse=True)
    if test_id:
        runs = [r for r in runs if r.test_id == test_id]
    return runs


# --- PromotionCandidate ---

def save_promotion(promo: PromotionCandidate) -> None:
    _save(promo, PROMOTIONS_DIR, promo.promotion_id)


def load_promotion(promotion_id: str) -> Optional[PromotionCandidate]:
    return _load(PROMOTIONS_DIR, promotion_id, PromotionCandidate)


def list_promotions(run_id: Optional[str] = None) -> list[PromotionCandidate]:
    promos = sorted(_list(PROMOTIONS_DIR, PromotionCandidate), key=lambda p: p.created_at, reverse=True)
    if run_id:
        promos = [p for p in promos if p.run_id == run_id]
    return promos
