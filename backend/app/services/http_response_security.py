from fastapi import Response


_NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def no_store_response_headers() -> dict[str, str]:
    return dict(_NO_STORE_HEADERS)


def apply_no_store_headers(response: Response) -> None:
    response.headers.update(_NO_STORE_HEADERS)
