"OUR PROJECT"
import os
import json
import requests
import uuid
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


class BookingFact(Fact):
    """Факт о бронировании."""
    id_user = Field(str, mandatory=True)
    name = Field(str, mandatory=True)
    city = Field(str, mandatory=True)
    check_in_date = Field(str, mandatory=True)
    check_out_date = Field(str, mandatory=True)
    n_guests = Field(int, mandatory=True)


class ReadBookingsFact(Fact):
    """Факт о выводе бронирований."""
    id_user = Field(str, mandatory=True)


class DeleteBookingFact(Fact):
    """Факт об удалении бронирования."""
    id = Field(str, mandatory=True)


# Определение движка знаний
class HotelBookingEngine(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.search_results = []  # Для хранения найденных отелей
        self.user_bookings = []

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

    @Rule(BookingFact(id_user=MATCH.id_user, name=MATCH.name, city=MATCH.city, check_in_date=MATCH.check_in_date,
                      check_out_date=MATCH.check_out_date, n_guests=MATCH.n_guests))
    def save_booking(self, id_user, name, city, check_in_date, check_out_date, n_guests):
        """Сохраняем бронирование в файл."""
        # Путь к файлу JSON
        file_name = "bookings.json"

        # Структура данных для сохранения
        booking_data = {
            "id": str(uuid.uuid4()),
            "id_user": id_user,
            "name": name,
            "city": city,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "n_guests": n_guests
        }

        # Читаем существующий файл, если он есть
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        # Добавляем новое бронирование
        data.append(booking_data)

        # Сохраняем обновлённые данные в файл
        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

        print(f"Бронирование сохранено: {booking_data}")

    @Rule(ReadBookingsFact(id_user=MATCH.id_user))
    def read_bookings(self, id_user):
        """Вывод бронирований из файла."""
        # Путь к файлу JSON
        file_name = "bookings.json"

        # Проверяем существование файла
        if not os.path.exists(file_name):
            print("Файл с бронированиями не найден.")
            return []

        # Читаем данные из файла
        with open(file_name, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                print("Ошибка чтения файла: поврежденный JSON.")
                return []

        # Фильтруем бронирования по id_user
        self.user_bookings = [booking for booking in data if booking.get("id_user") == id_user]

        # Проверяем наличие записей
        if not self.user_bookings:
            print(f"Бронирования для пользователя с ID {id_user} не найдены.")
        else:
            print(f"Бронирования для пользователя с ID {id_user}:")
            for booking in self.user_bookings:
                print(booking)

    @Rule(DeleteBookingFact(id=MATCH.id))
    def delete_booking(self, id):
        """Удаление бронирования из файла."""
        filename = "bookings.json"

        # Проверяем существование файла
        if not os.path.exists(filename):
            print("Файл бронирований не найден.")
            return False

        # Загружаем данные из файла
        with open(filename, "r", encoding="utf-8") as file:
            try:
                bookings = json.load(file)
            except json.JSONDecodeError:
                print("Файл пустой или содержит некорректные данные.")
                return False

        # Проверяем, есть ли запись с указанным ID
        booking_exists = any(booking["id"] == id for booking in bookings)
        if not booking_exists:
            print(f"Бронирование с ID {id} не найдено.")
            return False

        # Удаляем запись
        updated_bookings = [booking for booking in bookings if booking["id"] != id]

        # Сохраняем обновленные данные обратно в файл
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(updated_bookings, file, ensure_ascii=False, indent=4)

        print(f"Бронирование с ID {id} успешно удалено.")
        return True


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


@app.route("/book_hotel", methods=["POST"])
def book_hotel():
    """Бронирование отеля."""
    data = request.json
    id_user = data.get("id_user")
    city = data.get("city")
    name = data.get("name")
    check_in_date = data.get("check_in_date")
    check_out_date = data.get("check_out_date")
    n_guests = data.get("n_guests")

    if not id_user:
        return jsonify({"error": "Пользователь не указан"}), 400

    engine = HotelBookingEngine()
    engine.reset()
    engine.declare(BookingFact(id_user=id_user, name=name, city=city, check_in_date=check_in_date, check_out_date=check_out_date, n_guests=n_guests))
    engine.run()

    return jsonify({"message": "Create Booking Ok"})


@app.route("/read_hotel_bookings", methods=["GET"])
def read_hotel_bookings():
    """Вывод бронирований отелей."""
    data = request.json
    id_user = data.get("id_user")

    if not id_user:
        return jsonify({"error": "Пользователь не указан"}), 400

    engine = HotelBookingEngine()
    engine.reset()
    engine.declare(ReadBookingsFact(id_user=id_user))
    engine.run()

    return jsonify(engine.user_bookings)


@app.route("/delete_hotel_booking", methods=["POST"])
def delete_hotel_booking():
    """Удаление бронирования."""
    data = request.json
    id = data.get("id")

    if not id:
        return jsonify({"error": "Пользователь не указан"}), 400

    engine = HotelBookingEngine()
    engine.reset()
    engine.declare(DeleteBookingFact(id=id))
    engine.run()

    return jsonify({"message": "Delete Booking Ok"})


if __name__ == "__main__":
    app.run(debug=True)
