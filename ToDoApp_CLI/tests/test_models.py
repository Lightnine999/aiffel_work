"""도메인 값 객체와 입력 검증 테스트. DB를 쓰지 않는다."""
import pytest

from todoapp.models import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    Tag,
    Todo,
    ValidationError,
    normalize_color,
    normalize_due_date,
    normalize_priority,
    normalize_tag_name,
    normalize_title,
    parse_tag_list,
)


class TestNormalizeTitle:
    def test_앞뒤_공백을_제거한다(self):
        assert normalize_title("  장보기  ") == "장보기"

    def test_내부_연속_공백을_하나로_줄인다(self):
        assert normalize_title("장   보기") == "장 보기"

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n", None])
    def test_빈_제목은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_title(bad)

    def test_200자를_넘으면_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_title("가" * 201)

    def test_200자는_통과한다(self):
        assert len(normalize_title("가" * 200)) == 200


class TestNormalizeDueDate:
    def test_ISO_날짜를_그대로_돌려준다(self):
        assert normalize_due_date("2026-09-10") == "2026-09-10"

    @pytest.mark.parametrize("empty", [None, "", "   "])
    def test_빈_값은_None이다(self, empty):
        assert normalize_due_date(empty) is None

    def test_하이픈_없는_형식은_거부한다(self):
        # date.fromisoformat은 Python 3.11+에서 '20260904'를 통과시킨다.
        # 형식 검사를 먼저 걸지 않으면 DB에 잘못된 형식이 들어간다.
        with pytest.raises(ValidationError):
            normalize_due_date("20260904")

    @pytest.mark.parametrize("bad", ["2026/09/04", "26-09-04", "2026-9-4", "내일"])
    def test_잘못된_형식은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_due_date(bad)

    def test_존재하지_않는_날짜는_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_due_date("2026-02-31")

    def test_윤년_2월29일은_통과한다(self):
        assert normalize_due_date("2028-02-29") == "2028-02-29"


class TestNormalizeTagName:
    def test_앞뒤_공백을_제거한다(self):
        assert normalize_tag_name(" 공부 ") == "공부"

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_빈_태그는_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_tag_name(bad)

    def test_쉼표가_들어가면_거부한다(self):
        # CLI에서 쉼표로 태그를 나누므로 태그명에 쉼표가 있으면 안 된다.
        with pytest.raises(ValidationError):
            normalize_tag_name("공부,집안일")

    def test_30자를_넘으면_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_tag_name("가" * 31)


class TestParseTagList:
    def test_쉼표_문자열을_나눈다(self):
        assert parse_tag_list("공부, 집안일") == ("공부", "집안일")

    def test_리스트도_받는다(self):
        assert parse_tag_list(["공부", " 집안일 "]) == ("공부", "집안일")

    def test_빈_값은_빈_튜플이다(self):
        assert parse_tag_list(None) == ()
        assert parse_tag_list("") == ()

    def test_빈_조각은_건너뛴다(self):
        assert parse_tag_list("공부,,  ,집안일") == ("공부", "집안일")

    def test_중복은_순서를_지키며_한_번만_남긴다(self):
        assert parse_tag_list("공부,집안일,공부") == ("공부", "집안일")

    def test_대소문자만_다른_태그는_같은_것으로_본다(self):
        # DB의 tags.name이 COLLATE NOCASE라 대소문자 변형은 같은 행이 된다.
        assert parse_tag_list("Study,study") == ("Study",)


class TestNormalizeColor:
    def test_HEX_색상을_대문자로_정규화한다(self):
        assert normalize_color("#534ab7") == "#534AB7"

    def test_빈_값은_기본색이다(self):
        assert normalize_color(None) == "#888880"

    @pytest.mark.parametrize("bad", ["534AB7", "#534AB", "#GGGGGG", "red"])
    def test_잘못된_색상은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_color(bad)


class TestNormalizePriority:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (1, PRIORITY_HIGH),
            ("2", PRIORITY_NORMAL),
            ("high", PRIORITY_HIGH),
            ("HIGH", PRIORITY_HIGH),
            ("normal", PRIORITY_NORMAL),
            ("low", PRIORITY_LOW),
            (None, PRIORITY_NORMAL),
        ],
    )
    def test_숫자와_이름을_모두_받는다(self, raw, expected):
        assert normalize_priority(raw) == expected

    @pytest.mark.parametrize("bad", [0, 4, "urgent", "1.5"])
    def test_범위_밖은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_priority(bad)


class TestValueObjects:
    def test_Todo는_불변이다(self):
        todo = Todo(id=1, title="장보기")
        with pytest.raises(Exception):
            todo.title = "다른 제목"

    def test_Todo_기본값(self):
        todo = Todo(id=None, title="장보기")
        assert todo.is_done is False
        assert todo.due_date is None
        assert todo.priority == PRIORITY_NORMAL
        assert todo.tags == ()

    def test_Tag는_불변이다(self):
        tag = Tag(id=1, name="공부")
        with pytest.raises(Exception):
            tag.name = "운동"
