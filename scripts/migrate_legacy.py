"""Copy legacy Cairn projects into an independent Workbench DB; never alter the source."""

import argparse
import json
from pathlib import Path
import sqlite3
from cairn.workbench.store import Store, uid, now


def migrate(source: Path, destination: Path):
    store = Store(destination)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as legacy:
        legacy.row_factory = sqlite3.Row
        projects = legacy.execute("SELECT * FROM projects").fetchall()
        count = 0
        for old in projects:
            marker = f"legacy:{source.resolve()}:{old['id']}"
            if store.one("SELECT id FROM wb_hints WHERE content=?", (marker,)):
                continue
            pid = uid("project")
            facts = legacy.execute(
                "SELECT * FROM facts WHERE project_id=?", (old["id"],)
            ).fetchall()
            origin = next(
                (r["description"] for r in facts if r["id"] == "origin"), "从旧项目导入"
            )
            goal = next(
                (r["description"] for r in facts if r["id"] == "goal"), old["title"]
            )
            mapping = {r["id"]: uid("node") for r in facts}
            with store.connect() as c:
                c.execute(
                    "INSERT INTO wb_projects(id,title,origin,goal,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (pid, old["title"], origin, goal, old["created_at"], now()),
                )
                for fact in facts:
                    kind = fact["id"] if fact["id"] in ("origin", "goal") else "fact"
                    c.execute(
                        "INSERT INTO wb_graph VALUES(?,?,?,?,?,?,?)",
                        (
                            mapping[fact["id"]],
                            pid,
                            None,
                            kind,
                            fact["description"],
                            "[]",
                            now(),
                        ),
                    )
                for intent in legacy.execute(
                    "SELECT * FROM intents WHERE project_id=?", (old["id"],)
                ):
                    sources = [
                        mapping.get(r["fact_id"])
                        for r in legacy.execute(
                            "SELECT fact_id FROM intent_sources WHERE project_id=? AND intent_id=?",
                            (old["id"], intent["id"]),
                        )
                        if r["fact_id"] in mapping
                    ]
                    ident = uid("node")
                    c.execute(
                        "INSERT INTO wb_graph VALUES(?,?,?,?,?,?,?)",
                        (
                            ident,
                            pid,
                            None,
                            "intent",
                            intent["description"],
                            json.dumps(sources),
                            intent["created_at"],
                        ),
                    )
                    if intent["to_fact_id"] in mapping:
                        c.execute(
                            "UPDATE wb_graph SET sources=? WHERE id=?",
                            (json.dumps([ident]), mapping[intent["to_fact_id"]]),
                        )
                for hint in legacy.execute(
                    "SELECT * FROM hints WHERE project_id=?", (old["id"],)
                ):
                    c.execute(
                        "INSERT INTO wb_hints VALUES(?,?,?,?,?)",
                        (uid("hint"), pid, None, hint["content"], hint["created_at"]),
                    )
                c.execute(
                    "INSERT INTO wb_hints VALUES(?,?,?,?,?)",
                    (uid("hint"), pid, None, marker, now()),
                )
                store.event(pid, None, "project.imported", {"legacy_id": old["id"]}, c)
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print("Imported projects:", migrate(args.source, args.destination))
