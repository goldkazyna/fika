from typing import Any
import datetime
import httpx
from dateutil import tz
from src.bot.logging_ import logger
from src.config import settings


class TowecoRepository:
    BASE_URL = "https://api-v4.toweco.ru/"

    def __init__(self, username: str, password: str):
        self.client = httpx.AsyncClient(headers={"Content-Type": "application/json"})
        self.username = username
        self.password = password
        self.auth_was_called = False

    async def auth(self) -> None:
        url = f"{self.BASE_URL}api/v1/auth/getToken"
        payload = {"id": 1, "jsonrpc": "2.0", "params": {"username": self.username, "password": self.password}}
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        access_token = data["result"]["accessToken"]
        self.client.headers.update({"Authorization": f"Bearer {access_token}"})
        self.auth_was_called = True

    async def get_reviews(
        self,
        page: int | None = None,
        places: list[int] | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> list[dict]:
        params = {}
        if page is not None:
            params["page"] = page
        if places is not None:
            params["places"] = places
        if date_from is not None:
            params["dateFrom"] = date_from.strftime("%d.%m.%Y")
        if date_to is not None:
            params["dateTo"] = date_to.strftime("%d.%m.%Y")

        payload = [{"id": 0, "jsonrpc": "2.0", "method": "private.getReviews", "params": params}]
        result = await self.apply(self.BASE_URL, payload)
        reviews = result["reviews"]["reviews"]
        # filter out test reviews
        return [review for review in reviews if review["author"] not in ("Test", "0", "NEW TEST")]

    async def apply(self, url: str, payload: Any) -> dict:
        if not self.auth_was_called:
            await self.auth()

        response = await self.client.post(url, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(e)
            if e.response.status_code == 401:
                await self.auth()
                response = await self.client.post(url, json=payload)
                response.raise_for_status()

        as_python = response.json()[0]
        if "error" in as_python:
            logger.warning(f"Error in response from Toweco API: {as_python}")
            if as_python["error"] == "unauthorized" or as_python["error"] == "unauthorized":
                await self.auth()
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                as_python = response.json()[0]
                logger.info(as_python)

                if "result" in as_python:
                    return as_python["result"]
            raise RuntimeError(as_python)
        else:
            logger.info(as_python)
            return as_python["result"]

    async def get_locations(self, places: list[int] | None = None) -> dict:
        payload = [{"id": 0, "jsonrpc": "2.0", "method": "private.getLocations", "params": {"places": places}}]
        return await self.apply(self.BASE_URL, payload)

    async def close(self) -> None:
        await self.client.aclose()

    def format_review(self, review: dict) -> str:
        """
        Format review for passing to llm

        Input:
        {
          "publishedAt": "2024-12-12T03:13:34Z",
          "provider": "2ГИС",
          "location": "Fika",
          "address": "Казахстан, г Алматы, Алмалинский р-н, ул Кабанбай Батыра, д 104",
          "locationURL": "https://2gis.ru/firm/70000001081672623",
          "review": "Вкусная кухня ,очень вежливый персонал,особенно Бибигуль))",
          "reviewURL": "https://2gis.ru/search/%D0%9F%D0%BE%D0%B5%D1%81%D1%82%D1%8C/firm/70000001081672623/mediaTab/reviews",
          "answer": "",
          "answerURL": "",
          "author": "Bekbolat Urbaev",
          "authorURL": "",
          "rating": 5
        }

        Output:
        ★★★★★ (5/5)
        2ГИС, 12/12/2024 06:13
        Автор: Bekbolat Urbaev

        Вкусная кухня ,очень вежливый персонал,особенно Бибигуль))
        """
        if "rating" in review:
            stars = "★" * review["rating"] + "☆" * (5 - review["rating"])
        else:
            stars = ""

        published_at_utc = datetime.datetime.fromisoformat(review["publishedAt"])
        published_at_almaty = published_at_utc.astimezone(tz.gettz("Asia / Almaty"))
        published_at = published_at_almaty.strftime("%d/%m/%Y %H:%M")
        author = review["author"]
        provider = review["provider"]
        review = review["review"]

        return f"{stars}\n{provider}, {published_at}\nАвтор: {author}\n{review}".strip()


toweco_repository = TowecoRepository(settings.toweco_username, settings.toweco_password.get_secret_value())
