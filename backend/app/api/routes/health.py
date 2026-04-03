from fastapi import APIRouter

router = APIRouter()


@router.get("", summary="Health check")
def read_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/test", summary="test for health check")
def test_health() -> dict[str, str]:
    return {"status": "not ok.sssss"}
