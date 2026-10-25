from collections.abc import Callable

from faker import Faker

# fake type that replaces every character with "*" instead of generating a value
MASKING = "masking"


def fake_address(fake: Faker) -> str:
    # prefecture, chome, etc. exist only in the ja_JP provider
    if not hasattr(fake, "prefecture"):
        return fake.address().replace("\n", " ")
    return f"{fake.prefecture()}{fake.city()}{fake.chome()}{fake.gou()}{fake.ban()}{fake.building_name()}{fake.building_number()}"


def fake_street(fake: Faker) -> str:
    if not hasattr(fake, "chome"):
        return fake.street_address()
    return f"{fake.town()}{fake.chome()}{fake.ban()}{fake.gou()}"


# name types generated together per row so they describe the same person
NAME_TYPES = {
    "full_name",
    "first_name",
    "last_name",
    "full_name_kana",
    "first_name_kana",
    "last_name_kana",
}


def fake_person(fake: Faker) -> dict[str, str]:
    # *_name_pair (kanji, kana, romanized) exist only in the ja_JP provider
    if not hasattr(fake, "last_name_pair"):
        last, first = fake.last_name(), fake.first_name()
        return {"full_name": f"{last} {first}", "first_name": first, "last_name": last}
    last, last_kana, _ = fake.last_name_pair()
    first, first_kana, _ = fake.first_name_pair()
    return {
        "full_name": f"{last} {first}",
        "first_name": first,
        "last_name": last,
        "full_name_kana": f"{last_kana} {first_kana}",
        "first_name_kana": first_kana,
        "last_name_kana": last_kana,
    }


# generators that need a provider missing in the locale raise AttributeError
# and are hidden from the choices by build_type_choices()
FAKE_GROUPS: dict[str, dict[str, Callable[[Faker], str]]] = {
    "person": {
        "full_name": lambda fake: f"{fake.last_name()} {fake.first_name()}",
        "first_name": lambda fake: fake.first_name(),
        "last_name": lambda fake: fake.last_name(),
        "full_name_kana": lambda fake: fake.kana_name(),
        "last_name_kana": lambda fake: fake.last_kana_name(),
        "first_name_kana": lambda fake: fake.first_kana_name(),
        "email": lambda fake: fake.email(),
        "user_name": lambda fake: fake.user_name(),
        "date_of_birth": lambda fake: fake.date_of_birth(
            minimum_age=18, maximum_age=90
        ).isoformat(),
        "age": lambda fake: str(fake.random_int(18, 90)),
        "phone_number": lambda fake: fake.phone_number(),
    },
    "address": {
        "full_address": fake_address,
        "zipcode": lambda fake: fake.zipcode(),
        "prefecture": lambda fake: fake.administrative_unit(),
        "city": lambda fake: fake.city(),
        "street": fake_street,
        "building": lambda fake: f"{fake.building_name()}{fake.building_number()}",
    },
    "business": {
        "company": lambda fake: fake.company(),
        "job": lambda fake: fake.job(),
        "url": lambda fake: fake.url(),
        "domain": lambda fake: fake.domain_name(),
        "ipv4": lambda fake: fake.ipv4(),
        "ipv4_private": lambda fake: fake.ipv4_private(),
    },
    "finance / id": {
        "credit_card_number": lambda fake: fake.credit_card_number(),
        "credit_card_expire": lambda fake: fake.credit_card_expire(),
        "credit_card_security_code": lambda fake: fake.credit_card_security_code(),
        "bank_account": lambda fake: fake.bban(),
        "iban": lambda fake: fake.iban(),
        "uuid": lambda fake: fake.uuid4(),
        "passport_number": lambda fake: fake.passport_number(),
        "number": lambda fake: str(fake.random_int(0, 99999)),
        "date": lambda fake: fake.date(),
    },
}

FAKE_GENERATORS: dict[str, Callable[[Faker], str]] = {
    name: generator
    for group in FAKE_GROUPS.values()
    for name, generator in group.items()
}


def sample_fake_values(fake: Faker) -> dict[str, dict[str, str]]:
    # one sample per generator, grouped like FAKE_GROUPS; unsupported ones are dropped
    samples: dict[str, dict[str, str]] = {}
    for group, generators in FAKE_GROUPS.items():
        for name, generator in generators.items():
            try:
                samples.setdefault(group, {})[name] = generator(fake)
            except AttributeError:
                continue
    return samples
