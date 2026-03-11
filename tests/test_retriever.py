# tests/test_retriever.py

from rag.schema import CallContext, CallState
from rag.retriever import (
    build_car_query,
    retrieve_cars,
    format_cars_for_llm,
    retrieve_car_context,
)

def test_build_query():
    ctx = CallContext(
        state=CallState.OPENING,
        brand="比亚迪",
        budget="15-20万"
    )

    query = build_car_query(ctx)
    print("=== QUERY ===")
    print(query)

    assert "比亚迪" in query
    assert "15-20万" in query


def test_retrieve_cars():
    ctx = CallContext(
        state=CallState.OPENING,
        brand="比亚迪",
        budget="15-20万"
    )

    cars = retrieve_cars(ctx, top_k=2)

    print("=== RETRIEVED CARS ===")
    for c in cars:
        print(c)

    assert len(cars) > 0


def test_format_for_llm():
    ctx = CallContext(
        state=CallState.OPENING,
        brand="比亚迪",
        budget="15-20万"
    )

    cars = retrieve_cars(ctx)
    text = format_cars_for_llm(cars)

    print("=== LLM CONTEXT ===")
    print(text)

    assert "车型" in text
    assert "价格" in text


def test_full_pipeline():
    ctx = CallContext(
        state=CallState.OPENING,
        brand="比亚迪",
        budget="15-20万"
    )

    context = retrieve_car_context(ctx)

    print("=== FINAL CONTEXT FOR LLM ===")
    print(context)

    assert context.strip() != ""


if __name__ == "__main__":
    test_build_query()
    test_retrieve_cars()
    test_format_for_llm()
    test_full_pipeline()
