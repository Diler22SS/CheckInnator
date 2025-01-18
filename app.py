"OUR PROJECT"
import requests
from flask import Flask, request, jsonify
from experta import Fact, KnowledgeEngine, Rule, Field, MATCH


API_KEY = 'eabc2a42-d883-4a6d-ac0d-0e372b5f707e'
BASE_URL = "https://catalog.api.2gis.com/3.0/items"
FIELDS = "items.address,items.reviews"


# Определение фактов
class CityFact(Fact):
    """Факт о городе для поиска отелей."""
    city = Field(str, mandatory=True)
    sort_type = Field(str, mandatory=True)


class HotelAPIFact(Fact):
    """Факт об отелях из API 2ГИС."""
    name = Field(str, mandatory=True)
    rating = Field(float, mandatory=True)
    address = Field(str, mandatory=True)


class UserPreferencesFact(Fact):
    """Факт о предпочтениях пользователя."""
    preferred_rating = Field(float, default=4.0)  # Предпочитаемый рейтинг


# Определение движка знаний
class HotelBookingEngine(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.search_results = []  # Для хранения найденных отелей

    def fetch_hotels_from_api(self, city, sort_type="relevance"):
        """Получение отелей из API 2ГИС с учетом сортировки."""
        print(f"Ищем отели в городе {city}")

        # Запрос на получение ID города
        city_response = requests.get(f"{BASE_URL}?q={city}&key={API_KEY}")
        city_data = city_response.json()
        if not city_data['result'].get('items'):
            print(f"Город {city} не найден.")
            return

        city_id = city_data['result']['items'][0]['id']
        print(f"ID города {city}: {city_id}")

        hotels = []
        for page in range(1, 6):
            response = requests.get(
                f"{BASE_URL}?q=отели&fields={FIELDS}&city_id={city_id}&sort={sort_type}&page={page}&key={API_KEY}"
            )
            if response.status_code == 200:
                hotels.extend(response.json().get('result', {}).get('items', []))
            else:
                print(f"Ошибка API: {response.status_code}")
                return hotels
        return hotels

    @Rule(CityFact(city=MATCH.city, sort_type=MATCH.sort_type))
    def search_hotels(self, city, sort_type):
        """Поиск отелей через API 2ГИС с учетом сортировки и фильтрации."""
        hotels = self.fetch_hotels_from_api(city, sort_type)
        if hotels:
            for hotel in hotels:
                fact = HotelAPIFact(
                    name=hotel.get('name'),
                    rating=float(hotel.get('reviews', {}).get('general_rating', 0.0)),
                    address=hotel.get('address_name', ""),
                )
                self.declare(fact)
                self.search_results.append(fact)
        else:
            self.search_results = []

    @Rule(UserPreferencesFact(preferred_rating=MATCH.preferred_rating))
    def filter_hotels_by_user_preferences(self, preferred_rating):
        """Фильтрация отелей на основе предпочтений пользователя."""
        print('preferred_rating work', preferred_rating)
        self.search_results = [
            hotel for hotel in self.search_results
            if hotel["rating"] >= preferred_rating
        ]
        print("self.search_results filter_hotels_by_user_preferences", self.search_results)

    @Rule(HotelAPIFact(name=MATCH.name, rating=MATCH.rating, address=MATCH.address))
    def display_hotel(self, name, rating, address):
        """Отображение отелей, подходящих под фильтры."""
        print(f"Отель: {name}")
        print(f"Рейтинг: {rating}")
        print(f"Адрес: {address}")
        print("-" * 40)


app = Flask(__name__)

@app.route("/search_hotels", methods=["GET"])
def search_hotels():
    """Поиск отелей с учетом предпочтений пользователя и сортировки."""
    data = request.json
    city = data.get("city")
    preferred_rating = data.get("preferred_rating", 4.0)
    sort_type = data.get("sort_type", "relevance")  # Можно передать тип сортировки, например, "rating" или "name"

    if not city:
        return jsonify({"error": "Город не указан"}), 400

    engine = HotelBookingEngine()
    engine.reset()
    engine.declare(CityFact(city=city, sort_type=sort_type))
    engine.run()
    engine.declare(UserPreferencesFact(preferred_rating=preferred_rating))
    engine.run()

    hotels = [{
        "name": hotel["name"],
        "rating": hotel["rating"],
        "address": hotel["address"],
    } for hotel in engine.search_results]

    return jsonify({"hotels": hotels})


if __name__ == "__main__":
    app.run(debug=True)
