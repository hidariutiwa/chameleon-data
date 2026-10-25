from pathlib import Path

import pandas as pd
from faker import Faker
from pydantic import BaseModel
from rich import box
from rich.panel import Panel
from rich.table import Table

from chameleon_data.fakers import fake_address
from chameleon_data.ui import console


class ExampleData(BaseModel):
    no: int
    first_name: str
    last_name: str
    zipcode: str
    address: str
    phone_number: str


def create_example() -> None:
    Faker.seed(223)
    fake = Faker("ja_JP")

    persons = [
        ExampleData(
            no=i + 1,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            zipcode=fake.zipcode(),
            address=fake_address(fake),
            phone_number=fake.phone_number(),
        )
        for i in range(10)
    ]

    df = pd.DataFrame([p.model_dump() for p in persons])
    df = df.set_index("no")

    table = Table(box=box.ROUNDED, header_style="bold cyan", border_style="dim")
    table.add_column("no", justify="right", style="dim")
    for column in df.columns:
        table.add_column(column)
    for no, row in df.iterrows():
        table.add_row(str(no), *row)
    console.print(table)

    example_dir = Path(Path.cwd(), "example")
    Path.mkdir(example_dir, exist_ok=True)
    example_path = Path(example_dir, "example.csv")

    df.to_csv(example_path)
    console.print(
        Panel.fit(
            f"[bold]saved[/]    [cyan]{example_path}[/]\n"
            f"[bold]try it![/]  chameleon -f {example_path}",
            title="✔ example",
            title_align="left",
            border_style="green",
        )
    )
