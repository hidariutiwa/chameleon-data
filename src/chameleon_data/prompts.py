import pandas as pd
import questionary
from rich.cells import cell_len, set_cell_size

from chameleon_data.fakers import FAKE_GENERATORS, MASKING
from chameleon_data.ui import exit_cancelled, exit_with_error

# questionary prompt texts, keyed by the language part of the Faker locale
PROMPTS: dict[str, dict[str, str]] = {
    "ja": {
        "select_columns": "マスクする列を選択してください",
        "select_columns_hint": "(↑↓で移動、スペースで選択、aで全選択、iで反転、Enterで決定)",
        "select_type": "{column} の置き換え方法を選択してください",
        "select_type_hint": "(↑↓で移動、文字入力で絞り込み、Enterで決定)",
        "select_generate_type": "{column} に生成するデータの種類を選択してください",
        "enter_column": "{number} 列目の列名を入力してください",
        "enter_column_hint": "(空のままEnterで入力を終了)",
        "duplicate_column": "{column} はすでに入力されています",
    },
    "en": {
        "select_columns": "select masking columns",
        "select_columns_hint": "(↑↓ to move, <space> to select, <a> to toggle, <i> to invert)",
        "select_type": "type of {column}",
        "select_type_hint": "(↑↓ to move, type to filter, <enter> to choose)",
        "select_generate_type": "type of {column}",
        "enter_column": "name of column {number}",
        "enter_column_hint": "(leave empty and press <enter> to finish)",
        "duplicate_column": "{column} is already entered",
    },
    "zh": {
        "select_columns": "请选择要脱敏的列",
        "select_columns_hint": "(↑↓ 移动，空格 选择，a 全选，i 反选，回车 确认)",
        "select_type": "请选择 {column} 的替换方式",
        "select_type_hint": "(↑↓ 移动，输入文字 筛选，回车 确认)",
        "select_generate_type": "请选择 {column} 要生成的数据类型",
        "enter_column": "请输入第 {number} 列的列名",
        "enter_column_hint": "(留空并按回车 结束输入)",
        "duplicate_column": "{column} 已经输入过了",
    },
}


def get_prompts(language: str) -> dict[str, str]:
    # ja_JP -> ja, zh_TW -> zh; unsupported languages fall back to English
    return PROMPTS.get(language.split("_")[0].lower(), PROMPTS["en"])


# display names of fake types and FAKE_GROUPS, keyed like PROMPTS;
# languages without an entry show the plain type names
TYPE_LABELS: dict[str, dict[str, str]] = {
    "ja": {
        MASKING: "マスク",
        "person": "個人",
        "full_name": "氏名",
        "first_name": "名",
        "last_name": "姓",
        "full_name_kana": "氏名カナ",
        "last_name_kana": "姓カナ",
        "first_name_kana": "名カナ",
        "email": "メールアドレス",
        "user_name": "ユーザー名",
        "date_of_birth": "生年月日",
        "age": "年齢",
        "phone_number": "電話番号",
        "address": "住所",
        "full_address": "住所",
        "address_below_city": "市区町村以下",
        "zipcode": "郵便番号",
        "prefecture": "都道府県",
        "city": "市区町村",
        "street": "町名・番地",
        "building": "建物名",
        "business": "ビジネス",
        "company": "会社名",
        "job": "職業",
        "url": "URL",
        "domain": "ドメイン",
        "ipv4": "IPv4アドレス",
        "ipv4_private": "プライベートIPv4",
        "finance / id": "金融・ID",
        "credit_card_number": "クレジットカード番号",
        "credit_card_expire": "カード有効期限",
        "credit_card_security_code": "セキュリティコード",
        "bank_account": "口座番号",
        "iban": "IBAN",
        "uuid": "UUID",
        "passport_number": "旅券番号",
        "number": "数値",
        "date": "日付",
    },
}


def get_type_labels(language: str) -> dict[str, str]:
    return TYPE_LABELS.get(language.split("_")[0].lower(), {})


