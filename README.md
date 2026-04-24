command with docker:
* first build:
- docker build:
```
docker-compose up --build
```
------------------------------

start front-end (*note: install nodejs before start):
- bypass window powershell:
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
- install libs:
```
npm install
```
- run:
```
npm run dev
```

------------------------------

back-end hot-reloading for each:
example for all (auth-service):
- rebuild:
```
docker-compose up -d --no-deps --build auth-service
```
- restart:
```
docker-compose restart auth-service
```
