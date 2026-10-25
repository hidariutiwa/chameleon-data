# chameleon-cli

CSV / TSV / XLSX ファイルの列を選んで、[Faker](https://faker.readthedocs.io/) で生成したダミーデータに置き換える対話型 CLI です。結果は元と同じ形式で保存されます。

## インストール

Python 3.11 以上が必要です。

```bash
# CLI ツールとしてインストール (おすすめ)
uv tool install git+https://github.com/hidariutiwa/chameleon-cli

# インストールせずに 1 回だけ実行
uvx --from git+https://github.com/hidariutiwa/chameleon-cli chameleon -f data.csv

# 他プロジェクトの依存として追加
uv add git+https://github.com/hidariutiwa/chameleon-cli
pip install git+https://github.com/hidariutiwa/chameleon-cli
```

特定のバージョンを固定したい場合は `git+https://github.com/hidariutiwa/chameleon-cli@<tag or commit>` のように指定します。

アップデート / アンインストール:

```bash
uv tool upgrade chameleon-cli
uv tool uninstall chameleon-cli
```

## 使い方

```bash
chameleon -f data.csv                 # data_masked.csv に保存
chameleon -f data.xlsx -o out.xlsx    # 出力先を指定
chameleon -f data.tsv -l en_US -s 42  # ロケールとシードを指定
```

| オプション | 説明 |
| --- | --- |
| `-f`, `--filepath` | 入力ファイル (必須)。`.csv` / `.tsv` / `.xlsx` |
| `-o`, `--output` | 出力ファイル。デフォルトは `<ファイル名>_masked.<拡張子>` |
| `-l`, `--language` | Faker のロケール。デフォルトは `ja_JP` |
| `-s`, `--seed` | 乱数シード。指定すると毎回同じ結果になります |
| `-v`, `--version` | バージョンを表示 |

実行すると、マスクする列をチェックボックスで選び、列ごとに置き換え方を選択します。

| 種類 | 内容 |
| --- | --- |
| `masking` | すべての文字を `*` に置き換え (文字数は維持) |
| `full_name` / `first_name` / `last_name` | 氏名 |
| `full_address` | 住所 |
| `zipcode` | 郵便番号 |
| `phone_number` | 電話番号 |

同じ値は同じダミー値に置き換わるため、行同士の対応関係は保たれます。空セルは空のままです。

### サンプルデータ

```bash
chameleon-example   # ./example/example.csv にサンプルを生成
chameleon -f example/example.csv
```

## 開発

[uv](https://docs.astral.sh/uv/) を使います。

```bash
uv sync
uv run chameleon -f example/example.csv
uv build   # dist/ に wheel と sdist を作成
```