def build_type_choices(
    samples: dict[str, dict[str, str]],
    series: pd.Series | None,
    labels: dict[str, str],
) -> list[questionary.Choice | questionary.Separator]:
    # plain str titles: questionary's search filter calls title.lower()
    # the type name stays in the title so filtering by it keeps working
    # series is None when there are no original values (generate): no masking choice
    def display(name: str) -> str:
        return f"{labels[name]} ({name})" if name in labels else name

    names = [*FAKE_GENERATORS] if series is None else [MASKING, *FAKE_GENERATORS]
    width = max(cell_len(display(name)) for name in names) + 2

    def choice(name: str, sample: str) -> questionary.Choice:
        return questionary.Choice(set_cell_size(display(name), width) + sample, name)

    choices: list[questionary.Choice | questionary.Separator] = []
    if series is not None:
        first = series.dropna()
        masked = "*" * len(first.iloc[0]) if len(first) else "****"
        choices.append(choice(MASKING, masked))
    for group, group_samples in samples.items():
        choices.append(questionary.Separator(f"── {labels.get(group, group)} ──"))
        choices.extend(choice(name, sample) for name, sample in group_samples.items())
    return choices


COLUMN_SAMPLE_COUNT = 3
COLUMN_SAMPLE_WIDTH = 40


def build_column_choices(df: pd.DataFrame) -> list[questionary.Choice]:
    # cell widths, not len(): column names and values may be full-width
    names = [str(column) for column in df.columns]
    width = max(map(cell_len, names), default=0) + 2

    def sample(series: pd.Series) -> str:
        values = series.dropna().drop_duplicates().head(COLUMN_SAMPLE_COUNT)
        text = ", ".join(map(str, values)) or "-"
        if cell_len(text) <= COLUMN_SAMPLE_WIDTH:
            return text
        return set_cell_size(text, COLUMN_SAMPLE_WIDTH - 1).rstrip() + "…"

    return [
        questionary.Choice(set_cell_size(name, width) + sample(df[column]), column)
        for name, column in zip(names, df.columns, strict=True)
    ]


def ask_columns(df: pd.DataFrame, prompts: dict[str, str]) -> list[str]:
    columns: list[str] | None = questionary.checkbox(
        prompts["select_columns"],
        build_column_choices(df),
        instruction=prompts["select_columns_hint"],
    ).ask()
    if columns is None:
        exit_cancelled()
    if not columns:
        exit_with_error("no columns selected.")
    return columns


def ask_fake_type(
    column: str,
    series: pd.Series | None,
    samples: dict[str, dict[str, str]],
    prompts: dict[str, str],
    labels: dict[str, str],
) -> str:
    message = "select_type" if series is not None else "select_generate_type"
    fake_type: str | None = questionary.select(
        prompts[message].format(column=column),
        build_type_choices(samples, series, labels),
        instruction=prompts["select_type_hint"],
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()
    if fake_type is None:
        exit_cancelled()
    return fake_type


def ask_fake_types(
    columns: list[str],
    df: pd.DataFrame | None,
    samples: dict[str, dict[str, str]],
    prompts: dict[str, str],
    labels: dict[str, str],
) -> dict[str, str]:
    # df is None when generating: there are no original values to mask
    return {
        column: ask_fake_type(
            column, None if df is None else df[column], samples, prompts, labels
        )
        for column in columns
    }


def ask_new_columns(
    samples: dict[str, dict[str, str]],
    prompts: dict[str, str],
    labels: dict[str, str],
) -> dict[str, str]:
    # column name -> type, entered one by one until an empty name
    fake_types: dict[str, str] = {}

    def validate(name: str) -> bool | str:
        if name.strip() in fake_types:
            return prompts["duplicate_column"].format(column=name.strip())
        return True

    while True:
        name: str | None = questionary.text(
            prompts["enter_column"].format(number=len(fake_types) + 1),
            instruction=prompts["enter_column_hint"],
            validate=validate,
        ).ask()
        if name is None:
            exit_cancelled()
        name = name.strip()
        if not name:
            break
        fake_types[name] = ask_fake_type(name, None, samples, prompts, labels)

    if not fake_types:
        exit_with_error("no columns entered.")
    return fake_types
