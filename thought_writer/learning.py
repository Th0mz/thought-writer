# TODO
# Only call this when `collect` is functional

import json
import os
import random
import tempfile

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dataclasses_json import dataclass_json
from termcolor import colored

from thought_writer.db import DB, DBs
from thought_writer.domain import Step


@dataclass_json
@dataclass
class Review:
    ran: Optional[bool]
    perfect: Optional[bool]
    works: Optional[bool]
    comments: str
    raw: str


@dataclass_json
@dataclass
class Learning:
    model: str
    temperature: float
    steps: str
    steps_file_hash: str
    prompt: str
    logs: str
    workspace: str
    feedback: Optional[str]
    session: str
    review: Optional[Review]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "0.3"


TERM_CHOICES = (
    colored("y", "green")
    + "/"
    + colored("n", "red")
    + "/"
    + colored("u", "yellow")
    + "(ncertain): "
)


def human_input() -> Review:
    print()
    print(
        colored("To help thought-writer learn, please answer 3 questions:", "light_green")
    )
    print()

    ran = input("Were your thoughts made more clear at all? " + TERM_CHOICES)
    while ran not in ("y", "n", "u"):
        ran = input("Invalid input. Please enter y, n, or u: ")

    perfect = ""
    useful = ""

    if ran == "y":
        perfect = input(
            "Do you feel like the model asked the right questions to clarify your ideas? " + TERM_CHOICES
        )
        while perfect not in ("y", "n", "u"):
            perfect = input("Invalid input. Please enter y, n, or u: ")

        if perfect != "y":
            useful = input("Were the questions and conclusions done by the model useful? " + TERM_CHOICES)
            while useful not in ("y", "n", "u"):
                useful = input("Invalid input. Please enter y, n, or u: ")

    comments = ""
    if perfect != "y":
        comments = input(
            "If you have time, please explain what needs to be improved: "
            + colored("(ok to leave blank)\n", "light_green")
        )

    check_consent()

    return Review(
        raw=", ".join([ran, perfect, useful]),
        ran={"y": True, "n": False, "u": None, "": None}[ran],
        works={"y": True, "n": False, "u": None, "": None}[useful],
        perfect={"y": True, "n": False, "u": None, "": None}[perfect],
        comments=comments,
    )


def check_consent():
    path = Path(".gpte_consent")
    if path.exists() and path.read_text() == "true":
        return
    ans = input("Is it ok if we store your prompts to learn? (y/n)")
    while ans.lower() not in ("y", "n"):
        ans = input("Invalid input. Please enter y or n: ")

    if ans.lower() == "y":
        path.write_text("true")
        print(colored("Thank you️", "light_green"))
        print()
        print("(If you change your mind, delete the file .gpte_consent)")
    else:
        print(colored("We understand ❤️", "light_green"))


def collect_consent() -> bool:
    opt_out = os.environ.get("COLLECT_LEARNINGS_OPT_OUT") == "true"
    consent_flag = Path(".gpte_consent")
    has_given_consent = consent_flag.exists() and consent_flag.read_text() == "true"

    if opt_out:
        if has_given_consent:
            return ask_if_can_store()
        return False

    if has_given_consent:
        return True

    if ask_if_can_store():
        consent_flag.write_text("true")
        print()
        print("(If you change your mind, delete the file .gpte_consent)")
        return True
    return False


def ask_if_can_store() -> bool:
    print()
    can_store = input(
        "Have you understood and agree to that "
        + colored("OpenAI ", "light_green")
        + "and "
        + colored("thought-writer ", "light_green")
        + "store anonymous learnings about how thought-writer is used "
        + "(with the sole purpose of improving it)?\n(y/n)"
    ).lower()
    while can_store not in ("y", "n"):
        can_store = input("Invalid input. Please enter y or n: ").lower()

    if can_store == "n":
        print(colored("Ok we understand", "light_green"))

    return can_store == "y"


def logs_to_string(steps: List[Step], logs: DB):
    chunks = []
    for step in steps:
        chunks.append(f"--- {step.__name__} ---\n")
        messages = json.loads(logs[step.__name__])
        chunks.append(format_messages(messages))
    return "\n".join(chunks)


def format_messages(messages: List[dict]) -> str:
    return "\n".join(
        [f"{message['role']}:\n\n{message['content']}" for message in messages]
    )


def extract_learning(
    model: str, temperature: float, steps: List[Step], dbs: DBs, steps_file_hash
) -> Learning:
    review = None
    if "review" in dbs.memory:
        review = Review.from_json(dbs.memory["review"])  # type: ignore
    learning = Learning(
        prompt=dbs.input["prompt"],
        model=model,
        temperature=temperature,
        steps=json.dumps([step.__name__ for step in steps]),
        steps_file_hash=steps_file_hash,
        feedback=dbs.input.get("feedback"),
        session=get_session(),
        logs=logs_to_string(steps, dbs.logs),
        workspace=dbs.workspace["all_output.txt"],
        review=review,
    )
    return learning


def get_session():
    path = Path(tempfile.gettempdir()) / "thought_writer_user_id.txt"

    try:
        if path.exists():
            user_id = path.read_text()
        else:
            # random uuid:
            user_id = str(random.randint(0, 2**32))
            path.write_text(user_id)
        return user_id
    except IOError:
        return "ephemeral_" + str(random.randint(0, 2**32))
