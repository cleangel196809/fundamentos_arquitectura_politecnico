"""Lista, instancias sanas y round-robin."""


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_lista_sin_consul(cliente):
    assert cliente.get("/v1/servicios").json() == ["catalogo-service", "pedidos-service"]


def test_instancias_sanas(cliente):
    assert len(cliente.get("/v1/servicios/catalogo-service/instancias").json()) == 3


def test_round_robin_reparte(cliente):
    elegidas = [cliente.get("/v1/servicios/catalogo-service/resolver").json()["instancia"] for _ in range(6)]
    assert elegidas == ["cat-1", "cat-2", "cat-3", "cat-1", "cat-2", "cat-3"]


def test_sin_instancias_503(cliente):
    assert cliente.get("/v1/servicios/pedidos-service/resolver").status_code == 503
