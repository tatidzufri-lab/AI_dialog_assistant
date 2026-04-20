from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_RETREAT_MATERIAL = """
Ретрит «Познай себя» — это 5-дневное пространство тишины, рефлексии и возвращения
к внутреннему компасу. Мы работаем в малой группе (до 10 участниц) в горном доме.

Ценности бренда:
- бережность: нет жёстких трансформаций, только мягкие встречи с собой;
- глубина вместо скорости: за пять дней участница не «меняется навсегда»,
  а учится слышать себя в повседневной жизни;
- природа как зеркало: горы, тишина, ветер и тропа — главные соведущие;
- безопасное пространство: всё, что звучит на ретрите, остаётся в группе.

Программа 5 дней (каркас одинаков для всех тарифов):
- день 1: тихая встреча, знакомство с пространством, медитация на заземление;
- день 2: тело и дыхание — телесные практики, прогулка по горной тропе;
- день 3: арт-терапия — диалог с образами, работа с внутренним ребёнком;
- день 4: групповая сессия «ценности и границы» + индивидуальная практика;
- день 5: интеграция, письмо будущей себе, ритуал возвращения.

Форматы внутри программы: утренние медитации, арт-терапия, групповые сессии,
телесные практики, прогулки по природе, вечерние круги в тишине.

Тарифы:
- «Путь к Себе» (25 000 ₽): проживание в общем номере (2-3 чел.), базовая программа
  (утренние медитации, 2 групповые сессии, 1 арт-терапия), общие трапезы.
  Подходит тем, кто впервые пробует ретрит, хочет тишину и бережную разгрузку,
  идёт «просто выдохнуть и побыть в природе».
- «Ритм Гармонии» (50 000 ₽): двухместный номер, расширенная программа (все медитации,
  4 групповые сессии, 2 арт-терапии, 1 индивидуальная сессия с психологом), 1 SPA-процедура.
  Подходит тем, кто хочет глубже разобраться в запросе, но сохранить общий ритм группы,
  идёт с темой «понять, куда двигаться дальше».
- «Своя Вершина» (75 000 ₽): одноместный номер с видом на горы, полная программа
  + ежедневная индивидуальная работа с коучем, персональная арт-практика,
  план интеграции на 30 дней после ретрита, все SPA-процедуры.
  Подходит тем, кто идёт с серьёзным жизненным выбором или профессиональной развилкой
  и готов вложиться в глубокую персональную работу.

Что мы НЕ обещаем: мгновенных изменений, готовых ответов, «новой жизни за 5 дней».
Мы обещаем бережное время с собой и инструменты, которые останутся с участницей.
""".strip()


DEFAULT_AUDIENCE_PORTRAITS = """
Портрет 1 — «Уставшая перфекционистка» (30–45 лет):
  боли: выгорание, тревога, не умеет останавливаться, стыд за «неидеальность»;
  язык: рациональный, структурный, через «правильно/неправильно»;
  с ней работает: признание её усилий, мягкое разрешение не справляться,
  метафора «отпустить вершину, чтобы увидеть всю гору».

Портрет 2 — «Мама, которая потеряла себя» (28–40 лет):
  боли: декрет или маленькие дети, размытая собственная идентичность, вина,
  усталость, ощущение «меня больше нет, есть только функция»;
  язык: эмоциональный, тёплый, через заботу о других;
  с ней работает: признание её права на своё пространство, метафора
  «внутренний колодец, из которого она поит других и забывает пить сама».

Портрет 3 — «Творческий искатель» (25–50 лет):
  боли: поиск смысла, кризис идентичности, ощущение «я между путями»,
  иногда — одиночество рядом с теми, кто «не про то же»;
  язык: образный, метафорический, через символы и чувства;
  с ней работает: глубина, честный разговор, метафора «внутренний компас,
  который знает направление, когда карта больше не работает».
""".strip()


DEFAULT_FORBIDDEN_WORDS = (
    "успех,прорыв,гарантированный результат,быстрый эффект,"
    "навсегда изменим жизнь,100% результат,трансформация за 5 дней"
)


DEFAULT_CRISIS_KEYWORDS = (
    "суицид,покончить с собой,не хочу жить,хочу умереть,убить себя,"
    "режу себя,самоповреждение,клиническая депрессия,невыносимо жить"
)


DEFAULT_CRISIS_RESPONSE = (
    "Слышу, что тебе сейчас очень тяжело, и это правда важно. "
    "Ретрит — это про бережную работу с собой, но в таком состоянии "
    "рядом нужен человек, который умеет держать именно это. "
    "Пожалуйста, свяжись с бесплатной психологической помощью: "
    "телефон доверия 8-800-2000-122 (круглосуточно, анонимно). "
    "Если чувствуешь опасность для жизни — звони 112. "
    "Я рядом, но я не заменяю специалиста. Ты не одна."
)


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    retreat_topic: str = Field(
        default="Ретрит «Познай себя»",
        alias="RETREAT_TOPIC",
    )
    retreat_material: str = Field(
        default=DEFAULT_RETREAT_MATERIAL,
        alias="RETREAT_MATERIAL",
    )
    retreat_material_file: str | None = Field(default=None, alias="RETREAT_MATERIAL_FILE")
    audience_portraits: str = Field(
        default=DEFAULT_AUDIENCE_PORTRAITS,
        alias="AUDIENCE_PORTRAITS",
    )
    audience_portraits_file: str | None = Field(default=None, alias="AUDIENCE_PORTRAITS_FILE")

    reflection_question_count: int = Field(
        default=5, alias="REFLECTION_QUESTION_COUNT", ge=3, le=10,
    )

    forbidden_words: str = Field(default=DEFAULT_FORBIDDEN_WORDS, alias="FORBIDDEN_WORDS")
    crisis_keywords: str = Field(default=DEFAULT_CRISIS_KEYWORDS, alias="CRISIS_KEYWORDS")
    crisis_response: str = Field(default=DEFAULT_CRISIS_RESPONSE, alias="CRISIS_RESPONSE")

    booking_bot_username: str = Field(
        default="retreat_poznai_bot", alias="BOOKING_BOT_USERNAME",
    )
    booking_bot_display_name: str = Field(
        default="Лея", alias="BOOKING_BOT_DISPLAY_NAME",
    )
    booking_bot_dative_name: str = Field(
        default="Лее", alias="BOOKING_BOT_DATIVE_NAME",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_retreat_material(self) -> str:
        if self.retreat_material_file:
            return Path(self.retreat_material_file).read_text(encoding="utf-8").strip()
        return self.retreat_material.strip()

    def get_audience_portraits(self) -> str:
        if self.audience_portraits_file:
            return Path(self.audience_portraits_file).read_text(encoding="utf-8").strip()
        return self.audience_portraits.strip()

    def get_forbidden_words(self) -> list[str]:
        return [w.strip() for w in self.forbidden_words.split(",") if w.strip()]

    def get_crisis_keywords(self) -> list[str]:
        return [w.strip().lower() for w in self.crisis_keywords.split(",") if w.strip()]

    def get_booking_bot_url(self) -> str:
        username = self.booking_bot_username.lstrip("@").strip()
        return f"https://t.me/{username}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
