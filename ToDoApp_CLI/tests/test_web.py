"""Flask 웹 화면 테스트."""
from __future__ import annotations

import pytest

from todoapp.database import connect, initialize
from todoapp.service import TodoService
from todoapp.web import create_app

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def app(db_path):
    return create_app(db_path=db_path, secret_key="테스트용키", today=lambda: FIXED_TODAY)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeder(db_path):
    """테스트에서 직접 데이터를 넣기 위한 서비스. 앱과 별도 커넥션을 쓴다."""
    conn = connect(db_path)
    initialize(conn)
    yield TodoService(conn, today=lambda: FIXED_TODAY)
    conn.close()


class TestSecretKey:
    def test_비밀키가_없으면_앱_생성이_실패한다(self, db_path, monkeypatch):
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            create_app(db_path=db_path)

    def test_환경변수에서_비밀키를_읽는다(self, db_path, monkeypatch):
        monkeypatch.setenv("FLASK_SECRET_KEY", "환경변수키")
        app = create_app(db_path=db_path)
        assert app.secret_key == "환경변수키"

    def test_비밀키가_코드에_하드코딩되어_있지_않다(self):
        import pathlib

        source = pathlib.Path("todoapp/config.py").read_text(encoding="utf-8")
        assert "FLASK_SECRET_KEY" in source
        # os.getenv로만 읽어야 한다 (기본값 대입 금지)
        assert 'os.getenv("FLASK_SECRET_KEY", "")' in source


class TestIndex:
    def test_빈_목록도_200이다(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "할 일이 없습니다" in response.get_data(as_text=True)

    def test_할_일이_화면에_나온다(self, client, seeder):
        seeder.add("장보기", due="2026-09-10", tags="집안일")
        body = client.get("/").get_data(as_text=True)
        assert "장보기" in body
        assert "2026-09-10" in body
        assert "집안일" in body

    def test_범위_필터가_동작한다(self, client, seeder):
        seeder.add("지난 것", due="2026-09-01")
        seeder.add("미래 것", due="2026-09-30")
        body = client.get("/?scope=overdue").get_data(as_text=True)
        assert "지난 것" in body and "미래 것" not in body

    def test_태그_필터가_동작한다(self, client, seeder):
        seeder.add("공부하기", tags="공부")
        seeder.add("청소하기", tags="집안일")
        body = client.get("/?tag=공부").get_data(as_text=True)
        assert "공부하기" in body and "청소하기" not in body

    def test_검색이_동작한다(self, client, seeder):
        seeder.add("장보기")
        seeder.add("청소하기")
        body = client.get("/?q=장보").get_data(as_text=True)
        assert "장보기" in body and "청소하기" not in body

    def test_알_수_없는_범위는_400이다(self, client):
        assert client.get("/?scope=이상한값").status_code == 400

    def test_요약_숫자가_나온다(self, client, seeder):
        seeder.add("할 일", due="2026-09-01")
        assert "미완료" in client.get("/").get_data(as_text=True)

    def test_기한_지난_항목에_표시가_붙는다(self, client, seeder):
        seeder.add("지난 것", due="2026-09-01")
        assert "overdue" in client.get("/").get_data(as_text=True)

    def test_HTML이_이스케이프된다(self, client, seeder):
        seeder.add("<script>alert(1)</script>")
        body = client.get("/").get_data(as_text=True)
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body


class TestCreate:
    def test_추가하면_리다이렉트한다(self, client, seeder):
        response = client.post("/todos", data={"title": "장보기"})
        assert response.status_code == 302
        assert [t.title for t in seeder.list()] == ["장보기"]

    def test_모든_필드를_받는다(self, client, seeder):
        client.post(
            "/todos",
            data={
                "title": "장보기",
                "due_date": "2026-09-10",
                "tags": "집안일,장보기",
                "priority": "1",
                "notes": "우유",
            },
        )
        todo = seeder.list()[0]
        assert todo.due_date == "2026-09-10"
        assert todo.notes == "우유"
        assert {t.name for t in todo.tags} == {"집안일", "장보기"}

    def test_빈_제목은_안내_메시지와_함께_돌아온다(self, client, seeder):
        response = client.post("/todos", data={"title": "   "}, follow_redirects=True)
        assert response.status_code == 200
        assert "제목을 입력하세요" in response.get_data(as_text=True)
        assert seeder.list() == []

    def test_잘못된_날짜는_저장되지_않는다(self, client, seeder):
        response = client.post(
            "/todos",
            data={"title": "장보기", "due_date": "2026-02-31"},
            follow_redirects=True,
        )
        assert "존재하지 않는 날짜" in response.get_data(as_text=True)
        assert seeder.list() == []

    def test_추가_후_필터가_유지된다(self, client):
        response = client.post(
            "/todos", data={"title": "장보기", "scope": "active", "tag": "공부"}
        )
        assert "scope=active" in response.headers["Location"]

    def test_새로고침_중복_추가를_막기_위해_리다이렉트한다(self, client):
        # PRG 패턴: POST 응답은 200이 아니라 302여야 한다
        assert client.post("/todos", data={"title": "장보기"}).status_code == 302


class TestToggleAndDelete:
    def test_토글하면_완료_상태가_바뀐다(self, client, seeder):
        todo = seeder.add("장보기")
        client.post(f"/todos/{todo.id}/toggle")
        assert seeder.get(todo.id).is_done is True
        client.post(f"/todos/{todo.id}/toggle")
        assert seeder.get(todo.id).is_done is False

    def test_삭제하면_사라진다(self, client, seeder):
        todo = seeder.add("장보기")
        assert client.post(f"/todos/{todo.id}/delete").status_code == 302
        assert seeder.list() == []

    def test_삭제해도_태그_사전은_남는다(self, client, seeder):
        todo = seeder.add("장보기", tags="집안일")
        client.post(f"/todos/{todo.id}/delete")
        assert [t.name for t in seeder.all_tags()] == ["집안일"]

    def test_없는_id를_토글하면_404다(self, client):
        assert client.post("/todos/9999/toggle").status_code == 404

    def test_없는_id를_삭제하면_404다(self, client):
        assert client.post("/todos/9999/delete").status_code == 404

    def test_GET으로는_변경할_수_없다(self, client, seeder):
        todo = seeder.add("장보기")
        assert client.get(f"/todos/{todo.id}/delete").status_code == 405
        assert seeder.get(todo.id) is not None


class TestLayerBoundary:
    def test_화면_계층에_SQL이_없다(self):
        import pathlib

        for path in pathlib.Path("todoapp/web").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "SELECT" not in source.upper(), path
        cli = pathlib.Path("todoapp/cli.py").read_text(encoding="utf-8")
        assert "import sqlite3" not in cli
        assert "SELECT" not in cli.upper()


class TestConnectionHandling:
    def test_여러_요청을_연달아_처리한다(self, client, seeder):
        # 요청마다 커넥션을 새로 열고 닫는지 확인. 누수가 있으면 여기서 터진다.
        for i in range(15):
            client.post("/todos", data={"title": f"할 일 {i}"})
        assert client.get("/").status_code == 200
        assert len(seeder.list()) == 15
