# REST API testing в Postman

Коллекция тестирует публичный учебный API [JSONPlaceholder](https://jsonplaceholder.typicode.com/).

Покрыты GET списка и ресурса, фильтрация, POST, запрос отсутствующего ресурса, HTTP-статусы, Content-Type, время ответа и структура JSON.

## Запуск

1. Импортировать `jsonplaceholder.postman_collection.json` в Postman.
2. Запустить коллекцию через Collection Runner.
3. Убедиться, что все тесты зелёные.

JSONPlaceholder — mock-сервис: POST возвращает объект, но не сохраняет его постоянно.

